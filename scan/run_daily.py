#!/usr/bin/env python3
"""
Daily Scan Agent — Nuno Laboreiro Mendonça (GitHub Actions version)

Runs in a GitHub Actions workflow on cron schedule. Fetches opportunities
from free job boards, scores them against the 4 archetypes, merges with
persistent pipeline.json, and regenerates the dashboard at docs/index.html.

Uses only the Python standard library — no external dependencies.
"""
from __future__ import annotations
import hashlib
import html
import json
import re
import sys
import traceback
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------- Repo layout ----------
BASE_DIR = Path(__file__).resolve().parent.parent  # repo root
SCAN_DIR = BASE_DIR / "scan"
DOCS_DIR = BASE_DIR / "docs"

KEYWORDS_PATH = SCAN_DIR / "archetype_keywords.json"
PIPELINE_PATH = DOCS_DIR / "pipeline.json"
DASHBOARD_PATH = DOCS_DIR / "index.html"
LOG_PATH = SCAN_DIR / "last_run.log"

USER_AGENT_BROWSER = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
USER_AGENT_API = "nuno-scan-agent/1.0 (+https://github.com/nuno-svg/nuno-scan-agent)"
TIMEOUT_SEC = 20
MAX_PER_SOURCE = 50


class HTTPFailure(Exception):
    """Raised with full context (status + body snippet) when an HTTP call fails."""


def _read_err_body(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8", errors="replace")
    except Exception:
        body = "<no body>"
    return body[:400]


# ---------- Fetch helpers ----------
def http_get(url: str, accept: str = "application/json", extra_headers: dict | None = None,
             user_agent: str = USER_AGENT_BROWSER) -> str:
    headers = {
        "User-Agent": user_agent,
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise HTTPFailure(f"GET {url} → HTTP {exc.code}: body={_read_err_body(exc)!r}")


def http_post_json(url: str, body: dict, user_agent: str = USER_AGENT_API) -> str:
    """POST with JSON body — canonical for ReliefWeb API v1."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise HTTPFailure(f"POST {url} → HTTP {exc.code}: body={_read_err_body(exc)!r}")


# ---------- Source: ReliefWeb API ----------
RELIEFWEB_QUERIES = [
    "catalytic finance",
    "blended finance",
    "results-based financing",
    "innovative financing",
    "investment officer",
    "investment advisor",
    "financial structuring",
    "project finance consultant",
    "transaction advisor",
    "capacity building consultant finance",
    "training consultant finance",
    "budget planning trainer",
    "senior finance consultant Africa",
    "development finance consultant",
    "PPP consultant",
]


def _try_reliefweb_endpoints(q: str, body: dict, log: list[str]) -> str | None:
    """Try multiple ReliefWeb URL forms; return raw JSON text or None."""
    candidates = [
        ("POST v1", "https://api.reliefweb.int/v1/jobs?appname=nuno-scan-agent", "post"),
        ("GET v1", None, "get_v1"),
        ("POST v2", "https://api.reliefweb.int/v2/jobs?appname=nuno-scan-agent", "post"),
    ]
    last_err = None
    for label, url, mode in candidates:
        try:
            if mode == "post":
                return http_post_json(url, body)
            elif mode == "get_v1":
                params = {
                    "appname": "nuno-scan-agent",
                    "profile": "list",
                    "limit": body.get("limit", MAX_PER_SOURCE),
                    "query[value]": q,
                    "query[operator]": "AND",
                    "sort[]": "date.created:desc",
                }
                fields = body.get("fields", {}).get("include", [])
                for i, f in enumerate(fields):
                    params[f"fields[include][{i}]"] = f
                get_url = "https://api.reliefweb.int/v1/jobs?" + urllib.parse.urlencode(params, doseq=True)
                return http_get(get_url, user_agent=USER_AGENT_API)
        except HTTPFailure as exc:
            last_err = f"[{label}] {exc}"
    if last_err:
        log.append(f"[ReliefWeb] all endpoints failed for q='{q}': {last_err}")
    return None


def fetch_reliefweb(log: list[str]) -> list[dict[str, Any]]:
    """Hit ReliefWeb API using multiple endpoint forms."""
    seen_ids: set[str] = set()
    results: list[dict[str, Any]] = []
    fields_to_include = [
        "title", "url", "date", "country", "source", "type",
        "career_categories", "body-html", "how_to_apply",
    ]
    for q in RELIEFWEB_QUERIES:
        body = {
            "limit": MAX_PER_SOURCE,
            "profile": "list",
            "sort": ["date.created:desc"],
            "fields": {"include": fields_to_include},
            "query": {"value": q, "operator": "AND"},
        }
        raw = _try_reliefweb_endpoints(q, body, log)
        if raw is None:
            continue
        try:
            data = json.loads(raw)
            returned = data.get("data", [])
            for item in returned:
                iid = str(item.get("id"))
                if iid in seen_ids:
                    continue
                seen_ids.add(iid)
                f = item.get("fields", {})
                country_names = [c.get("name") for c in (f.get("country") or []) if c.get("name")]
                source_names = [s.get("name") for s in (f.get("source") or []) if s.get("name")]
                type_names = [t.get("name") for t in (f.get("type") or []) if t.get("name")]
                cat_names = [c.get("name") for c in (f.get("career_categories") or []) if c.get("name")]
                date_closing = (f.get("date") or {}).get("closing")
                results.append({
                    "id": "rw-" + iid,
                    "title": f.get("title") or "(no title)",
                    "url": f.get("url") or "",
                    "source": "ReliefWeb",
                    "publisher": ", ".join(source_names),
                    "country": ", ".join(country_names),
                    "job_type": ", ".join(type_names),
                    "category": ", ".join(cat_names),
                    "posted": (f.get("date") or {}).get("created"),
                    "closing": date_closing,
                    "description": f.get("body-html") or "",
                })
            log.append(f"[ReliefWeb] q='{q}' → {len(returned)} returned")
        except Exception as exc:
            log.append(f"[ReliefWeb] q='{q}' FAILED: {exc}")
    log.append(f"[ReliefWeb] unique total: {len(results)}")
    return results


# ---------- Source: UN Jobs HTML scrape ----------
UNJOBS_KEYWORDS = [
    "consultant+finance",
    "capacity+building+consultant",
    "investment+advisor",
    "blended+finance",
]


def fetch_unjobs(log: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for kw in UNJOBS_KEYWORDS:
        url = f"https://unjobs.org/search?kw={kw}"
        try:
            html_text = http_get(
                url,
                accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                extra_headers={"Referer": "https://unjobs.org/"},
            )
            for m in re.finditer(
                r'<a[^>]+class="jl"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                html_text, re.DOTALL,
            ):
                href = m.group(1)
                title_raw = re.sub(r"<[^>]+>", " ", m.group(2)).strip()
                full_url = href if href.startswith("http") else "https://unjobs.org" + href
                iid = "uj-" + hashlib.md5(full_url.encode()).hexdigest()[:16]
                results.append({
                    "id": iid,
                    "title": html.unescape(title_raw)[:240],
                    "url": full_url,
                    "source": "UNJobs",
                    "publisher": "",
                    "country": "",
                    "job_type": "",
                    "category": "",
                    "posted": None,
                    "closing": None,
                    "description": "",
                })
                if len(results) >= 200:
                    break
            log.append(f"[UNJobs] kw='{kw}' collected: {len(results)}")
        except Exception as exc:
            log.append(f"[UNJobs] kw='{kw}' FAILED: {exc}")
    # dedupe
    uniq: dict[str, dict] = {}
    for r in results:
        uniq.setdefault(r["id"], r)
    out = list(uniq.values())
    log.append(f"[UNJobs] unique total: {len(out)}")
    return out


# ---------- Scoring ----------
def load_keywords() -> dict[str, dict]:
    return json.loads(KEYWORDS_PATH.read_text())


def score_text(text: str, kw: dict) -> int:
    if not text:
        return 0
    t = text.lower()
    score = 0
    for term in kw.get("priority_terms", []):
        if term.lower() in t:
            score += 3
    for term in kw.get("supporting_terms", []):
        if term.lower() in t:
            score += 1
    return min(score, 10)


def score_opportunity(opp: dict, keywords: dict) -> dict:
    text_for_score = " ".join([
        opp.get("title", ""),
        opp.get("category", ""),
        opp.get("country", ""),
        opp.get("job_type", ""),
        opp.get("description", ""),
    ])
    scores = {code: score_text(text_for_score, kw) for code, kw in keywords.items()}
    best_code = max(scores, key=lambda k: scores[k])
    best_score = scores[best_code]
    overall = round((
        scores.get("A_BlendedCatalyticFinance", 0) * 1.0
        + scores.get("B_DealStructuring", 0) * 0.9
        + scores.get("C_ExecutiveTraining", 0) * 0.9
        + scores.get("D_EmergingMarkets", 0) * 0.7
    ) / 3.5, 1)
    opp["scores"] = scores
    opp["best_archetype"] = best_code
    opp["best_score"] = best_score
    opp["overall_score"] = overall
    return opp


# ---------- Merge ----------
def load_pipeline() -> dict:
    if PIPELINE_PATH.exists():
        try:
            return json.loads(PIPELINE_PATH.read_text())
        except Exception:
            pass
    return {
        "last_run_iso": None,
        "last_run_local": None,
        "runs_count": 0,
        "opportunities": [],
    }


def merge(existing: dict, new_opps: list[dict]) -> dict:
    by_id: dict[str, dict] = {o["id"]: o for o in existing.get("opportunities", [])}
    added = 0
    updated = 0
    for n in new_opps:
        if n["id"] in by_id:
            prev = by_id[n["id"]]
            by_id[n["id"]] = {
                **n,
                "status": prev.get("status", "new"),
                "notes": prev.get("notes", ""),
                "first_seen": prev.get("first_seen"),
            }
            updated += 1
        else:
            by_id[n["id"]] = {
                **n,
                "status": "new",
                "notes": "",
                "first_seen": datetime.now(timezone.utc).isoformat(),
            }
            added += 1
    now_utc = datetime.now(timezone.utc)
    existing["opportunities"] = sorted(
        by_id.values(),
        key=lambda o: (o.get("overall_score", 0), o.get("posted") or ""),
        reverse=True,
    )
    existing["last_run_iso"] = now_utc.isoformat()
    existing["last_run_local"] = now_utc.strftime("%Y-%m-%d %H:%M UTC")
    existing["runs_count"] = existing.get("runs_count", 0) + 1
    existing["last_added"] = added
    existing["last_updated"] = updated
    return existing


# ---------- Dashboard ----------
DASHBOARD_TEMPLATE_PATH = SCAN_DIR / "dashboard_template.html"


def render_dashboard(pipeline: dict) -> str:
    tpl = DASHBOARD_TEMPLATE_PATH.read_text()
    pipeline_json = json.dumps(pipeline, ensure_ascii=False)
    tpl = tpl.replace("__PIPELINE_JSON__", pipeline_json)
    tpl = tpl.replace("__LAST_RUN__", html.escape(pipeline.get("last_run_local") or "never"))
    tpl = tpl.replace("__RUNS_COUNT__", str(pipeline.get("runs_count", 0)))
    return tpl


# ---------- Main ----------
def main() -> int:
    log: list[str] = [f"=== Run start: {datetime.now(timezone.utc).isoformat()} ==="]
    try:
        keywords = load_keywords()
        log.append(f"Keywords loaded: {len(keywords)} archetypes")
    except Exception as exc:
        log.append(f"FATAL: keywords load failed: {exc}")
        LOG_PATH.write_text("\n".join(log))
        return 2

    new_opps: list[dict] = []
    for fetcher in [fetch_reliefweb, fetch_unjobs]:
        try:
            new_opps.extend(fetcher(log))
        except Exception as exc:
            log.append(f"Fetcher {fetcher.__name__} fatal: {exc}\n{traceback.format_exc()}")

    log.append(f"Raw new opportunities: {len(new_opps)}")
    scored = [score_opportunity(o, keywords) for o in new_opps]

    pipeline = load_pipeline()
    pipeline = merge(pipeline, scored)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    PIPELINE_PATH.write_text(json.dumps(pipeline, ensure_ascii=False, indent=2))
    log.append(f"Pipeline: {len(pipeline['opportunities'])} total "
               f"(+{pipeline.get('last_added', 0)} new, {pipeline.get('last_updated', 0)} updated)")

    try:
        DASHBOARD_PATH.write_text(render_dashboard(pipeline))
        log.append(f"Dashboard written: {DASHBOARD_PATH}")
    except Exception as exc:
        log.append(f"Dashboard render failed: {exc}")

    log.append(f"=== Run end: {datetime.now(timezone.utc).isoformat()} ===")
    LOG_PATH.write_text("\n".join(log))

    # Echo last lines to stdout for CI logs
    print("\n".join(log[-30:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
