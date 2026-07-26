# Narrative — Capability Map (buyer need × what we have × gap)

> Companion to [`POSITIONING.md`](./POSITIONING.md). Left column = what the v1
> buyer (corporate security / GSOC / duty-of-care) **pays incumbents for today**.
> Right columns = what Narrative already has (with the real module) and where the
> gap is. **The gaps are the roadmap.**
>
> **Evidence basis.** Originally written from the Wipro↔MidCat/Max QBR transcripts
> — i.e. from what the customer *said*. Since corrected against **first-hand
> observation of the four-vendor incumbent stack in production use** (Crisis24
> Horizon, MAX Intel Portal, MitKat Datasurfr, International SOS). That capture
> holds third-party confidential material and named individuals; it is kept
> **outside version control and git-ignored**, and nothing from it is reproduced
> here beyond counts and feature names.

## The map

| Buyer need (from the intel) | Narrative today | Module(s) | Status |
|---|---|---|---|
| **Official-source verification / caveats** (their #1 stated pain) | Every source graded (NATO-Admiralty A–F / 1–6); event promotion gated on ≥2 independent sources | `backend/services/source_reliability.py`, `backend/consequence_engine/corroboration.py` | ✅ **Have — lead with it** |
| **Consequence to our people / sites** | Deterministic consequence propagation + region/sector exposure scoring | `backend/consequence_engine/propagation.py`, `importance_scorer.py`; `backend/api/routes/exposure.py`, `backend/workers/exposure_snapshot_worker.py` | ✅ Have |
| **Self-graded accuracy / track record** | Calibration + auditable forward ledger + external-dataset benchmark (engine skill withheld until n≥20 — Aug ’26 accrual) | `backend/consequence_engine/calibration.py`; `scripts/benchmark_score.py`, `scripts/external_benchmark.py`, `scripts/publish_ledger.py`, `scripts/backtest_cpe.py` | ✅ **Have (unique — no incumbent has this)** |
| **Ask-the-analyst** (Wipro: 21 Qs/yr) | AI analyst (grounded, cited, local-LLM $0) + agentic operator loop over the graph + deep OODA reasoner | `backend/services/analyst.py`, `operator_loop.py`, `operator_tools.py`, `reasoner.py` | ✅ Have (AI form) |
| **Cyber threat watch** (external, non-technical, global) | CYBINT discipline in the multi-INT taxonomy; CISA / threat-intel feeds | `backend/taxonomy.py` (CYBINT), `backend/feeds/` | ✅ Have |
| **Imagery / photo interpretation** | IMINT event creation from operator imagery (vision LLM) | `backend/services/imint_event.py`, `backend/api/routes/imint.py` | ✅ Have |
| **Country / region risk ratings** (dynamic, per-section; last-updated; custom risk appetite) | Scoring maths exists (`domainScores`/`overallScore`/`countryProfile`) but lives **client-side inside the deck** — no country page, no API | `web/src/lib/domainScore.js`; `backend/api/routes/exposure.py` | 🟡 **Partial** |
| **Events calendar** (MAX month grid; observed `+103 more` in a day) | Live public holidays for the register's own countries, plus traveller departures. Names which countries the holiday SOURCE does not cover (Nager returns nothing for India/GCC). 🔴 No gatherings/festivals — no keyless source exists and we will not curate a list we cannot keep current | `web/src/pages/ExecDeck.jsx` (`CalendarGrid`), `/api/v1/context/calendar` | 🟡 **Holidays live, gatherings absent** |
| **Asset / location registry + import** (Crisis24: 199 sites w/ Add·Edit·Delete·export; Datasurfr: 42 assets) | `sites` table + CRUD + **idempotent CSV import, audited on arrival** + CSV export. The deck reads it live | `backend/api/routes/sites.py`, `backend/services/registry_audit.py`, migration `017` | 🟢 **Built** (unmerged branch) |
| **People / traveller tracking** (Crisis24 *People*; duty-of-care attaches to people) | `people` + `trips` tables, CRUD, server-stamped check-in; travellers join sites by **id**, not city name | `backend/api/routes/people.py` | 🟢 **Built** (unmerged branch) |
| **Org / roles / multi-tenancy** (Crisis24 filter: *"Organization: Wipro and Sub-Organizations"*) | Flat orgs + `admin`/`analyst`/`viewer` on the membership row; scoping is a dependency, not a per-route `where`. No sub-org nesting (deliberate) | `backend/api/routes/org.py`, `OrgDep` in `backend/api/dependencies.py` | 🟢 **Built** (unmerged branch) |
| **Email alert delivery** (how all four vendors actually arrive — 9,189 msgs in one observed inbox) | Subscriptions, distribution lists, a deduplicated delivery log and a digest worker. Sends what we escalated AND what we held, with reasons. 🔴 Fails closed: `EMAIL_SEND_ENABLED=false` by default, and needs SMTP credentials to actually send | `backend/workers/digest_worker.py`, `backend/services/mailer.py`, migration `018` | 🟡 **Built, not switched on** |
| **Mass-comms alerting** (MidCat "Next Alert"; Crisis24 *New Message*) | — | — | 🔴 **Gap** |
| **Reports / scheduled reporting** (Crisis24 *Reports*) | — | — | 🔴 **Gap** |
| **Advice library / travel guidance** (Crisis24: 143 advice sheets, Entry-Exit / Pre-Departure / On Arrival / In Transit; ISOS city guides) | 221 current sheets INGESTED from US State Dept + UK FCDO, in each government's own wording, dated and linked. We author none of it. Two authorities shown side by side, never merged into one score | `backend/feeds/advisories.py`, `web/src/pages/Advice.jsx`, migration `019` | 🟢 **Built** (unmerged branch) |
| **Branded advisory output** (MidCat "SAM AI": customer logo / format / color) | — | — | 🔴 **Gap** |

## What the map tells us

> **Rewritten 2026-07-26** after auditing our own surface against the incumbent
> stack. The earlier version said *"three real gaps"* and *"we're at parity or
> close."* Both were too kind. Counting properly: we held **4 of ~14** table-stakes
> surfaces, and the two most load-bearing for the buyer's daily job — *your sites*
> and *your people* — did not exist server-side at all.
>
> **Updated same day (final):** the spine (sites · people/travellers · org+roles),
> delivery (subscriptions · digest · delivery log) and the advice library are now
> **built and verified against a real database and in a browser** — 11 of ~14 — on
> branch `feat/product-spine-sites-people-org`. 🔴 Unmerged, so this is a claim about
> the branch, not about `main`. Still 🔴 **open: scheduled reports** (net-new — ReportLab
> is not in `backend/requirements.txt` and "print brief" is `window.print()`), branded
> advisory output, and mass-comms send. The remaining rows below are still accurate.

- **We win on the two things incumbents structurally can't do** — source
  grading/corroboration (their #1 complaint) and a self-graded track record.
  That remains true, and it is still the lead.
- **But those are differentiators layered on a product that isn't there yet.**
  You cannot win on "we grade sources better" against a vendor who can add a site
  when we can't.
- **The gaps are not exotic.** Registry, people, org, email, reports — this is
  ordinary CRUD and delivery plumbing with no research risk. That is good news:
  it is schedulable work, not invention.

## Build backlog (priority order)

> 🔴 **Sequencing reversed 2026-07-26.** This section previously read *"Do **not**
> start these until the engine-skill number flips from withheld → real."* That
> instruction is now **withdrawn**, and it was the costliest line in these docs:
> it deferred the entire duty-of-care product behind a date, leaving a demo skin
> over a real engine. The benchmark number is a *differentiator* and it needs a
> product to sit on. Skill accrual is calendar time and needs no engineering —
> the two tracks run in parallel, they do not queue.

1. **The spine — site register, people/travellers, org + roles.** Everything else
   joins to these. Registry import runs `web/src/lib/registryAudit.js` on ingest,
   which turns a competitor's observed data-quality defects into our day-one value.
2. **Delivery — subscriptions, digest, email send, mass-comms.** Real send behind
   a flag that fail-closes when SMTP is unconfigured.
3. **Breadth — country risk pages, real events calendar, scheduled reports.**
   Promote `domainScore.js` out of the deck into an API + page.
4. **Advice library — *ingested*, never authored.** Official government advisories
   (US State Dept / UK FCDO / AU Smartraveller) with issuing authority and date
   carried through. We do not write advisory text; that would be exactly the
   fabrication this project refuses elsewhere.
5. **Branded advisory export** — customer logo/format on the output.
