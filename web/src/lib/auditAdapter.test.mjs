// Pure test for auditAdapter (no network, no React). Run:
//   node web/src/lib/auditAdapter.test.mjs
import { adaptAudit } from "./auditAdapter.js";

let passed = 0, failed = 0;
const ok = (n, c) => { if (c) { passed++; console.log(`  ok  ${n}`); } else { failed++; console.error(`  XX  ${n}`); } };

const SITES = [
  { id: "uuid-1", external_id: "AFR08", name: "Johannesburg Campus" },
  { id: "uuid-2", external_id: "AFR08", name: "Johannesburg Annexe" },
  { id: "uuid-3", external_id: "IND01", name: "Electronic City" },
  { id: "uuid-4", external_id: null, name: "No Identifier" },
];

const SERVER = {
  findings: [
    { check: "conflicting_country", label: "Same identifier, different countries",
      severity: "critical", rank: 3, site_id: "AFR08", site_name: "Johannesburg Campus",
      detail: "2 rows share this identifier across 2 countries" },
    { check: "missing_headcount", label: "No headcount", severity: "warning", rank: 2,
      site_id: "GONE99", site_name: "Vanished", detail: "No headcount on this row" },
    { check: "missing_country", label: "No country", severity: "warning", rank: 2,
      site_id: null, site_name: null, detail: "Country is empty" },
  ],
  by_check: { conflicting_country: 1, missing_headcount: 1, missing_country: 1 },
  checked: 4, affected_sites: 2, critical: 1, warnings: 2, clean: false,
};

const a = adaptAudit(SERVER, SITES);

// ── the shape the board reads ───────────────────────────────────────────────
ok("snake_case by_check becomes byCheck", Object.keys(a.byCheck).length === 3);
ok("snake_case affected_sites becomes affectedSites", a.affectedSites === 2);
ok("counts survive", a.checked === 4 && a.critical === 1 && a.warnings === 2);
ok("clean survives as a boolean", a.clean === false);

// ── THE bug this exists to prevent: dead clicks on the integrity panel ──────
ok("a customer identifier resolves to our internal id", a.findings[0].siteId === "uuid-1");
ok("the customer's own identifier is preserved for them to search on",
  a.findings[0].siteRef === "AFR08");
ok("site_name is carried across", a.findings[0].siteName === "Johannesburg Campus");
ok("an identifier not in the register resolves to null, not to itself",
  a.findings[1].siteId === null);
ok("...and it is NOT silently dropped from the findings", a.findings.length === 3);
ok("a finding with no identifier stays null", a.findings[2].siteId === null);

// A duplicate identifier is ambiguous by nature; landing on either row is correct,
// but it must land somewhere rather than nowhere.
ok("a duplicated identifier still resolves to one of its rows",
  ["uuid-1", "uuid-2"].includes(a.findings[0].siteId));

// ── the affected count is the server's, not a recount of what resolved ──────
ok("affectedSites is not reduced by unresolvable rows", a.affectedSites === 2);

// ── pass-through and edge cases ─────────────────────────────────────────────
const browserShape = { findings: [], byCheck: {}, checked: 2, affectedSites: 0, clean: true };
ok("an audit already in browser shape is returned untouched",
  adaptAudit(browserShape, SITES) === browserShape);
ok("null in, null out", adaptAudit(null, SITES) === null);
ok("an empty server audit is clean and empty",
  adaptAudit({ findings: [], by_check: {}, checked: 0, affected_sites: 0, clean: true }, []).clean === true);
ok("a clean register reports zero findings",
  adaptAudit({ findings: [], by_check: {}, checked: 5, affected_sites: 0, clean: true }, SITES).findings.length === 0);
ok("sites with no external_id never claim a finding",
  adaptAudit({ findings: [{ check: "x", site_id: "", site_name: null }], by_check: {}, clean: false }, SITES)
    .findings[0].siteId === null);

console.log(`\nauditAdapter: ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
