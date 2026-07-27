// ─────────────────────────────────────────────────────────────────────────────
// FilterBar — the control that replaced the risk-appetite slider.
//
// The slider re-scored the world: dragging it changed every number underneath the
// reader, so the board being read was no longer the board that had been assessed.
// (It also silently restored itself to max on reload and collapsed the deck to
// zero.) Tolerance now lives at organisation level, set once by the security team.
//
// This changes only WHAT IS SHOWN. The assessment is untouched, which is what an
// executive surface needs.
//
// Every chip carries its faceted count — how many rows you get if you select it,
// with all other dimensions still applied. Zero-count options stay visible and
// disabled rather than disappearing: "0 Extreme" is a real and reassuring answer,
// and a bar whose options vanish as you use it is unusable.
//
// All state and counting is computed in lib/deckFilters.js (62 assertions). This
// file is presentation only.
// ─────────────────────────────────────────────────────────────────────────────

function Chip({ opt, onClick }) {
  const dead = opt.count === 0 && !opt.selected;
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={dead}
      aria-pressed={opt.selected}
      title={dead ? `No ${opt.label} in the current view` : `${opt.count} ${opt.label}`}
      className={[
        "group inline-flex items-center gap-1.5 pl-2 pr-1.5 py-1 rounded-[2px] border",
        "font-mono text-[10px] tracking-[0.06em] uppercase whitespace-nowrap transition-colors",
        dead
          ? "border-[var(--xd-7)] text-[var(--xd-14)] cursor-default"
          : opt.selected
            ? "border-transparent text-[var(--xd-0)]"
            : "border-[var(--xd-12)] text-[var(--xd-20)] hover:border-[var(--xd-17)] hover:text-[var(--xd-22)]",
      ].join(" ")}
      style={opt.selected ? { background: opt.color || "var(--xd-23)" } : undefined}
    >
      {opt.color && !opt.selected && !dead && (
        <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: opt.color }} />
      )}
      <span>{opt.label}</span>
      <span className={[
        "tabular-nums px-1 rounded-[2px] text-[9px]",
        opt.selected ? "bg-[rgba(0,0,0,0.22)] text-[var(--xd-0)]" : "bg-[var(--xd-5)] text-[var(--xd-19)]",
      ].join(" ")}>
        {opt.count}
      </span>
    </button>
  );
}

export default function FilterBar({
  facets = [], activeCount = 0, shown, total, onToggle, onClearDimension, onClearAll, note,
}) {
  const filtered = shown !== total;
  return (
    <div className="no-print border-y border-[var(--xd-8)] bg-[var(--xd-1)]">
      <div className="px-6 lg:px-10 py-3 flex flex-col gap-2.5">

        {facets.map((f) => (
          <div key={f.key} className="flex items-baseline gap-3">
            <button
              type="button"
              onClick={() => f.selectedCount && onClearDimension?.(f.key)}
              disabled={!f.selectedCount}
              title={f.selectedCount ? `Clear ${f.label}` : undefined}
              className={[
                "font-mono text-[9px] tracking-[0.2em] uppercase w-[104px] shrink-0 text-left pt-1",
                f.selectedCount ? "text-[#C80028] hover:underline cursor-pointer" : "text-[var(--xd-18)] cursor-default",
              ].join(" ")}
            >
              {f.label}{f.selectedCount ? ` ·${f.selectedCount}` : ""}
            </button>
            <div className="flex flex-wrap gap-1.5 min-w-0">
              {f.options.length === 0 && (
                <span className="font-mono text-[10px] text-[var(--xd-14)] pt-1">none in view</span>
              )}
              {f.options.map((o) => (
                <Chip key={String(o.value)} opt={o} onClick={() => onToggle?.(f.key, o.value)} />
              ))}
            </div>
          </div>
        ))}

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 pt-0.5 border-t border-[var(--xd-5)] mt-0.5">
          <span className="font-mono text-[10px] tracking-[0.12em] uppercase text-[var(--xd-20)] tabular-nums">
            {filtered
              ? <>Showing <span className="text-[var(--xd-23)]">{shown.toLocaleString()}</span> of {total.toLocaleString()}</>
              : <>All <span className="text-[var(--xd-23)]">{total.toLocaleString()}</span> shown</>}
          </span>
          {/* Always mounted, disabled when there is nothing to clear.
              It used to unmount at zero — which orphaned keyboard focus and dropped
              it onto an arbitrary severity/criticality chip, so the user's next
              Space or Enter silently toggled a filter they never chose and quietly
              changed what the board was showing. A control that disappears from
              under the caret is a correctness problem, not a cosmetic one. */}
          <button
            type="button"
            onClick={onClearAll}
            disabled={activeCount === 0}
            className={[
              "font-mono text-[10px] tracking-[0.12em] uppercase",
              activeCount ? "text-[#C80028] hover:underline" : "text-[var(--xd-13)] cursor-default",
            ].join(" ")}
          >
            Clear all{activeCount ? ` (${activeCount})` : ""}
          </button>
          {note && <span className="text-[11px] text-[var(--xd-16)] flex-1 min-w-[200px]">{note}</span>}
        </div>
      </div>
    </div>
  );
}
