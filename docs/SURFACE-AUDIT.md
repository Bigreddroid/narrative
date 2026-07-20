# Narrative — Surface Audit (what's shown vs. hidden, per market)

> Companion to [`POSITIONING.md`](./POSITIONING.md),
> [`CAPABILITY-MAP.md`](./CAPABILITY-MAP.md), and the root
> [`STATUS.md`](../STATUS.md).
>
> **Status: audit only — nothing has been trimmed.** Execution (nav-hiding,
> dashboard consolidation, Landing re-lead) is deferred to a later, organized
> plan. This file is the decision record it will act from.

## The one rule: **hide ≠ delete**

The engine, feeds, workers, and every capability's code **stay exactly where they
are.** They power the later markets (SOC, shipping, finance, gov/defense). "Cut"
in this document means **remove the surface from the v1 buyer's navigation** (or
gate it behind a flag) so their UI shows only what serves duty-of-care. It never
means deleting engine code.

The v1 buyer = corporate Global Security / GSOC / duty-of-care (see POSITIONING).

## Routed surface today (`web/src/App.jsx`)

Public: `/` Landing · `/auth` · `/benchmark` (public scoreboard)
Protected: `/onboarding` · `/world` · `/event/:id` · `/following` · `/analyst`
(OSINT folded in) · `/geolocate` · `/int` · `/wipro` (hidden demo) · `/settings`
Admin: `/admin` pipeline + costs (admin-gated)

## Core for v1 — keep, this *is* the product for this buyer
- **`/world`** — live event map/feed (situational awareness).
- **`/event/:id`** — the consequence chain + evidence + **graded sources** (the
  core value; answers their #1 pain).
- **`/analyst`** — ask-the-analyst (their most-used incumbent feature).
- **`/int`** — multi-INT fusion (relevant to an intel-security desk).
- **`/benchmark`** — public calibration scoreboard = the trust wedge (receipts).
- **Exposure surfacing** — `ExposurePanel`, `HowThisAffectsYou`, `LensSwitcher`
  (the "affects your region/assets" view).
- **`/settings`**, **`/admin`** (operator/internal).

## A. UI surfaces to hide from the v1 buyer

| Surface | What it is | Why surplus *for this buyer* | Real home |
|---|---|---|---|
| `/geolocate` | Photo geolocation (vision LLM) | IMINT party trick; not part of briefing regional risk to people/sites | gov/defense IMINT (later) |
| 1,098-tool OSINT directory (inside `/analyst`) | Pivot IP/domain/CVE/hash/**wallet** | The SOC/DFIR analyst-pivot workflow, not duty-of-care | SOC crowd (door #2) |
| `/following` | Follow/watchlist feed (consumer pattern) | GSOC works from assets & regions, not a personal follow feed. **Repurposable** → "watched sites/regions" | reframe or hide |
| Crypto/wallet · AIS ships · OpenSky aircraft (as headline layers) | Globe candy | People/sites buyer doesn't lead with vessels/planes/wallets | optional toggle layers; shipping door later |

## B. Framing & packaging to change (messaging, not features)

| Thing | Now | Should be |
|---|---|---|
| Landing hero (`Landing.jsx`) | "TRACK ANY IP/WALLET/VESSEL" + grocery/energy-bill chains | Security-buyer promise + GCC/Red-Sea/facility consequence chains |
| Pricing (`Landing.jsx` `TIERS_PREVIEW`) | 4 tiers: Free / "curious individuals" / "newsrooms" | Lead **Enterprise / contact-sales**; keep `web/src/lib/tiers.js` mechanics for later self-serve |
| `/onboarding` | Self-serve signup wizard | Enterprise buyers are **provisioned** (vendor creates org + sub-users). De-emphasize the consumer flow |

## C. Repo / code surplus (housekeeping, zero v1 product value)
- **`mobile/`** — React Native scaffold, never shipped → park, don't maintain.
- **`dist-frontend/`, `.fastembed_cache/`** — build artifact + model cache →
  should be `.gitignore`d, not tracked.
- **`Mockups/`, `demo/`** — design history / offline-demo assets (not product).
- **Installer sprawl** — the root launcher-script pile (see STATUS.md; note the
  `scripts/package_frontend.sh` + `scripts/build_strategy_pdf.py` path
  dependencies before relocating anything).

## The structural move (bigger than hiding)

`/world` + `/int` + `/wipro` are three takes on the **same** thing: events →
consequence → your exposure. Tailoring a customer should not be a new hand-coded
page — it should be **one configurable dashboard** where the customer's *assets,
regions, and disciplines of interest* filter the view and their logo brands it.
`/wipro` becomes a saved **config**, not a page. This is the "one canonical
engine, thin dashboards" principle applied to the frontend.

## Net v1 surface (what the buyer actually sees)
World/feed → Event consequence chain (graded sources) → Analyst Q&A →
Exposure-to-my-assets → Benchmark receipts. **Everything else: hidden but alive.**
