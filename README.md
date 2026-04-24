# Nuno Scan Agent

Daily automated scan of free job boards (UN/DFI/NGO consulting opportunities), scored against four personal archetypes:

- **A** — Blended & Catalytic Finance
- **B** — Deal Structuring & Investment Memoranda
- **C** — Executive Training & Capacity Building
- **D** — Emerging Markets & Lusophone Advantage

Runs on **GitHub Actions** every day at **07:00 UTC** (~08:00 Lisbon summer / 07:00 winter). Results are written back to the repo and published via GitHub Pages as a sortable dashboard.

**Dashboard URL (after setup):** `https://nuno-svg.github.io/nuno-scan-agent/`

## How it works

1. GitHub Actions cron wakes the runner at 07:00 UTC
2. Python 3.11 runs `scan/run_daily.py`
3. The script queries **ReliefWeb API** (15 keyword queries) and scrapes **UN Jobs**
4. Each opportunity is scored against the 4 archetypes using keyword matching
5. Results merge into `docs/pipeline.json` (preserving statuses you set in the dashboard)
6. `docs/index.html` is regenerated with fresh data
7. The runner commits the changes and GitHub Pages serves the updated dashboard

No server required. No Mac required to be on. Costs €0 (GitHub Actions free tier = 2000 minutes/month; this uses ~30 minutes/month).

## Repo layout

```
nuno-scan-agent/
├── .github/workflows/daily-scan.yml   # Cron + job definition
├── scan/
│   ├── run_daily.py                    # Main agent
│   ├── archetype_keywords.json         # Keyword dictionaries (edit to tune scoring)
│   ├── dashboard_template.html         # HTML template for the published dashboard
│   └── last_run.log                    # Last run diagnostics (written by the workflow)
├── docs/
│   ├── index.html                      # Published dashboard (GitHub Pages serves this)
│   └── pipeline.json                   # Persistent pipeline data
├── README.md
└── .gitignore
```

## Setup (first time, one-off)

See `SETUP.md` for the step-by-step.

## Manual trigger

Go to GitHub → Actions tab → "Daily Consulting Scan" → "Run workflow" button. Runs the same flow immediately without waiting for the cron.

## Tuning the scoring

Edit `scan/archetype_keywords.json`:

- `priority_terms` weight 3 each
- `supporting_terms` weight 1 each
- Score per archetype is capped at 10
- Overall score = weighted average (A × 1.0, B × 0.9, C × 0.9, D × 0.7) divided by 3.5

Commit the change; the next run uses the new weights.

## Adding more sources

Add a `fetch_XXX(log)` function in `scan/run_daily.py` that returns a list of dicts with keys: `id`, `title`, `url`, `source`, `publisher`, `country`, `job_type`, `category`, `posted`, `closing`, `description`.

Then append your fetcher to the list in `main()`.

Candidates worth adding next:
- World Bank Jobs (separate portal, STC/ETC listings)
- IFC Careers (investment-officer roles)
- African Development Bank jobs
- Green Climate Fund vacancies

## Logs and diagnostics

- Latest run log: `scan/last_run.log` (auto-committed)
- Full CI logs: GitHub → Actions tab → click a run

## Dashboard status tracking

Status changes (Review / Applied / Dismiss) are stored in your browser's `localStorage` per origin. Use the same browser to keep state consistent. It does NOT sync back to the repo — the scan agent treats all pipeline entries as "new" from its perspective but the dashboard layer merges your overrides on top.
