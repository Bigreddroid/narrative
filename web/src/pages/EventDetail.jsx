import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { getCategoryColor, TYPE_COLORS, SEVERITY_COLORS } from "../lib/colors.js";
import { biasLabel, BIAS_COLORS, SOURCE_BIAS, calcEventBias } from "../lib/bias.js";
import { useEventGraph } from "../hooks/useEventGraph.js";
import { useFollowing } from "../hooks/useFollowing.js";
import { useTheme } from "../hooks/useTheme.js";
import { useUser } from "../hooks/useUser.js";
import TierGate from "../components/TierGate.jsx";

// ─── Sub-components ───────────────────────────────────────────────────────────

function ArticleCard({ article, index }) {
  const srcBias   = SOURCE_BIAS[article.source] || null;
  const lean      = srcBias ? biasLabel(srcBias) : null;
  const nameColor = lean?.color || "#6A6A60";
  const href      = article.url && article.url !== "#" ? article.url : undefined;

  return (
    <motion.a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      onClick={e => { if (!href) e.preventDefault(); }}
      initial={{ opacity: 0, x: 10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.06, duration: 0.2 }}
      className="flex-shrink-0 w-48 sm:w-52 border border-ink/10 bg-ink/[0.02] p-3 flex flex-col gap-2 hover:border-ink/25 transition-colors"
      style={{ textDecoration: "none" }}
    >
      <div className="flex items-center justify-between gap-1">
        <span className="text-[9px] font-mono font-bold uppercase tracking-widest truncate" style={{ color: nameColor }}>
          {article.source}
        </span>
        {lean && (
          <span className="text-[8px] font-mono uppercase tracking-wide flex-shrink-0" style={{ color: lean.color, opacity: 0.65 }}>
            {lean.label}
          </span>
        )}
      </div>
      <p className="text-[12px] text-ink leading-snug font-medium line-clamp-3 flex-1">{article.title}</p>
      {srcBias && (
        <div className="flex h-[3px] rounded-full overflow-hidden gap-px">
          <div style={{ width: `${srcBias.left}%`,   backgroundColor: BIAS_COLORS.left,   opacity: 0.85 }} />
          <div style={{ width: `${srcBias.center}%`, backgroundColor: BIAS_COLORS.center, opacity: 0.6  }} />
          <div style={{ width: `${srcBias.right}%`,  backgroundColor: BIAS_COLORS.right,  opacity: 0.85 }} />
        </div>
      )}
      <p className="text-[9px] text-ink/35 font-mono">{article.date}</p>
    </motion.a>
  );
}

function ChainStep({ node, index, categoryColor, totalSteps }) {
  const typeColor = TYPE_COLORS[node.type] || "#6A6A60";
  const short     = node.type === "VERIFIED FACT"      ? "VERIFIED"
    : node.type   === "INFERRED MECHANISM" ? "INFERRED"
    : node.type   === "SPECULATIVE EFFECT" ? "SPECULATIVE"
    : node.type || "";
  const text     = node.content || node.description || node.node || "";
  const children = node.children || node.sub_steps || [];

  return (
    <motion.div
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.12, duration: 0.22 }}
    >
      <div className="flex gap-4">
        <div className="flex flex-col items-center flex-shrink-0">
          <motion.div
            className="w-6 h-6 flex items-center justify-center text-[10px] font-mono font-bold flex-shrink-0"
            style={{ backgroundColor: categoryColor + "18", color: categoryColor, border: `1px solid ${categoryColor}40` }}
            initial={{ scale: 1.3 }}
            animate={{ scale: 1 }}
            transition={{ delay: index * 0.12 + 0.08, duration: 0.28 }}
          >
            {index + 1}
          </motion.div>
          {index < totalSteps - 1 && (
            <motion.div
              className="w-px flex-1 mt-1"
              style={{ backgroundColor: categoryColor + "20", minHeight: 18 }}
              initial={{ scaleY: 0, originY: "0%" }}
              animate={{ scaleY: 1 }}
              transition={{ delay: index * 0.12 + 0.2, duration: 0.22 }}
            />
          )}
        </div>
        <div className="flex-1 pb-5">
          <span
            className="inline-block text-[9px] font-mono uppercase tracking-widest border px-1.5 py-px mb-2"
            style={{ color: typeColor, borderColor: typeColor + "35" }}
          >
            {short}
          </span>
          <p className="text-[13px] sm:text-sm text-ink leading-relaxed">{text}</p>
          {node.evidence && (
            <p className="text-[11px] text-ink/45 mt-2 leading-relaxed pl-3 border-l border-ink/15">
              {node.evidence}
            </p>
          )}
          {children.length > 0 && (
            <div className="mt-3 ml-3">
              {children.map((child, ci) => (
                <ChainStep key={ci} node={child} index={ci} categoryColor={categoryColor} totalSteps={children.length} />
              ))}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}

function PredictionArc({ score, label }) {
  const r     = 32;
  const circ  = 2 * Math.PI * r;
  const pct   = Math.min(100, Math.max(0, score));
  const color = pct >= 70 ? "#C80028" : pct >= 40 ? "#B07020" : "#2A6A40";

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-20 h-20">
        <svg viewBox="0 0 80 80" className="w-full h-full -rotate-90">
          <circle cx="40" cy="40" r={r} fill="none" stroke="#1A1A1A" strokeWidth="2.5" opacity="0.08" />
          <motion.circle
            cx="40" cy="40" r={r} fill="none" stroke={color} strokeWidth="2.5"
            strokeLinecap="butt"
            strokeDasharray={circ}
            initial={{ strokeDashoffset: circ }}
            animate={{ strokeDashoffset: circ - (pct / 100) * circ }}
            transition={{ duration: 1.1, ease: "easeOut", delay: 0.3 }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="font-mono font-bold text-base text-ink">{pct}%</span>
        </div>
      </div>
      <span className="text-[9px] font-mono text-ink/40 text-center max-w-[80px] leading-tight capitalize">
        {label}
      </span>
    </div>
  );
}

function ImpactCard({ impact, index }) {
  const color = SEVERITY_COLORS[impact.severity?.toLowerCase()] || "#6A6A60";
  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.2 }}
      className="border border-ink/10 p-4"
      style={{ borderLeftColor: color, borderLeftWidth: 2 }}
    >
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[10px] font-mono uppercase tracking-wider text-ink/50 flex-1">
          {impact.sector || "Impact"}
        </span>
        {impact.severity && (
          <span className="text-[9px] font-mono border px-1.5 py-px uppercase flex-shrink-0"
            style={{ color, borderColor: color + "40" }}>
            {impact.severity}
          </span>
        )}
      </div>
      <p className="text-[13px] text-ink leading-snug">{impact.description}</p>
      {impact.population_affected && (
        <p className="text-[11px] text-ink/40 mt-1.5">{impact.population_affected}</p>
      )}
      {impact.evidence && (
        <p className="text-[11px] text-ink/40 border-t border-ink/10 pt-2.5 mt-2.5 leading-relaxed">
          {impact.evidence}
        </p>
      )}
    </motion.div>
  );
}

// ─── Mock fallback ────────────────────────────────────────────────────────────

function getMockEvent(eventId) {
  if (eventId === "1") {
    return {
      id: "1", category: "conflict", current_status: "escalating",
      canonical_title: "Red Sea Shipping Corridor Under Sustained Attack",
      canonical_summary: "Houthi missile and drone strikes on commercial vessels have reduced Red Sea cargo transit by 40%, forcing rerouting around the Cape of Good Hope.",
      geographic_relevance: ["Yemen", "Red Sea", "Gulf of Aden"], global_importance_score: 91,
      consequence_map: {
        consequence_chain: [
          { type: "VERIFIED FACT",      content: "Houthi forces launched 45+ attacks on merchant vessels since November, disrupting 12-15% of global container shipping." },
          { type: "INFERRED MECHANISM", content: "Rerouting via Cape of Good Hope adds 10-14 days and $400-800k per voyage in fuel costs." },
          { type: "SPECULATIVE EFFECT", content: "Prolonged disruption could trigger inflationary pressure if rerouting persists beyond Q2." },
        ],
        direct_impact:   [{ sector: "Shipping & Logistics", severity: "critical", description: "40% reduction in Red Sea transits; 3x spike in Suez insurance premiums.", population_affected: "Global supply chains" }],
        indirect_impact: [{ sector: "Consumer Prices",      severity: "medium",   description: "6-9% increase in imported goods costs projected for EU and US markets." }],
        predictions: [{ label: "Escalation", confidence: 72 }, { label: "Diplomatic Resolution", confidence: 18 }, { label: "Status Quo", confidence: 10 }],
      },
      articles: [
        { source: "Reuters",   title: "Houthi attacks push shipping firms to avoid Red Sea despite Navy escorts", url: "#", date: "2024-01-15" },
        { source: "Bloomberg", title: "Red Sea chaos forces rethink of supply chain strategies across Europe",   url: "#", date: "2024-01-14" },
      ],
    };
  }
  return {
    id: eventId, category: "geopolitics", current_status: "developing",
    canonical_title: "Intelligence Signal Under Analysis",
    canonical_summary: "Consequence chain analysis in progress. Connect backend for live AI-generated intelligence.",
    geographic_relevance: ["Global"], global_importance_score: 70,
    consequence_map: {
      consequence_chain: [
        { type: "VERIFIED FACT",      content: "Primary signal confirmed across multiple independent source clusters." },
        { type: "INFERRED MECHANISM", content: "Second-order effects propagating through interconnected systems." },
        { type: "SPECULATIVE EFFECT", content: "Long-term consequence trajectory requires further monitoring." },
      ],
      direct_impact:   [{ sector: "Analysis Pending", severity: "medium", description: "Live AI consequence chain requires backend connection." }],
      indirect_impact: [],
      predictions:     [{ label: "Developing", confidence: 65 }, { label: "Stable", confidence: 35 }],
    },
    articles: [],
  };
}

// ─── Page header (shared across loading / gated / main states) ────────────────

function PageHeader({ isDark, onToggle, following, onTrack, onBack, onHome }) {
  return (
    <header style={{ backgroundColor: "#111111", borderBottom: "1px solid rgba(240,237,232,0.08)", flexShrink: 0 }}>
      <div className="max-w-[720px] mx-auto px-4 sm:px-6 py-3 flex items-center gap-4">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-widest transition-colors"
          style={{ color: "rgba(240,237,232,0.4)" }}
          onMouseEnter={e => e.currentTarget.style.color = "#C80028"}
          onMouseLeave={e => e.currentTarget.style.color = "rgba(240,237,232,0.4)"}
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M8 2L4 6l4 4" />
          </svg>
          Back
        </button>

        <button
          onClick={onHome}
          className="font-display text-lg leading-none tracking-tighter"
          style={{ color: "#F0EDE8" }}
        >
          THE <span style={{ color: "#C80028" }}>NARRATIVE</span>
        </button>

        <div className="ml-auto flex items-center gap-4">
          <button
            onClick={onTrack}
            className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest transition-colors"
            style={{ color: following ? "#C80028" : "rgba(240,237,232,0.35)" }}
          >
            <svg width="11" height="11" viewBox="0 0 14 14" fill={following ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.4">
              <path d="M7 1.5C5.5 1.5 3.5 2.8 3.5 5.2c0 2.8 3.5 6.8 3.5 6.8s3.5-4 3.5-6.8C10.5 2.8 8.5 1.5 7 1.5z" />
            </svg>
            {following ? "Tracking" : "Track"}
          </button>
          <button
            onClick={onToggle}
            className="transition-colors"
            style={{ color: "rgba(240,237,232,0.35)" }}
            title={isDark ? "Day mode" : "Night mode"}
          >
            {isDark
              ? <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"><circle cx="7" cy="7" r="2.5"/><line x1="7" y1="1" x2="7" y2="2.5"/><line x1="7" y1="11.5" x2="7" y2="13"/><line x1="1" y1="7" x2="2.5" y2="7"/><line x1="11.5" y1="7" x2="13" y2="7"/><line x1="2.93" y1="2.93" x2="3.99" y2="3.99"/><line x1="10.01" y1="10.01" x2="11.07" y2="11.07"/><line x1="11.07" y1="2.93" x2="10.01" y2="3.99"/><line x1="3.99" y1="10.01" x2="2.93" y2="11.07"/></svg>
              : <svg width="12" height="12" viewBox="0 0 13 13" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"><path d="M11 8.5A5.5 5.5 0 1 1 4.5 2a4 4 0 0 0 6.5 6.5z"/></svg>
            }
          </button>
        </div>
      </div>
    </header>
  );
}

// ─── Tabs ─────────────────────────────────────────────────────────────────────

const TABS = ["Intelligence", "Predictions", "Effects"];

// ─── Main page ────────────────────────────────────────────────────────────────

export default function EventDetail() {
  const { eventId }  = useParams();
  const navigate     = useNavigate();
  const { isDark, toggle } = useTheme();
  const { isFollowing, follow, unfollow } = useFollowing();
  const { can }      = useUser();
  const { event: rawEvent, graph, loading, error } = useEventGraph(eventId);
  const [activeTab, setActiveTab] = useState("Intelligence");

  const following = isFollowing(eventId);

  const event = rawEvent
    ? {
        ...rawEvent,
        importance_score: rawEvent.importance_score ?? rawEvent.global_importance_score ?? 0,
        geography:        rawEvent.geography         ?? rawEvent.geographic_relevance    ?? [],
      }
    : (error ? getMockEvent(eventId) : null);

  const headerProps = {
    isDark,
    onToggle: toggle,
    following,
    onTrack: () => following ? unfollow(eventId) : follow(event || { id: eventId }),
    onBack:  () => navigate(-1),
    onHome:  () => navigate("/"),
  };

  if (!loading && !can("eventGraph")) {
    return (
      <div className="flex flex-col h-screen overflow-hidden bg-paper">
        <PageHeader {...headerProps} />
        <div className="flex-1 flex items-center justify-center">
          <TierGate feature="eventGraph" />
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex flex-col h-screen overflow-hidden bg-paper">
        <PageHeader {...headerProps} />
        <div className="flex-1 flex items-center justify-center">
          <div className="w-5 h-5 border-2 border-ink/10 border-t-crimson rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  if (!event) return null;

  const color   = getCategoryColor(event.category);
  const map     = event.consequence_map;
  const chain   = map?.consequence_chain || [];
  const articles = event.articles || [];

  const directImpacts   = Array.isArray(map?.direct_impact)   ? map.direct_impact   : map?.direct_impact   ? [map.direct_impact]   : [];
  const indirectImpacts = Array.isArray(map?.indirect_impact) ? map.indirect_impact : map?.indirect_impact ? [map.indirect_impact] : [];

  const predictions = Array.isArray(map?.predictions)
    ? map.predictions
    : map?.prediction_score !== undefined
    ? [{ label: map.confidence || "confidence", confidence: map.prediction_score }]
    : [];

  const aggrBias = calcEventBias(articles);
  const isLive   = event.current_status === "escalating" || event.current_status === "developing";

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-paper">
      <PageHeader {...headerProps} />

      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="max-w-[720px] mx-auto px-4 sm:px-6 pt-6 pb-28 md:pb-10">

          {/* ── Hero ─────────────────────────────────────────────────────────── */}
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.22 }}
            className="mb-7"
          >
            <div className="flex items-center gap-2 mb-3 flex-wrap">
              <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
              <span className="text-[9px] font-mono font-bold uppercase tracking-widest" style={{ color }}>
                {event.category}
              </span>
              {isLive && (
                <span className="flex items-center gap-1 text-[9px] font-medium text-crimson">
                  <span className="w-1 h-1 rounded-full bg-crimson animate-pulse" />
                  Live
                </span>
              )}
              {event.current_status && (
                <span className="text-[9px] font-mono border px-2 py-px uppercase tracking-widest text-ink/40 border-ink/12">
                  {event.current_status}
                </span>
              )}
              {event.importance_score > 0 && (
                <span
                  className="ml-auto text-[9px] font-mono font-bold border px-2 py-px"
                  style={{ color, borderColor: color + "30" }}
                >
                  {Math.round(event.importance_score)}
                </span>
              )}
            </div>

            <h1 className="font-display text-2xl sm:text-3xl text-ink leading-tight tracking-tight mb-3">
              {event.canonical_title || event.title}
            </h1>

            {event.canonical_summary && (
              <p className="text-[14px] sm:text-[15px] text-ink/60 leading-relaxed mb-4">
                {event.canonical_summary}
              </p>
            )}

            {event.geography?.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {event.geography.slice(0, 6).map(g => (
                  <span
                    key={g}
                    className="text-[9px] font-mono uppercase tracking-wider border px-2 py-px text-ink/35"
                    style={{ borderColor: "rgba(26,26,26,0.1)" }}
                  >
                    {g}
                  </span>
                ))}
              </div>
            )}
          </motion.div>

          {/* ── Source articles ───────────────────────────────────────────────── */}
          {articles.length > 0 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.22, delay: 0.1 }}
              className="mb-6 -mx-4 sm:-mx-6"
            >
              <div className="flex items-center justify-between px-4 sm:px-6 mb-2.5">
                <span className="text-[9px] font-mono uppercase tracking-[0.3em] text-ink/35">
                  Source Articles
                </span>
                <div className="flex items-center gap-2.5">
                  {aggrBias && (
                    <div className="flex items-center gap-1.5">
                      <span className="text-[8px] font-mono text-ink/25 hidden sm:inline">Coverage bias</span>
                      <div className="flex h-1.5 rounded-full overflow-hidden w-14 gap-px">
                        <div style={{ width: `${aggrBias.left}%`,   backgroundColor: BIAS_COLORS.left,   opacity: 0.8 }} />
                        <div style={{ width: `${aggrBias.center}%`, backgroundColor: BIAS_COLORS.center, opacity: 0.6 }} />
                        <div style={{ width: `${aggrBias.right}%`,  backgroundColor: BIAS_COLORS.right,  opacity: 0.8 }} />
                      </div>
                    </div>
                  )}
                  <span className="text-[9px] font-mono text-ink/25">{articles.length}</span>
                </div>
              </div>
              <div
                className="flex gap-2 px-4 sm:px-6 pb-1 overflow-x-auto"
                style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}
              >
                {articles.map((a, i) => <ArticleCard key={i} article={a} index={i} />)}
              </div>
            </motion.div>
          )}

          {/* ── Tab bar ───────────────────────────────────────────────────────── */}
          <div
            className="flex border-b border-ink/10 mb-6 -mx-4 sm:-mx-6 px-4 sm:px-6"
            style={{ borderTop: "1px solid rgba(26,26,26,0.06)" }}
          >
            {TABS.map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className="flex-1 py-3 text-[10px] font-mono uppercase tracking-widest transition-colors relative"
                style={{ color: activeTab === tab ? "#C80028" : "rgba(26,26,26,0.38)" }}
              >
                {tab}
                {activeTab === tab && (
                  <motion.div
                    layoutId="ed-tab-indicator"
                    className="absolute bottom-0 left-0 right-0 h-px bg-crimson"
                  />
                )}
              </button>
            ))}
          </div>

          {/* ── Tab content ───────────────────────────────────────────────────── */}
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.14 }}
            >
              {/* Intelligence */}
              {activeTab === "Intelligence" && (
                chain.length > 0 ? (
                  <div>
                    {chain.map((node, i) => (
                      <ChainStep key={i} node={node} index={i} categoryColor={color} totalSteps={chain.length} />
                    ))}
                    {map?.sources_analyzed?.length > 0 && (
                      <div className="mt-1 pt-5 border-t border-ink/10">
                        <span className="text-[9px] font-mono text-ink/35 uppercase tracking-wider mr-2">Analyzed</span>
                        {map.sources_analyzed.map(s => (
                          <span key={s} className="inline-block text-[9px] font-mono text-ink/35 border border-ink/10 px-1.5 py-px mr-1 mb-1">{s}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-ink/30 text-center py-12 font-mono uppercase tracking-wider">
                    Chain analysis in progress
                  </p>
                )
              )}

              {/* Predictions */}
              {activeTab === "Predictions" && (
                <TierGate feature="predictions">
                  {predictions.length > 0 ? (
                    <div>
                      <div className="flex flex-wrap gap-8 justify-center py-8">
                        {predictions.map((p, i) => (
                          <PredictionArc key={i} score={p.confidence} label={p.label} />
                        ))}
                      </div>
                      {map?.prediction_reasoning && (
                        <div className="border-t border-ink/10 pt-5">
                          <p className="text-[9px] font-mono uppercase tracking-wider text-ink/35 mb-2.5">Reasoning</p>
                          <p className="text-[13px] text-ink/60 leading-relaxed">{map.prediction_reasoning}</p>
                        </div>
                      )}
                    </div>
                  ) : (
                    <p className="text-xs text-ink/30 text-center py-12 font-mono uppercase tracking-wider">No predictions.</p>
                  )}
                </TierGate>
              )}

              {/* Effects */}
              {activeTab === "Effects" && (
                <TierGate feature="effects">
                  {directImpacts.length > 0 || indirectImpacts.length > 0 ? (
                    <div className="space-y-6">
                      {directImpacts.length > 0 && (
                        <div>
                          <p className="text-[9px] font-mono uppercase tracking-[0.3em] text-ink/35 mb-3">Direct Effects</p>
                          <div className="space-y-2.5">
                            {directImpacts.map((imp, i) => <ImpactCard key={i} impact={imp} index={i} />)}
                          </div>
                        </div>
                      )}
                      {indirectImpacts.length > 0 && (
                        <div>
                          <p className="text-[9px] font-mono uppercase tracking-[0.3em] text-ink/35 mb-3">Indirect Effects</p>
                          <div className="space-y-2.5">
                            {indirectImpacts.map((imp, i) => <ImpactCard key={i} impact={imp} index={i} />)}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <p className="text-xs text-ink/30 text-center py-12 font-mono uppercase tracking-wider">No impact data.</p>
                  )}
                </TierGate>
              )}
            </motion.div>
          </AnimatePresence>

          {/* Related events (uses graph data already fetched by useEventGraph) */}
          {graph?.connected_events?.length > 0 && (
            <div className="mt-8 pt-6 border-t border-ink/10">
              <p className="text-[9px] font-mono uppercase tracking-[0.3em] text-ink/35 mb-3">Related events</p>
              <div className="space-y-2">
                {graph.connected_events.map(r => (
                  <button
                    key={r.id}
                    onClick={() => navigate(`/event/${r.id}`)}
                    className="w-full text-left flex items-start gap-2 p-3 border border-ink/10 hover:border-crimson/40 hover:bg-ink/[0.02] transition-colors cursor-pointer"
                  >
                    <span className="w-1.5 h-1.5 rounded-full flex-shrink-0 mt-1.5" style={{ backgroundColor: getCategoryColor(r.category) }} />
                    <span className="text-[13px] text-ink/70 leading-snug flex-1">{r.title}</span>
                    <span className="text-ink/25 flex-shrink-0">→</span>
                  </button>
                ))}
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
