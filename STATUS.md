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

> **Corrected 2026-07-26** after a surface-by-surface audit against the incumbent
> stack actually in use at the target customer. The previous version of this
> section read *"Product: built and runs"* and *"the one open item is time, not
> code."* Both were true of the **engine** and false of the **product**, and that
> conflation let a hollow middle go unexamined for weeks. Keep the distinction.

- **Engine + ingest: built, real, running.** Live feeds → embed → cluster → grade
  → consequence chain. Verified 2026-07-26: **29,474 / 29,474** articles linked to
  events, unclustered backlog **0**, **1,509** events carrying ≥2 distinct outlets,
  0 scheduler crashes. Live on Vercel (frontend) + Railway (API/scheduler/PG/Redis).
- **Scoreboard: built.** Calibration + benchmark + tamper-evident forward ledger
  (Phases 0–4 all merged). Synthetic controls pass; real *crowd* calibration
  proven on Autocast. Engine *skill* honestly **withheld** until n≥20
  (**~2026-08-12**) — keep the local Docker stack alive so outcomes accrue
  (memory: `reminder_aug12_cpe_accrual_check`).
- 🔴 **The product around the engine: largely missing.** The API serves **50
  routes** and **none** of them are `sites`, `people`, `org`, `reports`, `advice`
  or `communication`. The executive deck at `/wipro/exec` computes every per-site
  and per-person figure from `web/src/data/customers/wipro.exec.sample.js` —
  invented sites and travellers, in the browser (`ExecDeck.jsx:314,328,345`).
  Only the *events* on that screen are live.

**True status: engine built and proven · scoreboard built and accruing · the
customer-facing product is still a demo skin over both.**

## What's next

> **Reordered 2026-07-26.** The previous order put "build the gaps" *last*, after
> the Aug-12 benchmark number. That was backwards. The score is a **differentiator**
> and a differentiator needs a product to sit on — you cannot win on "we grade
> sources better" against a vendor who can add a site when we can't. See the
> reversal note in [`docs/CAPABILITY-MAP.md`](docs/CAPABILITY-MAP.md).

1. **Now — build the spine:** site register (+ CSV import + `registryAudit` on
   ingest), people/travellers, org + roles. Every number the buyer pays for joins
   to these, and **none of it is blocked on Aug 12 or on customer-supplied data.**
2. **Then — delivery:** notification subscriptions, digest, and mass-comms. This is
   how all four incumbents actually reach the analyst (9,189 vendor messages in one
   observed inbox).
3. **Then — breadth:** country risk pages, real events calendar, scheduled reports,
   official-advisory library (ingested from government sources, never authored).
4. **~Aug 12, in parallel — no code:** engine skill flips withheld → real.
   *That number is the pitch — but it is the proof layer, not the product.*
5. **Ongoing:** repo tidy + landing re-lead
   (`~/.claude/plans/get-bak-wi-the-dazzling-umbrella.md`).

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
