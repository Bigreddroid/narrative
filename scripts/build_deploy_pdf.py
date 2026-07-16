"""Generate Deploy.pdf — the Narrative production deployment runbook.
Run: ~/nv-venv/bin/python scripts/build_deploy_pdf.py
"""
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import os
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Preformatted,
    HRFlowable, PageBreak, KeepTogether,
)

# Repo-root-relative so this works regardless of where the repo lives.
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "Deploy.pdf")

INK   = colors.HexColor("#1A1A1A")
CRIM  = colors.HexColor("#C80028")
TEAL  = colors.HexColor("#2E8B57")
GOLD  = colors.HexColor("#C9A227")
GREY  = colors.HexColor("#6B6B6B")
LINE  = colors.HexColor("#D8D4CC")
CODEBG= colors.HexColor("#F4F2EE")
HEADBG= colors.HexColor("#11201E")
ROWBG = colors.HexColor("#F7F5F1")

MARGIN = 0.8 * inch
PAGE_W, PAGE_H = letter
CONTENT_W = PAGE_W - 2 * MARGIN

ss = getSampleStyleSheet()
def style(name, **kw):
    kw.setdefault("parent", ss["Normal"])
    return ParagraphStyle(name, **kw)

TITLE   = style("t", fontName="Helvetica-Bold", fontSize=24, textColor=colors.white, leading=28)
SUBT    = style("s", fontName="Helvetica", fontSize=11, textColor=colors.HexColor("#C9C4BC"), leading=15)
H1      = style("h1", fontName="Helvetica-Bold", fontSize=14, textColor=CRIM, leading=18, spaceBefore=14, spaceAfter=6)
H2      = style("h2", fontName="Helvetica-Bold", fontSize=11, textColor=INK, leading=15, spaceBefore=8, spaceAfter=3)
BODY    = style("b", fontName="Helvetica", fontSize=9.5, textColor=INK, leading=14, spaceAfter=4)
BULLET  = style("bl", parent=BODY, leftIndent=12, bulletIndent=2, spaceAfter=2)
SMALL   = style("sm", fontName="Helvetica", fontSize=8, textColor=GREY, leading=11)
CODEST  = style("c", fontName="Courier", fontSize=8.2, textColor=colors.HexColor("#10302B"), leading=11.5)
CELL    = style("cell", fontName="Helvetica", fontSize=8.5, textColor=INK, leading=11.5)
CELLB   = style("cellb", parent=CELL, fontName="Helvetica-Bold")

def code(txt):
    p = Preformatted(txt.strip("\n"), CODEST)
    t = Table([[p]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), CODEBG),
        ("BOX", (0,0), (-1,-1), 0.6, LINE),
        ("LEFTPADDING", (0,0), (-1,-1), 8), ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    return t

def para(txt, st=BODY): return Paragraph(txt, st)
def bullets(items):
    return [Paragraph("&bull;&nbsp;&nbsp;" + i, BULLET) for i in items]

def table(rows, widths, header=True):
    data = [[Paragraph(c, CELLB if (header and r==0) else CELL) for c in row] for r, row in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    sty = [
        ("GRID", (0,0), (-1,-1), 0.5, LINE),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 6), ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, ROWBG]),
    ]
    if header:
        sty += [("BACKGROUND", (0,0), (-1,0), HEADBG), ("TEXTCOLOR", (0,0), (-1,0), colors.white)]
    t.setStyle(TableStyle(sty))
    return t

story = []

# ── Header band ──────────────────────────────────────────────────────────────
band = Table([[Paragraph("THE NARRATIVE", TITLE)],
              [Paragraph("Production Deployment Runbook &nbsp;&middot;&nbsp; Railway + Vercel", SUBT)],
              [Paragraph("Generated 2026-06-21 &nbsp;&middot;&nbsp; target hosting ~$30–$50/mo", SUBT)]],
             colWidths=[CONTENT_W])
band.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,-1), HEADBG),
    ("LEFTPADDING", (0,0), (-1,-1), 18), ("RIGHTPADDING", (0,0), (-1,-1), 18),
    ("TOPPADDING", (0,0), (0,0), 18), ("BOTTOMPADDING", (0,-1), (-1,-1), 16),
    ("TOPPADDING", (0,1), (-1,-1), 2),
]))
story += [band, Spacer(1, 12)]

# ── 1. Overview ──────────────────────────────────────────────────────────────
story += [para("1 &nbsp; Overview &amp; architecture", H1)]
story += [para(
    "Two app services deploy from this repo to <b>Railway</b>: <b>api</b> (FastAPI under gunicorn) "
    "and <b>scheduler</b> (one process that runs every pipeline worker — scrape, embed, cluster, "
    "score, map, graph, exposure). Railway-managed <b>Postgres</b> (with pgvector) and <b>Redis</b> "
    "back them. The React/Vite frontend deploys to <b>Vercel</b> and proxies <span face='Courier'>/api</span> "
    "to the Railway API. The Consequence Propagation Engine is deterministic — <b>no LLM at serving "
    "time</b> — so running cost is dominated by hosting, not tokens.")]
story += [para(
    "<b>Cost reality (measured):</b> the entire Claude spend to build the current dataset "
    "(354 mapped events from 1,613 articles over 11 days) was <b>$2.10</b> — about <b>$6/month</b> "
    "at this ingestion rate. Hosting is the lever.", BODY)]
story += [Spacer(1,4), table([
    ["Path", "Hosting", "Total / month"],
    ["Lean", "1 small VPS (docker-compose) + Vercel free", "~$15–$25"],
    ["Managed (chosen)", "Railway 4 services + Vercel free", "~$30–$50"],
    ["Naive (avoid)", "Deploy all 13 railway.toml services", "~$100–$170"],
], [1.4*inch, 3.5*inch, 1.6*inch])]

# ── 2. Pre-deploy ────────────────────────────────────────────────────────────
story += [para("2 &nbsp; Pre-deploy checklist", H1)]
story += bullets([
    "<b>Rotate</b> the Anthropic + Voyage keys in their consoles — the old ones leaked via the "
    "OneDrive <span face='Courier'>.env</span>. New keys go into Railway variables only, never committed.",
    "Confirm the canonical repo copy (three exist on disk; only the OneDrive copy is git-initialized).",
    "Generate a JWT secret: <span face='Courier'>openssl rand -hex 32</span>.",
])

# ── 3. Push to GitHub ────────────────────────────────────────────────────────
story += [para("3 &nbsp; Push to GitHub", H1)]
story += [code(
"# from the project root (already git-initialized, 2 commits on main)\n"
"gh repo create the-narrative --private --source . --remote origin --push\n"
"# or manually:\n"
"git remote add origin https://github.com/<you>/the-narrative.git\n"
"git push -u origin main")]

# ── 4. Railway ───────────────────────────────────────────────────────────────
story += [para("4 &nbsp; Provision on Railway", H1)]
story += bullets([
    "New Project &rarr; <b>Deploy from GitHub repo</b>. Railway reads <span face='Courier'>railway.toml</span> "
    "and creates the <b>api</b> + <b>scheduler</b> services.",
    "Add plugins: <b>New &rarr; Database &rarr; PostgreSQL</b>, and <b>New &rarr; Database &rarr; Redis</b>.",
    "Enable pgvector (the Alembic migration also runs <span face='Courier'>CREATE EXTENSION vector</span>):",
])
story += [code('psql "$DATABASE_URL" -c "CREATE EXTENSION IF NOT EXISTS vector;"')]
story += [para("Set service <b>Variables</b> (both api &amp; scheduler) — reference the plugin vars and add secrets:", H2)]
story += [code(
"DATABASE_URL = postgresql+asyncpg://...   # from ${{ Postgres.DATABASE_URL }} (+asyncpg)\n"
"REDIS_URL    = ${{ Redis.REDIS_URL }}\n"
"APP_ENV      = production                  # disables /docs, runs gunicorn\n"
"SECRET_KEY   = <openssl rand -hex 32>\n"
"ANTHROPIC_API_KEY = <rotated>\n"
"VOYAGE_API_KEY    = <rotated>\n"
"ALLOWED_ORIGINS   = https://<your-app>.vercel.app\n"
"APP_BASE_URL      = https://<your-app>.vercel.app")]
story += [para("Full required/optional list is in <span face='Courier'>.env.production.example</span>. The api "
               "start command runs <span face='Courier'>alembic upgrade head</span> automatically.", SMALL)]

# ── 5. Data migration ────────────────────────────────────────────────────────
story += [para("5 &nbsp; Migrate the real data", H1)]
story += [para("The new Railway DB starts empty. A fresh dump of the real data "
               "(<span face='Courier'>scripts/narrative.dump</span>, 7.8&nbsp;MB — 1,613 articles / 354 mapped) "
               "restores it so the site has data on day one. Regenerate then restore:", BODY)]
story += [code(
"bash scripts/dump_for_railway.sh          # refresh scripts/narrative.dump\n"
"pg_restore --no-owner --no-acl --clean --if-exists \\\n"
"  -d \"<RAILWAY_DATABASE_URL without +asyncpg>\" scripts/narrative.dump")]

# ── 6. Vercel ────────────────────────────────────────────────────────────────
story += [para("6 &nbsp; Deploy the frontend (Vercel)", H1)]
story += bullets([
    "Import the GitHub repo in Vercel. Build is defined in <span face='Courier'>vercel.json</span> "
    "(<span face='Courier'>cd web &amp;&amp; npm install &amp;&amp; npm run build</span>).",
    "No map token needed (the world map is d3/topojson). "
    "<b>Do not</b> set <span face='Courier'>VITE_DEMO_MODE</span> — leaving it unset keeps the app on real data.",
    "Replace the <span face='Courier'>vercel.json</span> rewrite placeholder "
    "<span face='Courier'>REPLACE-WITH-RAILWAY-API…</span> with the real Railway API URL, commit, redeploy.",
    "Back on Railway, set <span face='Courier'>ALLOWED_ORIGINS</span> to the Vercel domain (CORS — keep it an explicit allowlist, never <span face='Courier'>*</span>).",
])

# ── 7. Caps & cost controls (the requested section) ──────────────────────────
story += [PageBreak(), para("7 &nbsp; Caps &amp; cost controls", H1)]
story += [para("7.1 &nbsp; API rate / request caps", H2)]
story += [para(
    "Per-user / per-IP throttling lives in <span face='Courier'>backend/api/rate_limit.py</span> and is "
    "Redis-backed (exact across gunicorn workers). Key = hashed bearer token (per-user, proxy-safe) with "
    "client-IP fallback. <span face='Courier'>/health</span> is exempt; the limiter fails open if Redis "
    "hiccups (never its own outage).", BODY)]
story += [table([
    ["Control", "Default", "Where to change"],
    ["Global request cap", "120 / minute", "default_limits in rate_limit.py"],
    ["Key", "hashed token, else IP", "rate_limit_key() in rate_limit.py"],
    ["Store", "Redis (REDIS_URL)", "auto; memory:// if unset"],
    ["Over-limit response", "HTTP 429", "slowapi handler in main.py"],
], [1.7*inch, 1.9*inch, 2.9*inch])]
story += [code(
"# tighten / loosen the global cap:\n"
"limiter = Limiter(key_func=rate_limit_key,\n"
"                  default_limits=[\"120/minute\"],   # <- edit here\n"
"                  storage_uri=_storage_uri, swallow_errors=True)")]

story += [para("7.2 &nbsp; Claude (token) cost caps", H2)]
story += [para(
    "The only paid LLM step is <span face='Courier'>mapping_worker</span>, which is budget-routed "
    "(a small number of deep Claude calls per run). Cost alerting + budget are configured via env:", BODY)]
story += [table([
    ["Env var", "Default", "Effect"],
    ["CLAUDE_DAILY_COST_ALERT_USD", "20", "alert when day's Claude spend exceeds it"],
    ["CLAUDE_MONTHLY_BUDGET_USD", "200", "monthly budget ceiling for alerting"],
    ["ADMIN_ALERT_EMAIL", "(unset)", "where budget alerts are emailed (needs SMTP)"],
    ["CONSEQUENCE_ENGINE_MODEL", "claude-sonnet-4", "model used for mapping (cost driver)"],
], [2.5*inch, 1.2*inch, 2.8*inch])]
story += [para(
    "Ingestion cadence also caps spend — slower intervals = fewer mappings = lower cost. Tune in env "
    "(<span face='Courier'>SCRAPE_INTERVAL_HOURS</span>, <span face='Courier'>MAPPING_INTERVAL_MINUTES</span>, "
    "thresholds <span face='Courier'>IMPORTANCE_THRESHOLD_DEEP/LIGHT</span>). Real measured rate: "
    "~$0.19/day. Live spend is visible in the <span face='Courier'>pipeline_metrics</span> table and the "
    "admin Cost dashboard.", SMALL)]
story += [para("To run with <b>zero</b> ongoing LLM spend, simply don't deploy the scheduler service — the "
               "api keeps serving the existing data and the deterministic exposure engine.", BODY)]

# ── 8. Verify ────────────────────────────────────────────────────────────────
story += [para("8 &nbsp; Post-deploy verification", H1)]
story += [code(
"curl https://<api>.up.railway.app/health            # {\"status\":\"ok\",\"env\":\"production\"}\n"
"# open the Vercel URL, sign in (enterprise@narrative.dev in non-prod), confirm:\n"
"#   - real events render (Feed / World / Deck / Exposure)\n"
"#   - /admin loads for an admin-tier user\n"
"#   - burst >120 req/min on an endpoint returns HTTP 429\n"
"#   - /docs is DISABLED (APP_ENV=production)")]
story += [para("Verified locally before this runbook: 9/9 backend test files, 3/3 frontend test suites, "
               "production build, and all 11 main API endpoints returning real data.", SMALL)]

# ── 9. Rollback ──────────────────────────────────────────────────────────────
story += [para("9 &nbsp; Rollback &amp; ops notes", H1)]
story += bullets([
    "Railway keeps deploy history — roll back to a previous deployment from the service's Deployments tab.",
    "DB safety: snapshot before migrations with <span face='Courier'>pg_dump</span>; Railway Postgres also offers backups.",
    "Known follow-up: upgrade FastAPI/Starlette (0.111 predates Starlette DoS fixes) as a separate, tested change.",
    "Scheduler is optional; start it only when you want fresh ingestion (it also generates the event "
    "trajectory history shown in Event detail).",
])

story += [Spacer(1, 10), HRFlowable(width="100%", color=LINE),
          para("The Narrative — deployment runbook. Generated by build_deploy_pdf.py. "
               "Secrets are never included; fill real values only in the Railway/Vercel dashboards.", SMALL)]

def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(GREY)
    canvas.drawString(MARGIN, 0.5*inch, "The Narrative · Deployment Runbook")
    canvas.drawRightString(PAGE_W - MARGIN, 0.5*inch, "Page %d" % doc.page)
    canvas.setStrokeColor(LINE)
    canvas.line(MARGIN, 0.62*inch, PAGE_W - MARGIN, 0.62*inch)
    canvas.restoreState()

doc = SimpleDocTemplate(OUT, pagesize=letter, leftMargin=MARGIN, rightMargin=MARGIN,
                        topMargin=0.7*inch, bottomMargin=0.8*inch,
                        title="The Narrative - Deployment Runbook", author="The Narrative")
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("wrote", OUT)
