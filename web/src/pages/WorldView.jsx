import { useState, useCallback, useMemo } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useNavigate, useSearchParams } from "react-router-dom";
import FeedHeader from "../components/layout/FeedHeader.jsx";
import WorldMap from "../components/graph/WorldMap.jsx";
import EventGraph from "../components/graph/EventGraph.jsx";
import { useWorldGraph } from "../hooks/useWorldGraph.js";
import { useEventFeed } from "../hooks/useEventFeed.js";
import { useSearch } from "../hooks/useSearch.js";
import { useFollowing } from "../hooks/useFollowing.js";
import { getCategoryColor } from "../lib/colors.js";
import { biasLabel, BIAS_COLORS } from "../lib/bias.js";
import { useTheme } from "../hooks/useTheme.js";
import { useUser } from "../hooks/useUser.js";

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
      <div className="flex w-full max-w-[1400px] mx-auto min-w-0">
      {/* Center column — fills up to the rail (no awkward middle gap) */}
      <div className="flex-1 overflow-y-auto min-w-0">
        <div className="w-full pb-20 md:pb-0">

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
      <div className="w-80 flex-shrink-0 hidden lg:block relative border-l border-ink/10 overflow-hidden">
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
              <EventGraph eventId={selectedEventId} onClose={onEventClose} onSelectRelated={onEventSelect} />
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
  const { isDark }                = useTheme();
  const { can }                   = useUser();
  const handleNodeClick = useCallback((node) => onEventSelect(node.id), [onEventSelect]);

  const mapBg     = isDark ? "#060809" : "#F5F1EB";
  const tabBg     = isDark ? "rgba(6,8,9,0.97)" : "rgba(245,241,235,0.97)";
  const headerBg  = isDark ? "#08090C" : "#F5F1EB";
  const stripBg   = isDark ? "#08090C" : "#F5F1EB";
  const tabActiveColor   = isDark ? "#E8E4DC" : "#1A1A1A";
  const tabInactiveColor = isDark ? "rgba(232,228,220,0.30)" : "rgba(26,26,26,0.35)";
  const cardBg    = isDark ? "#111620" : "#FFFFFF";
  const cardBorder = isDark ? "rgba(255,255,255,0.07)" : "rgba(26,26,26,0.1)";

  return (
    <div className="flex-1 w-full max-w-[1400px] mx-auto flex flex-col overflow-hidden" style={{ backgroundColor: mapBg }}>

      {/* Region tab bar + World News header (desktop mock style) */}
      <div
        className="flex-shrink-0 flex items-center overflow-x-auto z-10"
        style={{
          scrollbarWidth: "none",
          msOverflowStyle: "none",
          backgroundColor: tabBg,
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
      </div>

      {/* World News serif header — matches mockup large bold title */}
      <div
        className="flex-shrink-0 px-4 md:px-6 py-3 md:py-4 flex items-center gap-4"
        style={{
          backgroundColor: headerBg,
          borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : 'rgba(26,26,26,0.08)'}`,
        }}
      >
        <span className="text-lg md:text-xl" style={{ color: isDark ? 'rgba(232,228,220,0.35)' : 'rgba(26,26,26,0.35)' }}>≡</span>
        <span
          className="text-xl md:text-3xl font-bold tracking-tight"
          style={{ fontFamily: 'Georgia, "Times New Roman", serif', color: isDark ? '#E8E4DC' : '#1A1A1A', letterSpacing: '-0.5px' }}
        >
          World News
        </span>
        <div className="ml-auto flex items-center gap-3">
          {/* Apr → filter pill */}
          <div
            className="hidden md:flex items-center gap-2 px-4 py-1 rounded-full border text-sm"
            style={{
              borderColor: isDark ? 'rgba(232,228,220,0.2)' : 'rgba(26,26,26,0.2)',
              color: isDark ? 'rgba(232,228,220,0.55)' : 'rgba(26,26,26,0.55)',
            }}
          >
            {new Date().toLocaleDateString('en-US', { month: 'short' })}
            <span style={{ color: isDark ? 'rgba(232,228,220,0.35)' : 'rgba(26,26,26,0.35)' }}>›</span>
          </div>
          {/* Live indicator */}
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-crimson animate-pulse" style={{ boxShadow: '0 0 4px #C80028' }} />
            <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: isDark ? 'rgba(232,228,220,0.4)' : 'rgba(26,26,26,0.4)' }}>
              Live · {new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            </span>
          </div>
        </div>
      </div>

      {/* Map area (70%) + stories below (30%) */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-[8] min-h-0 relative overflow-hidden">
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
                style={{ width: 420 }}
              >
                <EventGraph eventId={selectedEventId} onClose={onEventClose} onSelectRelated={onEventSelect} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Bottom "How this affects you" strip — desktop mock style: dense terminal cards with crimson impact */}
        {!loading && nodes.length > 0 && (
          <div className="flex-[2] min-h-0 border-t px-4 md:px-6 py-4 overflow-y-auto" style={{ backgroundColor: stripBg, borderColor: cardBorder }}>
            <div className="text-[10px] font-mono uppercase tracking-[2px] mb-2" style={{ color: isDark ? 'rgba(232,228,220,0.4)' : 'rgba(26,26,26,0.4)' }}>
              How this affects you
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
              {nodes.slice(0, 6).map((node, idx) => {
                const catColor = getCategoryColor(node.category);
                const impactLine = {
                  geopolitics: "Supply chain shocks · Energy prices up",
                  economics:   "Higher borrowing costs · Market volatility",
                  climate:     "Crop losses · Food price spikes",
                  health:      "Healthcare costs · Workforce disruption",
                  technology:  "Data privacy exposure · Market shifts",
                  security:    "Travel disruption · Insurance premiums",
                }[node.category] || (node.current_status === "escalating" ? "Escalating regional impacts" : "Developing cross-sector effects");

                return (
                  <div
                    key={node.id || idx}
                    onClick={() => handleNodeClick(node)}
                    className="rounded-lg border p-3.5 cursor-pointer transition-all hover:-translate-y-0.5 hover:shadow-md"
                    style={{ backgroundColor: cardBg, borderColor: cardBorder }}
                  >
                    <div className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: catColor }}>
                      {node.category}
                    </div>
                    <div className="text-[12px] font-semibold leading-snug line-clamp-2 mb-2" style={{ color: isDark ? '#E8E4DC' : '#1A1A1A' }}>
                      {node.title || node.canonical_title}
                    </div>
                    <div className="text-[9px] leading-snug line-clamp-2 mb-1.5" style={{ color: isDark ? 'rgba(232,228,220,0.7)' : 'rgba(26,26,26,0.6)' }}>
                      {impactLine}
                    </div>
                    <div>
                      <span className="text-[8px] font-bold px-1 py-0.5 rounded" style={{ backgroundColor: '#C80028', color: '#fff' }}>
                        Bias
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Root ─────────────────────────────────────────────────────────────────────

export default function WorldView() {
  const navigate             = useNavigate();
  const [searchParams]       = useSearchParams();
  const [activeTab,       setActiveTab]       = useState(() => searchParams.get("tab") === "feed" ? "feed" : "world"); // default to world for desktop mock feel
  const [selectedEventId, setSelectedEventId] = useState(null);
  const [category,        setCategory]        = useState(null);
  const [search,          setSearch]          = useState("");

  const handleSelect  = useCallback((id) => {
    if (window.innerWidth < 1024) { navigate(`/event/${id}`); return; }
    setSelectedEventId(prev => prev === id ? null : id);
  }, [navigate]);
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
