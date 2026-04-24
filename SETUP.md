# Setup — Nuno Scan Agent

Guia passo a passo para ter o agente a correr na nuvem GitHub em ~20 minutos. Desenhado para a conta **nuno-svg**.

**Pré-requisitos:** conta GitHub, Git instalado no Mac (vem com Xcode Command Line Tools — se não tem, abrir Terminal e correr `xcode-select --install`).

---

## Passo 1 — Criar o repositório no GitHub (2 min)

1. Abrir https://github.com/new
2. Preencher:
   - **Repository name:** `nuno-scan-agent`
   - **Description:** "Daily scan of UN/DFI/NGO consulting opportunities"
   - **Visibility:** **Public** (necessário para GitHub Pages grátis; o conteúdo são só URLs de vagas públicas, nada sensível)
   - **Initialize this repository:** deixar TUDO desmarcado (não criar README, .gitignore, license — já os temos no ZIP)
3. Clicar **Create repository**
4. GitHub mostra uma página com os comandos para fazer push. Deixar essa janela aberta ou copiar o URL do repositório: deve ser `https://github.com/nuno-svg/nuno-scan-agent.git`

---

## Passo 2 — Push do código para o repo (3 min)

Abrir o **Terminal** no Mac e executar:

```bash
# Navegar até onde extraiu o ZIP
cd ~/Desktop/Em\ Curso/Projetos\ Nuno\ 2025/nuno-scan-agent

# Inicializar git e primeiro commit
git init
git branch -M main
git add .
git commit -m "Initial scan agent setup"

# Conectar ao repo remoto e fazer push
git remote add origin https://github.com/nuno-svg/nuno-scan-agent.git
git push -u origin main
```

Na primeira vez que faz `push` o Mac pode pedir credenciais:

- **Username:** `nuno-svg`
- **Password:** aqui **não é a sua password do GitHub**, tem de ser um *Personal Access Token*. Salte para o Passo 3 se ainda não tiver um, depois volte a correr `git push -u origin main`.

---

## Passo 3 — Criar um Personal Access Token (3 min)

O GitHub já não aceita a password normal para operações de Git na linha de comandos. Precisa de um token, que funciona como uma password específica para cada aplicação.

1. Ir a https://github.com/settings/tokens?type=beta
2. Clicar **Generate new token** → **Fine-grained personal access token**
3. Preencher:
   - **Token name:** `nuno-scan-agent-push`
   - **Expiration:** 90 days (ou "No expiration" se preferir, mas é mais seguro rodar)
   - **Repository access:** *Only select repositories* → escolher `nuno-svg/nuno-scan-agent`
   - **Permissions** → Repository permissions:
     - **Contents:** **Read and write** ← ESSENCIAL
     - **Metadata:** Read-only (automático)
     - **Workflows:** Read and write (para poder editar workflows no futuro)
     - Deixar tudo o resto como "No access"
4. Clicar **Generate token** em baixo
5. **COPIAR O TOKEN AGORA** — começa por `github_pat_...`. É a única vez que o GitHub o mostra; se fechar a página perde-o e tem de gerar outro.

Guardar o token num sítio seguro (password manager, Apple Keychain, ou por 10 minutos num ficheiro temporário).

**Usar o token:** quando o `git push` pedir password, cole o token em vez da password. O Mac pode oferecer guardar no Keychain — aceitar, assim não tem de colar de novo em cada push.

---

## Passo 4 — Activar GitHub Pages (2 min)

Depois do primeiro push ter corrido:

1. Ir ao repo no browser: `https://github.com/nuno-svg/nuno-scan-agent`
2. Menu **Settings** (em cima à direita, dentro do repo)
3. No menu da esquerda clicar **Pages**
4. Em **Source**: escolher **Deploy from a branch**
5. **Branch:** `main` / Folder: `/docs`
6. Clicar **Save**
7. Aguardar 1-2 minutos. No topo da página Pages aparece um rectângulo verde com o URL publicado: `https://nuno-svg.github.io/nuno-scan-agent/`

Abra este URL — vai ver o dashboard vazio ("never run", zero opportunities). É normal. Adicione aos bookmarks.

---

## Passo 5 — Correr o primeiro scan manualmente (1 min)

Para não esperar até amanhã às 07:00 UTC:

1. No repo → **Actions** (tab no topo)
2. Lado esquerdo, clicar em **Daily Consulting Scan**
3. Botão à direita **Run workflow** → deixar branch `main` → **Run workflow**
4. Ao fim de ~30 segundos aparece uma run com um círculo amarelo (em progresso) → fica verde (sucesso) ou vermelho (falha) em ~1-2 minutos
5. Clicar na run para ver os logs, especialmente o step **"Run scan agent"** para confirmar que a ReliefWeb respondeu
6. Recarregar o URL do dashboard — deve aparecer vagas pontuadas

Se o run ficar vermelho, abra o log do step que falhou e cole-me aqui. Diagnóstico é directo.

---

## Passo 6 — Confirmar o cron (30 seg)

O workflow já está configurado para `0 7 * * *` (07:00 UTC todos os dias). Não precisa fazer nada; o GitHub acorda sozinho a partir de agora. Para confirmar:

- Actions → Daily Consulting Scan → veja que diz "Scheduled" como trigger
- O próximo run aparece com timestamp futuro

Nota: cron no GitHub pode atrasar até 30 minutos em horas de pico. 07:00 UTC significa algures entre 07:00 e 07:30 UTC. Para o caso não é problema.

---

## Manutenção — afinar o agente

Tudo o que precisar de mudar no futuro:

- **Adicionar/remover keywords:** editar `scan/archetype_keywords.json` → commit → push
- **Mudar hora do cron:** editar `.github/workflows/daily-scan.yml` → linha `cron:` → commit → push
- **Adicionar novas fontes:** editar `scan/run_daily.py` (ver secção no README)

Cada push despoleta imediatamente um novo scan (porque `workflow_dispatch` também é trigger) só se correr manualmente. O cron continua normalmente.

---

## Troubleshooting

**"Run workflow" não aparece**
Confirme que está na tab Actions do seu repo `nuno-svg/nuno-scan-agent` e que o ficheiro `.github/workflows/daily-scan.yml` foi mesmo para o GitHub (check em `https://github.com/nuno-svg/nuno-scan-agent/tree/main/.github/workflows`).

**Workflow corre mas o commit falha com permission denied**
Menu Settings do repo → Actions → General → "Workflow permissions" → seleccione **Read and write permissions** → Save. Correr novamente.

**Pages mostra 404**
Pode demorar 2-3 minutos a propagar depois do primeiro deploy. Se persistir, confirme que Settings → Pages está com Source = "Deploy from a branch", Branch = main, Folder = /docs.

**O scan encontra zero opportunities**
Abrir logs do step "Run scan agent" para ver se a ReliefWeb respondeu. Se respondeu com JSON mas zero resultados, as queries podem não estar a bater — ajustar keywords em `scan/archetype_keywords.json`.

**Token expirou**
Gerar novo token (Passo 3). No próximo push, colar o novo token quando pedir password.
