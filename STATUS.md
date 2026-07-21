# Narrative — STATUS

*The one file to read when it feels like too much. Last updated 2026-07-20.*

---

## What it is (one line)

**An engine that takes a world event and tells *you* what it means *for you* —
the consequence chain, with a graded probability.** Signal → consequence → an
honest number it will be scored on.

The engine is domain-blind (it can serve security, shipping, police, military,
gov…). **v1 aims it at one buyer on purpose.** Full reasoning:
[`docs/POSITIONING.md`](docs/POSITIONING.md).

## Who v1 is for

The **corporate Global Security / GSOC / duty-of-care team** — keep employees and
sites safe in risky regions; brief leadership on exposure. We displace
physical/geo security-intel incumbents (**MidCat, Max Security, Seerist-class**),
winning on the two things they can't do: **official-source grading** and a
**self-graded accuracy record**. Buyer need × capability × gap:
[`docs/CAPABILITY-MAP.md`](docs/CAPABILITY-MAP.md).

Everything broader (military / shipping / police / gov / finance / insurers) is
the **expansion path off the same engine** — later, one door at a time. Not v1.

## Where we stand

- **Product: built and runs.** Ingests real events, builds consequence chains,
  serves them. Live on Vercel (frontend) + Railway (API/scheduler/Postgres/Redis).
- **Scoreboard: built.** Calibration + benchmark + tamper-evident forward ledger
  (Phases 0–4 all merged). Synthetic controls pass; real *crowd* calibration
  proven on Autocast.
- **The one open item is time, not code.** Engine *skill* is honestly **withheld**
  until enough predictions cross the 30-day mark (**~2026-08-12**, gated at n≥20).
  Keep the local Docker stack alive so outcomes accrue — see the memory reminder
  `reminder_aug12_cpe_accrual_check`.

**True status: product built · scoreboard built · waiting on time to prove the
score.**

## What's next

1. **Now:** the redefinition docs above (this is the "make it clear" work).
2. **Then:** tidy the repo + re-lead the landing page around the security buyer
   (see the plan: `~/.claude/plans/get-bak-wi-the-dazzling-umbrella.md`).
3. **~Aug 12:** flip engine skill withheld → real numbers. *That number is the
   pitch.*
4. **After:** build the 3 gaps (asset registry → alerting → branded advisories).

## What each top-level folder is

| Folder | Job | It's one of the 4 real things? |
|---|---|---|
| `backend/consequence_engine/` | The CPE — the core IP | **1. The engine** |
| `backend/feeds/` `scrapers/` `workers/` `scheduler.py` | Ingest: scrape → embed → cluster → score → map | **2. Feeding it** |
| `backend/api/` `services/` `models/` + `web/` | API + the React dashboards | **3. Showing it** |
| `scripts/benchmark_*` `external_benchmark.py` `publish_ledger.py` `backtest_cpe.py` + `docs/benchmark/` | Calibration, benchmark, forward ledger | **4. Proving it** |
| `backend/taxonomy.py` `geo.py` | Shared single-source-of-truth modules | supporting |
| root: `INSTALL_*` `START_*` `*.bat` `*.command`, 3 READMEs, PDFs | Distribution / installers / handoff docs | **clutter — the reorg target** |

> If the repo ever feels like "too much" again, it's almost always the root
> clutter lying to you. There are **4 real things**. Everything else feeds, shows,
> or proves them.
