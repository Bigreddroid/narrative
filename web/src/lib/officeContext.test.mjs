// Pure test for officeContext (no network, no React). Run:
//   node web/src/lib/officeContext.test.mjs
import {
  officeContext, layerOf, deriveTraffic, upcomingHolidays, DISRUPTION_K,
} from "./officeContext.js";

let passed = 0, failed = 0;
const ok = (n, c) => { if (c) { passed++; console.log(`  ok  ${n}`); } else { failed++; console.error(`  XX  ${n}`); } };

const OFFICE = { id: "mum-powai", name: "Mumbai", country: "India", lat: 19.1187, lng: 72.9050, headcount: 3400 };
const near = (dLat = 0, dLng = 0, extra = {}) => ({
  geo_centroid_lat: OFFICE.lat + dLat, geo_centroid_lng: OFFICE.lng + dLng,
  global_importance_score: 80, canonical_title: "T", ...extra,
});

// ── layerOf classification ────────────────────────────────────────────────────
ok("cyber category ⇒ cyber", layerOf({ category: "cyber" }) === "cyber");
ok("CYBINT discipline ⇒ cyber", layerOf({ int_discipline: "CYBINT" }) === "cyber");
ok("economics ⇒ market", layerOf({ category: "economics" }) === "market");
ok("FININT ⇒ market", layerOf({ int_discipline: "FININT" }) === "market");
ok("storm ⇒ weather", layerOf({ category: "storm" }) === "weather");
ok("climate ⇒ hazards bucket", layerOf({ category: "climate" }) === "hazard");
ok("conflict ⇒ geopolitics", layerOf({ category: "conflict" }) === "geopolitics");
ok("unknown geolocated ⇒ geopolitics (never vanishes)", layerOf({ category: "wat" }) === "geopolitics");

// ── proximity + appetite thresholds ───────────────────────────────────────────
const ctx = { events: [near(0, 0, { category: "conflict", global_importance_score: 85 })], appetite: 50 };
ok("nearby high-importance conflict ⇒ geopolitics alert", officeContext(OFFICE, ctx).layers.geopolitics.level === "alert");

const far = { events: [near(20, 20, { category: "conflict", global_importance_score: 95 })], appetite: 50 };
ok("event outside radius ⇒ geopolitics clear", officeContext(OFFICE, far).layers.geopolitics.level === "clear");

const midImp = { events: [near(0, 0, { category: "conflict", global_importance_score: 50 })], appetite: 50 };
ok("mid importance ⇒ watch (not alert)", officeContext(OFFICE, midImp).layers.geopolitics.level === "watch");

// higher appetite calms the same signal a notch
const calm = { events: [near(0, 0, { category: "conflict", global_importance_score: 85 })], appetite: 100 };
ok("higher risk appetite reads the same signal calmer", officeContext(OFFICE, calm).layers.geopolitics.level === "watch");

// ── quiet office is honest 'clear', never blank ───────────────────────────────
const quiet = officeContext(OFFICE, { events: [], appetite: 50 });
ok("no signals ⇒ every incident layer clear", ["geopolitics", "cyber", "market", "hazards", "weather"].every((k) => quiet.layers[k].level === "clear"));
ok("no context ⇒ worst is clear", quiet.worst === "clear");
ok("clear office still returns all 8 layers", Object.keys(quiet.layers).length === 8);

// ── holidays window ───────────────────────────────────────────────────────────
const TODAY = new Date("2026-08-14T00:00:00Z");
const hraw = [
  { date: "2026-08-15", name: "Independence Day" },  // +1
  { date: "2026-08-10", name: "Past" },              // excluded
  { date: "2026-12-25", name: "Far" },               // beyond window
];
const up = upcomingHolidays(hraw, TODAY, 60);
ok("upcoming keeps in-window, drops past + far", up.length === 1 && up[0].name === "Independence Day");
ok("stamps in_days for curated", up[0].in_days === 1);
ok("keeps backend-supplied in_days", upcomingHolidays([{ date: "2026-08-20", name: "L", in_days: 6 }], TODAY, 60)[0].in_days === 6);

// ── derived traffic (the slice-6 core) ────────────────────────────────────────
const flat = deriveTraffic({ festivals: [], holidays: [], weatherBest: null, incidentBest: null }, 1);
ok("no stressors ⇒ traffic clear, 0%", flat.level === "clear" && flat.pct === 0);

const jam = deriveTraffic({
  festivals: [{ name: "Ganesh visarjan", active: true }],
  holidays: [{ name: "Holiday", in_days: 0 }],
  weatherBest: { imp: 80, event: { id: "w1" } },
  incidentBest: { imp: 90, event: { id: "i1", canonical_title: "Protest" } },
}, 1);
ok("stacked stressors ⇒ traffic alert", jam.level === "alert");
ok("traffic % is bounded by the ceiling", jam.pct <= 100 * DISRUPTION_K);
ok("traffic explains itself (drivers listed)", jam.drivers.length === 4);
ok("festival driver present", jam.drivers.some((d) => d.kind === "festival"));

const soonOnly = deriveTraffic({ festivals: [{ name: "F", soon: true, startsIn: 5 }], holidays: [], weatherBest: null, incidentBest: null }, 1);
ok("only a distant festival ⇒ at most a watch", soonOnly.level !== "alert");

// ── festival wiring end-to-end through officeContext ──────────────────────────
const withFest = officeContext(OFFICE, {
  events: [], appetite: 50, today: new Date("2026-09-16T00:00:00Z"),
  festivals: [{ id: "f", name: "Ganesh Chaturthi", nearAssets: ["mum-powai"], startISO: "2026-09-14", endISO: "2026-09-24", lat: 19.07, lng: 72.87 }],
});
ok("active festival ⇒ festival layer alert", withFest.layers.festivals.level === "alert");
ok("active festival raises derived traffic off clear", withFest.layers.traffic.level !== "clear");
ok("worst rolls up to the festival alert", withFest.worst === "alert");

console.log(`\nofficeContext: ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
