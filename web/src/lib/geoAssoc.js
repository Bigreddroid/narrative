// ─────────────────────────────────────────────────────────────────────────────
//  Geo-association — ties live ship/plane traffic to consequence events.
//  Pure (no React/DOM), so it is unit-testable in isolation.
//
//  Each traffic item is assigned to its nearest event within that event's impact
//  radius; events get traffic counts; deviation from a learned baseline flags an
//  anomaly (rerouting / surge). Powers: zone highlight, exposure tint, affected
//  counts, traffic→CPE disruption, and anomaly signals.
// ─────────────────────────────────────────────────────────────────────────────

const R = 6371; // km
const toRad = (d) => (d * Math.PI) / 180;
const round1 = (x) => Math.round(x * 10) / 10;

export function haversineKm(aLng, aLat, bLng, bLat) {
  const dLat = toRad(bLat - aLat);
  const dLng = toRad(bLng - aLng);
  const s = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(aLat)) * Math.cos(toRad(bLat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(s)));
}

const importanceOf = (e) => e.importance ?? e.importance_score ?? e.global_importance_score ?? 50;

// Impact radius scales with event importance (300–1200 km).
export function eventRadiusKm(event) {
  return Math.max(300, Math.min(1200, 300 + importanceOf(event) * 9));
}

// Assign each traffic item to its nearest in-radius event.
//   events: [{ id, lat, lng, importance? }]
//   items:  [{ id, lat, lng, kind: "vessel" | "aircraft" }]
// → { zonesByEvent: Map(eventId → {vessels, aircraft, items}), nearestByItem: Map(id → {eventId, distKm}) }
export function associate(events, items) {
  const evs = (events || [])
    .filter((e) => e.lat != null && e.lng != null)
    .map((e) => ({ e, r: eventRadiusKm(e) }));
  const zonesByEvent = new Map();
  const nearestByItem = new Map();

  for (const it of items || []) {
    if (it.lat == null || it.lng == null) continue;
    let best = null, bestD = Infinity;
    for (const { e, r } of evs) {
      const d = haversineKm(it.lng, it.lat, e.lng, e.lat);
      if (d <= r && d < bestD) { bestD = d; best = e; }
    }
    if (!best) continue;
    const eid = String(best.id);
    nearestByItem.set(it.id, { eventId: eid, distKm: Math.round(bestD) });
    let z = zonesByEvent.get(eid);
    if (!z) { z = { vessels: 0, aircraft: 0, items: [] }; zonesByEvent.set(eid, z); }
    z.items.push(it);
    if (it.kind === "aircraft") z.aircraft++; else z.vessels++;
  }
  return { zonesByEvent, nearestByItem };
}

// Compact { eventId: {vessels, aircraft} } map for feeding the CPE (traffic disruption).
export function trafficByEvent(zonesByEvent) {
  const out = {};
  for (const [id, z] of zonesByEvent) out[id] = { vessels: z.vessels, aircraft: z.aircraft };
  return out;
}

// Flag a zone whose traffic count deviates from its baseline {mean, std}.
// Negative deviation ⇒ rerouting (traffic avoiding the area); positive ⇒ surge.
export function detectAnomaly(count, baseline) {
  if (!baseline || baseline.mean == null) return null;
  const std = Math.max(1, baseline.std ?? baseline.mean * 0.3);
  const z = (count - baseline.mean) / std;
  if (z <= -1) return { type: "rerouting", z: round1(z), count, baseline: Math.round(baseline.mean) };
  if (z >= 1.5) return { type: "surge", z: round1(z), count, baseline: Math.round(baseline.mean) };
  return null;
}
