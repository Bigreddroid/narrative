// Pure test for officeContext (no network, no React). Run:
//   node web/src/lib/officeContext.test.mjs
import {
  officeContext, layerOf, deriveTraffic, upcomingHolidays, DISRUPTION_K,
  extentKm, EXTENT_KM, EXTENT_DEFAULT, topSignal,
  attenuate, ATTENUATION_FLOOR, ATTENUATION_FALLOFF,
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

// ── per-event spatial extent ──────────────────────────────────────────────────
// One radius per LAYER made a CBD protest "reach" offices 290 km away. Extent is now
// a property of the event, so a local disorder signal stays local.
ok("localised disorder extent is tight", extentKm({ category: "security" }) === 25);
ok("armed conflict reaches further than disorder", extentKm({ category: "conflict" }) > extentKm({ category: "security" }));
ok("weather fronts stay wide", extentKm({ category: "storm" }) === 150);
ok("economic effects radiate furthest", extentKm({ category: "economics" }) >= EXTENT_KM.climate);
ok("unknown category falls back to the default", extentKm({ category: "wat" }) === EXTENT_DEFAULT);
ok("an explicit impact_radius_km from the API wins", extentKm({ category: "security", impact_radius_km: 400 }) === 400);
ok("a nonsense impact_radius_km is ignored", extentKm({ category: "security", impact_radius_km: -5 }) === 25);

// 0.9° of latitude ≈ 100 km — inside a conflict's 50 km extent? No. Inside a storm's 150? Yes.
const at100km = (extra) => ({ geo_centroid_lat: OFFICE.lat + 0.9, geo_centroid_lng: OFFICE.lng, global_importance_score: 90, canonical_title: "T", ...extra });
const farConflict = officeContext(OFFICE, { events: [at100km({ category: "security" })], appetite: 50 });
ok("a localised incident 100 km away no longer touches the site", farConflict.layers.geopolitics.level === "clear");
// Before proximity attenuation this asserted `level === "alert"`, using alert as a
// proxy for "reaches". Attenuation separates those two ideas: the storm is still IN
// RANGE (150 km extent) and still scored, but at 100 km — two-thirds of its reach —
// it no longer carries full alert weight. Asserting "not clear" is the honest form of
// the original intent; the pair below proves distance is what moved it.
const nearStorm = officeContext(OFFICE, { events: [at100km({ category: "storm" })], appetite: 50 });
ok("a weather front 100 km away still reaches the site", nearStorm.layers.weather.level !== "clear");
ok("...but is no longer at full alert strength that far out", nearStorm.layers.weather.level === "watch");
const overheadStorm = officeContext(OFFICE, { events: [near(0, 0, { category: "storm", global_importance_score: 90 })], appetite: 50 });
ok("the same storm overhead IS an alert", overheadStorm.layers.weather.level === "alert");
ok("distance is what separates them", overheadStorm.layers.weather.imp > nearStorm.layers.weather.imp);

// ── cyber is organisation-scoped, not proximity-scored ────────────────────────
const cyberFar = { geo_centroid_lat: OFFICE.lat + 40, geo_centroid_lng: OFFICE.lng + 40, global_importance_score: 88, canonical_title: "Campaign", category: "cyber", id: "c1" };
const cy = officeContext(OFFICE, { events: [cyberFar], appetite: 50 });
ok("cyber is scored regardless of distance", cy.layers.cyber.level === "alert");
ok("cyber declares organisation scope", cy.layers.cyber.scope === "organisation");
ok("cyber carries no distance to fake", cy.layers.cyber.best.km === null);
ok("cyber still respects risk appetite", officeContext(OFFICE, { events: [cyberFar], appetite: 100 }).layers.cyber.level === "watch");
ok("no cyber signal ⇒ honest clear, still org-scoped",
  officeContext(OFFICE, { events: [], appetite: 50 }).layers.cyber.scope === "organisation");
// topSignal drives the map line from a building to an event — cyber must never draw one.
ok("topSignal ignores org-scoped cyber", topSignal(cy) === null);
// Org-scoped cyber must NOT roll into a site's status: letting it would mark all 214
// sites "alert" for a campaign not attributable to any one of them — swapping a
// geographic overclaim for a blanket one. It stays visible in `layers`.
ok("org-scoped cyber does NOT drive the site's worst", cy.worst === "clear");
ok("...but is still carried for display", cy.layers.cyber.level === "alert");
ok("a site-local signal does still drive worst",
  officeContext(OFFICE, { events: [cyberFar, near(0, 0, { category: "conflict", global_importance_score: 85 })], appetite: 50 }).worst === "alert");

// ── Proximity attenuation ─────────────────────────────────────────────────────
// The scoring change in Phase 4. Being inside an extent used to be binary, so a site
// at 24 km of a 25 km protest scored identically to one at 1 km.
const approx = (a, b, eps = 1e-9) => Math.abs(a - b) < eps;

ok("at the epicentre importance is untouched", approx(attenuate(90, 0, 25), 90));
ok("at the extent boundary it decays to the floor, NOT to zero",
  approx(attenuate(90, 25, 25), 90 * ATTENUATION_FLOOR));
ok("the boundary residue is deliberately non-zero", attenuate(90, 25, 25) > 0);
ok("attenuation is monotonic with distance",
  attenuate(90, 1, 25) > attenuate(90, 12, 25) && attenuate(90, 12, 25) > attenuate(90, 24, 25));
ok("beyond the extent it clamps at the floor rather than going negative",
  approx(attenuate(90, 999, 25), 90 * ATTENUATION_FLOOR));
ok("falloff keeps the near field strong (>75% within the first 10% of reach)",
  attenuate(100, 2.5, 25) > 75);
ok("a 0 importance event stays 0 at every distance",
  attenuate(0, 0, 25) === 0 && attenuate(0, 25, 25) === 0);

// Degenerate inputs must carry importance through unchanged, never invent a discount.
ok("no extent ⇒ unchanged", attenuate(90, 10, 0) === 90);
ok("negative extent ⇒ unchanged", attenuate(90, 10, -5) === 90);
ok("non-numeric distance ⇒ unchanged", attenuate(90, null, 25) === 90);
ok("undefined distance ⇒ unchanged", attenuate(90, undefined, 25) === 90);
ok("FALLOFF > 1 so decay is not linear", ATTENUATION_FALLOFF > 1);
ok("a linear model would differ at the midpoint",
  !approx(attenuate(100, 12.5, 25), 100 * (ATTENUATION_FLOOR + (1 - ATTENUATION_FLOOR) * 0.5)));

// THE POINT OF THE WHOLE CHANGE: distance inside the extent must move the score.
{
  // ~0.09° lat ≈ 10 km; unrest extent is 25 km so both are genuinely in range.
  const close = officeContext(OFFICE, { events: [near(0, 0, { category: "unrest", global_importance_score: 90 })], appetite: 50 });
  const far = officeContext(OFFICE, { events: [near(0.18, 0, { category: "unrest", global_importance_score: 90 })], appetite: 50 });
  ok("same event, different distance ⇒ different score",
    close.layers.geopolitics.imp !== far.layers.geopolitics.imp);
  ok("the nearer site scores higher", close.layers.geopolitics.imp > far.layers.geopolitics.imp);
}
{
  // A nearby moderate event should now outrank a severe one at the edge of its reach.
  const nearModerate = near(0, 0, { category: "unrest", global_importance_score: 60, canonical_title: "NEAR" });
  const farSevere = near(0.20, 0, { category: "unrest", global_importance_score: 95, canonical_title: "FAR" });
  const c = officeContext(OFFICE, { events: [farSevere, nearModerate], appetite: 50 });
  ok("ranking uses attenuated importance, so the nearby event wins",
    c.layers.geopolitics.best?.event.canonical_title === "NEAR");
  ok("the raw score is retained for display", c.layers.geopolitics.best?.raw === 60);
}

console.log(`\nofficeContext: ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
