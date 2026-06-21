# The Narrative — Algorithm Catalog & IP Strategy

> ⚠️ **Not legal advice.** This documents what the system does and a practical IP
> framework. Confirm anything legal with a qualified IP attorney before filing.
> Last updated: 2026-06-18.

---

## Part 1 — The Algorithm Catalog (the actual IP inventory)

Every quantitative formula in the pipeline, in execution order. Tunable
parameters (the "secret sauce") are called out — these are the trade-secret
candidates, not the formula shapes themselves.

### 1. Article importance score — `consequence_engine/importance_scorer.py`
Rules-based, no AI. Additive keyword/source signals, capped at 100.

```
score(article) = 15·[affected-population kw]
               + 15·[economic kw]
               + 15·[state-actor kw]
               + 10·[conflict kw]
               + 10·[commodity kw]
               + 15·[source ∈ Tier-1]
score = min(score, 100)
```
Params: the keyword lexicons, the per-signal weights {15,15,15,10,10,15}, the
Tier-1 source set {Reuters, AP, FT, Bloomberg, BBC, Economist}.

### 2. Cluster importance + routing — `importance_scorer.py`
```
cluster_score = min( mean(article_score)
                     + 20·[≥3 distinct sources]
                     + 15·[any Tier-1 source], 100 )
```
Routing to the (expensive) LLM mapper:
```
cluster_score ≥ deep_threshold   → deep Claude mapping (full chain+evidence+prediction)
cluster_score ≥ light_threshold  → light Claude summary
else                             → store only, no LLM   ← cost-control IP
```
Params: cross-source threshold (3), bonuses {20,15}, deep/light thresholds (configurable, defaults ~70 / ~40).

### 3. Clustering — `workers/cluster_worker.py` (pgvector)
Articles merge into an event by embedding cosine similarity:
```
merge if  cos_sim(article_embedding, event_embedding) ≥ 0.82
```
Param: similarity threshold 0.82. Embeddings via Voyage.

### 4. Event→event connection weight — `consequence_engine/graph_connector.py`
Jaccard overlap per dimension, weighted blend:
```
overlap(A,B) = |A ∩ B| / |A ∪ B|              (Jaccard, case-insensitive)
weight = 0.5·sector_overlap + 0.3·geo_overlap + 0.2·keyword_overlap
keep edge if weight ≥ graph_connection_threshold
```
Params: dimension weights {0.5, 0.3, 0.2}, connection threshold.

### 5. Evolution / drift detection — `consequence_engine/evolution_tracker.py`
Re-map an event when it materially changes. Two triggers:
```
(a) any new article with importance_score ≥ 80           → re-map
(b) embedding drift > 0.15                                → re-map
    drift = 1 − cos_sim(event_embedding, mean(new_article_embeddings))
```
Params: high-importance rescore threshold 80, drift threshold 0.15.

### 6. Prediction outcome calibration — `workers/outcome_worker.py`
Closes the loop: scores past predictions against what actually happened
(currently a status-based heuristic; designed to become a true calibration metric).
```
resolved   → materialized,  calibration_error = |score − 85| / 100
escalating → partial,        calibration_error = |score − 65| / 100
stable     → failed,         calibration_error = score / 100
```
This **calibration dataset is itself defensible IP** — a proprietary, growing
record of how well the system's predictions track reality.

### 7. ★ Consequence Propagation Engine (CPE) — `web/src/lib/propagation.js`
**The crown jewel.** Deterministic, explainable, runs without the LLM. Turns the
LLM's evidence-graded impacts into a bounded, attributable **Exposure Index**.

Per-event base signal:
```
importance(e) = clamp01( importance_score / 100 )
confidence(e) = mean over consequence-chain nodes of:
                  VERIFIED → 1.0,  INFERRED → 0.6,  SPECULATIVE → 0.3
base(e)       = importance(e) · confidence(e)
```
Severity weights (the tuned table):
```
SEVERITY = { critical: 1.0, high: 0.72, medium: 0.45, low: 0.22 }
```
Emissions (what each event projects shock onto):
```
sector emission weight = SEVERITY[severity]            (direct)
                       = SEVERITY[severity] · 0.6      (indirect, INDIRECT_FACTOR)
region emission weight = max severity across the event's impacts
```
Propagation (1-hop direct + 2-hop causal amplification):
```
for each event e, for each emitted (entity, w):
    shock(entity) += base(e) · w                                    # 1-hop
    for each causal neighbor nb of e:
        shock(entity) += base(nb) · edge_weight(nb) · LAMBDA · w    # 2-hop, decayed
```
Saturating, bounded index + attribution:
```
ExposureIndex(entity) = round( 100 · (1 − e^(−shock / K)) )         # 0–100
drivers(entity)       = top-3 source events by contribution share (%)
```
Profile (personalized) exposure:
```
ProfileExposure = round( 0.65 · max(matched dimensions)
                       + 0.35 · mean(matched dimensions) )
```
**Tuned parameters (the secret sauce — versioned with the model):**
`LAMBDA = 0.5` (per-hop decay), `K = 0.8` (saturation constant),
`INDIRECT_FACTOR = 0.6`, the severity table, the evidence-grade confidence map,
and the 0.65/0.35 profile blend.

### 8. Per-event exposure heat + traffic→CPE disruption — `propagation.js` / `propagation.py`
Each event gets a 0–100 **heat** = its total drive across all entities:
```
drive(e)      = Σ_entities |contribution of e|           (from the attribution pass)
EventHeat(e)  = 100 · (1 − e^(−drive(e) / K_EVENT))      K_EVENT = 1.2
```
Live **traffic disruption** as a consequence — heavy ship/plane traffic near an
escalating event raises Shipping / Aviation exposure:
```
w_disrupt(e, n) = DISRUPTION_K · (1 − e^(−n / TAU_TRAFFIC)) · (escalating ? 1 : 0.5)
                  DISRUPTION_K = 0.8,  TAU_TRAFFIC = 30   (n = vessels|aircraft in zone)
```

### 9. Geo-association — `web/src/lib/geoAssoc.js`
Ties each ship/plane to its nearest event within a scaled impact radius, and flags anomalies:
```
radius(e)        = clamp(300 + importance·9, 300, 1200) km
assign(item)     = argmin_e haversine(item, e)  s.t. dist ≤ radius(e)
anomaly(count)   = z = (count − μ) / σ  over the cross-event baseline;
                   z ≤ −1 ⇒ "rerouting" (avoidance),  z ≥ +1.5 ⇒ "surge"
```

### 10. ★ Temporal layer — history, timelines & patterns — `temporal.js` / `temporal.py`
Turns snapshots into trajectories. **This is the compounding moat** — every formula
sharpens as proprietary history accrues.
```
EMA_α(x)        = α·xₜ + (1−α)·EMA(x₍<ₜ₎)                  α = 0.4
Momentum        = xₜ − EMA_α(x₍<ₜ₎)        Trend = sign(Momentum) past ±ε
Analog(target)  = 0.40·[same category] + 0.35·Jaccard(sectors) + 0.25·Jaccard(geography)
                  → ranked past events, each carrying its REALISED outcome
LeadLag         = median over directed edges of  (t_effect − t_cause)  in days
```
Calibration is also **pattern-conditioned** over time (base rates per category/pattern)
and prediction scores are **isotonically recalibrated** from realised outcomes (#6 above).

> **Why temporal = the moat:** competitors can copy a weighted-sum formula, but not your
> *accumulated, outcome-labelled history* of events → consequences → exposure. Analogs,
> lead-lag, momentum, and calibration all improve monotonically with that dataset, which
> only you hold. This is the defensible compounding asset to protect as a **trade secret**.

---

## Part 2 — IP reality check (where the instinct is right, where it's off)

**Right:** there's real, nameable, differentiating IP here — a *named*
deterministic algorithm (the CPE) with tunable parameters, end-to-end
explainability, evidence-grading, and a self-improving calibration dataset. Worth
protecting.

**Off (the common conflation):** "TM **or** patent **or** something" treats them as
interchangeable. They're four distinct regimes protecting four different assets:

| Regime | Protects | Cost / speed | Fit here |
|---|---|---|---|
| **Trademark** (™/®) | Brand & product *names*, logo | Cheap; ™ free now, ® ~$250–350/class | Names only — NOT the math |
| **Copyright** | Your *source code as written* (expression) | Free & automatic; registration optional | The codebase, automatically |
| **Trade secret** | Confidential, valuable info you keep secret | Free, but requires real secrecy | **Best fit for the tuned params** |
| **Patent (utility)** | *Inventions* (a technical method/system) | $10–20k+, 2–4 yrs, public disclosure | Hard & probably premature |

**The hard truth about patenting the formulas:** in the US, abstract ideas and
mathematical formulas are *not* patent-eligible on their own (Alice v. CLS Bank,
Mayo; 35 U.S.C. §101). A weighted sum, cosine similarity, Jaccard overlap, and an
exponential saturation curve are textbook math and largely known. You could *maybe*
patent a specific **technical system/pipeline** if framed as a concrete technical
improvement — but it's expensive, slow, uncertain, and **publishes your method to
every competitor**. For an early-stage product this is rarely the first move.

**The biggest immediate risk is not "no patent" — it's exposure.** The CPE
(`propagation.js`) currently runs **client-side in the browser**, which means
`LAMBDA`, `K`, the severity table, and every tuned constant are **shipped to every
user in plaintext** and trivially extractable. That actively *defeats* trade-secret
protection. If the CPE is the crown jewel, **it must move server-side.**

---

## Part 3 — How to proceed (ordered cheap → expensive)

1. **Trade-secret hygiene — do now, ~free, highest ROI**
   - Move the CPE server-side (a `/api/v1/exposure` endpoint); ship only computed
     scores + drivers to the client, never the parameters.
   - Keep params in server config / env, out of any client bundle. Private repos.
   - Add NDAs + IP-assignment agreements for any contractor/collaborator/employee.
   - Add proprietary/confidential headers to engine files (the CPE header is a good start).
2. **Copyright — free & automatic; register before any dispute**
   - It already attaches to your code. Add a `LICENSE` (proprietary, all rights
     reserved) and per-file headers. Register key files with the Copyright Office
     (~$45–65) if/when you want enforceable statutory damages.
3. **Trademark — cheap, do soon**
   - Knockout-search and clear distinctive names: the product brand, **"Consequence
     Propagation Engine"**, **"Exposure Index"**. Note "The Narrative" is fairly
     generic and may be hard to register — consider a more distinctive mark.
   - Use **™** today (no filing needed); file **®** for the core brand when budget allows.
4. **Patent — later, maybe, with counsel**
   - Only if you can frame a concrete *technical* improvement, have funding, and
     accept public disclosure. A **provisional** ($75–$300 gov fee + attorney) buys
     12 months of "patent pending" and a priority date. Optional for now.
5. **Defensive evidence**
   - Keep dated version history of the parameters and engine (you have file
     timestamps + the `CPE.VERSION` field — formalize this).

**Recommended first action:** move the CPE server-side (protects the secret sauce
*and* unblocks wiring the Exposure Index into the UI), then apply ™ + a proprietary
license. Defer patent until there's funding and a clear technical claim.
