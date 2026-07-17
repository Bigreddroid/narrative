# Wipro Demo — customer-centric dashboard on the Narrative backend

A single-page, client-branded view (`/wipro`) that answers the questions the client
actually asked in their vendor QBR — driven **entirely by the live Narrative backend**
(no new backend code, no mock UI data; the only seeded content is one clearly-labelled
`[DEMO]` scenario so the fusion engine has something to fuse on a fresh stack).

## Why this demo exists

The renewal transcripts show the client (7 seats, 212 assets, staff concentrated in
UAE/Saudi + a growing Europe footprint) asking their incumbent geopolitical-risk vendor
for **cross-domain connections** — how Middle East events, Europe/Ukraine, and cyber
threats connect — and the vendor's human analyst could only offer "some are connected."
Structural cross-discipline fusion is exactly what Narrative computes deterministically.

## Feature-for-feature vs the incumbent ("Team Max")

| Incumbent sells | This dashboard | Edge |
|---|---|---|
| Country risk ratings, analyst-timestamped | **Country Risk cards** computed live from event flow | continuous, not editorial-cycle |
| **Canvas** — client overrides ratings to own risk appetite | **Risk-appetite slider** re-baselines all ratings client-side | same control, zero analyst round-trip |
| Ask-the-analyst, **quota'd (client used 21/yr)** | **Ask the Analyst — Unlimited** (local LLM, agentic over the live graph) | unlimited, $0 marginal cost |
| Seat portal tracking 212 assets | **Real Estate & Asset Exposure** — every site scored against nearby events | proximity-scored, not just listed |
| GSOC travel advisories + evac | **Travel Security** panel — trips matched to events + country rating | advisory parity; *physical response honestly out of scope → partner tier* |
| Non-technical cyber intel | CYBINT is a first-class discipline fused with the rest | cyber **connected to** geopolitical, not a silo |
| Hand-waved cross-domain links | **Cross-Domain Fusion strip** — engine-corroborated multi-INT convergences | the wedge: structural, explainable, per-event |

Honest boundaries (say them in the room): no physical GSOC/evacuation/human liability —
that stays a partner/services play. No satellite tasking; imagery is interpretation of
provided photos (IMINT, `/imint`).

## Run it

```bash
docker compose up -d                      # full stack, $0/keyless
python demo/wipro/seed_scenario.py        # idempotent [DEMO] scenario (or run inside the api container)
# open http://localhost:5173/wipro        # login: enterprise@narrative.dev / betatest1
```

The dashboard reads: `GET /api/v1/exposure`, `GET /api/v1/events/` (trailing slash
matters), `POST /api/v1/chat` (`agent: true`). Asset + travel fixtures live in
`web/src/data/wipro/` and are plainly demo data.

## Before a live demo (two-minute checklist)

- **Re-run the seeder the morning of the demo.** The fusion strip only fires on
  events within a 72 h window of each other; the seeded cluster ages out of that
  window and the strip goes quiet. Re-running `seed_scenario.py` slides the demo
  rows' detection time back to *now*, so the cross-domain connections light up
  again. It's idempotent — safe to run as many times as you like.
  ```bash
  python demo/wipro/seed_scenario.py     # or: docker compose exec api python demo/wipro/seed_scenario.py
  ```
- **After any `git pull`, restart the web container.** Vite's file watcher does not
  see git changes through the Windows/OneDrive bind mount, so a pulled `/wipro`
  change won't appear until you restart it (this once made the whole page 404):
  ```bash
  docker compose restart web
  ```

## What's in this folder

| File | Purpose |
|---|---|
| `README.md` | this — story, positioning, run steps |
| `seed_scenario.py` | idempotent cross-domain `[DEMO]` scenario (Gulf + Black Sea clusters) via the canonical ingest path |
| `TIMELINE.md` | where the build is, what's left, drawn timeline |
