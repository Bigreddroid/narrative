# Narrative — Capability Map (buyer need × what we have × gap)

> Companion to [`POSITIONING.md`](./POSITIONING.md). Left column = what the v1
> buyer (corporate security / GSOC / duty-of-care) **pays incumbents for today**,
> taken from the Wipro↔MidCat/Max transcripts. Right columns = what Narrative
> already has (with the real module) and where the gap is. **The gaps are the
> roadmap.**

## The map

| Buyer need (from the intel) | Narrative today | Module(s) | Status |
|---|---|---|---|
| **Official-source verification / caveats** (their #1 stated pain) | Every source graded (NATO-Admiralty A–F / 1–6); event promotion gated on ≥2 independent sources | `backend/services/source_reliability.py`, `backend/consequence_engine/corroboration.py` | ✅ **Have — lead with it** |
| **Consequence to our people / sites** | Deterministic consequence propagation + region/sector exposure scoring | `backend/consequence_engine/propagation.py`, `importance_scorer.py`; `backend/api/routes/exposure.py`, `backend/workers/exposure_snapshot_worker.py` | ✅ Have |
| **Self-graded accuracy / track record** | Calibration + auditable forward ledger + external-dataset benchmark (engine skill withheld until n≥20 — Aug ’26 accrual) | `backend/consequence_engine/calibration.py`; `scripts/benchmark_score.py`, `scripts/external_benchmark.py`, `scripts/publish_ledger.py`, `scripts/backtest_cpe.py` | ✅ **Have (unique — no incumbent has this)** |
| **Ask-the-analyst** (Wipro: 21 Qs/yr) | AI analyst (grounded, cited, local-LLM $0) + agentic operator loop over the graph + deep OODA reasoner | `backend/services/analyst.py`, `operator_loop.py`, `operator_tools.py`, `reasoner.py` | ✅ Have (AI form) |
| **Cyber threat watch** (external, non-technical, global) | CYBINT discipline in the multi-INT taxonomy; CISA / threat-intel feeds | `backend/taxonomy.py` (CYBINT), `backend/feeds/` | ✅ Have |
| **Imagery / photo interpretation** | IMINT event creation from operator imagery (vision LLM) | `backend/services/imint_event.py`, `backend/api/routes/imint.py` | ✅ Have |
| **Country / region risk ratings** (dynamic, per-section: armed conflict / militancy / terrorism; last-updated; custom risk appetite) | Region exposure scoring exists, but not packaged as a per-section, customer-tunable "country page" | `backend/api/routes/exposure.py`, `backend/models/exposure_snapshot.py` | 🟡 **Partial** |
| **Asset / location registry + geofencing** (Wipro: 212 assets, add/remove, admin/sub-user) | Region *lens* only — no first-class asset registry a customer curates | — | 🔴 **Gap** |
| **Mass-comms alerting** (MidCat "Next Alert": push to distro lists / phone / WhatsApp) | — | — | 🔴 **Gap** |
| **Branded advisory output** (MidCat "SAM AI": customer logo / format / color) | — | — | 🔴 **Gap** |

## What the map tells us

- **We already win on the two things incumbents structurally can't do** —
  source grading/corroboration (their #1 complaint) and a self-graded track
  record. Lead every conversation there.
- **We're at parity or close** on consequence, ask-the-analyst, cyber, imagery.
- **Three real gaps** separate us from a like-for-like replacement of MidCat/Max.

## Post-Aug-’26 build backlog (priority order)

Do **not** start these until the engine-skill number flips from withheld → real
(that proof is the pitch centerpiece — see [`STATUS.md`](../STATUS.md)). Then:

1. **Asset / location registry + geofencing** — turns "region lens" into "our
   sites," which is the whole duty-of-care buy.
2. **Alerting / mass-comms** — the Next Alert equivalent; push graded advisories
   to a distribution list.
3. **Branded advisory export** — customer logo/format on the output.
4. *(Stretch)* **Country-page packaging** — promote exposure into a per-section,
   customer-tunable risk rating with a last-updated stamp.
