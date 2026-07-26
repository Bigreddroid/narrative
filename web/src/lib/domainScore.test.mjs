// Pure test for domainScore (no network, no React). Run:
//   node web/src/lib/domainScore.test.mjs
import { domainScores, overallScore, countryProfile, scoreFromImportance, bandFor } from "./domainScore.js";
import { officeContext } from "./officeContext.js";

let passed = 0, failed = 0;
const ok = (n, c) => { if (c) { passed++; console.log(`  ok  ${n}`); } else { failed++; console.error(`  XX  ${n}`); } };

const TODAY = new Date("2026-07-25T09:00:00Z");
const office = (id, headcount, extra = {}) => ({
  id, name: id, city: id, country: "India", lat: 17.45, lng: 78.35, headcount, ...extra,
});
const A = office("site-alpha", 12000);
const B = office("site-bravo", 8000, { lat: 18.59, lng: 73.74, country: "Romania" });
const at = (o, over = {}) => ({
  id: `e-${Math.random().toString(36).slice(2, 7)}`,
  geo_centroid_lat: o.lat, geo_centroid_lng: o.lng,
  global_importance_score: 85, canonical_title: "Signal", category: "conflict",
  source_count: 3, ...over,
});

// ── importance → 0–5 ─────────────────────────────────────────────────────────
ok("zero importance scores 0", scoreFromImportance(0) === 0);
ok("full importance scores 5", scoreFromImportance(100) === 5);
ok("mid importance lands mid-scale", scoreFromImportance(50) === 2.5);
ok("the scale is clamped at 5", scoreFromImportance(400) === 5);
ok("negative/garbage importance is safe", scoreFromImportance(-9) === 0 && scoreFromImportance("x") === 0);
// A cautious appetite (factor < 1) must read the SAME signal higher — that is the
// entire purpose of the control.
ok("a cautious appetite reads the same signal higher", scoreFromImportance(50, 0.5) > scoreFromImportance(50, 1));
ok("a tolerant appetite reads it lower", scoreFromImportance(50, 1.5) < scoreFromImportance(50, 1));

// ── bands ────────────────────────────────────────────────────────────────────
// One scale product-wide: these bands now come from severity.js, so a "2.5" reads
// "Moderate" here, on the map, in the brief and in an email — with the same
// consequence sentence attached in every one of them.
ok("4.75 is Extreme", bandFor(4.75).label === "Extreme");
ok("0 is Minimal", bandFor(0).label === "Minimal");
ok("2.5 is Moderate", bandFor(2.5).label === "Moderate");
ok("every band carries a colour", [0, 1.5, 2.5, 3.5, 4.5].every((s) => Boolean(bandFor(s).color)));
ok("every band carries its consequence definition",
  [0, 1.5, 2.5, 3.5, 4.5].every((s) => (bandFor(s).consequence || "").length > 40));

// ── per-domain scoring off a real rollup ─────────────────────────────────────
const hot = officeContext(A, { events: [at(A)], appetite: 50, today: TODAY });
const s = domainScores(hot, { appetite: 50 });
ok("every layer receives a domain score", Object.keys(s).length === 8);
ok("the driving domain scores above zero", s.geopolitics.score > 0);
ok("a quiet domain honestly scores zero", s.market.score === 0);
ok("the driving domain carries its evidence", Boolean(s.geopolitics.evidence?.id));
ok("a quiet domain carries no invented evidence", s.market.evidence === null);
ok("evidence includes distance for drill-through", typeof s.geopolitics.evidence.km === "number");

const quiet = domainScores(officeContext(A, { events: [], appetite: 50, today: TODAY }));
ok("a site with no signals scores 0 across the board",
  Object.values(quiet).every((d) => d.score === 0));
ok("...and still returns all eight domains, never blank", Object.keys(quiet).length === 8);

// ── overall = worst, never the mean ──────────────────────────────────────────
// One severe domain among seven quiet ones must NOT average away to "Moderate".
const overall = overallScore(s);
ok("overall takes the worst domain", overall.score === Math.max(...Object.values(s).map((d) => d.score)));
ok("overall names the driving domain", overall.driver?.key === "geopolitics");
ok("overall carries a band", Boolean(overall.band.label));
ok("an all-quiet site is Minimal with no driver",
  overallScore(quiet).band.label === "Minimal" && overallScore(quiet).driver === null);
ok("empty input is safe", overallScore({}).score === 0);

// ── cyber keeps its organisation scope through scoring ───────────────────────
const cyberEv = { id: "cy", category: "cyber", canonical_title: "Campaign", geo_centroid_lat: 55, geo_centroid_lng: 12, global_importance_score: 86, source_count: 4 };
const cy = domainScores(officeContext(A, { events: [cyberEv], appetite: 50, today: TODAY }));
ok("org-scoped cyber still scores", cy.cyber.score > 0);
ok("org-scoped cyber declares its scope", cy.cyber.scope === "organisation");

// The regression this guards: one cyber campaign is identical at every site, so if
// it can set a site's overall band, all 214 sites read Extreme off a single report
// and the register stops distinguishing anything. Found on a live 214-site board.
const cyOverall = overallScore(cy);
ok("a cyber-only site is NOT banded off the org-wide campaign", cyOverall.score === 0);
ok("and therefore names no driving domain", cyOverall.driver === null);
ok("cyber is still scored and displayed, just not attributed to a building", cy.cyber.score > 0);
ok("an explicit organisation-level rollup CAN include it",
  overallScore(cy, { includeOrgScope: true }).driver?.key === "cyber");
// A genuinely site-proximate signal must still drive the site, so the exclusion is
// narrow rather than a blanket "ignore severe things".
const cyPlusLocal = domainScores(officeContext(A, { events: [cyberEv, at(A)], appetite: 50, today: TODAY }));
ok("a real local signal still sets the site's overall",
  overallScore(cyPlusLocal).driver?.key === "geopolitics");

// ── country profile ──────────────────────────────────────────────────────────
const ctxs = [
  officeContext(A, { events: [at(A)], appetite: 50, today: TODAY }),
  officeContext(B, { events: [], appetite: 50, today: TODAY }),
];
const profile = countryProfile(ctxs, { appetite: 50 });
ok("one row per country", profile.length === 2);
ok("countries are ranked worst-first", profile[0].country === "India");
ok("country row aggregates people", profile[0].people === 12000);
ok("country row names its worst site", profile[0].worstSite?.office.id === "site-alpha");
ok("country row carries a band", Boolean(profile[0].band.label));
ok("a quiet country is honestly Minimal", profile[1].band.label === "Minimal");
ok("sites without a country are skipped, not crashed",
  countryProfile([officeContext({ ...A, country: undefined }, { events: [], appetite: 50, today: TODAY })]).length === 0);

console.log(`\ndomainScore: ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
