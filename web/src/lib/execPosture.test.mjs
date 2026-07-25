// Pure test for execPosture (no network, no React). Run:
//   node web/src/lib/execPosture.test.mjs
import {
  exposure, delta, decisionQueue, suppression, travelPosture, forward, snapshot,
  VERDICTS, MIN_SOURCES,
} from "./execPosture.js";
import { officeContext } from "./officeContext.js";
import { haversineKm as _havKm } from "./geoAssoc.js";

const haversineKm = (lat1, lng1, lat2, lng2) => _havKm(lng1, lat1, lng2, lat2);

let passed = 0, failed = 0;
const ok = (n, c) => { if (c) { passed++; console.log(`  ok  ${n}`); } else { failed++; console.error(`  XX  ${n}`); } };

const TODAY = new Date("2026-07-25T09:00:00Z");
const office = (id, headcount, extra = {}) => ({
  id, name: id, city: id, country: "India", lat: 17.45, lng: 78.35, headcount, ...extra,
});
const HYD = office("site-alpha", 12000);
const PNQ = office("site-bravo", 8000, { lat: 18.59, lng: 73.74 });

// Event at the office, in the API shape officeContext actually consumes.
const at = (o, over = {}) => ({
  id: `e-${Math.random().toString(36).slice(2, 8)}`,
  geo_centroid_lat: o.lat, geo_centroid_lng: o.lng,
  global_importance_score: 85, canonical_title: "Signal", category: "conflict",
  source_count: 3, ...over,
});

// ── exposure: counts PEOPLE, not sites ───────────────────────────────────────
const cAlert = officeContext(HYD, { events: [at(HYD)], appetite: 50, today: TODAY });
const cClear = officeContext(PNQ, { events: [], appetite: 50, today: TODAY });
const exp = exposure([cAlert, cClear]);
ok("exposure counts sites", exp.sites === 2);
ok("exposure totals headcount across all sites", exp.people === 20000);
ok("exposure attributes people to the alerting site", exp.peopleAlert === 12000);
ok("a quiet site contributes zero exposed people", exp.peopleExposed === 12000);
ok("exposure counts distinct countries", exp.countries === 1);
ok("empty input is safe", exposure([]).people === 0);

// ── delta: direction + the layer that drove it ───────────────────────────────
const prior = snapshot([officeContext(HYD, { events: [], appetite: 50, today: TODAY }), cClear]);
const d = delta([cAlert, cClear], prior);
ok("delta detects deterioration", d.deteriorated.length === 1);
ok("delta names the deteriorating site", d.deteriorated[0].office.id === "site-alpha");
ok("delta explains itself with a driving layer", d.deteriorated[0].drivers.some((x) => x.layer === "geopolitics"));
ok("delta carries people at stake", d.deteriorated[0].people === 12000);
ok("unchanged sites are counted, not listed", d.unchanged === 1);
const dImproved = delta([officeContext(HYD, { events: [], appetite: 50, today: TODAY })], snapshot([cAlert]));
ok("delta detects improvement in the other direction", dImproved.improved.length === 1 && dImproved.net === -1);
ok("no prior snapshot ⇒ no fabricated delta", delta([cAlert], {}).deteriorated.length === 0);

// ── decision queue: every bar is enforced ────────────────────────────────────
const q = decisionQueue([cAlert, cClear], null, { appetite: 50, limit: 3 });
ok("corroborated high signal reaches the executive", q.items.length === 1);
ok("queue item carries the people at stake", q.items[0].people === 12000);
ok("queue item carries its source count", q.items[0].sources === 3);

// Grouped by SITUATION, not by building. One event hitting many campuses is one
// executive decision — emitting a row per site is the item-spam we exist to kill.
const shared = at(HYD, { id: "shared-1" });
const HYD2 = office("site-alpha-2", 5000, { lat: 17.4504, lng: 78.3810 });
const twoSites = [
  officeContext(HYD, { events: [shared], appetite: 50, today: TODAY }),
  officeContext(HYD2, { events: [shared], appetite: 50, today: TODAY }),
];
const grouped = decisionQueue(twoSites, null, { appetite: 50 });
ok("one event across two sites ⇒ ONE decision item", grouped.items.length === 1);
ok("grouped item sums people across affected sites", grouped.items[0].people === 17000);
ok("grouped item counts the sites it covers", grouped.items[0].siteCount === 2);
ok("grouped item lists the largest sites first", grouped.items[0].topSites[0].office.id === "site-alpha");
ok("grouped item reports the nearest approach", grouped.items[0].nearestKm === 0);

const single = officeContext(HYD, { events: [at(HYD, { source_count: 1 })], appetite: 50, today: TODAY });
ok("single-sourced signal is NOT escalated (two-source bar)", decisionQueue([single], null, {}).items.length === 0);
ok("MIN_SOURCES is the documented two-source bar", MIN_SOURCES === 2);

const lowImp = officeContext(HYD, { events: [at(HYD, { global_importance_score: 45 })], appetite: 50, today: TODAY });
ok("below-threshold signal is not escalated", decisionQueue([lowImp], null, {}).items.length === 0);

// THE REBUTTAL: a site coloured only by routine weather/holiday context must never
// produce an executive decision item. This is the incumbent failure we observed —
// a named office graded "High" off a metro weather roundup.
const rainOnly = officeContext(HYD, {
  events: [at(HYD, { category: "storm", global_importance_score: 45, canonical_title: "India Metro City Weather Update" })],
  appetite: 50, today: TODAY,
});
ok("weather-only context does NOT reach the executive", decisionQueue([rainOnly], null, {}).items.length === 0);
ok("...but the site is still honestly coloured, not hidden", rainOnly.worst !== "clear");

// ── suppression: nothing is silently dropped ─────────────────────────────────
const sup = suppression([rainOnly], { appetite: 50 });
ok("the held weather signal is recorded, not discarded", sup.held.length >= 1);
ok("suppression names the site it was held for", sup.held[0].office.id === "site-alpha");
ok("suppression gives a machine-checkable reason", Boolean(sup.held[0].reason && sup.held[0].reasonLabel));
ok("below-threshold weather reads as below_threshold", sup.held.some((h) => h.reason === "below_threshold"));
ok("suppression counts what it considered", sup.considered >= sup.suppressed);

const supSingle = suppression([single], { appetite: 50 });
ok("single-sourced signal is held as uncorroborated", supSingle.held.some((h) => h.reason === "uncorroborated"));
ok("a fully clear site suppresses nothing", suppression([cClear], {}).held.length === 0);

// ── travel posture: verdicts, parity, and reachability ───────────────────────
const DXB = { toLat: 25.2532, toLng: 55.3657 };
const trip = (over = {}) => ({
  id: "t1", traveler: "A. Menon", role: "SVP", from: "Bengaluru", to: "Dubai",
  ...DXB, country: "United Arab Emirates",
  departISO: "2026-07-20", returnISO: "2026-07-30", ...over,
});
const hot = { geo_centroid_lat: 25.26, geo_centroid_lng: 55.37, global_importance_score: 88, canonical_title: "Unrest", source_count: 3, id: "x1" };
const tp = travelPosture([trip()], [hot], { appetite: 50, today: TODAY, haversineKm });
ok("traveller inside the window reads active", tp.rows[0].status === "active");
ok("high signal at destination ⇒ Reconsider", tp.rows[0].verdict.key === "reconsider");
ok("verdict vocabulary matches the analyst deck", VERDICTS.reconsider.label === "Reconsider" && VERDICTS.proceed.label === "Proceed");
ok("in-motion count is aggregated", tp.inMotion === 1);
ok("no check-in in an elevated location ⇒ unaccounted for", tp.unaccounted.length === 1);

const seen = travelPosture([trip({ lastCheckInISO: "2026-07-25T06:00:00Z" })], [hot], { appetite: 50, today: TODAY, haversineKm });
ok("a recent check-in clears the unaccounted flag", seen.unaccounted.length === 0);

const quietDest = travelPosture([trip()], [], { appetite: 50, today: TODAY, haversineKm });
ok("no adverse signal at destination ⇒ Proceed", quietDest.rows[0].verdict.key === "proceed");
ok("Proceed travellers are never unaccounted-for", quietDest.unaccounted.length === 0);

const future = travelPosture([trip({ departISO: "2026-08-10", returnISO: "2026-08-20" })], [hot], { appetite: 50, today: TODAY, haversineKm });
ok("a future trip reads upcoming, not active", future.rows[0].status === "upcoming" && future.upcomingCount === 1);
ok("travelPosture refuses to run without a distance function",
  (() => { try { travelPosture([trip()], [], { today: TODAY }); return false; } catch { return true; } })());

// travellers escalate into the same decision queue as sites
const qt = decisionQueue([cClear], tp, { appetite: 50, limit: 3 });
ok("an at-risk traveller becomes a decision item", qt.items.some((i) => i.kind === "traveller"));

// ── forward posture ──────────────────────────────────────────────────────────
const withFest = officeContext(PNQ, {
  events: [], appetite: 50, today: TODAY,
  festivals: [{ id: "f1", name: "Ganesh Chaturthi", nearAssets: ["site-bravo"], startISO: "2026-09-14", endISO: "2026-09-24", lat: 18.59, lng: 73.74 }],
});
const fwd = forward([withFest], { today: TODAY, windowDays: 60 });
ok("forward surfaces an upcoming festival window", fwd.length === 1);
ok("forward carries the people behind the date", fwd[0].people === 8000);
ok("forward is ordered soonest-first", fwd.every((r, i, a) => i === 0 || a[i - 1].inDays <= r.inDays));
ok("events beyond the window are excluded", forward([withFest], { today: TODAY, windowDays: 7 }).length === 0);

// ── snapshot round-trip ──────────────────────────────────────────────────────
const snap = snapshot([cAlert]);
ok("snapshot records the rolled-up worst", snap["site-alpha"].worst === "alert");
ok("snapshot records every layer for attribution", Object.keys(snap["site-alpha"].layers).length === 8);
ok("snapshot of nothing is an empty baseline", Object.keys(snapshot([])).length === 0);

// ── organisation-scoped cyber ────────────────────────────────────────────────
// Cyber carries no geography, so it must never claim a headcount. Inventing
// "organisation-wide, 703,196 people" would be a bigger overclaim than the 700 km
// proximity bug it replaced.
const cyberEv = { id: "cy-1", category: "cyber", int_discipline: "CYBINT", canonical_title: "Credential-stuffing campaign", geo_centroid_lat: 55, geo_centroid_lng: 12, global_importance_score: 86, source_count: 4, admiralty_grade: "B2" };
const cyCtx = [HYD, PNQ].map((o) => officeContext(o, { events: [cyberEv], appetite: 50, today: TODAY }));
const cyQ = decisionQueue(cyCtx, null, { appetite: 50, limit: 3 });
ok("org-scoped cyber reaches the executive", cyQ.items.length === 1);
ok("org-scoped cyber is emitted ONCE, not once per site", cyQ.total === 1);
ok("org-scoped cyber claims NO headcount", cyQ.items[0].people === null);
ok("org-scoped cyber is flagged as such", cyQ.items[0].orgScope === true && cyQ.items[0].kind === "organisation");
ok("org-scoped cyber claims no sites or distance", cyQ.items[0].siteCount === 0 && cyQ.items[0].nearestKm === null);

// An org-wide compromise outranks a bigger-headcount local incident.
const mixedQ = decisionQueue(
  [officeContext(HYD, { events: [cyberEv, at(HYD)], appetite: 50, today: TODAY }),
   officeContext(PNQ, { events: [cyberEv, at(HYD)], appetite: 50, today: TODAY })],
  null, { appetite: 50, limit: 3 },
);
ok("org-wide cyber leads the queue", mixedQ.items[0].orgScope === true);
ok("the local incident still follows it", mixedQ.items.some((i) => !i.orgScope));

// Single-sourced cyber is held once, with a reason — not 214 duplicate rows.
const weakCyber = { ...cyberEv, id: "cy-2", source_count: 1 };
const weakCtx = [HYD, PNQ].map((o) => officeContext(o, { events: [weakCyber], appetite: 50, today: TODAY }));
ok("single-sourced org cyber does not escalate", decisionQueue(weakCtx, null, {}).items.length === 0);
const cySup = suppression(weakCtx, { appetite: 50 });
const cyHeld = cySup.held.filter((h) => h.layer === "cyber");
ok("held org cyber appears exactly once across all sites", cyHeld.length === 1);
ok("held org cyber is labelled organisation-wide", cyHeld[0].office.name === "Organisation-wide");
ok("held org cyber states why it was held", cyHeld[0].reason === "uncorroborated");

// ── travel uses per-event extent, not a flat 300 km ──────────────────────────
// 0.9° of latitude ≈ 100 km from the destination.
const localFar = { id: "lf", category: "security", canonical_title: "Localised disorder", geo_centroid_lat: 25.2532 + 0.9, geo_centroid_lng: 55.3657, global_importance_score: 90, source_count: 3 };
const tpFar = travelPosture([trip()], [localFar], { appetite: 50, today: TODAY, haversineKm });
ok("localised disorder 100 km from destination ⇒ Proceed", tpFar.rows[0].verdict.key === "proceed");
const stormFar = { ...localFar, id: "sf", category: "storm", canonical_title: "Severe weather" };
const tpStorm = travelPosture([trip()], [stormFar], { appetite: 50, today: TODAY, haversineKm });
ok("a weather front 100 km from destination still counts", tpStorm.rows[0].verdict.key === "reconsider");

console.log(`\nexecPosture: ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
