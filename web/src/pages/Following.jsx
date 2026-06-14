import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import FeedHeader from "../components/layout/FeedHeader.jsx";
import { useFollowing } from "../hooks/useFollowing.js";
import { getCategoryColor } from "../lib/colors.js";
import { api } from "../lib/api.js";

const TYPE_COLORS = {
  VERIFIED:    "#2A6A40",
  INFERRED:    "#B07020",
  SPECULATIVE: "#6A3090",
};

const FALLBACK_CHAIN = [
  { type: "VERIFIED",    content: "Event confirmed by multiple primary sources." },
  { type: "INFERRED",    content: "Secondary effects propagating through connected systems." },
  { type: "SPECULATIVE", content: "Long-term implications remain uncertain pending further developments." },
];

function useEventDetail(eventId) {
  const [data, setData] = useState(null);
  useEffect(() => {
    if (!eventId) return;
    api.get(`/events/${eventId}`).then(setData).catch(() => {});
  }, [eventId]);
  return data;
}

function TrackedEvent({ event, onUnfollow, onOpenAnalysis }) {
  const [expanded, setExpanded] = useState(true);
  const detail   = useEventDetail(event.id);
  const color    = getCategoryColor(event.category);
  const since    = new Date(event.followedAt).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  const isLive   = event.current_status === "escalating" || event.current_status === "developing";

  const chain    = detail?.consequence_map?.consequence_chain || FALLBACK_CHAIN;
  const articles = detail?.articles || [];

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.2 }}
      className="border border-ink/10 bg-paper"
    >
      {/* Header */}
      <div
        className="px-4 sm:px-6 py-4 cursor-pointer flex items-start gap-3"
        onClick={() => setExpanded(e => !e)}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color }}>
              {event.category}
            </span>
            {isLive && (
              <span className="flex items-center gap-1 text-[10px] font-medium text-crimson">
                <span className="w-1 h-1 rounded-full bg-crimson animate-pulse" />
                Live
              </span>
            )}
            <span className="text-[10px] text-ink/30 ml-auto whitespace-nowrap">Since {since}</span>
          </div>
          <h3 className="text-[15px] font-semibold text-ink leading-snug">
            {event.canonical_title || event.title}
          </h3>
          {event.canonical_summary && (
            <p className="text-[13px] text-ink/50 mt-1 leading-relaxed line-clamp-2">
              {event.canonical_summary}
            </p>
          )}
        </div>
        <motion.svg
          animate={{ rotate: expanded ? 180 : 0 }}
          transition={{ duration: 0.18 }}
          width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5"
          className="text-ink/30 flex-shrink-0 mt-1"
        >
          <path d="M3 5l4 4 4-4" />
        </motion.svg>
      </div>

      {/* Expanded chain */}
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22 }}
            style={{ overflow: "hidden" }}
          >
            <div className="px-4 sm:px-6 pb-5" style={{ borderTop: "1px solid rgba(26,26,26,0.06)" }}>

              <p className="text-[9px] font-bold uppercase tracking-[0.35em] text-ink/30 mt-4 mb-3">
                Consequence Chain
              </p>

              <div className="space-y-0">
                {chain.map((step, i) => {
                  const tc = TYPE_COLORS[step.type] || TYPE_COLORS[step.evidence_type] || "#6A6A60";
                  const text = step.content || step.text || "";
                  return (
                    <div key={i} className="flex gap-3">
                      <div className="flex flex-col items-center flex-shrink-0 w-5">
                        <div
                          className="w-5 h-5 flex items-center justify-center text-[9px] font-bold flex-shrink-0"
                          style={{ backgroundColor: tc + "15", color: tc, border: `1px solid ${tc}35` }}
                        >
                          {i + 1}
                        </div>
                        {i < chain.length - 1 && (
                          <div className="w-px flex-1 mt-1 mb-1" style={{ backgroundColor: tc + "20", minHeight: 12 }} />
                        )}
                      </div>
                      <div className="flex-1 pb-3 min-w-0">
                        <span
                          className="inline-block text-[9px] font-mono uppercase tracking-widest border px-1.5 py-px mb-1.5"
                          style={{ color: tc, borderColor: tc + "30" }}
                        >
                          {step.type || step.evidence_type || "—"}
                        </span>
                        <p className="text-[13px] text-ink/80 leading-relaxed">{text}</p>
                      </div>
                    </div>
                  );
                })}
              </div>

              {articles.length > 0 && (
                <>
                  <p className="text-[9px] font-bold uppercase tracking-[0.35em] text-ink/30 mt-4 mb-2">Sources</p>
                  <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1">
                    {articles.map((a, i) => (
                      <a
                        key={i}
                        href={a.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex-shrink-0 border border-ink/10 px-3 py-2 hover:border-ink/25 transition-colors"
                        style={{ minWidth: 160, maxWidth: 200 }}
                        onClick={e => e.stopPropagation()}
                      >
                        <p className="text-[9px] font-bold uppercase tracking-wider text-ink/40 mb-1">
                          {a.source}{a.date ? ` · ${a.date}` : ""}
                        </p>
                        <p className="text-[12px] text-ink/70 leading-snug line-clamp-2">{a.title}</p>
                      </a>
                    ))}
                  </div>
                </>
              )}

              <div className="flex items-center gap-4 mt-4 pt-4" style={{ borderTop: "1px solid rgba(26,26,26,0.06)" }}>
                <button
                  onClick={() => onOpenAnalysis(event.id)}
                  className="text-[11px] font-semibold uppercase tracking-wider text-crimson hover:underline"
                >
                  Full Analysis →
                </button>
                <button
                  onClick={() => onUnfollow(event.id)}
                  className="ml-auto text-[11px] text-ink/30 hover:text-crimson transition-colors uppercase tracking-wider"
                >
                  Unfollow
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function Following() {
  const navigate = useNavigate();
  const { followed, unfollow } = useFollowing();
  const [activeTab, setActiveTab] = useState("following");

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-paper">
      <FeedHeader
        activeTab={activeTab}
        onTabChange={(tab) => { if (tab === "feed" || tab === "world") navigate("/world"); else setActiveTab(tab); }}
        activeCategory={null}
        onCategoryChange={() => {}}
        searchValue=""
        onSearchChange={() => {}}
      />

      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 py-6 pb-28 md:pb-8">

          <div className="flex items-baseline justify-between mb-6">
            <div>
              <h2 className="font-display text-2xl text-ink tracking-tight">TRACKED EVENTS</h2>
              <p className="text-[12px] text-ink/40 mt-0.5">
                {followed.length === 0
                  ? "No events tracked yet"
                  : `${followed.length} event${followed.length !== 1 ? "s" : ""} — chains update as events develop`}
              </p>
            </div>
          </div>

          {followed.length === 0 && (
            <div className="border border-ink/10 p-8 sm:p-12 text-center">
              <svg width="28" height="28" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" className="text-ink/20 mx-auto mb-4">
                <path d="M7 1.5C5.5 1.5 3.5 2.8 3.5 5.2c0 2.8 3.5 6.8 3.5 6.8s3.5-4 3.5-6.8C10.5 2.8 8.5 1.5 7 1.5z" />
              </svg>
              <p className="text-[13px] text-ink/40 mb-4">
                Tap the bookmark icon on any event to start tracking its consequence chain.
              </p>
              <button
                onClick={() => navigate("/world")}
                className="text-[11px] font-bold uppercase tracking-widest border border-ink/20 px-5 py-2.5 hover:border-crimson hover:text-crimson transition-colors"
              >
                Go to Intelligence Feed →
              </button>
            </div>
          )}

          <AnimatePresence>
            <div className="space-y-3">
              {followed.map(event => (
                <TrackedEvent
                  key={event.id}
                  event={event}
                  onUnfollow={unfollow}
                  onOpenAnalysis={(id) => navigate(`/world?event=${id}`)}
                />
              ))}
            </div>
          </AnimatePresence>

        </div>
      </div>
    </div>
  );
}
