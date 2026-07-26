// ─────────────────────────────────────────────────────────────────────────────
// deckFilters — table mechanics for the executive deck: filtering, faceted counts,
// sorting, pagination and CSV export. All pure, all unit-tested.
//
// WHY THIS REPLACED THE RISK-APPETITE SLIDER
// A tolerance slider RE-SCORES the world: drag it and every number underneath you
// changes, so the board you are reading is no longer the board that was assessed.
// (It also silently pinned itself to max on reload and collapsed the whole deck to
// zero — the exact failure mode of a control that rewrites data.) A filter changes
// only WHAT YOU ARE LOOKING AT and leaves the assessment untouched. An executive
// should never be re-scoring anything mid-briefing, so tolerance moved to a
// settings-level organisational setting and this took its place on the surface.
//
// SEMANTICS
//   within a dimension : OR   (Extreme OR High)
//   across dimensions  : AND  ((Extreme OR High) AND India AND Intelligence)
// That is what every filter bar in the world does, and doing anything cleverer here
// would make the counts unexplainable.
//
// FACETED COUNTS
// The count beside "High" is how many rows you would get if you selected it, with
// every OTHER dimension still applied — not the count of the currently-visible rows.
// Without this, selecting one severity drives every other option to 0 and the bar
// becomes a dead end. This is the single detail that makes a filter bar usable.
//
// Pure + unit-tested (deckFilters.test.mjs).
// ─────────────────────────────────────────────────────────────────────────────

// ── Filter state ─────────────────────────────────────────────────────────────
// Shape: { [dimensionKey]: [selectedValue, ...] }. A dimension absent or empty means
// "no constraint" — never "match nothing", which is how empty filter bars break.
export const emptyFilters = () => ({});

export function selectedIn(filters, dimKey) {
  const v = filters?.[dimKey];
  return Array.isArray(v) ? v : [];
}

export function isSelected(filters, dimKey, value) {
  return selectedIn(filters, dimKey).includes(value);
}

// Immutable toggle — React state, so never mutate.
export function toggleValue(filters, dimKey, value) {
  const cur = selectedIn(filters, dimKey);
  const next = cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value];
  const out = { ...filters };
  if (next.length) out[dimKey] = next; else delete out[dimKey];
  return out;
}

export function clearDimension(filters, dimKey) {
  const out = { ...filters };
  delete out[dimKey];
  return out;
}

export const clearAll = () => ({});

// ── URL round-trip ───────────────────────────────────────────────────────────
// Deck state lives in the query string so a board is linkable, back-navigable and
// resumable — a demo that loses its filters on reload cannot be handed to anyone.
//
// Wire format: `dim:v1,v2;dim2:v3`. Every key and value is percent-encoded, because
// real filter values contain the delimiters ("Korea, Republic of" has a comma) and a
// naive split would silently shear it into two filters that match nothing.
//
// Dimensions are sorted so the SAME filter set always produces the SAME string —
// otherwise two identical boards yield different URLs and nothing downstream can
// compare or cache them.
export function encodeFilters(filters) {
  return Object.entries(filters || {})
    .filter(([, v]) => Array.isArray(v) && v.length)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, vs]) => `${encodeURIComponent(k)}:${vs.map(encodeURIComponent).join(",")}`)
    .join(";");
}

// Tolerant by design: a hand-edited or truncated URL should degrade to a usable board,
// never throw. Malformed segments are dropped, not guessed at.
export function decodeFilters(str) {
  const out = {};
  for (const part of String(str || "").split(";")) {
    if (!part) continue;
    const i = part.indexOf(":");
    if (i <= 0) continue;                       // no key, or empty key
    let key, values;
    try {
      key = decodeURIComponent(part.slice(0, i));
      values = part.slice(i + 1).split(",").filter(Boolean).map(decodeURIComponent);
    } catch {
      continue;                                 // malformed percent-encoding
    }
    if (values.length) out[key] = values;
  }
  return out;
}

// How many constraints are in force — drives the "Clear all (3)" affordance.
export function countActive(filters) {
  return Object.values(filters || {}).reduce((n, v) => n + (Array.isArray(v) ? v.length : 0), 0);
}

export const hasAnyFilter = (filters) => countActive(filters) > 0;

// ── Matching ─────────────────────────────────────────────────────────────────
// A dimension is { key, label, values(row) -> scalar | array | null }.
// A row matches a dimension when ANY of its values is selected. A row with no value
// for a constrained dimension does not match — an unknown is not a wildcard, because
// silently passing unknowns through a security filter is how a gap gets hidden.
function valuesOf(dim, row) {
  const v = dim.values(row);
  if (v == null) return [];
  return Array.isArray(v) ? v.filter((x) => x != null) : [v];
}

export function matchesDimension(row, dim, filters) {
  const sel = selectedIn(filters, dim.key);
  if (!sel.length) return true;
  const vals = valuesOf(dim, row);
  return vals.some((v) => sel.includes(v));
}

export function matches(row, filters, dims = []) {
  return dims.every((d) => matchesDimension(row, d, filters));
}

export function applyFilters(rows = [], filters = {}, dims = []) {
  if (!hasAnyFilter(filters)) return [...rows];
  return rows.filter((r) => matches(r, filters, dims));
}

// ── Faceted counts ───────────────────────────────────────────────────────────
// For each dimension, count each option against the rows surviving every OTHER
// dimension. Options come from the dimension's declared list when it has one (so a
// severity bar always shows all five bands in scale order, including the zeroes —
// "0 Extreme" is a real and reassuring answer), otherwise they are discovered from
// the data and sorted by count.
export function facets(rows = [], filters = {}, dims = []) {
  return dims.map((dim) => {
    const others = dims.filter((d) => d.key !== dim.key);
    const pool = rows.filter((r) => others.every((d) => matchesDimension(r, d, filters)));

    const counts = new Map();
    for (const r of pool) for (const v of valuesOf(dim, r)) counts.set(v, (counts.get(v) || 0) + 1);

    let options;
    if (dim.options && dim.options.length) {
      options = dim.options.map((o) => ({
        value: o.value, label: o.label ?? String(o.value), color: o.color ?? null,
        count: counts.get(o.value) || 0,
      }));
    } else {
      options = [...counts.entries()]
        .map(([value, count]) => ({ value, label: String(value), color: null, count }))
        .sort((a, b) => b.count - a.count || String(a.label).localeCompare(String(b.label)));
      if (dim.maxOptions) options = options.slice(0, dim.maxOptions);
    }

    const sel = selectedIn(filters, dim.key);
    return {
      key: dim.key,
      label: dim.label,
      selectedCount: sel.length,
      options: options.map((o) => ({ ...o, selected: sel.includes(o.value) })),
    };
  });
}

// ── Sorting ──────────────────────────────────────────────────────────────────
// Columns declare their own accessor so the table never sorts on rendered strings
// ("28 km" vs "9 km" sorts wrong as text — a bug that quietly misranks a register).
// Stable: equal keys keep their incoming order.
export function sortRows(rows = [], sort, columns = []) {
  if (!sort?.key) return [...rows];
  const col = columns.find((c) => c.key === sort.key);
  if (!col) return [...rows];
  const dir = sort.dir === "asc" ? 1 : -1;
  const get = col.sortValue || col.value;

  return rows
    .map((row, i) => ({ row, i, v: get(row) }))
    .sort((a, b) => {
      const av = a.v, bv = b.v;
      // Nulls always sink, in both directions — a missing value is not "lowest".
      const an = av == null || av === "", bn = bv == null || bv === "";
      if (an && bn) return a.i - b.i;
      if (an) return 1;
      if (bn) return -1;
      let c;
      if (typeof av === "number" && typeof bv === "number") c = av - bv;
      else c = String(av).localeCompare(String(bv), undefined, { numeric: true, sensitivity: "base" });
      return c === 0 ? a.i - b.i : c * dir;
    })
    .map((x) => x.row);
}

// Click a column: first click sorts by its natural direction, second reverses.
export function nextSort(sort, key, defaultDir = "desc") {
  if (sort?.key !== key) return { key, dir: defaultDir };
  return { key, dir: sort.dir === "asc" ? "desc" : "asc" };
}

// ── Pagination ───────────────────────────────────────────────────────────────
// Clamps the page rather than returning an empty view — filtering a 214-row register
// down to 12 while sitting on page 6 must not show a blank table.
export function paginate(rows = [], page = 1, pageSize = 25) {
  const size = Math.max(1, Number(pageSize) || 25);
  const total = rows.length;
  const pages = Math.max(1, Math.ceil(total / size));
  const current = Math.min(Math.max(1, Number(page) || 1), pages);
  const start = (current - 1) * size;
  const slice = rows.slice(start, start + size);
  return {
    rows: slice, page: current, pages, pageSize: size, total,
    from: total ? start + 1 : 0,
    to: start + slice.length,
  };
}

// ── CSV export ───────────────────────────────────────────────────────────────
// Escapes quotes, commas and newlines, and neutralises formula injection: a cell
// beginning = + - @ (or tab/CR) is executed by Excel and Sheets on open. Site notes
// and event titles are attacker-influenced text in a security product, so this is a
// real vector and not a theoretical one.
const RISKY_LEAD = /^[=+\-@\t\r]/;

export function csvCell(value) {
  if (value == null) return "";
  let s = String(value);
  if (RISKY_LEAD.test(s)) s = `'${s}`;
  if (/[",\n\r]/.test(s)) s = `"${s.replace(/"/g, '""')}"`;
  return s;
}

export function toCSV(rows = [], columns = []) {
  const header = columns.map((c) => csvCell(c.label ?? c.key)).join(",");
  const body = rows.map((r) =>
    columns.map((c) => csvCell((c.csvValue || c.value)(r))).join(","),
  );
  return [header, ...body].join("\r\n");
}

// Browser-only side effect, kept beside its format so they cannot drift. Returns the
// filename so a caller can log what was exported.
export function downloadCSV(rows, columns, filename = "export.csv") {
  const csv = toCSV(rows, columns);
  // BOM so Excel opens UTF-8 site names correctly instead of mojibake.
  const blob = new Blob(["﻿", csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
  return filename;
}
