import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { api } from "../lib/api.js";
import {
  DISCIPLINES,
  DISCIPLINE_LABELS,
  DISCIPLINE_BLURB,
} from "../lib/taxonomy.js";
import { getDisciplineColor, getCategoryColor } from "../lib/colors.js";
import { useTheme } from "../hooks/useTheme.js";

// ─────────────────────────────────────────────────────────────────────────────
// Phase 2d — INT Fusion dashboard (dashboard-first fast-track).
//
// A read-only, all-source view over the SAME live data the rest of the app uses:
// one panel per intelligence discipline (driven by GET /events?discipline=…),
// SIGINT driven by the live ADS-B/AIS track endpoints, and a "cross-discipline
// fusion" strip surfacing events where ≥2 disciplines corroborate (from the CPE's
// corroboration output on /exposure — the payoff of Phase 2b).
//
// Everything degrades honestly: a discipline with no live data shows an explicit
// empty state rather than a fabricated one, and the $0 ceiling is stated in-product
// (SIGINT = transponders only, IMINT = provided imagery, GEOINT = mapping).
// ─────────────────────────────────────────────────────────────────────────────

const PANEL_LIMIT = 8;

// One fetch per discipline. Event-backed disciplines hit /events?discipline=…;
// SIGINT is special (live transponder tracks, no DB events) and handled separately.
function useDisciplineEvents(discipline, enabled = true) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!enabled) { setLoading(false); return; }
    let cancelled = false;
    setLoading(true);
    const q = new URLSearchParams({ discipline, limit: String(PANEL_LIMIT) });
    api.get(`/events/?${q}`)
      .then((data) => {
        if (cancelled) return;
        setEvents(Array.isArray(data) ? data : data.events || []);
        setError(null);
      })
      .catch((err) => { if (!cancelled) { setEvents([]); setError(err); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [discipline, enabled]);

  return { events, loading, error };
}

// SIGINT panel data: live ADS-B (aircraft) + AIS (vessel) transponder counts.
// Both endpoints degrade to source:"none" when no feed is configured — surfaced
// honestly rather than shown as zero-with-no-context.
function useSigint() {
  const [state, setState] = useState({ loading: true, air: null, sea: null });
  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([api.get("/aircraft"), api.get("/vessels")])
      .then(([a, v]) => {
        if (cancelled) return;
        const air = a.status === "fulfilled" ? a.value : null;
        const sea = v.status === "fulfilled" ? v.value : null;
        setState({ loading: false, air, sea });
      });
    return () => { cancelled = true; };
  }, []);
  return state;
}

// Cross-discipline fusion strip: pull the CPE corroboration map off /exposure and
// keep only convergences spanning ≥2 disciplines. Titles are joined from a broad
// /events fetch (best-effort — falls back to the discipline list if a title is
// missing). This is intentionally read-only: no engine constants reach the client.
function useFusion() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([
      api.get("/exposure", { timeoutMs: 20000 }),
      api.get("/events/?limit=100"),
    ]).then(([ex, evs]) => {
      if (cancelled) return;
      const corrob = ex.status === "fulfilled" ? (ex.value?.corroboration || {}) : {};
      const eventList = evs.status === "fulfilled"
        ? (Array.isArray(evs.value) ? evs.value : evs.value?.events || [])
        : [];
      const titleById = {};
      for (const e of eventList) titleById[e.id] = e;
      const rows = Object.entries(corrob)
        .map(([id, c]) => ({
          id,
          index: c.index || 0,
          count: c.count || 0,
          disciplines: c.disciplines || [],
          event: titleById[id] || null,
        }))
        .filter((r) => (r.disciplines?.length || 0) >= 2)
        .sort((a, b) => b.index - a.index)
        .slice(0, 6);
      setItems(rows);
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, []);
  return { items, loading };
}

function DisciplineBadge({ code }) {
  const color = getDisciplineColor(code);
  return (
    <span
      className="text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded-sm"
      style={{ color, border: `1px solid ${color}55`, backgroundColor: `${color}12` }}
    >
      {DISCIPLINE_LABELS[code] || code}
    </span>
  );
}

function EventRow({ event, onOpen }) {
  const title = event.canonical_title || event.title || "Untitled event";
  const score = Math.round(event.global_importance_score || event.importance_score || 0);
  const geo = (event.geographic_relevance || event.geography || []).slice(0, 2).join(" · ");
  const catColor = getCategoryColor(event.category);
  const escalating = event.current_status === "escalating";
  return (
    <button
      type="button"
      onClick={() => onOpen(event.id)}
      className="w-full text-left px-4 py-2.5 border-b border-ink/8 hover:bg-ink/[0.03] transition-colors group"
    >
      <div className="flex items-center gap-2 mb-1">
        {event.category && (
          <span className="text-[9px] font-bold uppercase tracking-wider" style={{ color: catColor }}>
            {event.category}
          </span>
        )}
        {escalating && (
          <span className="flex items-center gap-1 text-[9px] font-medium text-crimson">
            <span className="w-1 h-1 rounded-full bg-crimson animate-pulse" /> Escalating
          </span>
        )}
        {score > 0 && <span className="ml-auto text-[10px] text-ink/30 tabular-nums">{score}</span>}
      </div>
      <p className="text-[13px] font-medium text-ink leading-snug line-clamp-2 group-hover:text-crimson transition-colors">
        {title}
      </p>
      {geo && <p className="text-[10px] text-ink/40 mt-1 truncate">{geo}</p>}
    </button>
  );
}

function PanelShell({ code, count, live, children }) {
  const color = getDisciplineColor(code);
  return (
    <section className="flex flex-col bg-paper border border-ink/10 rounded-sm overflow-hidden min-h-[220px]">
      <header
        className="px-4 py-3 flex items-start gap-2 border-b border-ink/10"
        style={{ borderTop: `2px solid ${color}` }}
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-[13px] font-bold uppercase tracking-widest" style={{ color }}>
              {DISCIPLINE_LABELS[code] || code}
            </span>
            {live != null && (
              <span
                className="flex items-center gap-1 text-[8px] font-mono uppercase tracking-wider"
                style={{ color: live ? "#3FA7A0" : "rgba(120,120,120,0.7)" }}
              >
                <span
                  className="w-1.5 h-1.5 rounded-full"
                  style={{ backgroundColor: live ? "#3FA7A0" : "rgba(120,120,120,0.5)" }}
                />
                {live ? "Live" : "No source"}
              </span>
            )}
          </div>
          <p className="text-[10px] text-ink/45 leading-snug mt-0.5">{DISCIPLINE_BLURB[code]}</p>
        </div>
        {count != null && (
          <span className="text-[11px] font-mono tabular-nums text-ink/40 flex-shrink-0">{count}</span>
        )}
      </header>
      <div className="flex-1 overflow-y-auto max-h-[320px]">{children}</div>
    </section>
  );
}

function EmptyState({ text }) {
  return (
    <div className="flex items-center justify-center h-full min-h-[140px] px-4 py-8 text-center">
      <p className="text-[11px] text-ink/30 leading-relaxed">{text}</p>
    </div>
  );
}

function PanelSkeleton() {
  return (
    <div className="px-4 py-3 space-y-3 animate-pulse">
      {Array(3).fill(0).map((_, i) => (
        <div key={i} className="space-y-1.5">
          <div className="h-2.5 bg-ink/10 rounded w-16" />
          <div className="h-3.5 bg-ink/10 rounded w-4/5" />
        </div>
      ))}
    </div>
  );
}

// Event-backed discipline panel.
function DisciplinePanel({ code, onOpen }) {
  const { events, loading } = useDisciplineEvents(code);
  const emptyMsg = {
    IMINT: "No imagery interpreted yet. Upload a photo in Locate to derive an IMINT track (interpretation of provided imagery only — no satellite tasking).",
    GEOINT: "No geolocated signals in view. GEOINT maps the positions of existing signals (no commercial imagery).",
  }[code] || `No ${DISCIPLINE_LABELS[code] || code} events in view right now.`;

  return (
    <PanelShell code={code} count={loading ? null : events.length}>
      {loading ? (
        <PanelSkeleton />
      ) : events.length === 0 ? (
        <EmptyState text={emptyMsg} />
      ) : (
        events.map((e) => <EventRow key={e.id} event={e} onOpen={onOpen} />)
      )}
    </PanelShell>
  );
}

// SIGINT panel — live transponder tracks (ADS-B + AIS), not DB events.
function SigintPanel() {
  const { loading, air, sea } = useSigint();
  const airCount = air?.aircraft?.length || 0;
  const seaCount = sea?.vessels?.length || 0;
  const airLive = !!air?.live && (air?.source && air.source !== "none");
  const seaLive = !!sea?.live && (sea?.source && sea.source !== "none");
  const anyLive = airLive || seaLive;
  const total = airCount + seaCount;

  return (
    <PanelShell code="SIGINT" count={loading ? null : total} live={loading ? null : anyLive}>
      {loading ? (
        <PanelSkeleton />
      ) : total === 0 && !anyLive ? (
        <EmptyState text="No live transponder feed configured. SIGINT here = ADS-B aircraft + AIS vessel emitters (no RF interception at $0). Enable Air/Maritime layers in World View to stream tracks." />
      ) : (
        <div className="px-4 py-3 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "#5BA3D0" }} />
              <span className="text-[11px] font-semibold text-ink">ADS-B aircraft</span>
            </div>
            <div className="text-right">
              <span className="text-[15px] font-bold tabular-nums text-ink">{airCount}</span>
              <span className="ml-2 text-[9px] font-mono uppercase" style={{ color: airLive ? "#3FA7A0" : "rgba(120,120,120,0.7)" }}>
                {airLive ? air.source : "no source"}
              </span>
            </div>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "#3FA7A0" }} />
              <span className="text-[11px] font-semibold text-ink">AIS vessels</span>
            </div>
            <div className="text-right">
              <span className="text-[15px] font-bold tabular-nums text-ink">{seaCount}</span>
              <span className="ml-2 text-[9px] font-mono uppercase" style={{ color: seaLive ? "#3FA7A0" : "rgba(120,120,120,0.7)" }}>
                {seaLive ? sea.source : "no source"}
              </span>
            </div>
          </div>
          <p className="text-[10px] text-ink/35 leading-relaxed pt-1 border-t border-ink/8">
            Emitter positions tracked on the World View globe (Air / Maritime layers).
          </p>
        </div>
      )}
    </PanelShell>
  );
}

// Cross-discipline fusion strip — the Phase 2b payoff made visible.
function FusionStrip({ onOpen }) {
  const { items, loading } = useFusion();

  return (
    <div style={{ backgroundColor: "#111111" }} className="rounded-sm overflow-hidden mb-6">
      <div className="px-5 py-3 flex items-center gap-2" style={{ borderBottom: "1px solid rgba(240,237,232,0.08)" }}>
        <span className="w-1.5 h-1.5 rounded-full bg-crimson animate-pulse" />
        <span className="text-[10px] font-mono font-bold uppercase tracking-[0.35em] text-crimson">
          Cross-Discipline Fusion
        </span>
        <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: "rgba(240,237,232,0.3)" }}>
          — where ≥2 disciplines converge in space &amp; time
        </span>
      </div>

      {loading ? (
        <div className="px-5 py-6 flex items-center gap-2">
          <span className="w-3 h-3 border border-t-crimson rounded-full animate-spin"
            style={{ borderColor: "rgba(240,237,232,0.15)", borderTopColor: "#C80028" }} />
          <span className="text-[11px] font-mono uppercase tracking-wider" style={{ color: "rgba(240,237,232,0.35)" }}>
            Correlating sources…
          </span>
        </div>
      ) : items.length === 0 ? (
        <div className="px-5 py-6">
          <p className="text-[11px] leading-relaxed" style={{ color: "rgba(240,237,232,0.4)" }}>
            No multi-discipline convergence detected in the current window. When independent
            disciplines (e.g. a MASINT quake, a HUMINT report, and a FININT market move) land on
            the same place and time, they surface here as a fused signal.
          </p>
        </div>
      ) : (
        <div className="flex overflow-x-auto divide-x" style={{ borderColor: "rgba(240,237,232,0.06)" }}>
          {items.map((row) => {
            const title = row.event?.canonical_title || row.event?.title;
            return (
              <button
                key={row.id}
                type="button"
                onClick={() => row.event && onOpen(row.id)}
                className="flex-shrink-0 w-[280px] text-left px-5 py-4 transition-colors"
                style={{ cursor: row.event ? "pointer" : "default" }}
                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "rgba(240,237,232,0.03)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = ""; }}
              >
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {row.disciplines.map((d) => <DisciplineBadge key={d} code={d} />)}
                </div>
                <p className="text-[13px] font-semibold leading-snug line-clamp-2 mb-2"
                  style={{ color: title ? "rgba(240,237,232,0.85)" : "rgba(240,237,232,0.45)" }}>
                  {title || `${row.disciplines.length}-discipline convergence`}
                </p>
                <div className="flex items-center gap-3 text-[9px] font-mono uppercase tracking-wider"
                  style={{ color: "rgba(240,237,232,0.4)" }}>
                  <span>{row.count} source{row.count !== 1 ? "s" : ""}</span>
                  <span>·</span>
                  <span style={{ color: "#C08A2E" }}>fusion {Math.round(row.index * 100)}%</span>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function IntFusion() {
  const navigate = useNavigate();
  const { isDark, toggle } = useTheme();

  const onOpen = (id) => navigate(`/event/${id}`);

  // Render order: SIGINT sits where the taxonomy lists it, but the special panel
  // is swapped in for it.
  const panels = useMemo(() => DISCIPLINES, []);

  return (
    <div className="min-h-screen bg-paper flex flex-col">
      {/* Masthead — consistent with FeedHeader */}
      <header style={{ backgroundColor: "#111111" }} className="sticky top-0 z-40">
        <div className="max-w-[1400px] mx-auto px-4 md:px-6 py-2.5 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate("/world")}
              className="text-[11px] font-mono uppercase tracking-wider hover:text-crimson transition-colors"
              style={{ color: "rgba(240,237,232,0.5)" }}
            >
              ← Feed
            </button>
            <div>
              <h1 className="font-display text-[1.5rem] md:text-[2rem] tracking-tighter leading-none" style={{ color: "#F0EDE8" }}>
                INT <span style={{ color: "#C80028" }}>FUSION</span>
              </h1>
              <p className="text-[7px] md:text-[8px] tracking-[0.35em] uppercase mt-0.5 hidden md:block" style={{ color: "rgba(240,237,232,0.3)" }}>
                All-source · seven disciplines · one graph
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <span className="hidden md:flex items-center gap-1.5 text-[9px] uppercase tracking-wider" style={{ color: "rgba(240,237,232,0.3)" }}>
              <span className="w-1.5 h-1.5 rounded-full bg-crimson animate-pulse" /> Live
            </span>
            <button
              onClick={toggle}
              className="text-[11px] font-mono uppercase tracking-wider hover:text-crimson transition-colors"
              style={{ color: "rgba(240,237,232,0.5)" }}
              title={isDark ? "Day mode" : "Night mode"}
            >
              {isDark ? "☀" : "☾"}
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-[1400px] w-full mx-auto px-4 md:px-6 py-6 pb-24 md:pb-6">
        <FusionStrip onOpen={onOpen} />

        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
          className="grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-3"
        >
          {panels.map((code) =>
            code === "SIGINT"
              ? <SigintPanel key={code} />
              : <DisciplinePanel key={code} code={code} onOpen={onOpen} />
          )}
        </motion.div>

        {/* Honest $0-ceiling footnote (plan requirement). */}
        <p className="text-[10px] text-ink/30 leading-relaxed mt-6 max-w-3xl">
          Coverage is honest about its ceiling at $0: <strong className="text-ink/45">SIGINT</strong> is
          transponder tracking only (ADS-B / AIS — no RF interception); <strong className="text-ink/45">IMINT</strong> is
          interpretation of provided imagery (no satellite tasking); <strong className="text-ink/45">GEOINT</strong> is
          geolocation and mapping of existing signals (no commercial imagery). All panels read the
          same live event graph the rest of Narrative runs on.
        </p>
      </main>
    </div>
  );
}
