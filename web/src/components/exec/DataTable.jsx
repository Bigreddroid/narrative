// ─────────────────────────────────────────────────────────────────────────────
// DataTable — sortable, paginated, exportable. The table-stakes register controls.
//
// A 214-row site list and a 42-row traveller list rendered as an unsorted scrolling
// column is not a register, it is a list. Every incumbent console in this category
// sorts on every column, paginates, and downloads — so this is not innovation, it is
// the floor, and we were below it.
//
// All the mechanics are pure and unit-tested in lib/deckFilters.js (sortRows,
// nextSort, paginate, toCSV — 62 assertions). This component is the surface over
// them. In particular, columns sort on `sortValue`, never on the rendered string:
// "9 km" vs "28 km" sorts wrong as text, which silently misranks a register by
// proximity — exactly the kind of quiet error a security board must not contain.
//
// The CSV path escapes and neutralises formula injection (a leading = + - @ is
// executed by Excel on open, and event titles are attacker-influenced text).
// ─────────────────────────────────────────────────────────────────────────────
import { useState, useMemo } from "react";
import { sortRows, nextSort, paginate, downloadCSV } from "../../lib/deckFilters.js";

const PAGE_SIZES = [25, 50, 100];

function Arrow({ dir }) {
  return (
    <span className="inline-block text-[8px] leading-none ml-1 translate-y-[-1px]">
      {dir === "asc" ? "▲" : "▼"}
    </span>
  );
}

export default function DataTable({
  columns = [], rows = [], rowKey = (r, i) => i, onRowClick, selectedKey,
  defaultSort = null, filename = "export.csv", empty = "Nothing matches the current filters.",
  caption,
}) {
  const [sort, setSort] = useState(defaultSort);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const sorted = useMemo(() => sortRows(rows, sort, columns), [rows, sort, columns]);
  // Clamping lives in paginate(), so filtering a 214-row register down to 12 while
  // parked on page 6 shows page 1 rather than a blank table.
  const view = useMemo(() => paginate(sorted, page, pageSize), [sorted, page, pageSize]);

  const clickHeader = (key) => {
    setSort((s) => nextSort(s, key, columns.find((c) => c.key === key)?.defaultDir || "desc"));
    setPage(1);
  };

  return (
    <div className="bg-[#0A0A0A]">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2 border-b border-[#1A1A1A]">
        <span className="font-mono text-[10px] tracking-[0.14em] uppercase text-[#6A6A64] tabular-nums">
          {view.total
            ? <>{view.from}–{view.to} of <span className="text-[#B8B5AE]">{view.total.toLocaleString()}</span></>
            : "0 rows"}
        </span>
        {caption && <span className="text-[11px] text-[#4A4845] flex-1 min-w-[160px]">{caption}</span>}

        <label className="flex items-center gap-1.5 ml-auto">
          <span className="font-mono text-[9px] tracking-[0.14em] uppercase text-[#5A5A55]">Rows</span>
          <select
            value={pageSize}
            onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
            className="bg-[#0E0E0E] border border-[#242424] rounded-[2px] px-1.5 py-0.5 font-mono text-[10px] text-[#B8B5AE] focus:outline-none focus:border-[#3A3A3A]"
          >
            {PAGE_SIZES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>

        <button
          type="button"
          onClick={() => downloadCSV(sorted, columns, filename)}
          disabled={!view.total}
          title={`Download all ${view.total} rows as shown, in the current sort order`}
          className="font-mono text-[10px] tracking-[0.14em] uppercase border border-[#242424] px-2.5 py-1 rounded-[2px] text-[#8A8A82] hover:text-[#F0EDE8] hover:border-[#3A3A3A] disabled:text-[#3A3A38] disabled:hover:border-[#242424]"
        >
          Download CSV
        </button>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse min-w-[560px]">
          <thead>
            <tr className="border-b border-[#1A1A1A]">
              {columns.map((c) => {
                const active = sort?.key === c.key;
                return (
                  <th key={c.key} scope="col"
                    style={{ width: c.width, textAlign: c.align || "left" }}
                    aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
                    className="px-3 py-2 font-mono text-[9px] tracking-[0.16em] uppercase font-normal">
                    {c.sortable === false ? (
                      <span className="text-[#5A5A55]">{c.label}</span>
                    ) : (
                      <button type="button" onClick={() => clickHeader(c.key)}
                        className={active ? "text-[#F0EDE8]" : "text-[#5A5A55] hover:text-[#B8B5AE]"}>
                        {c.label}{active && <Arrow dir={sort.dir} />}
                      </button>
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {view.rows.map((r, i) => {
              const k = rowKey(r, i);
              const isSel = selectedKey != null && k === selectedKey;
              return (
                <tr key={k}
                  onClick={onRowClick ? () => onRowClick(r) : undefined}
                  className={[
                    "border-b border-[#141414]",
                    onRowClick ? "cursor-pointer hover:bg-[#111]" : "",
                    isSel ? "bg-[#141414]" : "",
                  ].join(" ")}>
                  {columns.map((c) => (
                    <td key={c.key} style={{ textAlign: c.align || "left" }}
                      className={`px-3 py-2 text-[12px] ${c.mono ? "font-mono tabular-nums text-[11px]" : ""} ${c.className || ""}`}>
                      {c.render ? c.render(r) : c.value(r)}
                    </td>
                  ))}
                </tr>
              );
            })}
            {!view.total && (
              <tr><td colSpan={columns.length} className="px-4 py-8 text-[12px] text-[#5A5A55] text-center">{empty}</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pager */}
      {view.pages > 1 && (
        <div className="flex items-center justify-between gap-3 px-4 py-2 border-t border-[#1A1A1A]">
          <button type="button" disabled={view.page <= 1} onClick={() => setPage(view.page - 1)}
            className="font-mono text-[10px] tracking-[0.14em] uppercase text-[#8A8A82] disabled:text-[#2E2E2C] hover:text-[#F0EDE8]">
            ← Prev
          </button>
          <span className="font-mono text-[10px] text-[#5A5A55] tabular-nums">
            Page {view.page} of {view.pages}
          </span>
          <button type="button" disabled={view.page >= view.pages} onClick={() => setPage(view.page + 1)}
            className="font-mono text-[10px] tracking-[0.14em] uppercase text-[#8A8A82] disabled:text-[#2E2E2C] hover:text-[#F0EDE8]">
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
