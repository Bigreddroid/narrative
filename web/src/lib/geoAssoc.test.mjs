// Property test for geoAssoc (pure). Run:  node web/src/lib/geoAssoc.test.mjs
import { haversineKm, eventRadiusKm, associate, trafficByEvent, detectAnomaly } from "./geoAssoc.js";

let passed = 0, failed = 0;
const ok = (n, c) => { if (c) { passed++; console.log(`  ✓ ${n}`); } else { failed++; console.error(`  ✗ ${n}`); } };

// haversine
ok("same point ⇒ 0 km", haversineKm(0, 0, 0, 0) === 0);
ok("NYC→London ≈ 5570 km", Math.abs(haversineKm(-74, 40.7, -0.1, 51.5) - 5570) < 100);

// radius scales with importance, clamped
ok("low importance ⇒ floor 300", eventRadiusKm({ importance: 0 }) === 300);
ok("high importance ⇒ cap 1200", eventRadiusKm({ importance: 100 }) === 1200);
ok("mid importance between", eventRadiusKm({ importance: 50 }) > 300 && eventRadiusKm({ importance: 50 }) < 1200);

// associate
const events = [{ id: "A", lat: 14.5, lng: 42.8, importance: 91 }, { id: "B", lat: 35, lng: 139, importance: 80 }];
const items = [
  { id: "v1", lat: 13.0, lng: 43.0, kind: "vessel" },   // near A (Red Sea)
  { id: "a1", lat: 34.5, lng: 139.5, kind: "aircraft" },// near B (Tokyo)
  { id: "v2", lat: -40, lng: -100, kind: "vessel" },    // middle of nowhere
];
const { zonesByEvent, nearestByItem } = associate(events, items);
ok("near item assigned to its event", nearestByItem.get("v1")?.eventId === "A");
ok("aircraft assigned to nearest event", nearestByItem.get("a1")?.eventId === "B");
ok("far item unassigned", !nearestByItem.has("v2"));
ok("zone counts by kind", zonesByEvent.get("A").vessels === 1 && zonesByEvent.get("B").aircraft === 1);
ok("distance recorded", nearestByItem.get("v1").distKm >= 0);

// trafficByEvent shape
const tbe = trafficByEvent(zonesByEvent);
ok("trafficByEvent maps counts", tbe.A.vessels === 1 && tbe.B.aircraft === 1);

// anomaly detection
ok("below baseline ⇒ rerouting", detectAnomaly(2, { mean: 10, std: 3 })?.type === "rerouting");
ok("above baseline ⇒ surge", detectAnomaly(20, { mean: 10, std: 3 })?.type === "surge");
ok("near baseline ⇒ none", detectAnomaly(10, { mean: 10, std: 3 }) === null);
ok("no baseline ⇒ none", detectAnomaly(5, null) === null);

console.log(`\ngeoAssoc: ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
