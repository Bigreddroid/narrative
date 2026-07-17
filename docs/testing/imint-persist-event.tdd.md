# TDD evidence — IMINT interpretation → real event

**Branch:** `worktree-imint-persist-event` (based on `worktree-phase-2e-int-gapfill`, tip `f145d21`)
**Source plan:** none — journeys derived during this TDD run.

## The gap this closes

Phase 2e shipped a working IMINT interpreter and a working geolocator. Both were
analytical dead-ends: they returned a read-out and persisted nothing. An operator could
get an excellent OODA-traced assessment of an image and it vanished when the response
closed — never a globe pin, never a graph node, never available to corroborate anything.
Every other discipline produces events; IMINT alone produced a paragraph.

Underneath it was worse than "doesn't persist": **IMINT was unreachable**. `IMINT` is
declared in `taxonomy.DISCIPLINES`, but no entry in `SOURCE_DISCIPLINE` or
`CATEGORY_DISCIPLINE` mapped to it, so `discipline_for()` could never return `"IMINT"`.
The `/int` dashboard's IMINT empty state was not a data gap — it was structural.

## User journeys

1. As an operator, I want an image I upload to become a real event on the globe, so the
   interpretation can be fused with other disciplines instead of being a dead paragraph.
2. As an operator, I want an image that cannot be confidently placed to *stay* off the
   map, so the fusion strip is never fed a coordinate the system invented.
3. As an analyst, I want IMINT events to read as IMINT through the same deterministic
   taxonomy as every other event, not via a hand-set string.

## Task report

| Task | Execution | Validation command | RED | GREEN |
|---|---|---|---|---|
| Compose interpretation + location into an event signal | Pure function `services/imint_event.py`; honesty gate declines to pin a guess | `python -m backend.services.imint_event_test` | `ImportError: cannot import name 'imint_event'` | `24 passed, 0 failed` (26 after the percent regression cases) |
| Make IMINT reachable | Registered `"imint": IMINT` in `taxonomy.SOURCE_DISCIPLINE` + import-time drift guard | same as above | assert would fire | `discipline_for('imint', None) == 'IMINT'` |
| Persist through the canonical path | `/imint?persist=true` runs geolocate + `hazard_ingest_worker._upsert` | live drive (below) | n/a (integration) | HTTP 200, endpoint executes end-to-end |
| Read model confidence as percent | `llm.normalize_confidence`, shared by geolocate/imint/imint_event | `python -m backend.services.llm_test` | `AttributeError: module 'backend.services.llm' has no attribute 'normalize_confidence'` | all pass; `_norm_candidate(...confidence=90.0)` → `0.9` (was `0.0`) |

## Test specification

| # | What is guaranteed | Test | Type | Result |
|---|---|---|---|---|
| 1 | An unavailable interpretation never creates an event | `imint_event_test:unavailable interpretation → no event` | unit | PASS |
| 2 | An image that cannot be located never becomes a pin | `imint_event_test:unplaceable image → no event` | unit | PASS |
| 3 | A location below the 0.35 confidence floor never becomes a pin | `imint_event_test:low-confidence location → no event` | unit | PASS |
| 4 | Out-of-range / missing coordinates are rejected | `imint_event_test:out-of-range latitude → no event` | unit | PASS |
| 5 | A well-evidenced pair produces an event at the interpreted coordinates | `imint_event_test:well-evidenced pair → event` | unit | PASS |
| 6 | The event resolves to IMINT via the real taxonomy, not a hand-set string | `imint_event_test:event resolves to IMINT via the real taxonomy` | unit | PASS |
| 7 | Re-uploading the same image dedupes on its hash | `imint_event_test:re-uploading the same image dedupes on its hash` | unit | PASS |
| 8 | One photo never outranks a measured hazard (importance ≤ 70) | `imint_event_test:a single photo never outranks a major hazard` | unit | PASS |
| 9 | Importance rises with evidence; shaky geolocation drags it down | `imint_event_test:importance rises with evidence` | unit | PASS |
| 10 | A percent-style confidence (llava's real output) still earns an event | `imint_event_test:percent-style confidence still earns an event` | unit | PASS |
| 11 | Percent confidence is rescaled, not discarded and not read as certainty | `llm_test:percent confidence is rescaled, not discarded` | unit | PASS |

Command: `bash scripts/run_backend_tests.sh` → 16/16 registered modules ok.

## Live drive (the part unit tests cannot prove)

Real stack, real llava, `$0`. Isolated: a throwaway `imint-verify` container on a scratch
`narrative_verify` DB, attached to the running compose network — the user's api and dev
DB were never mutated.

- `POST /api/v1/imint` with a real Eiffel Tower photo → **HTTP 200 in ~108s**, provider
  `ollama`, `cost_usd 0.0`, `discipline: IMINT`, assessment *"A well-known cityscape with
  the Eiffel Tower as the main focus"* (confidence 0.9).
- `event.persisted: false` — the honesty gate fired correctly and refused to invent a
  coordinate.
- `GET /events/?discipline=IMINT` baseline → `{"events":[],"total":0}`.

**This drive is what found the confidence bug.** Raw llava output for the geolocate
prompt contained the correct pin (`"lat": 48.8572, "lng": 2.3521, "confidence": 90.0`)
which `_coord(90.0, 0, 1)` discarded as out-of-range → `confidence: 0.0` → below the 0.35
gate → no event, forever, no matter how good the read.

## Happy path — verified on DEFAULT config

Re-driven with no env overrides (text timeout 120s, vision timeout 600s, both defaults):

```
POST /api/v1/imint  → HTTP 200 in 224s
IMINT : "This image shows a cityscape with the Eiffel Tower in the background..."
LOC   : {"place":"Paris","country":"France","lat":48.8561,"lng":2.3577,"confidence":0.9}
EVENT : {"persisted": true, "event_id": "106fa2b7-09f4-42a6-9749-cbf715a15006"}

GET /events/?discipline=IMINT → total: 1
  • IMINT | This image shows a cityscape with the Eiffel Tower... | 48.8561 2.3577
```

DB row: `int_discipline=IMINT`, `source=imint`, real centroid, importance 67 (≤ the 70
ceiling), `embedding IS NOT NULL` (so graph linkage engages). The `/int` IMINT panel —
which was structurally incapable of showing anything — now returns the event with no
frontend change.

Probes:

- 🔍 Re-upload the same image → same `event_id`, `total` still 1. The sha dedupe holds.
- 🔍 `?persist=false` → 52s (one vision call, not two), no `event`/`location` keys. The
  read-only shape is preserved.
- 🔍 Non-image upload → 415 with a clear message. No auth → 401.

## Two more bugs this drive found (both fixed here)

1. **Wrong-shaped model output 502'd the endpoint.** llava returns `"decide"` as a list
   of bare strings often enough to matter; `_norm_candidate` called `.get()` on a `str`
   → `AttributeError` → HTTP 502, violating the module's own doctrine of degrading
   honestly. Same latent trap in geolocate. Both now guard shape and drop the malformed
   entry. RED reproduced the exact live error.
2. **Vision shared the 120s text timeout.** llava on CPU takes ~90-170s per call and
   `/imint` makes two back-to-back, so the geolocate leg always `ReadTimeout`'d — an
   image could never become an event on the default $0 config. New
   `ollama_vision_timeout_seconds` (600s) is used only by the vision path, so text calls
   keep their fast failure detection. The timeout was also *misreported* as "The active
   model can't read images", which sent this session hunting a model-capability problem
   that did not exist; it now says it timed out.

## Coverage and known gaps

- ⚠️ **llava's coordinates are not always right, and it is confident anyway.** One run
  returned `lng -2.229` for Paris (sign error — that pin lands in the Atlantic off
  Brittany) at `confidence: 0.9`; the next returned a correct `2.3577`. The gate cannot
  catch this: it filters on *stated* confidence, and the model states 0.9 either way. The
  honesty gate stops us pinning an image we *can't* place; it cannot stop us pinning one
  the model places *wrongly*.
- **A re-upload still pays for both vision calls** before the `(source, external_id)`
  dedupe short-circuits inside `_upsert`. At $0 local that is only latency (~94s), but on
  paid vision it is real money for a result already on disk. Hashing first and
  short-circuiting before the models run would be a clean follow-up.
- **llava intermittently emits malformed JSON** on the geolocate prompt (observed:
  `"act}: {"` truncation), discarding an otherwise-correct pin. Makes persistence *flaky*,
  not wrong. A salvage parser is a separate change with its own risk.
- No test drives `_upsert` for IMINT against a live DB; it is exercised only through the
  endpoint (which is what the live drive above does).
- `GEOINT` remains unreachable in the taxonomy by design — no collector produces a purely
  geospatial event yet.
