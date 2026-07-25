// Pure test for severity (no network, no React). Run:
//   node web/src/lib/severity.test.mjs
import {
  SEVERITY, SEVERITY_BY_KEY, BANDS, bandFor, scoreFrom, levelOfBand,
  ALERT_TYPES, alertTypeOf, validityOf, validityDays, isExpired, activeOnly,
  twoLevelRisk, assetsAffected, classify, VALIDITY_DAYS,
} from "./severity.js";
import { EXTENT_KM } from "./officeContext.js";

let passed = 0, failed = 0;
const ok = (n, c) => { if (c) { passed++; console.log(`  ok  ${n}`); } else { failed++; console.error(`  XX  ${n}`); } };

const NOW = new Date("2026-07-25T09:00:00Z");
const hoursAgo = (h) => new Date(NOW.getTime() - h * 3_600_000).toISOString();
const daysAgo = (d) => hoursAgo(d * 24);

// ── 1 · five bands, defined by consequence ───────────────────────────────────
ok("there are exactly five bands", SEVERITY.length === 5);
ok("bands run Minimal -> Extreme in index order",
  SEVERITY.map((s) => s.label).join(",") === "Minimal,Low,Moderate,High,Extreme");
ok("indices are 0..4 and match position", SEVERITY.every((s, i) => s.index === i));

// The whole point of this module: every band explains itself in terms of the world,
// not in terms of our importance score. A band without a consequence sentence is a
// threshold with a nicer name, which is what we are replacing.
ok("every band carries a consequence sentence",
  SEVERITY.every((s) => typeof s.consequence === "string" && s.consequence.length > 40));
ok("no consequence sentence mentions the model's own vocabulary",
  SEVERITY.every((s) => !/importance|score|threshold|appetite/i.test(s.consequence)));
ok("consequence sentences are distinct",
  new Set(SEVERITY.map((s) => s.consequence)).size === 5);
ok("every band carries a colour", SEVERITY.every((s) => /^#[0-9A-F]{6}$/i.test(s.color)));

ok("BANDS is descending for find-style lookup", BANDS[0].key === "extreme" && BANDS[4].key === "minimal");
ok("4.75 is Extreme", bandFor(4.75).label === "Extreme");
ok("3.0 is High at the boundary", bandFor(3.0).label === "High");
ok("2.99 is Moderate just below it", bandFor(2.99).label === "Moderate");
ok("0 is Minimal, not Low", bandFor(0).label === "Minimal");
ok("garbage scores fall back to Minimal, never crash",
  bandFor("x").key === "minimal" && bandFor(null).key === "minimal" && bandFor(undefined).key === "minimal");
ok("scores above the scale still band as Extreme", bandFor(99).key === "extreme");

// ── the 0-100 -> 0-5 ladder ──────────────────────────────────────────────────
ok("zero importance scores 0", scoreFrom(0) === 0);
ok("full importance scores 5", scoreFrom(100) === 5);
ok("mid importance lands mid-scale", scoreFrom(50) === 2.5);
ok("the scale is clamped at 5", scoreFrom(400) === 5);
ok("negative/garbage importance is safe", scoreFrom(-9) === 0 && scoreFrom("x") === 0);
ok("a cautious tolerance reads the same signal higher", scoreFrom(50, 0.5) > scoreFrom(50, 1));
ok("a zero/garbage factor does not divide by zero", Number.isFinite(scoreFrom(50, 0)) && scoreFrom(50, 0) === 2.5);

// ── five bands collapse to three map colours, one way only ───────────────────
ok("Extreme and High both draw as alert",
  levelOfBand("extreme") === "alert" && levelOfBand("high") === "alert");
ok("Moderate draws as watch", levelOfBand("moderate") === "watch");
ok("Low and Minimal draw as clear",
  levelOfBand("low") === "clear" && levelOfBand("minimal") === "clear");
ok("an unknown band key is clear, not alert", levelOfBand("nonsense") === "clear");

// ── 2 · alert type is EARNED, never asserted ─────────────────────────────────
const assessedCorroborated = {
  consequence_for_site: "Hinjewadi campus access road blocked from 07:00.",
  recommended_action: "Shift the first bus wave to the east gate.",
  source_count: 3,
};
ok("assessed + corroborated is Intelligence",
  alertTypeOf(assessedCorroborated).key === "intelligence");
ok("assessed but single-sourced is only Informative",
  alertTypeOf({ ...assessedCorroborated, source_count: 1 }).key === "informative");
ok("corroborated but unassessed is only Informative",
  alertTypeOf({ source_count: 5 }).key === "informative");
ok("a recommended action alone is enough to be assessed",
  alertTypeOf({ recommended_action: "Hold travel.", source_count: 2 }).key === "intelligence");
ok("whitespace is not an assessment",
  alertTypeOf({ consequence_for_site: "   ", source_count: 4 }).key === "informative");
ok("a missing event does not throw", alertTypeOf(undefined).key === "informative");
ok("both types define themselves",
  Object.values(ALERT_TYPES).every((t) => t.definition.length > 40));

// ── 3 · validity: alerts expire ──────────────────────────────────────────────
ok("a storm's window is short, a border dispute's is long",
  validityDays({ category: "storm" }) < validityDays({ category: "geopolitics" }));
ok("an unknown category gets the default window", validityDays({ category: "zzz" }) === 7);

// The engine's real vocabulary — backend/taxonomy.py CATEGORIES + LLM_CATEGORIES.
// The first version of these tables was written against the sample fixture and
// silently defaulted the live feed's four most common categories. This guard is why
// that cannot happen again quietly.
const ENGINE_CATEGORIES = [
  "disaster", "wildfire", "storm", "flood", "drought", "volcano", "conflict",
  "unrest", "cyber", "sanction", "space", "market", "disinfo",
  "geopolitics", "economy", "climate", "health", "technology", "policy",
];
ok("every engine category has an explicit validity window",
  ENGINE_CATEGORIES.every((c) => VALIDITY_DAYS[c] !== undefined));
ok("every engine category has an explicit spatial extent",
  ENGINE_CATEGORIES.every((c) => EXTENT_KM[c] !== undefined));
// The specific defect the table fixes: a sanction in force for months must not
// silently expire off the board after a week.
ok("a month-old sanction is still in force", validityOf({ category: "sanction", first_detected_at: daysAgo(30) }, NOW).state === "active");
ok("a month-old wildfire has expired", validityOf({ category: "wildfire", first_detected_at: daysAgo(30) }, NOW).state === "expired");
ok("unrest is treated as short-lived and local",
  validityDays({ category: "unrest" }) <= 3 && EXTENT_KM.unrest <= 25);
ok("a sanction reaches nationally, a protest does not", EXTENT_KM.sanction > EXTENT_KM.unrest * 10);

const freshStorm = { category: "storm", first_detected_at: hoursAgo(2) };
ok("a 2h-old storm is active", validityOf(freshStorm, NOW).state === "active");
ok("a 3-day-old storm has expired (2-day window)",
  validityOf({ category: "storm", first_detected_at: daysAgo(3) }, NOW).state === "expired");
ok("a 40-hour-old storm is expiring, not yet expired",
  validityOf({ category: "storm", first_detected_at: hoursAgo(40) }, NOW).state === "expiring");
ok("a 3-day-old geopolitical signal is still active",
  validityOf({ category: "geopolitics", first_detected_at: daysAgo(3) }, NOW).state === "active");

// Forward-compatible: when the API one day supplies a real window, it must win over
// our category-derived guess in BOTH directions.
ok("an explicit effective_to wins over the derived window",
  validityOf({ category: "geopolitics", first_detected_at: daysAgo(3), effective_to: daysAgo(1) }, NOW).state === "expired");
ok("an explicit effective_to can also extend the window",
  validityOf({ category: "storm", first_detected_at: daysAgo(3), effective_to: hoursAgo(-48) }, NOW).state === "active");
ok("an explicit effective_from is preferred over detection time",
  validityOf({ category: "storm", first_detected_at: daysAgo(9), effective_from: hoursAgo(1) }, NOW).state === "active");

ok("an event with no timestamps is 'unknown', never silently expired",
  validityOf({ category: "storm" }, NOW).state === "unknown");
ok("an unparseable timestamp is 'unknown', not NaN",
  validityOf({ category: "storm", first_detected_at: "not a date" }, NOW).state === "unknown");
ok("an unknown-validity event is NOT treated as expired",
  isExpired({ category: "storm" }, NOW) === false);
ok("remaining hours are reported", validityOf(freshStorm, NOW).remainingHours === 46);
ok("pctElapsed is bounded 0..1",
  [0, 0.5, 1].every(() => {
    const p = validityOf({ category: "storm", first_detected_at: daysAgo(30) }, NOW).pctElapsed;
    return p >= 0 && p <= 1;
  }));

const mixed = [
  { id: "a", category: "storm", first_detected_at: hoursAgo(1) },
  { id: "b", category: "storm", first_detected_at: daysAgo(5) },
  { id: "c", category: "geopolitics", first_detected_at: daysAgo(5) },
];
ok("activeOnly drops the expired storm and keeps the rest",
  activeOnly(mixed, NOW).map((e) => e.id).join(",") === "a,c");
ok("activeOnly on an empty list is an empty list", activeOnly([], NOW).length === 0);
ok("activeOnly on undefined does not throw", activeOnly(undefined, NOW).length === 0);

// ── 4 · two-level risk ───────────────────────────────────────────────────────
const calmCountryHotIncident = twoLevelRisk(0.5, 4.2);
ok("country and incident are banded separately",
  calmCountryHotIncident.country.key === "minimal" && calmCountryHotIncident.incident.key === "extreme");
ok("the gap is the interesting number", calmCountryHotIncident.gap === 4);
ok("a severe incident in a calm country is flagged anomalous", calmCountryHotIncident.anomalous === true);
ok("a severe incident in a severe country is NOT anomalous",
  twoLevelRisk(4.2, 4.4).anomalous === false);
ok("a quiet incident in a severe country has a negative gap",
  twoLevelRisk(4.2, 0.4).gap === -4);

// ── assets affected: attribution at the item level ───────────────────────────
const site = (id, lat, lng, headcount) => ({ office: { id, lat, lng, headcount, name: id } });
const blr = [site("s1", 12.97, 77.59, 1000), site("s2", 12.99, 77.62, 500), site("s3", 28.61, 77.21, 9000)];

// security extent is 25 km — reaches the two Bengaluru sites, never Delhi.
const protest = { category: "security", geo_centroid_lat: 12.98, geo_centroid_lng: 77.60 };
const hit = assetsAffected(protest, blr);
ok("a 25 km protest reaches only the two nearby sites", hit.count === 2);
ok("it never reaches the site 1,700 km away", !hit.sites.some((s) => s.office.id === "s3"));
ok("people are summed from the sites it actually reaches", hit.people === 1500);
ok("affected sites come back nearest-first", hit.sites[0].km <= hit.sites[1].km);
ok("each affected site carries its distance", hit.sites.every((s) => Number.isFinite(s.km)));

// A wide-extent event legitimately reaches further — the extent does the work, not
// a flat radius. Economics is 300 km.
ok("a 300 km economic signal reaches wider than a 25 km protest",
  assetsAffected({ category: "economics", geo_centroid_lat: 12.98, geo_centroid_lng: 77.60 }, blr).count >= hit.count);

// The honest zero: we do not guess an asset list for an event with no location.
const nowhere = assetsAffected({ category: "security" }, blr);
ok("a non-geolocated event affects zero assets, not 'all'", nowhere.count === 0 && nowhere.people === 0);
ok("assetsAffected with no contexts is zero, not a crash", assetsAffected(protest).count === 0);
ok("sites missing coordinates are skipped, not counted at 0,0",
  assetsAffected(protest, [{ office: { id: "x", headcount: 100 } }]).count === 0);

// ── classify: the whole read in one call ─────────────────────────────────────
const full = classify(
  { ...assessedCorroborated, category: "security", global_importance_score: 82,
    first_detected_at: hoursAgo(4), geo_centroid_lat: 12.98, geo_centroid_lng: 77.60 },
  { factor: 1, now: NOW, countryScore: 1.2, contexts: blr },
);
ok("classify bands the score", full.band.key === "extreme" && full.score === 4.1);
ok("classify carries the consequence sentence, not the number",
  full.consequence === SEVERITY_BY_KEY.extreme.consequence);
ok("classify resolves the map level", full.level === "alert");
ok("classify earns the alert type", full.type.key === "intelligence");
ok("classify resolves validity", full.validity.state === "active");
ok("classify pairs country risk with incident risk", full.risk.country.key === "low" && full.risk.incident.key === "extreme");
ok("a severe incident in a low-risk country reads as anomalous", full.risk.anomalous === true);
ok("classify attributes assets", full.assets.count === 2);
ok("classify omits risk when no country score is supplied", classify({}, { now: NOW }).risk === null);
ok("classify omits assets when no contexts are supplied", classify({}, { now: NOW }).assets === null);
ok("classify on an empty event does not throw", classify({}, { now: NOW }).band.key === "minimal");

console.log(`\nseverity: ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
