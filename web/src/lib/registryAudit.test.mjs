// Pure test for registryAudit (no network, no React). Run:
//   node web/src/lib/registryAudit.test.mjs
import { auditRegister, CHECK_LABELS } from "./registryAudit.js";

let passed = 0, failed = 0;
const ok = (n, c) => { if (c) { passed++; console.log(`  ok  ${n}`); } else { failed++; console.error(`  XX  ${n}`); } };

const CC = { India: "IN", "South Africa": "ZA", "United Arab Emirates": "AE" };
const site = (o) => ({ id: "s1", name: "Site", city: "City", country: "India", lat: 12.9, lng: 77.6, headcount: 100, ...o });
const has = (r, check) => r.findings.some((f) => f.check === check);

// ── a clean register is reported clean ───────────────────────────────────────
const clean = auditRegister([
  site({ id: "a", name: "Alpha", city: "Bengaluru" }),
  site({ id: "b", name: "Bravo", city: "Pune", lat: 18.5, lng: 73.8 }),
], { countryCodes: CC });
ok("a clean register produces no findings", clean.clean === true && clean.findings.length === 0);
ok("clean register still reports what it checked", clean.checked === 2);
ok("empty register is safe", auditRegister([], {}).clean === true);

// ── THE observed failure: one identifier, two countries ──────────────────────
const conflict = auditRegister([
  site({ id: "AFR08", country: "India", city: "Johannesburg" }),
  site({ id: "AFR08", country: "South Africa", city: "Johannesburg", lat: -26.1, lng: 28.05 }),
], { countryCodes: CC });
ok("same identifier across two countries is caught", has(conflict, "conflicting_country"));
ok("conflicting country is critical", conflict.findings.find((f) => f.check === "conflicting_country").severity === "critical");
ok("the finding names both countries", /India/.test(conflict.findings.find((f) => f.check === "conflicting_country").detail));
ok("it is NOT double-reported as a plain duplicate", !has(conflict, "duplicate_id"));

// A duplicate id within ONE country is a plain duplicate, not a country conflict.
const dupe = auditRegister([site({ id: "X1" }), site({ id: "X1", lat: 13.0 })], { countryCodes: CC });
ok("duplicate identifier in one country is caught", has(dupe, "duplicate_id"));
ok("...and is not mislabelled a country conflict", !has(dupe, "conflicting_country"));

// ── missing / unmapped country ───────────────────────────────────────────────
const noCountry = auditRegister([site({ id: "n1", country: "" })], { countryCodes: CC });
ok("a row with no country is caught", has(noCountry, "missing_country"));
const unmapped = auditRegister([site({ id: "u1", country: "Narnia" })], { countryCodes: CC });
ok("a country with no ISO mapping is surfaced", has(unmapped, "unmapped_country"));
ok("unmapped country explains the consequence", /holiday/i.test(unmapped.findings[0].detail));
ok("a mapped country is not flagged", !has(auditRegister([site({ id: "m1" })], { countryCodes: CC }), "unmapped_country"));

// ── coordinates ──────────────────────────────────────────────────────────────
ok("missing coordinates are caught", has(auditRegister([site({ lat: null, lng: null })], { countryCodes: CC }), "missing_coordinates"));
ok("out-of-range coordinates are caught", has(auditRegister([site({ lat: 120, lng: 12 })], { countryCodes: CC }), "invalid_coordinates"));
ok("0,0 is caught as an import default", has(auditRegister([site({ lat: 0, lng: 0 })], { countryCodes: CC }), "null_island"));

// ── headcount ────────────────────────────────────────────────────────────────
ok("a site with no headcount is flagged", has(auditRegister([site({ headcount: 0 })], { countryCodes: CC }), "missing_headcount"));
ok("headcount finding explains the exposure consequence",
  /exposure/i.test(auditRegister([site({ headcount: 0 })], { countryCodes: CC }).findings.find((f) => f.check === "missing_headcount").detail));

// ── geographic coherence ─────────────────────────────────────────────────────
// Four Indian sites, one of which is actually in Johannesburg.
const outlier = auditRegister([
  site({ id: "i1", lat: 12.9, lng: 77.6 }), site({ id: "i2", lat: 13.0, lng: 77.5 }),
  site({ id: "i3", lat: 18.5, lng: 73.8 }), site({ id: "i4", lat: -26.2, lng: 28.0 }),
], { countryCodes: CC });
ok("a site far from its country's other sites is flagged", has(outlier, "country_outlier"));
ok("the outlier is the wrong-country row", outlier.findings.find((f) => f.check === "country_outlier").siteId === "i4");
ok("its peers are not flagged", outlier.findings.filter((f) => f.check === "country_outlier").length === 1);
ok("too few peers ⇒ no outlier judgement",
  !has(auditRegister([site({ id: "p1" }), site({ id: "p2", lat: -26.2, lng: 28.0 })], { countryCodes: CC }), "country_outlier"));

// ── reporting shape ──────────────────────────────────────────────────────────
const mixed = auditRegister([
  site({ id: "d1", country: "" }), site({ id: "d1", country: "South Africa", lat: -26, lng: 28 }),
  site({ id: "d2", headcount: 0 }),
], { countryCodes: CC });
ok("findings are ranked critical-first", mixed.findings[0].severity === "critical");
ok("counts are broken down by check", Object.keys(mixed.byCheck).length >= 2);
ok("affected sites are counted distinctly", mixed.affectedSites >= 1 && mixed.affectedSites <= 3);
ok("every finding carries a human label", mixed.findings.every((f) => Boolean(CHECK_LABELS[f.check])));
ok("every finding names its row", mixed.findings.every((f) => f.siteId !== undefined));
ok("every finding explains itself", mixed.findings.every((f) => typeof f.detail === "string" && f.detail.length > 10));

console.log(`\nregistryAudit: ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
