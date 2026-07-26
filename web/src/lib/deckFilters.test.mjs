// Pure test for deckFilters (no network, no React). Run:
//   node web/src/lib/deckFilters.test.mjs
import {
  emptyFilters, selectedIn, isSelected, toggleValue, clearDimension, clearAll,
  countActive, hasAnyFilter, matches, applyFilters, facets,
  sortRows, nextSort, paginate, csvCell, toCSV, encodeFilters, decodeFilters,
} from "./deckFilters.js";

let passed = 0, failed = 0;
const ok = (n, c) => { if (c) { passed++; console.log(`  ok  ${n}`); } else { failed++; console.error(`  XX  ${n}`); } };

// A small, deliberately awkward register: mixed countries, one site with no type,
// one traveller-ish row with multiple tags.
const rows = [
  { id: "s1", country: "India",  band: "extreme", type: "Office",  tags: ["hq", "critical"] },
  { id: "s2", country: "India",  band: "high",    type: "Office",  tags: ["critical"] },
  { id: "s3", country: "India",  band: "low",     type: "Vendor",  tags: [] },
  { id: "s4", country: "UK",     band: "high",    type: "Vendor",  tags: ["critical"] },
  { id: "s5", country: "UK",     band: "minimal", type: null,      tags: ["hq"] },
  { id: "s6", country: "Poland", band: "moderate", type: "Administrative", tags: [] },
];

const SEV_OPTIONS = [
  { value: "extreme", label: "Extreme" }, { value: "high", label: "High" },
  { value: "moderate", label: "Moderate" }, { value: "low", label: "Low" },
  { value: "minimal", label: "Minimal" },
];
const dims = [
  { key: "band", label: "Severity", values: (r) => r.band, options: SEV_OPTIONS },
  { key: "country", label: "Country", values: (r) => r.country },
  { key: "type", label: "Site type", values: (r) => r.type },
  { key: "tags", label: "Tags", values: (r) => r.tags },
];

// ── state ────────────────────────────────────────────────────────────────────
ok("an empty filter set is empty", countActive(emptyFilters()) === 0 && !hasAnyFilter(emptyFilters()));
let f = emptyFilters();
f = toggleValue(f, "band", "high");
ok("toggling selects", isSelected(f, "band", "high") && countActive(f) === 1);
f = toggleValue(f, "band", "extreme");
ok("a second value in the same dimension adds, not replaces", selectedIn(f, "band").length === 2);
f = toggleValue(f, "band", "high");
ok("toggling the same value deselects", !isSelected(f, "band", "high") && countActive(f) === 1);
f = toggleValue(f, "band", "extreme");
ok("emptying a dimension removes it entirely", !("band" in f) && countActive(f) === 0);

const before = { band: ["high"] };
const after = toggleValue(before, "band", "extreme");
ok("toggle never mutates the previous state (React safety)",
  before.band.length === 1 && after.band.length === 2 && before !== after);

ok("clearDimension drops just that dimension",
  countActive(clearDimension({ band: ["high"], country: ["India"] }, "band")) === 1);
ok("clearAll drops everything", countActive(clearAll()) === 0);
ok("selectedIn on a missing dimension is an empty array, not undefined",
  Array.isArray(selectedIn({}, "nope")) && selectedIn(undefined, "nope").length === 0);

// ── matching semantics ───────────────────────────────────────────────────────
ok("no filters means every row passes", applyFilters(rows, {}, dims).length === 6);
ok("within a dimension is OR",
  applyFilters(rows, { band: ["extreme", "high"] }, dims).length === 3);
ok("across dimensions is AND",
  applyFilters(rows, { band: ["extreme", "high"], country: ["India"] }, dims).map((r) => r.id).join() === "s1,s2");
ok("an array-valued dimension matches on any member",
  applyFilters(rows, { tags: ["critical"] }, dims).map((r) => r.id).join() === "s1,s2,s4");

// An unknown must NOT be a wildcard. s5 has no type; constraining on type must
// exclude it rather than quietly passing it through — a hidden gap in a security
// register is worse than a visible one.
ok("a row with no value for a constrained dimension is excluded",
  !applyFilters(rows, { type: ["Office", "Vendor"] }, dims).some((r) => r.id === "s5"));
ok("an empty-array value is likewise excluded",
  !applyFilters(rows, { tags: ["hq"] }, dims).some((r) => r.id === "s3"));
ok("a selection matching nothing yields zero rows, not all rows",
  applyFilters(rows, { country: ["Atlantis"] }, dims).length === 0);
ok("applyFilters returns a copy, never the original array",
  applyFilters(rows, {}, dims) !== rows);
ok("matches() agrees with applyFilters", matches(rows[0], { country: ["India"] }, dims) === true);

// ── faceted counts — the detail that makes a filter bar usable ───────────────
const plain = facets(rows, {}, dims);
const bandFacet = plain.find((x) => x.key === "band");
ok("declared options keep scale order and include the zeroes",
  bandFacet.options.map((o) => o.value).join() === "extreme,high,moderate,low,minimal");
ok("unfiltered counts are the raw distribution",
  bandFacet.options.find((o) => o.value === "high").count === 2);

// With India selected, the SEVERITY facet must be counted against India only...
const inIndia = facets(rows, { country: ["India"] }, dims);
ok("other dimensions constrain a facet's counts",
  inIndia.find((x) => x.key === "band").options.find((o) => o.value === "high").count === 1);
// ...but the COUNTRY facet itself must ignore its own selection, or every other
// country would read 0 and the bar would become a dead end.
ok("a dimension does not constrain its own facet",
  inIndia.find((x) => x.key === "country").options.find((o) => o.value === "UK").count === 2);
ok("selection state round-trips into the facet",
  inIndia.find((x) => x.key === "country").options.find((o) => o.value === "India").selected === true);
ok("selectedCount is reported per dimension",
  inIndia.find((x) => x.key === "country").selectedCount === 1);

const discovered = facets(rows, {}, dims).find((x) => x.key === "country");
ok("undeclared options are discovered from the data",
  discovered.options.length === 3 && discovered.options[0].value === "India");
ok("discovered options are ordered by count, descending",
  discovered.options[0].count >= discovered.options[1].count);
ok("facets on an empty row set still return every declared option",
  facets([], {}, dims).find((x) => x.key === "band").options.length === 5);
ok("a null value never becomes a facet option",
  !facets(rows, {}, dims).find((x) => x.key === "type").options.some((o) => o.value == null));

// ── sorting ──────────────────────────────────────────────────────────────────
const cols = [
  { key: "id", label: "Site", value: (r) => r.id },
  { key: "km", label: "Distance", value: (r) => `${r.km} km`, sortValue: (r) => r.km },
  { key: "people", label: "People", value: (r) => r.people },
];
const srows = [
  { id: "a", km: 9, people: 100 }, { id: "b", km: 28, people: 100 },
  { id: "c", km: 130, people: null }, { id: "d", km: 3, people: 100 },
];
ok("descending numeric sort", sortRows(srows, { key: "km", dir: "desc" }, cols).map((r) => r.id).join() === "c,b,a,d");
ok("ascending numeric sort", sortRows(srows, { key: "km", dir: "asc" }, cols).map((r) => r.id).join() === "d,a,b,c");
// The bug this prevents: sorting "9 km" vs "28 km" as text puts 9 last.
ok("a column sorts on its sortValue, not its rendered string",
  sortRows(srows, { key: "km", dir: "desc" }, cols)[0].id === "c");
ok("equal keys keep incoming order (stable)",
  sortRows(srows, { key: "people", dir: "desc" }, cols).map((r) => r.id).join() === "a,b,d,c");
ok("nulls sink descending", sortRows(srows, { key: "people", dir: "desc" }, cols).at(-1).id === "c");
ok("nulls sink ascending too", sortRows(srows, { key: "people", dir: "asc" }, cols).at(-1).id === "c");
ok("no sort key leaves the order alone", sortRows(srows, null, cols).map((r) => r.id).join() === "a,b,c,d");
ok("an unknown sort key leaves the order alone", sortRows(srows, { key: "zzz" }, cols).map((r) => r.id).join() === "a,b,c,d");
ok("sortRows never mutates its input", (() => { const c = [...srows]; sortRows(srows, { key: "km", dir: "asc" }, cols); return srows.map((r) => r.id).join() === c.map((r) => r.id).join(); })());
ok("text sorts naturally (Site 2 before Site 10)",
  sortRows([{ id: "Site 10" }, { id: "Site 2" }], { key: "id", dir: "asc" }, cols).map((r) => r.id).join() === "Site 2,Site 10");

ok("first click on a new column uses its default direction", nextSort(null, "km").dir === "desc");
ok("second click reverses", nextSort({ key: "km", dir: "desc" }, "km").dir === "asc");
ok("third click reverses back", nextSort({ key: "km", dir: "asc" }, "km").dir === "desc");
ok("switching columns resets to the default direction", nextSort({ key: "km", dir: "asc" }, "people").dir === "desc");

// ── pagination ───────────────────────────────────────────────────────────────
const many = Array.from({ length: 214 }, (_, i) => ({ i }));
const p1 = paginate(many, 1, 25);
ok("page 1 of a 214-row register", p1.rows.length === 25 && p1.pages === 9 && p1.total === 214);
ok("the range readout is 1-indexed and human", p1.from === 1 && p1.to === 25);
const p9 = paginate(many, 9, 25);
ok("the last page holds the remainder", p9.rows.length === 14 && p9.from === 201 && p9.to === 214);
// Filtering down while parked on a high page must not show a blank table.
ok("a page beyond the end clamps to the last page", paginate(many.slice(0, 12), 6, 25).page === 1);
ok("an empty set is one empty page with a 0 range",
  (() => { const p = paginate([], 1, 25); return p.pages === 1 && p.total === 0 && p.from === 0 && p.to === 0; })());
ok("page 0 or negative clamps to 1", paginate(many, 0, 25).page === 1 && paginate(many, -3, 25).page === 1);
ok("a garbage page size falls back rather than dividing by zero", paginate(many, 1, 0).pageSize === 25);

// ── CSV ──────────────────────────────────────────────────────────────────────
ok("plain cells pass through", csvCell("Bengaluru") === "Bengaluru");
ok("null becomes empty, not the string 'null'", csvCell(null) === "" && csvCell(undefined) === "");
ok("commas force quoting", csvCell("Bengaluru, India") === '"Bengaluru, India"');
ok("embedded quotes are doubled", csvCell('He said "go"') === '"He said ""go"""');
ok("newlines force quoting", csvCell("line1\nline2") === '"line1\nline2"');
// Real vector: event titles and site notes are attacker-influenced text, and Excel
// executes a leading = + - @ on open.
ok("a formula-injection lead is neutralised", csvCell("=cmd|'/c calc'!A1").startsWith("'="));
ok("+ - @ leads are neutralised too",
  csvCell("+1").startsWith("'") && csvCell("-1").startsWith("'") && csvCell("@SUM").startsWith("'"));
ok("a neutralised cell containing a comma is also quoted", csvCell("=A1,B2") === `"'=A1,B2"`);

const csv = toCSV(
  [{ id: "s1", city: "Pune, MH" }, { id: "s2", city: null }],
  [{ key: "id", label: "Site", value: (r) => r.id }, { key: "city", label: "City", value: (r) => r.city }],
);
ok("CSV emits a header row", csv.split("\r\n")[0] === "Site,City");
ok("CSV emits one row per record", csv.split("\r\n").length === 3);
ok("CSV quotes a value containing a comma", csv.split("\r\n")[1] === 's1,"Pune, MH"');
ok("CSV uses CRLF line endings", csv.includes("\r\n"));
ok("an empty row set still emits the header", toCSV([], [{ key: "id", label: "Site", value: (r) => r.id }]) === "Site");

// ── URL round-trip ────────────────────────────────────────────────────────────
const rt = (f) => decodeFilters(encodeFilters(f));
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

ok("empty filters encode to an empty string", encodeFilters({}) === "");
ok("empty string decodes to no filters", same(decodeFilters(""), {}));
ok("null/undefined are tolerated", encodeFilters(null) === "" && same(decodeFilters(undefined), {}));

const simpleF = { band: ["high", "moderate"], country: ["India"] };
ok("round-trips a multi-dimension filter set", same(rt(simpleF), simpleF));

// The delimiters appear inside REAL values — this is the bug a naive split causes.
const commasF = { country: ["Korea, Republic of", "Bosnia and Herzegovina"] };
ok("a value containing a comma survives the round-trip", same(rt(commasF), commasF));
ok("a comma value does not shear into two filters", rt(commasF).country.length === 2);
const semisF = { note: ["a;b", "c:d"] };
ok("values containing ; and : survive too", same(rt(semisF), semisF));

// Stable output: the same set must always yield the same string.
ok("dimension order does not change the encoding",
  encodeFilters({ band: ["high"], country: ["India"] })
  === encodeFilters({ country: ["India"], band: ["high"] }));

// An empty dimension means "no constraint" and must not survive.
ok("empty dimensions are dropped", encodeFilters({ band: [], country: ["India"] }) === "country:India");
ok("a non-array value is ignored", encodeFilters({ band: "high" }) === "");

// Tolerant decoding: a hand-edited URL degrades to a usable board, never throws.
ok("a segment with no colon is dropped", same(decodeFilters("garbage"), {}));
ok("a segment with an empty key is dropped", same(decodeFilters(":a,b"), {}));
ok("a segment with no values is dropped", same(decodeFilters("band:"), {}));
ok("trailing separators are tolerated", same(decodeFilters("band:high;;"), { band: ["high"] }));
ok("malformed percent-encoding does not throw", same(decodeFilters("band:%E0%A4%A"), {}));
ok("a good segment survives beside a bad one", same(decodeFilters("garbage;band:high"), { band: ["high"] }));

// Decoded filters must actually drive the existing machinery.
{
  const urlDims = [{ key: "band", label: "Severity", values: (r) => r.band }];
  const urlRows = [{ band: "high" }, { band: "low" }, { band: "high" }];
  ok("a decoded filter set filters rows", applyFilters(urlRows, decodeFilters("band:high"), urlDims).length === 2);
}

console.log(`\ndeckFilters: ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
