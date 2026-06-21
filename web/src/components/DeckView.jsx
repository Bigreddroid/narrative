import { useState, useMemo, useCallback } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useEventFeed } from "../hooks/useEventFeed.js";
import { useFollowing } from "../hooks/useFollowing.js";
import { useMediaQuery } from "../hooks/useMediaQuery.js";
import EventGraph from "./graph/EventGraph.jsx";
import { getCategoryColor } from "../lib/colors.js";
import { biasLabel } from "../lib/bias.js";

// ─── TweetDeck-inspired multi-column intelligence board ───────────────────────
// Borrowed UX from TweetDeck: a horizontally scrolling wall of dense, live,
// independently-scrolling columns — adapted to Narrative's signals + theme.

// Dark "command-center" palette (deck is always dark, like classic TweetDeck).
const C = {
  board:   "#0B0E13",
  column:  "#141922",
  header:  "#11151D",
  card:    "#161C26",
  cardHov: "#1B2230",
  border:  "rgba(240,237,232,0.07)",
  border2: "rgba(240,237,232,0.12)",
  fg:      "#E8E4DC",
  fg80:    "rgba(232,228,220,0.80)",
  fg50:    "rgba(232,228,220,0.50)",
  fg35:    "rgba(232,228,220,0.35)",
  fg20:    "rgba(232,228,220,0.20)",
  crimson: "#C80028",
};

const CATEGORY_OPTIONS = ["Geopolitics", "Conflict", "Economics", "Climate", "Technology", "Health", "Policy", "Security"];

let _uid = 0;
const nextId = () => `col-${++_uid}`;

const DEFAULT_COLUMNS = [
  { id: nextId(), title: "All Signals", kind: "all" },
  { id: nextId(), title: "Escalating",  kind: "status",   value: "escalating" },
  { id: nextId(), title: "Conflict",    kind: "category", value: "conflict" },
  { id: nextId(), title: "Economics",   kind: "category", value: "economics" },
  { id: nextId(), title: "Geopolitics", kind: "category", value: "geopolitics" },
  { id: nextId(), title: "Climate",     kind: "category", value: "climate" },
];

function columnIcon(kind) {
  if (kind === "all") {
    return <path d="M2 3h12M2 7h12M2 11h8" />;
  }
  if (kind === "status") {
    return <path d="M8 1.5l1.8 3.7 4.1.6-3 2.9.7 4.1L8 10.9 4.4 12.8l.7-4.1-3-2.9 4.1-.6z" />;
  }
  return <><circle cx="8" cy="8" r="6" /><path d="M2 8h12M8 2c1.6 1.6 2.4 3.7 2.4 6S9.6 12.4 8 14M8 2C6.4 3.6 5.6 5.7 5.6 8S6.4 12.4 8 14" /></>;
}

// ─── Compact deck card ────────────────────────────────────────────────────────
function DeckCard({ event, isSelected, onClick, following, onFollow }) {
  const color      = getCategoryColor(event.category);
  const escalating = event.current_status === "escalating";
  const title      = event.canonical_title || event.title || "Untitled signal";
  const summary    = event.canonical_summary || event.summary || "";
  const geo        = (event.geography || []).slice(0, 2).join(" · ");
  const score      = Math.round(event.importance_score || event.importance || 0);
  const lean       = event.source_bias ? biasLabel(event.source_bias) : null;

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
      onClick={() => onClick(event.id)}
      className="cursor-pointer group"
      style={{
        borderBottom: `1px solid ${C.border}`,
        borderLeft: `2px solid ${isSelected ? color : "transparent"}`,
        backgroundColor: isSelected ? C.cardHov : "transparent",
      }}
      onMouseEnter={e => { if (!isSelected) e.currentTarget.style.backgroundColor = C.cardHov; }}
      onMouseLeave={e => { if (!isSelected) e.currentTarget.style.backgroundColor = "transparent"; }}
    >
      <div className="px-3 py-2.5">
        <div className="flex items-center gap-1.5 mb-1.5">
          <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
          <span className="text-[8px] font-mono font-bold uppercase tracking-widest" style={{ color }}>
            {event.category}
          </span>
          {escalating && (
            <span className="w-1 h-1 rounded-full animate-pulse flex-shrink-0" style={{ backgroundColor: C.crimson }} />
          )}
          <div className="ml-auto flex items-center gap-1.5">
            {score > 0 && <span className="text-[9px] font-mono tabular-nums" style={{ color: C.fg35 }}>{score}</span>}
            <button
              onClick={e => { e.stopPropagation(); onFollow(event); }}
              title={following ? "Untrack" : "Track signal"}
              className="transition-colors"
              style={{ color: following ? C.crimson : C.fg20 }}
            >
              <svg width="11" height="11" viewBox="0 0 14 14" fill={following ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.4">
                <path d="M7 1.5C5.5 1.5 3.5 2.8 3.5 5.2c0 2.8 3.5 6.8 3.5 6.8s3.5-4 3.5-6.8C10.5 2.8 8.5 1.5 7 1.5z" />
              </svg>
            </button>
          </div>
        </div>

        <h3 className="text-[12.5px] font-semibold leading-snug mb-1 transition-colors line-clamp-3"
          style={{ color: C.fg }}>
          {title}
        </h3>

        {summary && (
          <p className="text-[10.5px] leading-snug line-clamp-2 mb-1.5" style={{ color: C.fg50 }}>
            {summary}
          </p>
        )}

        <div className="flex items-center gap-2 text-[9px] font-mono" style={{ color: C.fg35 }}>
          {geo && <span className="truncate uppercase tracking-wider">{geo}</span>}
          {lean && (
            <span className="flex items-center gap-1 flex-shrink-0 ml-auto" style={{ color: lean.color }}>
              <span className="w-1 h-1 rounded-full" style={{ backgroundColor: lean.color }} />
              {lean.label}
            </span>
          )}
        </div>
      </div>
    </motion.article>
  );
}

// ─── Column ───────────────────────────────────────────────────────────────────
function Column({ column, events, selectedEventId, onSelect, onRemove, isFollowing, onFollow }) {
  const accent = column.kind === "category" ? getCategoryColor(column.value)
    : column.kind === "status" ? C.crimson
    : C.fg50;
  // Narrower columns on phones so a column + its neighbour's edge stay visible
  // (the board still scrolls horizontally — classic TweetDeck UX).
  const isMobile = useMediaQuery("(max-width: 767px)");

  return (
    <div
      className="flex-shrink-0 flex flex-col h-full"
      style={{ width: isMobile ? 264 : 320, backgroundColor: C.column, borderRight: `1px solid ${C.border}` }}
    >
      {/* Column header */}
      <div className="flex items-center gap-2 px-3 py-2.5 flex-shrink-0"
        style={{ backgroundColor: C.header, borderBottom: `1px solid ${C.border2}` }}>
        <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke={accent} strokeWidth="1.4" strokeLinejoin="round">
          {columnIcon(column.kind)}
        </svg>
        <span className="text-[11px] font-bold uppercase tracking-widest" style={{ color: C.fg80 }}>
          {column.title}
        </span>
        <span className="text-[9px] font-mono tabular-nums px-1.5 py-px rounded-sm"
          style={{ color: C.fg50, backgroundColor: "rgba(240,237,232,0.06)" }}>
          {events.length}
        </span>
        <button
          onClick={() => onRemove(column.id)}
          title="Remove column"
          className="ml-auto transition-colors"
          style={{ color: C.fg20 }}
          onMouseEnter={e => e.currentTarget.style.color = C.crimson}
          onMouseLeave={e => e.currentTarget.style.color = C.fg20}
        >
          <svg width="11" height="11" viewBox="0 0 12 12" stroke="currentColor" strokeWidth="1.5">
            <line x1="1" y1="1" x2="11" y2="11" /><line x1="11" y1="1" x2="1" y2="11" />
          </svg>
        </button>
      </div>

      {/* Column body */}
      <div className="flex-1 overflow-y-auto deck-scroll">
        {events.length === 0 ? (
          <div className="flex items-center justify-center h-32 px-4">
            <p className="text-[10px] font-mono uppercase tracking-widest text-center" style={{ color: C.fg20 }}>
              No signals in this column
            </p>
          </div>
        ) : (
          events.map(e => (
            <DeckCard
              key={e.id}
              event={e}
              isSelected={e.id === selectedEventId}
              onClick={onSelect}
              following={isFollowing(e.id)}
              onFollow={ev => isFollowing(ev.id) ? onFollow.unfollow(ev.id) : onFollow.follow(ev)}
            />
          ))
        )}
      </div>
    </div>
  );
}

// ─── Add-column control ───────────────────────────────────────────────────────
function AddColumn({ onAdd }) {
  const [open, setOpen] = useState(false);
  const isMobile = useMediaQuery("(max-width: 767px)");
  const menuWidth = isMobile ? 196 : 240;

  const add = (col) => { onAdd({ ...col, id: nextId() }); setOpen(false); };

  return (
    <div className="flex-shrink-0 relative h-full flex items-start" style={{ width: open ? menuWidth : 56, backgroundColor: C.board }}>
      {!open ? (
        <button
          onClick={() => setOpen(true)}
          title="Add column"
          className="w-14 h-full flex flex-col items-center justify-center gap-2 transition-colors"
          style={{ color: C.fg35, borderRight: `1px solid ${C.border}` }}
          onMouseEnter={e => e.currentTarget.style.color = C.crimson}
          onMouseLeave={e => e.currentTarget.style.color = C.fg35}
        >
          <svg width="18" height="18" viewBox="0 0 18 18" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
            <line x1="9" y1="3" x2="9" y2="15" /><line x1="3" y1="9" x2="15" y2="9" />
          </svg>
          <span className="text-[9px] font-mono uppercase tracking-widest" style={{ writingMode: "vertical-rl" }}>Add</span>
        </button>
      ) : (
        <div className="h-full overflow-y-auto deck-scroll" style={{ width: menuWidth, borderRight: `1px solid ${C.border}` }}>
          <div className="flex items-center justify-between px-3 py-2.5" style={{ backgroundColor: C.header, borderBottom: `1px solid ${C.border2}` }}>
            <span className="text-[11px] font-bold uppercase tracking-widest" style={{ color: C.fg80 }}>Add Column</span>
            <button onClick={() => setOpen(false)} style={{ color: C.fg35 }}>
              <svg width="11" height="11" viewBox="0 0 12 12" stroke="currentColor" strokeWidth="1.5">
                <line x1="1" y1="1" x2="11" y2="11" /><line x1="11" y1="1" x2="1" y2="11" />
              </svg>
            </button>
          </div>

          <p className="px-3 pt-3 pb-1.5 text-[9px] font-mono uppercase tracking-[0.3em]" style={{ color: C.fg35 }}>Status</p>
          {[{ t: "Escalating", v: "escalating" }, { t: "Developing", v: "developing" }, { t: "Stable", v: "stable" }].map(s => (
            <button key={s.v} onClick={() => add({ title: s.t, kind: "status", value: s.v })}
              className="w-full text-left px-3 py-2 text-[12px] flex items-center gap-2 transition-colors"
              style={{ color: C.fg80 }}
              onMouseEnter={e => e.currentTarget.style.backgroundColor = C.cardHov}
              onMouseLeave={e => e.currentTarget.style.backgroundColor = "transparent"}>
              <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: C.crimson }} />{s.t}
            </button>
          ))}

          <p className="px-3 pt-3 pb-1.5 text-[9px] font-mono uppercase tracking-[0.3em]" style={{ color: C.fg35 }}>Category</p>
          {CATEGORY_OPTIONS.map(cat => {
            const v = cat.toLowerCase();
            return (
              <button key={v} onClick={() => add({ title: cat, kind: "category", value: v })}
                className="w-full text-left px-3 py-2 text-[12px] flex items-center gap-2 transition-colors"
                style={{ color: C.fg80 }}
                onMouseEnter={e => e.currentTarget.style.backgroundColor = C.cardHov}
                onMouseLeave={e => e.currentTarget.style.backgroundColor = "transparent"}>
                <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: getCategoryColor(v) }} />{cat}
              </button>
            );
          })}

          <button onClick={() => add({ title: "All Signals", kind: "all" })}
            className="w-full text-left px-3 py-2.5 mt-1 text-[12px] flex items-center gap-2 transition-colors"
            style={{ color: C.fg80, borderTop: `1px solid ${C.border}` }}
            onMouseEnter={e => e.currentTarget.style.backgroundColor = C.cardHov}
            onMouseLeave={e => e.currentTarget.style.backgroundColor = "transparent"}>
            <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: C.fg50 }} />All Signals
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Deck root ────────────────────────────────────────────────────────────────
export default function DeckView({ selectedEventId, onEventSelect, onEventClose }) {
  const { events, loading } = useEventFeed({ limit: 100 });
  const { follow, unfollow, isFollowing } = useFollowing();
  const [columns, setColumns] = useState(DEFAULT_COLUMNS);

  const filterFor = useCallback((col) => {
    let list = events;
    if (col.kind === "category") list = events.filter(e => e.category === col.value);
    else if (col.kind === "status") list = events.filter(e => e.current_status === col.value);
    return [...list].sort((a, b) => (b.importance_score || 0) - (a.importance_score || 0));
  }, [events]);

  const columnData = useMemo(
    () => columns.map(col => ({ col, list: filterFor(col) })),
    [columns, filterFor]
  );

  const addColumn    = useCallback((col) => setColumns(c => [...c, col]), []);
  const removeColumn = useCallback((id) => setColumns(c => c.filter(x => x.id !== id)), []);

  return (
    <div className="flex-1 min-h-0 relative" style={{ backgroundColor: C.board }}>
      {/* Deck bar */}
      <div className="flex items-center gap-2 px-4 py-2 flex-shrink-0"
        style={{ backgroundColor: C.header, borderBottom: `1px solid ${C.border2}` }}>
        <span className="text-[10px] font-mono font-bold uppercase tracking-[0.3em]" style={{ color: C.fg50 }}>
          Intelligence Deck
        </span>
        <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: C.crimson }} />
        <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: C.fg35 }}>
          {columns.length} columns · {events.length} signals live
        </span>
      </div>

      {/* Columns row */}
      <div className="flex overflow-x-auto deck-scroll" style={{ height: "calc(100% - 37px)" }}>
        {loading ? (
          <div className="flex items-center justify-center w-full">
            <div className="w-6 h-6 border-2 rounded-full animate-spin"
              style={{ borderColor: C.border2, borderTopColor: C.crimson }} />
          </div>
        ) : (
          <>
            {columnData.map(({ col, list }) => (
              <Column
                key={col.id}
                column={col}
                events={list}
                selectedEventId={selectedEventId}
                onSelect={onEventSelect}
                onRemove={removeColumn}
                isFollowing={isFollowing}
                onFollow={{ follow, unfollow }}
              />
            ))}
            <AddColumn onAdd={addColumn} />
          </>
        )}
      </div>

      {/* Event detail overlay panel (desktop) */}
      <AnimatePresence>
        {selectedEventId && (
          <motion.div
            initial={{ opacity: 0, x: 40 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 40 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="hidden lg:block absolute top-4 right-4 bottom-4 overflow-hidden z-30 shadow-2xl"
            style={{ width: 420 }}
          >
            <EventGraph eventId={selectedEventId} onClose={onEventClose} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
