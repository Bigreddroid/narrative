// ─────────────────────────────────────────────────────────────────────────────
//  THE NARRATIVE — CONSEQUENCE PROPAGATION ENGINE (CPE)  v2
//  Proprietary core. Deterministic. Explainable. Runs WITHOUT the LLM.
//
//  The LLM (consensus_mapper) is a *feeder*: it extracts evidence-graded impacts
//  per event. This engine is the product — it assembles a typed causal graph and
//  propagates each event's shock outward to compute a bounded, attributable
//  EXPOSURE INDEX for any entity (sector, region, commodity, or user profile).
//
//  v2 upgrades over v1 (all still deterministic + explainable + attributable):
//   • n-hop influence via a converging Katz/personalized-PageRank diffusion
//     (replaces the single fixed 2-hop term) — true multi-step causal reach.
//   • Confidence now rewards corroboration (# independent sources, saturating)
//     and penalizes the LLM's own `disputed_points` (previously ignored).
//   • Temporal decay — fresh shocks dominate; stale events fade (e-folding TAU).
//   • Signed / mitigating impacts — a ceasefire or resolution REDUCES exposure,
//     so the net index is genuinely meaningful (not monotonic-up only).
//   • Entity resolution — canonical alias map collapses "Shipping & Logistics"
//     and "Shipping" so exposure stops silently fragmenting across name variants.
//   • Directed edges — when the graph carries cause→effect direction, influence
//     flows downstream only; otherwise it degrades gracefully to undirected.
//   • Full attribution survives the diffusion: every entity's score decomposes
//     into ranked SOURCE events (drivers) + mitigating factors, with % share.
//
//  Math
//  ────
//  base(e)        = importance(e) · confidence(e) · recency(e)
//  effective(e)   = base(e) + LAMBDA · Σ_{c→e}  w(c→e) · effective(c)   (Katz)
//  shock(entity)  = Σ_e  Σ_impacts  sign · severity · effective(e)
//  ExposureIndex  = 100 · (1 − e^(−max(net_shock,0) / K))               (0–100)
//
//  Why this is defensible IP (not prompt engineering):
//   • a named, deterministic algorithm with explicit, tunable, versioned params
//   • explainable end-to-end (every score decomposes to source events)
//   • confidence-weighted by evidence grade (VERIFIED > INFERRED > SPECULATIVE)
//   • compounds with proprietary data (more events/edges/outcomes → sharper graph)
// ─────────────────────────────────────────────────────────────────────────────

// NOTE (IP): this module is the trade-secret surface (the engine + its tuned
// constants). It is the AUTHORITATIVE engine ONLY server-side
// (backend/consequence_engine/propagation.py). This client copy exists solely to
// render the OFFLINE DEMO and must never be statically imported — load it lazily
// behind a DEMO_MODE guard so it is dead-code-eliminated from production builds.
// See docs/IP-AND-ALGORITHMS.md.
import { canonicalize } from "./exposureProfile.js";

// Engine parameters (the tuned "secret sauce" — versioned with the model).
export const CPE = {
  VERSION: "2.0",
  ENGINE_VERSION: "2.0",
  LAMBDA: 0.5,            // per-hop decay for causal amplification (LAMBDA·ρ(W) < 1 ⇒ converges)
  K: 0.8,                // saturation constant for the exposure curve
  INDIRECT_FACTOR: 0.6,  // downstream (indirect) impacts count less than direct
  SEVERITY: { critical: 1.0, high: 0.72, medium: 0.45, low: 0.22 },
  EVIDENCE: { VERIFIED: 1.0, INFERRED: 0.6, SPECULATIVE: 0.3 },
  KAPPA: 2.5,            // corroboration saturation — sources needed for high confidence
  DELTA: 0.5,            // max confidence penalty from fully-disputed claims
  TAU_HOURS: 168,        // event-freshness e-folding horizon (≈7 days)
  MAX_ITERS: 64,         // Katz diffusion iteration cap
  EPSILON: 1e-4,         // Katz convergence tolerance (max per-node delta)
  K_EVENT: 1.2,          // saturation for per-event exposure heat
  DISRUPTION_K: 0.8,     // max shock from traffic disruption near an event
  TAU_TRAFFIC: 30,       // traffic-count saturation for disruption emissions
};

const clamp01 = (x) => Math.max(0, Math.min(1, x));
const asArray = (v) => (Array.isArray(v) ? v : v ? [v] : []);
const sevWeight = (s) => CPE.SEVERITY[String(s || "medium").toLowerCase()] ?? CPE.SEVERITY.medium;
const importanceOf = (e) => clamp01((e.importance_score ?? e.global_importance_score ?? e.importance ?? 0) / 100);

// Freshness: events decay with age so a 6-month-old shock no longer dominates.
function recencyOf(e, now) {
  const raw = e.last_updated_at || e.first_detected_at || e.created_at || e.detected_at;
  if (!raw) return 1; // no timestamp → treat as current (don't punish mock/test data)
  const t = new Date(raw).getTime();
  if (Number.isNaN(t)) return 1;
  const ageHours = Math.max(0, (now - t) / 3_600_000);
  return Math.exp(-ageHours / CPE.TAU_HOURS);
}

// Confidence from evidence grade × corroboration × (1 − dispute). The LLM feed's
// evidence grades, source count, and disputed points all flow in here.
function confidenceOf(e) {
  const m = e.consequence_map || {};
  const chain = m.consequence_chain || [];

  let grade;
  if (chain.length) {
    let s = 0;
    for (const n of chain) {
      const t = (n.type || "").toUpperCase();
      s += t.includes("VERIFIED") ? CPE.EVIDENCE.VERIFIED
        : t.includes("INFERRED") ? CPE.EVIDENCE.INFERRED
        : CPE.EVIDENCE.SPECULATIVE;
    }
    grade = s / chain.length;
  } else {
    const c = m.confidence;
    grade = c === "high" ? 0.85 : c === "low" ? 0.4 : 0.6;
  }

  const nSources = (m.sources_analyzed?.length)
    ?? e.sources_count
    ?? (e.articles?.length)
    ?? (chain.length || 1);
  const corroboration = 1 - Math.exp(-nSources / CPE.KAPPA);

  const disputed = m.disputed_points?.length || 0;
  const disputePenalty = disputed ? CPE.DELTA * (disputed / (chain.length + disputed)) : 0;

  return clamp01(grade * corroboration * (1 - disputePenalty));
}

// The seed shock each event injects before any propagation.
const baseOf = (e, now) => importanceOf(e) * confidenceOf(e) * recencyOf(e, now);

// Whether an impact mitigates (reduces) rather than aggravates exposure.
const isMitigating = (i) =>
  String(i?.direction || i?.effect || "").toLowerCase().match(/mitigat|reduc|de-?escalat|resolv/) != null;

// Entity emitters — what each event projects shock onto, how hard, and which sign.
// `trafficByEvent` (optional) injects live disruption: heavy ship/plane traffic near
// an event raises Shipping / Aviation exposure — traffic disruption as a consequence.
function sectorEmissions(e, trafficByEvent) {
  const m = e.consequence_map || {};
  const out = [];
  asArray(m.direct_impact).forEach((i) => {
    if (i?.sector) out.push({ target: i.sector.trim(), w: sevWeight(i.severity), sign: isMitigating(i) ? -1 : 1 });
  });
  asArray(m.indirect_impact).forEach((i) => {
    if (i?.sector) out.push({ target: i.sector.trim(), w: sevWeight(i.severity) * CPE.INDIRECT_FACTOR, sign: isMitigating(i) ? -1 : 1 });
  });
  const tr = trafficByEvent && trafficByEvent[String(e.id)];
  if (tr) {
    const esc = e.current_status === "escalating" ? 1 : 0.5;
    const disrupt = (n) => CPE.DISRUPTION_K * (1 - Math.exp(-(n || 0) / CPE.TAU_TRAFFIC)) * esc;
    if (tr.vessels) out.push({ target: "shipping", w: disrupt(tr.vessels), sign: 1 });
    if (tr.aircraft) out.push({ target: "aviation", w: disrupt(tr.aircraft), sign: 1 });
  }
  return out;
}

function regionEmissions(e) {
  const geos = e.geography || e.geographic_relevance || [];
  const impacts = [...asArray(e.consequence_map?.direct_impact), ...asArray(e.consequence_map?.indirect_impact)];
  const maxSev = impacts.length ? Math.max(...impacts.map((i) => sevWeight(i.severity))) : 0.5;
  // Region sign follows the dominant impact: an all-mitigating event eases regional exposure.
  const allMitigating = impacts.length > 0 && impacts.every(isMitigating);
  return geos.map((g) => ({ target: String(g).trim(), w: maxSev, sign: allMitigating ? -1 : 1 }));
}

// ── Katz/PPR diffusion over the event→event graph, with per-source attribution ─
// effective(e) = base(e) + LAMBDA·Σ_{c→e} w·effective(c), iterated to convergence.
// attr.get(e) decomposes effective(e) into the SOURCE events it traces back to.
function diffuse(events, edges, now) {
  const byId = new Map(events.map((e) => [String(e.id), e]));
  const ids = events.map((e) => String(e.id));

  // Incoming adjacency: in.get(effect) = [{ from: cause, w }]
  const inAdj = new Map(ids.map((id) => [id, []]));
  (edges || []).forEach((ed) => {
    const a = String(ed.source_event_id ?? ed.source);
    const b = String(ed.target_event_id ?? ed.target);
    const w = ed.weight ?? ed.connection_weight ?? 0.5;
    if (!byId.has(a) || !byId.has(b)) return;
    inAdj.get(b).push({ from: a, w });                 // cause a → effect b
    if (ed.directed !== true) inAdj.get(a).push({ from: b, w }); // undirected ⇒ both ways
  });

  const base = new Map(ids.map((id) => [id, baseOf(byId.get(id), now)]));
  let eff = new Map(base);
  let attr = new Map(ids.map((id) => [id, new Map([[id, base.get(id)]])]));

  for (let iter = 0; iter < CPE.MAX_ITERS; iter++) {
    const nextEff = new Map();
    const nextAttr = new Map();
    let maxDelta = 0;

    for (const id of ids) {
      let v = base.get(id);
      const m = new Map([[id, base.get(id)]]);
      for (const { from, w } of inAdj.get(id)) {
        v += CPE.LAMBDA * w * eff.get(from);
        for (const [src, amt] of attr.get(from)) {
          m.set(src, (m.get(src) || 0) + CPE.LAMBDA * w * amt);
        }
      }
      nextEff.set(id, v);
      nextAttr.set(id, m);
      maxDelta = Math.max(maxDelta, Math.abs(v - eff.get(id)));
    }

    eff = nextEff;
    attr = nextAttr;
    if (maxDelta < CPE.EPSILON) break;
  }

  return { byId, attr };
}

// Core propagation over a given emitter. Returns ranked entities with drivers.
function propagate(events, edges, emit, now) {
  const { byId, attr } = diffuse(events, edges, now);

  // entity(canonical) -> { display, parts: Map<sourceEventId, signedAmount> }
  const contrib = new Map();
  for (const e of events) {
    const eid = String(e.id);
    const effAttr = attr.get(eid);
    for (const { target, w, sign } of emit(e)) {
      const key = canonicalize(target);
      if (!key) continue;
      const slot = contrib.get(key) || { display: target, parts: new Map() };
      for (const [src, amt] of effAttr) {
        slot.parts.set(src, (slot.parts.get(src) || 0) + sign * w * amt);
      }
      contrib.set(key, slot);
    }
  }

  const titleOf = (id) => byId.get(id)?.canonical_title || byId.get(id)?.title || id;
  const out = [];
  for (const [key, slot] of contrib) {
    let pos = 0, neg = 0;
    for (const amt of slot.parts.values()) { if (amt > 0) pos += amt; else neg += -amt; }
    const net = pos - neg;
    const score = Math.round(100 * (1 - Math.exp(-Math.max(net, 0) / CPE.K)));

    const sorted = [...slot.parts.entries()].sort((a, b) => (b[1] - a[1]) || String(a[0]).localeCompare(String(b[0])));
    const drivers = sorted.filter(([, amt]) => amt > 0).slice(0, 3).map(([id, amt]) => ({
      id, title: titleOf(id), category: byId.get(id)?.category, pct: pos ? Math.round((100 * amt) / pos) : 0,
    }));
    const mitigators = sorted.filter(([, amt]) => amt < 0).sort((a, b) => a[1] - b[1]).slice(0, 2).map(([id, amt]) => ({
      id, title: titleOf(id), category: byId.get(id)?.category, pct: neg ? Math.round((100 * -amt) / neg) : 0,
    }));

    out.push({ name: slot.display, key, score, net, raw: pos, drivers, mitigators });
  }

  // Per-event drive: total exposure this event projects across all entities.
  const eventDrive = new Map();
  for (const slot of contrib.values()) {
    for (const [src, amt] of slot.parts) eventDrive.set(src, (eventDrive.get(src) || 0) + Math.abs(amt));
  }

  return { ranked: out.sort((a, b) => (b.score - a.score) || a.key.localeCompare(b.key)), eventDrive };
}

/**
 * Compute the full exposure model from the live event graph.
 * @param {Array} events  events with importance + consequence_map + geography
 * @param {Array} edges   event→event causal connections (optionally `directed`)
 * @param {{now?: number, trafficByEvent?: Object}} [opts]  fixed clock + live traffic disruption
 * @returns {{sectors, regions, pressure, eventScores, meta}}
 */
export function computeExposureModel(events = [], edges = [], opts = {}) {
  const now = opts.now ?? Date.now();
  const tbe = opts.trafficByEvent;
  const s = propagate(events, edges, (e) => sectorEmissions(e, tbe), now);
  const r = propagate(events, edges, regionEmissions, now);
  const sectors = s.ranked, regions = r.ranked;

  // Per-event exposure heat (0–100): how much consequence each event drives.
  const drive = new Map();
  for (const m of [s.eventDrive, r.eventDrive]) for (const [id, v] of m) drive.set(id, (drive.get(id) || 0) + v);
  const eventScores = {};
  for (const [id, v] of drive) eventScores[id] = Math.round(100 * (1 - Math.exp(-v / CPE.K_EVENT)));

  const top = sectors.slice(0, 5);
  const pressure = top.length ? Math.round(top.reduce((acc, x) => acc + x.score, 0) / top.length) : 0;
  return {
    sectors,
    regions,
    eventScores,
    pressure,
    meta: {
      events: events.length,
      links: (edges || []).length,
      version: CPE.VERSION,
      params: { LAMBDA: CPE.LAMBDA, K: CPE.K, INDIRECT_FACTOR: CPE.INDIRECT_FACTOR, TAU_HOURS: CPE.TAU_HOURS, KAPPA: CPE.KAPPA, DELTA: CPE.DELTA },
    },
  };
}
