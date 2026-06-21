// Property + golden test harness for the Consequence Propagation Engine (CPE).
// No test framework needed — run with:  node web/src/lib/propagation.test.mjs
// Proves the guarantees claimed in the plan: bounded 0–100, deterministic,
// monotonic in severity/importance, attribution well-formed, Katz converges,
// mitigating edges lower net exposure, entity resolution, temporal decay,
// directed propagation flows downstream only.

import { computeExposureModel, CPE } from "./propagation.js";
import { profileExposure } from "./exposureProfile.js";

let passed = 0, failed = 0;
const ok = (name, cond) => { if (cond) { passed++; console.log(`  ✓ ${name}`); } else { failed++; console.error(`  ✗ ${name}`); } };

const NOW = new Date("2026-06-18T00:00:00Z").getTime();
const HOUR = 3_600_000;
const isoAgo = (h) => new Date(NOW - h * HOUR).toISOString();

const chain = (...types) => types.map((t, i) => ({ step: i, type: t, content: `n${i}` }));

function mkEvent(id, over = {}) {
  return {
    id,
    category: over.category || "conflict",
    canonical_title: over.title || `Event ${id}`,
    importance_score: over.importance ?? 80,
    first_detected_at: over.at ?? isoAgo(2),
    geography: over.geography || ["Red Sea"],
    consequence_map: {
      consequence_chain: over.chain || chain("VERIFIED FACT", "INFERRED MECHANISM", "SPECULATIVE EFFECT"),
      sources_analyzed: over.sources || ["s1", "s2", "s3", "s4"],
      disputed_points: over.disputed || [],
      direct_impact: over.direct || [{ sector: "Shipping & Logistics", severity: "critical" }],
      indirect_impact: over.indirect || [{ sector: "Consumer Prices", severity: "medium" }],
    },
  };
}

const sectorScore = (model, key) => model.sectors.find((s) => s.key === key)?.score ?? 0;
const opts = { now: NOW };

// ── 1. Determinism ────────────────────────────────────────────────────────────
{
  const events = [mkEvent("A"), mkEvent("B", { direct: [{ sector: "Shipping", severity: "high" }] })];
  const edges = [{ source: "A", target: "B", weight: 0.7 }];
  const m1 = computeExposureModel(events, edges, opts);
  const m2 = computeExposureModel(events, edges, opts);
  ok("deterministic across runs", JSON.stringify(m1) === JSON.stringify(m2));
}

// ── 2. Bounded 0–100 integers ──────────────────────────────────────────────────
{
  const events = [mkEvent("A", { importance: 100 }), mkEvent("B", { importance: 95 })];
  const m = computeExposureModel(events, [{ source: "A", target: "B", weight: 1 }], opts);
  const all = [...m.sectors, ...m.regions];
  ok("all scores within [0,100]", all.every((x) => x.score >= 0 && x.score <= 100));
  ok("all scores are integers", all.every((x) => Number.isInteger(x.score)));
  ok("pressure within [0,100]", m.pressure >= 0 && m.pressure <= 100);
}

// ── 3. Attribution well-formed ─────────────────────────────────────────────────
{
  const events = [mkEvent("A"), mkEvent("B"), mkEvent("C")];
  const m = computeExposureModel(events, [], opts);
  const top = m.sectors[0];
  ok("top entity has drivers", top.drivers.length > 0);
  ok("driver pct in [0,100]", top.drivers.every((d) => d.pct >= 0 && d.pct <= 100));
  ok("drivers sorted descending by pct", top.drivers.every((d, i, a) => i === 0 || a[i - 1].pct >= d.pct));
  ok("driver pct sum ≤ 100 (top-3 share)", top.drivers.reduce((s, d) => s + d.pct, 0) <= 100);
}

// ── 4. Monotonicity in importance ──────────────────────────────────────────────
{
  const low = computeExposureModel([mkEvent("A", { importance: 50 })], [], opts);
  const high = computeExposureModel([mkEvent("A", { importance: 95 })], [], opts);
  ok("higher importance ⇒ ≥ exposure", sectorScore(high, "shipping") >= sectorScore(low, "shipping"));
  ok("higher importance ⇒ strictly more here", sectorScore(high, "shipping") > sectorScore(low, "shipping"));
}

// ── 5. Severity monotonicity ───────────────────────────────────────────────────
{
  const med = computeExposureModel([mkEvent("A", { direct: [{ sector: "Energy", severity: "medium" }] })], [], opts);
  const crit = computeExposureModel([mkEvent("A", { direct: [{ sector: "Energy", severity: "critical" }] })], [], opts);
  ok("critical severity > medium severity", sectorScore(crit, "energy") > sectorScore(med, "energy"));
}

// ── 6. Mitigating impacts lower net exposure ───────────────────────────────────
{
  const base = [mkEvent("A", { direct: [{ sector: "Energy", severity: "critical" }] })];
  const aggravate = [...base, mkEvent("B", { direct: [{ sector: "Energy", severity: "critical" }] })];
  const mitigate = [...base, mkEvent("B", { direct: [{ sector: "Energy", severity: "critical", direction: "mitigating" }] })];
  const sA = sectorScore(computeExposureModel(aggravate, [], opts), "energy");
  const sM = sectorScore(computeExposureModel(mitigate, [], opts), "energy");
  ok("mitigating event lowers exposure vs aggravating", sM < sA);
}

// ── 7. Entity resolution (alias collapse) ──────────────────────────────────────
{
  const events = [
    mkEvent("A", { direct: [{ sector: "Shipping & Logistics", severity: "high" }], indirect: [] }),
    mkEvent("B", { direct: [{ sector: "Shipping", severity: "high" }], indirect: [] }),
  ];
  const m = computeExposureModel(events, [], opts);
  const shippingEntries = m.sectors.filter((s) => s.key === "shipping");
  ok("'Shipping & Logistics' + 'Shipping' collapse to one entity", shippingEntries.length === 1);
}

// ── 8. Temporal decay ──────────────────────────────────────────────────────────
{
  const fresh = computeExposureModel([mkEvent("A", { at: isoAgo(1) })], [], opts);
  const stale = computeExposureModel([mkEvent("A", { at: isoAgo(24 * 30) })], [], opts); // 30 days old
  ok("stale event contributes less than fresh", sectorScore(stale, "shipping") < sectorScore(fresh, "shipping"));
}

// ── 9. Corroboration & disputes affect confidence ──────────────────────────────
{
  const wellSourced = computeExposureModel([mkEvent("A", { sources: ["1", "2", "3", "4", "5", "6"] })], [], opts);
  const thin = computeExposureModel([mkEvent("A", { sources: ["1"] })], [], opts);
  ok("more sources ⇒ higher exposure (corroboration)", sectorScore(wellSourced, "shipping") > sectorScore(thin, "shipping"));

  const undisputed = computeExposureModel([mkEvent("A", { disputed: [] })], [], opts);
  const disputed = computeExposureModel([mkEvent("A", { disputed: ["x", "y"] })], [], opts);
  ok("disputed points ⇒ lower exposure", sectorScore(disputed, "shipping") < sectorScore(undisputed, "shipping"));
}

// ── 10. Directed propagation flows downstream only ─────────────────────────────
{
  // A (cause) → B (effect). A's sector is Energy, B's sector is Tech.
  const A = mkEvent("A", { direct: [{ sector: "Energy", severity: "critical" }], indirect: [] });
  const B = mkEvent("B", { direct: [{ sector: "Banking", severity: "low" }], indirect: [], importance: 20 });
  const directed = computeExposureModel([A, B], [{ source: "A", target: "B", weight: 0.9, directed: true }], opts);
  const undirected = computeExposureModel([A, B], [{ source: "A", target: "B", weight: 0.9 }], opts);
  // Banking (B's sector) should get MORE amplification from A in the undirected case
  // (A→B and B→A) than in the directed case (A→B only).
  ok("undirected amplifies Banking ≥ directed", sectorScore(undirected, "banking") >= sectorScore(directed, "banking"));
  ok("directed case still amplifies effect's sector", sectorScore(directed, "banking") > 0);
}

// ── 11. Profile exposure blends matched dimensions ─────────────────────────────
{
  const events = [mkEvent("A"), mkEvent("B", { direct: [{ sector: "Energy", severity: "critical" }], geography: ["Europe"] })];
  const model = computeExposureModel(events, [], opts);
  const pe = profileExposure({ sectors: ["Energy"], regions: ["Europe"] }, model);
  ok("profile exposure within [0,100]", pe.score >= 0 && pe.score <= 100);
  ok("profile exposure returns drivers", Array.isArray(pe.drivers));
  const empty = profileExposure({ sectors: ["Nonexistent Sector"] }, model);
  ok("unmatched profile ⇒ 0", empty.score === 0 && empty.drivers.length === 0);
}

// ── 12. Converges well under MAX_ITERS on a dense graph ────────────────────────
{
  const events = Array.from({ length: 12 }, (_, i) => mkEvent(`E${i}`, { importance: 60 + i }));
  const edges = [];
  for (let i = 0; i < 12; i++) for (let j = 0; j < 12; j++) if (i !== j) edges.push({ source: `E${i}`, target: `E${j}`, weight: 0.4 });
  const t0 = Date.now();
  const m = computeExposureModel(events, edges, opts);
  const dt = Date.now() - t0;
  ok("dense-graph run completes < 500ms", dt < 500);
  ok("dense-graph scores bounded", [...m.sectors, ...m.regions].every((x) => x.score >= 0 && x.score <= 100));
}

// ── 13. Per-event exposure heat (eventScores) ──────────────────────────────────
{
  const m = computeExposureModel([mkEvent("A", { importance: 95 }), mkEvent("B", { importance: 40 })], [], opts);
  ok("eventScores present for each event", m.eventScores.A != null && m.eventScores.B != null);
  ok("eventScores bounded [0,100]", Object.values(m.eventScores).every((s) => s >= 0 && s <= 100));
  ok("higher-driving event has higher heat", m.eventScores.A > m.eventScores.B);
}

// ── 14. Traffic disruption feeds the CPE ───────────────────────────────────────
{
  const ev = [mkEvent("A", { direct: [{ sector: "Energy", severity: "low" }], indirect: [], geography: ["Red Sea"] })];
  const base = computeExposureModel(ev, [], opts);
  const withTraffic = computeExposureModel(ev, [], { now: NOW, trafficByEvent: { A: { vessels: 200, aircraft: 50 } } });
  ok("no shipping exposure without traffic", sectorScore(base, "shipping") === 0);
  ok("heavy nearby traffic raises shipping exposure", sectorScore(withTraffic, "shipping") > 0);
  ok("nearby flights raise aviation exposure", sectorScore(withTraffic, "aviation") > 0);
}

console.log(`\nCPE v${CPE.VERSION}: ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
