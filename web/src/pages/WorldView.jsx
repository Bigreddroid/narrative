import { useState, useCallback, useMemo, useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useNavigate, useSearchParams } from "react-router-dom";
import FeedHeader from "../components/layout/FeedHeader.jsx";
import WorldMap from "../components/graph/WorldMap.jsx";
import EventGraph from "../components/graph/EventGraph.jsx";
import DeckView from "../components/DeckView.jsx";
import ExposurePanel from "../components/ExposurePanel.jsx";
import LiveNewsTab from "../components/livenews/LiveNewsTab.jsx";
import { useWorldGraph } from "../hooks/useWorldGraph.js";
import { useEventFeed } from "../hooks/useEventFeed.js";
import { useVesselFeed } from "../hooks/useVesselFeed.js";
import { useAircraftFeed } from "../hooks/useAircraftFeed.js";
import { MOCK_EVENTS, MOCK_EDGES } from "../lib/mockData.js";
import { DEMO_MODE } from "../lib/demoMode.js";
import { associate, trafficByEvent as buildTrafficByEvent, detectAnomaly } from "../lib/geoAssoc.js";
import { useSearch } from "../hooks/useSearch.js";
import { useFollowing } from "../hooks/useFollowing.js";
import { getCategoryColor } from "../lib/colors.js";
import { biasLabel, BIAS_COLORS } from "../lib/bias.js";
import { useTheme } from "../hooks/useTheme.js";
import { useUser } from "../hooks/useUser.js";
import { useMediaQuery } from "../hooks/useMediaQuery.js";

function Highlight({ text, query }) {
  if (!query || !text) return text;
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return text;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-crimson/20 text-crimson rounded-sm px-px">{text.slice(idx, idx + query.length)}</mark>
      {text.slice(idx + query.length)}
    </>
  );
}

// ─── Newspaper event card ─────────────────────────────────────────────────────

function EventCard({ event, isSelected, onClick, onNavigate, following, onFollow, searchQuery = "" }) {
  const color      = getCategoryColor(event.category);
  const escalating = event.current_status === "escalating";
  const developing = event.current_status === "developing";
  const title      = event.canonical_title || event.title || "Untitled event";
  const summary    = event.canonical_summary || event.summary || "";
  const geo        = (event.geography || []).slice(0, 3).join(" · ");
  const score      = Math.round(event.importance_score || event.importance || 0);
  const lean       = event.source_bias ? biasLabel(event.source_bias) : null;

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={`border-b border-ink/10 group transition-colors ${isSelected ? "bg-ink/[0.04]" : "bg-paper"}`}
    >
      {/* Main tap area */}
      <div
        className="cursor-pointer px-4 md:px-6 pt-4 md:pt-5 pb-3 md:pb-4 hover:bg-ink/[0.02] transition-colors"
        onClick={() => onClick(event.id)}
      >
        {/* Category + status row */}
        <div className="flex items-center gap-2 mb-2">
          <span className="text-[10px] md:text-[11px] font-bold uppercase tracking-wider" style={{ color }}>{event.category}</span>
          {escalating && (
            <span className="flex items-center gap-1 text-[10px] md:text-[11px] font-medium text-crimson">
              <span className="w-1 h-1 rounded-full bg-crimson animate-pulse" /> Escalating
            </span>
          )}
          {developing && !escalating && <span className="text-[10px] md:text-[11px] text-ink/40">Developing</span>}
          {event.is_osint && (
            <span
              className="text-[9px] md:text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-sm"
              style={{ color: "#B07820", border: "1px solid rgba(176,120,32,0.4)" }}
              title="Open-source intelligence — unverified, AI-triaged"
            >
              OSINT{typeof event.confidence === "number" ? ` · ${Math.round(event.confidence * 100)}%` : ""}
            </span>
          )}
          <div className="ml-auto flex items-center gap-2">
            {score > 0 && <span className="text-[11px] text-ink/30 tabular-nums">{score}</span>}
            <button
              onClick={(e) => { e.stopPropagation(); onFollow(event); }}
              title={following ? "Unfollow" : "Track event"}
              className={`w-8 h-8 md:w-auto md:h-auto flex items-center justify-center transition-colors ${following ? "" : "text-ink/30 hover:text-crimson"}`}
              style={following ? { color: "#C80028" } : {}}
            >
              <svg width="15" height="15" viewBox="0 0 14 14" fill={following ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.4">
                <path d="M7 1.5C5.5 1.5 3.5 2.8 3.5 5.2c0 2.8 3.5 6.8 3.5 6.8s3.5-4 3.5-6.8C10.5 2.8 8.5 1.5 7 1.5z" />
              </svg>
            </button>
          </div>
        </div>

        {/* Title */}
        <h2 className="text-[16px] md:text-[17px] font-semibold leading-snug text-ink mb-2 group-hover:text-crimson transition-colors">
          <Highlight text={title} query={searchQuery} />
        </h2>

        {/* Summary */}
        {summary && (
          <p className="text-[13px] md:text-sm text-ink/55 leading-relaxed line-clamp-2 mb-3">
            <Highlight text={summary} query={searchQuery} />
          </p>
        )}

        {/* Footer */}
        <div className="flex items-center gap-3 text-xs text-ink/40">
          {geo && <span className="truncate">{geo}</span>}
          {lean && (
            <span className="flex items-center gap-1 flex-shrink-0" style={{ color: lean.color }}>
              <span className="w-1 h-1 rounded-full" style={{ backgroundColor: lean.color }} />
              {lean.label}
            </span>
          )}
          <span className="ml-auto flex-shrink-0 text-ink/30 group-hover:text-crimson transition-colors flex items-center gap-1">
            Analysis →
          </span>
        </div>
      </div>

    </motion.article>
  );
}

function EventCardSkeleton() {
  return (
    <div className="border-b border-ink/10 px-4 md:px-6 py-5 animate-pulse">
      <div className="flex gap-2 mb-3">
        <div className="h-4 bg-ink/10 rounded w-16" />
        <div className="h-4 bg-ink/10 rounded w-20" />
      </div>
      <div className="h-7 bg-ink/10 rounded w-4/5 mb-2" />
      <div className="h-4 bg-ink/10 rounded w-full mb-1" />
      <div className="h-4 bg-ink/10 rounded w-2/3 mb-4" />
      <div className="h-3 bg-ink/10 rounded w-32" />
    </div>
  );
}

// ─── Dark ink sidebar widgets ─────────────────────────────────────────────────

function SignalWidget({ events }) {
  const breaking = useMemo(() =>
    events.filter(e => e.current_status === "escalating")
      .sort((a, b) => (b.importance_score || 0) - (a.importance_score || 0))
      .slice(0, 5),
    [events]
  );

  const stats = useMemo(() => {
    if (!events.length) return null;
    const cats = {};
    events.forEach(e => { const c = e.category || "other"; cats[c] = (cats[c] || 0) + 1; });
    const top = Object.entries(cats).sort((a, b) => b[1] - a[1]).slice(0, 4);
    return { total: events.length, escalating: breaking.length, top };
  }, [events, breaking]);

  const FG    = "#F0EDE8";
  const FG30  = "rgba(240,237,232,0.30)";
  const FG20  = "rgba(240,237,232,0.20)";
  const FG40  = "rgba(240,237,232,0.40)";
  const FG80  = "rgba(240,237,232,0.80)";
  const FG50  = "rgba(240,237,232,0.50)";
  const BD    = "rgba(240,237,232,0.07)";

  return (
    <div className="h-full overflow-y-auto" style={{ backgroundColor: "#111111", color: FG }}>
      {/* Breaking header */}
      <div className="p-5" style={{ borderBottom: `1px solid ${BD}` }}>
        <div className="flex items-center gap-2 mb-1">
          <span className="w-1.5 h-1.5 rounded-full bg-crimson animate-pulse-fast" />
          <span className="text-[9px] font-mono font-bold uppercase tracking-[0.4em] text-crimson">
            Breaking Signals
          </span>
        </div>
        <p className="text-[9px] font-mono uppercase tracking-wider" style={{ color: FG30 }}>
          Active escalations
        </p>
      </div>

      <div style={{ borderTop: `0px solid ${BD}` }}>
        {breaking.map(e => {
          const color = getCategoryColor(e.category);
          return (
            <div key={e.id} className="p-5 flex gap-3 items-start transition-colors"
              style={{ borderBottom: `1px solid ${BD}` }}
              onMouseEnter={ev => ev.currentTarget.style.backgroundColor = "rgba(240,237,232,0.03)"}
              onMouseLeave={ev => ev.currentTarget.style.backgroundColor = ""}
            >
              <div className="w-[2px] flex-shrink-0 self-stretch" style={{ backgroundColor: color + "80" }} />
              <div className="min-w-0">
                <p className="text-xs font-semibold leading-snug line-clamp-2 mb-1" style={{ color: FG80 }}>
                  {e.canonical_title || e.title}
                </p>
                <p className="text-[9px] font-mono uppercase tracking-wider" style={{ color }}>
                  {e.category}
                </p>
              </div>
            </div>
          );
        })}

        {breaking.length === 0 && (
          <div className="p-5">
            <p className="text-[10px] font-mono uppercase tracking-wider" style={{ color: FG20 }}>
              No active escalations
            </p>
          </div>
        )}
      </div>

      {/* Signal stats */}
      {stats && (
        <div className="p-5 mt-4" style={{ borderTop: `1px solid ${BD}` }}>
          <p className="text-[9px] font-mono font-bold uppercase tracking-[0.4em] mb-4" style={{ color: FG40 }}>
            Signal Metrics
          </p>
          <div className="space-y-2.5">
            <div className="flex justify-between text-[10px] font-mono">
              <span className="uppercase tracking-wider" style={{ color: FG40 }}>Active events</span>
              <span className="tabular-nums" style={{ color: FG80 }}>{stats.total}</span>
            </div>
            <div className="flex justify-between text-[10px] font-mono">
              <span className="text-crimson uppercase tracking-wider">Escalating</span>
              <span className="text-crimson tabular-nums font-bold">{stats.escalating}</span>
            </div>
            <div className="my-3" style={{ borderTop: `1px solid ${BD}` }} />
            {stats.top.map(([cat, count]) => (
              <div key={cat} className="flex justify-between text-[10px] font-mono">
                <span className="uppercase tracking-wider" style={{ color: FG30 }}>{cat}</span>
                <span className="tabular-nums" style={{ color: FG50 }}>{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer note */}
      <div className="p-5" style={{ borderTop: `1px solid ${BD}` }}>
        <p className="text-[9px] font-mono uppercase tracking-wider leading-relaxed" style={{ color: FG20 }}>
          Intelligence updated continuously. Consequence chains powered by AI analysis of global source signals.
        </p>
      </div>
    </div>
  );
}

// ─── Feed view ────────────────────────────────────────────────────────────────

function FeedView({ selectedEventId, onEventSelect, onEventClose, category, onCategoryChange, search }) {
  const [status, setStatus] = useState(null);
  const { events, loading: feedLoading } = useEventFeed({ category, status, limit: 60 });
  const { results: searchResults, loading: searchLoading } = useSearch(search);
  const { follow, unfollow, isFollowing } = useFollowing();
  const navigate = useNavigate();

  const isSearching = search.trim().length >= 2;
  const displayEvents = isSearching ? searchResults : events;
  const loading = isSearching ? searchLoading : feedLoading;

  const STATUSES = ["All", "Escalating", "Developing", "Stable"];

  return (
    <div className="flex-1 min-h-0 flex overflow-hidden">
      {/* Center column — capped at readable width */}
      <div className="flex-1 overflow-y-auto min-w-0">
        <div className="max-w-2xl mx-auto pb-20 md:pb-0">

        {/* Status filter strip — hidden during search */}
        {!isSearching && (
          <div className="border-b border-ink/10 px-4 md:px-6 flex items-center gap-4 md:gap-6 overflow-x-auto">
            {STATUSES.map(s => {
              const val = s === "All" ? null : s.toLowerCase();
              const active = status === val;
              return (
                <button
                  key={s}
                  type="button"
                  onClick={() => setStatus(active ? null : val)}
                  className={`text-[11px] font-semibold uppercase tracking-wider py-3 border-b-2 transition-colors -mb-px ${
                    active ? "border-crimson text-crimson" : "border-transparent text-ink/35 hover:text-crimson"
                  }`}
                >
                  {s}
                </button>
              );
            })}
          </div>
        )}

        {/* Search results header */}
        {isSearching && (
          <div className="border-b border-ink/10 px-4 md:px-6 py-3 flex items-center gap-3">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-ink/40">
              Search
            </span>
            <span className="text-[11px] font-mono text-crimson">"{search}"</span>
            {!searchLoading && (
              <span className="ml-auto text-[10px] font-mono text-ink/30">
                {displayEvents.length} result{displayEvents.length !== 1 ? "s" : ""}
              </span>
            )}
            {searchLoading && (
              <span className="ml-auto w-3 h-3 border border-t-crimson rounded-full animate-spin"
                style={{ borderColor: "rgba(26,26,26,0.1)", borderTopColor: "#C80028" }} />
            )}
          </div>
        )}

        {/* Cards */}
        <div>
          {loading ? (
            Array(6).fill(0).map((_, i) => <EventCardSkeleton key={i} />)
          ) : displayEvents.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 gap-2">
              <p className="text-xs font-mono text-ink/30 uppercase tracking-widest">
                {isSearching ? "No matching signals." : "No events yet."}
              </p>
              {isSearching && (
                <p className="text-[11px] text-ink/25">Try a different term or browse the feed.</p>
              )}
            </div>
          ) : (
            displayEvents.map(e => (
              <EventCard
                key={e.id}
                event={e}
                isSelected={e.id === selectedEventId}
                onClick={onEventSelect}
                onNavigate={(id) => navigate(`/event/${id}`)}
                following={isFollowing(e.id)}
                onFollow={(ev) => isFollowing(ev.id) ? unfollow(ev.id) : follow(ev)}
                searchQuery={isSearching ? search : ""}
              />
            ))
          )}
        </div>
        </div>{/* /max-w-2xl */}
      </div>{/* /center column */}

      {/* Right panel: EventGraph or dark signal widgets */}
      <div className="w-96 flex-shrink-0 hidden lg:block relative border-l border-ink/10 overflow-hidden">
        <AnimatePresence mode="wait">
          {selectedEventId ? (
            <motion.div
              key="graph"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              style={{ position: "absolute", inset: 0 }}
            >
              <EventGraph eventId={selectedEventId} onClose={onEventClose} />
            </motion.div>
          ) : (
            <motion.div
              key="widgets"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              style={{ position: "absolute", inset: 0, overflow: "hidden" }}
            >
              <SignalWidget events={events} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

// ─── World view tab ───────────────────────────────────────────────────────────

const MAP_REGIONS = [
  { id: "world",    label: "World"    },
  { id: "americas", label: "Americas" },
  { id: "europe",   label: "Europe"   },
  { id: "asia",     label: "Asia"     },
  { id: "india",    label: "India"    },
  { id: "africa",   label: "Africa"   },
];

function WorldViewTab({ selectedEventId, onEventSelect, onEventClose }) {
  const { nodes, edges, loading } = useWorldGraph();
  const [region, setRegion]       = useState("world");
  const [maritime, setMaritime]   = useState(false);
  const [air, setAir]             = useState(false);
  const { isDark }                = useTheme();
  const { can }                   = useUser();
  const { getVessels, vesselCount, live } = useVesselFeed(maritime);
  const { getAircraft, aircraftCount, live: airLive } = useAircraftFeed(air);
  const [exposureLayer, setExposureLayer] = useState(false);

  // Live traffic→event association, refreshed gently; feeds the CPE disruption term.
  const [trafficByEvent, setTrafficByEvent] = useState({});
  useEffect(() => {
    const tick = () => {
      const items = [
        ...((maritime && getVessels) ? getVessels() : []).map((v) => ({ id: v.mmsi, lat: v.lat, lng: v.lng, kind: "vessel" })),
        ...((air && getAircraft) ? getAircraft() : []).map((a) => ({ id: a.icao, lat: a.lat, lng: a.lng, kind: "aircraft" })),
      ];
      const evs = nodes.map((n) => ({ id: n.id, lat: n.lat, lng: n.lng, importance: n.importance }));
      setTrafficByEvent(buildTrafficByEvent(associate(evs, items).zonesByEvent));
    };
    tick();
    const id = setInterval(tick, 4000);
    return () => clearInterval(id);
  }, [maritime, air, getVessels, getAircraft, nodes]);

  // Per-event exposure heat for the globe heat layer. The engine is the
  // trade-secret CPE, so it is loaded lazily and ONLY in the offline demo build
  // (this import is dead-code-eliminated from production). In production the heat
  // is served by the backend (event_scores from /api/v1/exposure).
  const [exposureModel, setExposureModel] = useState({ eventScores: {} });
  useEffect(() => {
    if (!DEMO_MODE) return;
    let alive = true;
    import("../lib/propagation.js").then(({ computeExposureModel }) => {
      if (alive) setExposureModel(computeExposureModel(MOCK_EVENTS, MOCK_EDGES, { trafficByEvent }));
    });
    return () => { alive = false; };
  }, [trafficByEvent]);

  // Traffic anomalies: events whose nearby traffic deviates from the cross-event baseline.
  const anomalies = useMemo(() => {
    const counts = Object.values(trafficByEvent).map((t) => (t.vessels || 0) + (t.aircraft || 0)).filter((c) => c > 0);
    if (counts.length < 3) return {};
    const mean = counts.reduce((a, b) => a + b, 0) / counts.length;
    const std = Math.sqrt(counts.reduce((a, b) => a + (b - mean) ** 2, 0) / counts.length);
    const out = {};
    for (const [id, t] of Object.entries(trafficByEvent)) {
      const an = detectAnomaly((t.vessels || 0) + (t.aircraft || 0), { mean, std });
      if (an) out[id] = an;
    }
    return out;
  }, [trafficByEvent]);
  const handleNodeClick = useCallback((node) => onEventSelect(node.id), [onEventSelect]);

  const mapBg = isDark ? "#0E1520" : "#C8D8E4";
  const tabActiveColor = isDark ? "#E8E4DC" : "#1A1A1A";
  const tabInactiveColor = isDark ? "rgba(232,228,220,0.35)" : "rgba(26,26,26,0.35)";

  return (
    <div className="flex-1 flex flex-col overflow-hidden" style={{ backgroundColor: mapBg }}>

      {/* Region tab bar */}
      <div
        className="flex-shrink-0 flex items-center overflow-x-auto z-10"
        style={{
          scrollbarWidth: "none",
          msOverflowStyle: "none",
          backgroundColor: isDark ? "rgba(17,17,17,0.97)" : "rgba(245,241,235,0.97)",
          borderBottom: `1px solid ${isDark ? "rgba(232,228,220,0.10)" : "rgba(26,26,26,0.10)"}`,
          backdropFilter: "blur(8px)",
        }}
      >
        {MAP_REGIONS.map(r => {
          const locked = r.id !== "world" && !can("worldRegions");
          return (
            <button
              key={r.id}
              onClick={() => !locked && setRegion(r.id)}
              className="relative flex-shrink-0 px-3 sm:px-5 py-3 text-[11px] font-bold uppercase tracking-widest transition-colors flex items-center gap-1"
              style={{
                color: locked ? (isDark ? "rgba(232,228,220,0.18)" : "rgba(26,26,26,0.18)")
                              : region === r.id ? tabActiveColor : tabInactiveColor,
                cursor: locked ? "default" : "pointer",
              }}
            >
              {r.label}
              {locked && (
                <svg width="8" height="8" viewBox="0 0 8 8" fill="none" stroke="currentColor" strokeWidth="1.2" style={{ opacity: 0.4 }}>
                  <rect x="1" y="3.5" width="6" height="4" rx="0.5" />
                  <path d="M2.5 3.5V2.5a1.5 1.5 0 0 1 3 0v1" />
                </svg>
              )}
              {region === r.id && !locked && (
                <motion.div
                  layoutId="region-indicator"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-crimson"
                />
              )}
            </button>
          );
        })}

        {/* Event count badge */}
        {!loading && nodes.length > 0 && (
          <div className="ml-auto flex items-center gap-2 text-[10px] text-ink/35 tracking-wide">
            <span className="w-1.5 h-1.5 rounded-full bg-crimson" style={{ boxShadow: "0 0 4px #C80028" }} />
            {nodes.length} events mapped
          </div>
        )}

        {/* Maritime layer toggle */}
        <button
          onClick={() => setMaritime((m) => !m)}
          className="flex-shrink-0 ml-3 mr-1 flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest transition-colors border"
          style={{
            color: maritime ? "#E8E4DC" : tabInactiveColor,
            borderColor: maritime ? "rgba(63,167,160,0.6)" : (isDark ? "rgba(232,228,220,0.12)" : "rgba(26,26,26,0.12)"),
            backgroundColor: maritime ? "rgba(63,167,160,0.12)" : "transparent",
          }}
          title="Toggle live ship tracking"
        >
          <svg width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round">
            <path d="M7 1.5v7M7 8.5L2 7l1 4.2a6 6 0 0 0 8 0L12 7 7 8.5zM4.5 4h5" />
          </svg>
          Maritime
        </button>

        {/* Maritime live/sim badge + count */}
        {maritime && (
          <div className="flex-shrink-0 mr-3 flex items-center gap-1.5 text-[10px] tracking-wide" style={{ color: "#3FA7A0" }}>
            <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: "#3FA7A0" }} />
            <span className="font-bold uppercase">{live ? "Live AIS" : vesselCount > 0 ? "Simulated" : "No AIS source"}</span>
            <span style={{ color: isDark ? "rgba(232,228,220,0.4)" : "rgba(26,26,26,0.4)" }}>· {vesselCount} vessels</span>
          </div>
        )}

        {/* Air-traffic layer toggle */}
        <button
          onClick={() => setAir((a) => !a)}
          className="flex-shrink-0 ml-1 mr-1 flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest transition-colors border"
          style={{
            color: air ? "#E8E4DC" : tabInactiveColor,
            borderColor: air ? "rgba(91,163,208,0.6)" : (isDark ? "rgba(232,228,220,0.12)" : "rgba(26,26,26,0.12)"),
            backgroundColor: air ? "rgba(91,163,208,0.12)" : "transparent",
          }}
          title="Toggle live air-traffic tracking"
        >
          <svg width="12" height="12" viewBox="0 0 14 14" fill="currentColor">
            <path d="M13 8.2 8.3 7 7.4 1.6C7.3 1.2 7.2 1 7 1s-.3.2-.4.6L5.7 7 1 8.2v1L5.6 8.8l-.3 2.6L4 12v.9L7 12l3 .9V12l-1.3-.6-.3-2.6L13 9.2z" />
          </svg>
          Air
        </button>

        {/* Air live/sim badge + count */}
        {air && (
          <div className="flex-shrink-0 mr-3 flex items-center gap-1.5 text-[10px] tracking-wide" style={{ color: "#5BA3D0" }}>
            <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: "#5BA3D0" }} />
            <span className="font-bold uppercase">{airLive ? "Live OpenSky" : aircraftCount > 0 ? "Simulated" : "No source"}</span>
            <span style={{ color: isDark ? "rgba(232,228,220,0.4)" : "rgba(26,26,26,0.4)" }}>· {aircraftCount} flights</span>
          </div>
        )}

        {/* Exposure heat layer toggle */}
        <button
          onClick={() => setExposureLayer((x) => !x)}
          className="flex-shrink-0 ml-1 mr-3 flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest transition-colors border"
          style={{
            color: exposureLayer ? "#E8E4DC" : tabInactiveColor,
            borderColor: exposureLayer ? "rgba(217,102,58,0.6)" : (isDark ? "rgba(232,228,220,0.12)" : "rgba(26,26,26,0.12)"),
            backgroundColor: exposureLayer ? "rgba(217,102,58,0.14)" : "transparent",
          }}
          title="Tint events & traffic by Exposure Index"
        >
          <svg width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round">
            <path d="M7 1.5c2 2.5 3.5 4.2 3.5 6.5a3.5 3.5 0 1 1-7 0C3.5 5.7 5 4 7 1.5z" />
          </svg>
          Exposure
        </button>

        {/* Traffic anomaly indicator */}
        {Object.keys(anomalies).length > 0 && (
          <div className="flex-shrink-0 mr-3 flex items-center gap-1.5 text-[10px] tracking-wide" style={{ color: "#D9A227" }}>
            <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: "#D9A227" }} />
            <span className="font-bold uppercase">{Object.keys(anomalies).length} traffic {Object.keys(anomalies).length === 1 ? "anomaly" : "anomalies"}</span>
          </div>
        )}
      </div>

      {/* Map area */}
      <div className="flex-1 relative overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-full" style={{ backgroundColor: mapBg }}>
            <div className="text-center">
              <div className="w-6 h-6 border-2 border-t-crimson rounded-full animate-spin mx-auto mb-3"
                style={{ borderColor: isDark ? "rgba(232,228,220,0.1)" : "rgba(26,26,26,0.1)", borderTopColor: "#C80028" }} />
              <p className="text-[11px] uppercase tracking-wider" style={{ color: isDark ? "rgba(232,228,220,0.3)" : "rgba(26,26,26,0.3)" }}>
                Loading consequence map
              </p>
            </div>
          </div>
        ) : (
          <WorldMap
            nodes={nodes}
            edges={edges}
            selectedNodeId={selectedEventId}
            onNodeClick={handleNodeClick}
            region={region}
            isDark={isDark}
            getVessels={getVessels}
            showVessels={maritime}
            getAircraft={getAircraft}
            showAircraft={air}
            eventScores={exposureModel.eventScores}
            exposureLayer={exposureLayer}
            anomalies={anomalies}
          />
        )}

        {/* EventGraph panel overlay — desktop only */}
        <AnimatePresence>
          {selectedEventId && (
            <motion.div
              initial={{ opacity: 0, x: 40 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 40 }}
              transition={{ type: "spring", stiffness: 300, damping: 30 }}
              className="hidden lg:block absolute top-4 right-4 bottom-4 overflow-hidden z-30 shadow-2xl"
              style={{ width: 480 }}
            >
              <EventGraph eventId={selectedEventId} onClose={onEventClose} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

// ─── Root ─────────────────────────────────────────────────────────────────────

export default function WorldView() {
  const navigate             = useNavigate();
  const [searchParams]       = useSearchParams();
  const [activeTab,       setActiveTab]       = useState(() => {
    const t = searchParams.get("tab");
    return t === "world" || t === "deck" || t === "exposure" || t === "live-news" ? t : "feed";
  });
  const [selectedEventId, setSelectedEventId] = useState(null);
  const [category,        setCategory]        = useState(null);
  const [search,          setSearch]          = useState("");
  // Below lg the inline detail overlay is hidden (hidden lg:block), so route to
  // the full detail page instead. Reactive via matchMedia, not a one-shot read.
  const isBelowLg = useMediaQuery("(max-width: 1023px)");

  const handleSelect  = useCallback((id) => {
    if (isBelowLg) { navigate(`/event/${id}`); return; }
    setSelectedEventId(prev => prev === id ? null : id);
  }, [navigate, isBelowLg]);
  const handleClose   = useCallback(() => setSelectedEventId(null), []);
  const handleTabChange = useCallback((tab) => {
    if (tab === "following") { navigate("/following"); return; }
    setActiveTab(tab);
    setSelectedEventId(null);
  }, [navigate]);

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-paper">
      <FeedHeader
        activeCategory={category}
        onCategoryChange={(cat) => { setCategory(cat); setSelectedEventId(null); }}
        activeTab={activeTab}
        onTabChange={handleTabChange}
        searchValue={search}
        onSearchChange={setSearch}
      />

      <div className="flex-1 min-h-0 flex overflow-hidden">
        {activeTab === "feed" ? (
          <FeedView
            selectedEventId={selectedEventId}
            onEventSelect={handleSelect}
            onEventClose={handleClose}
            category={category}
            onCategoryChange={setCategory}
            search={search}
          />
        ) : activeTab === "deck" ? (
          <DeckView
            selectedEventId={selectedEventId}
            onEventSelect={handleSelect}
            onEventClose={handleClose}
          />
        ) : activeTab === "exposure" ? (
          <ExposurePanel />
        ) : activeTab === "live-news" ? (
          <LiveNewsTab />
        ) : (
          <WorldViewTab
            selectedEventId={selectedEventId}
            onEventSelect={handleSelect}
            onEventClose={handleClose}
          />
        )}
      </div>
    </div>
  );
}
