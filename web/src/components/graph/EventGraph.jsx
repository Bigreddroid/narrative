import { useEffect, useState, useRef, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { getCategoryColor, TYPE_COLORS, SEVERITY_COLORS, scoreColor } from "../../lib/colors.js";
import { api } from "../../lib/api.js";
import { biasLabel, BIAS_COLORS, SOURCE_BIAS } from "../../lib/bias.js";
import TierGate from "../TierGate.jsx";
import { useUser } from "../../hooks/useUser.js";
import { COUNTRY_NAMES } from "../../lib/countries.js";
import ConsequenceTrace from "./ConsequenceTrace.jsx";

// ─── Source article card ───────────────────────────────────────────────────────

function ArticleCard({ article, index }) {
  const srcBias = SOURCE_BIAS[article.source] || null;
  const lean    = srcBias ? biasLabel(srcBias) : null;
  const nameColor = lean?.color || "#6A6A60";

  return (
    <motion.a
      href={article.url && article.url !== "#" ? article.url : undefined}
      target="_blank"
      rel="noopener noreferrer"
      onClick={(e) => { if (!article.url || article.url === "#") e.preventDefault(); }}
      initial={{ opacity: 0, x: 12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.07, duration: 0.2 }}
      className="flex-shrink-0 w-44 border border-ink/10 bg-ink/[0.03] p-3 flex flex-col gap-2 hover:border-ink/25 hover:bg-ink/[0.06] transition-colors cursor-pointer"
      style={{ textDecoration: "none" }}
    >
      <div className="flex items-center justify-between">
        <span className="text-[9px] font-mono font-bold uppercase tracking-widest" style={{ color: nameColor }}>
          {article.source}
        </span>
        {lean && (
          <span className="text-[7px] font-mono uppercase tracking-wider" style={{ color: lean.color, opacity: 0.7 }}>
            {lean.label}
          </span>
        )}
        <svg width="8" height="8" viewBox="0 0 8 8" fill="none" stroke="#1A1A1A" strokeWidth="1.2" opacity="0.3">
          <path d="M1 7L7 1M7 1H3.5M7 1V4.5" />
        </svg>
      </div>
      <p className="text-xs text-ink leading-snug font-medium line-clamp-3 flex-1">{article.title}</p>
      {srcBias && (
        <div className="flex h-0.5 rounded-full overflow-hidden gap-px">
          <div style={{ width: `${srcBias.left}%`,   backgroundColor: BIAS_COLORS.left,   opacity: 0.8 }} />
          <div style={{ width: `${srcBias.center}%`, backgroundColor: BIAS_COLORS.center, opacity: 0.6 }} />
          <div style={{ width: `${srcBias.right}%`,  backgroundColor: BIAS_COLORS.right,  opacity: 0.8 }} />
        </div>
      )}
      <p className="text-[9px] text-ink/35 font-mono">{article.date}</p>
    </motion.a>
  );
}

// ─── Consequence chain step ────────────────────────────────────────────────────

function ChainStep({ node, index, categoryColor, totalSteps }) {
  const typeColor = TYPE_COLORS[node.type] || "#6A6A60";
  const short = node.type === "VERIFIED FACT"      ? "VERIFIED"
    : node.type === "INFERRED MECHANISM" ? "INFERRED"
    : node.type === "SPECULATIVE EFFECT" ? "SPECULATIVE"
    : node.type || "";

  const text     = node.content || node.description || node.node || "";
  const children = node.children || node.sub_steps || [];

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.15, duration: 0.25 }}
    >
      <div className="flex gap-3">
        <div className="flex flex-col items-center flex-shrink-0">
          <motion.div
            className="w-5 h-5 flex items-center justify-center text-[9px] font-mono font-bold flex-shrink-0"
            style={{ backgroundColor: categoryColor + "18", color: categoryColor, border: `1px solid ${categoryColor}40` }}
            initial={{ scale: 1.4, backgroundColor: categoryColor + "40" }}
            animate={{ scale: 1,   backgroundColor: categoryColor + "18" }}
            transition={{ delay: index * 0.15 + 0.1, duration: 0.35 }}
          >
            {index + 1}
          </motion.div>
          {index < totalSteps - 1 && (
            <motion.div
              className="w-px flex-1 mt-1"
              style={{ backgroundColor: categoryColor + "20", minHeight: 14 }}
              initial={{ scaleY: 0 }}
              animate={{ scaleY: 1 }}
              transition={{ delay: index * 0.15 + 0.25, duration: 0.2 }}
            />
          )}
        </div>

        <div className="flex-1 pb-4">
          <div className="flex items-center gap-2 mb-1.5">
            <span
              className="text-[9px] font-mono uppercase tracking-widest border px-1.5 py-px"
              style={{ color: typeColor, borderColor: typeColor + "35" }}
            >
              {short}
            </span>
          </div>
          <p className="text-xs text-ink leading-relaxed">{text}</p>
          {node.evidence && (
            <p className="text-[10px] text-ink/45 mt-1.5 leading-relaxed pl-2 border-l border-ink/15">
              {node.evidence}
            </p>
          )}
          {children.length > 0 && (
            <div className="mt-2 ml-2 space-y-2">
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

// ─── Prediction arc ───────────────────────────────────────────────────────────

function PredictionArc({ score, label }) {
  const r    = 28;
  const circ = 2 * Math.PI * r;
  const pct  = Math.min(100, Math.max(0, score));
  const color = scoreColor(pct);

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="relative w-16 h-16">
        <svg viewBox="0 0 72 72" className="w-full h-full -rotate-90">
          <circle cx="36" cy="36" r={r} fill="none" stroke="#1A1A1A" strokeWidth="2.5" opacity="0.08" />
          <motion.circle
            cx="36" cy="36" r={r} fill="none" stroke={color} strokeWidth="2.5"
            strokeLinecap="butt"
            strokeDasharray={circ}
            initial={{ strokeDashoffset: circ }}
            animate={{ strokeDashoffset: circ - (pct / 100) * circ }}
            transition={{ duration: 1, ease: "easeOut", delay: 0.3 }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="font-mono font-bold text-sm text-ink">{pct}%</span>
        </div>
      </div>
      <span className="text-[9px] font-mono text-ink/40 text-center max-w-[72px] leading-tight capitalize">
        {label}
      </span>
    </div>
  );
}

// ─── Impact card ──────────────────────────────────────────────────────────────

function ImpactCard({ impact, index }) {
  const color = SEVERITY_COLORS[impact.severity] || "#6A6A60";
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.2 }}
      className="border border-ink/10 bg-ink/[0.03] p-3"
      style={{ borderLeftColor: color, borderLeftWidth: 2 }}
    >
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[10px] font-mono uppercase tracking-wider text-ink/50 flex-1">
          {impact.sector || "Impact"}
        </span>
        {impact.severity && (
          <span className="text-[9px] font-mono border px-1.5 py-px uppercase"
            style={{ color, borderColor: color + "40" }}>
            {impact.severity}
          </span>
        )}
      </div>
      <p className="text-xs text-ink leading-snug mb-1">{impact.description}</p>
      {impact.population_affected && (
        <p className="text-[10px] text-ink/40 mt-1">{impact.population_affected}</p>
      )}
      {impact.evidence && (
        <p className="text-[10px] text-ink/40 border-t border-ink/10 pt-2 mt-2 leading-relaxed">
          {impact.evidence}
        </p>
      )}
    </motion.div>
  );
}

// ─── Main panel ───────────────────────────────────────────────────────────────

const TABS = ["Intelligence", "Trace", "Predictions", "Effects"];

export default function EventGraph({ eventId, onClose }) {
  const [event,     setEvent]     = useState(null);
  const [loading,   setLoading]   = useState(true);
  const [activeTab, setActiveTab] = useState("Intelligence");
  const articlesRef = useRef(null);
  const { can } = useUser();

  useEffect(() => {
    if (!eventId) return;
    setLoading(true);
    setActiveTab("Intelligence");
    api.get(`/events/${eventId}`)
      .then(data => setEvent({
        ...data,
        importance_score: data.importance_score ?? data.global_importance_score ?? 0,
        geography:        data.geography ?? data.geographic_relevance ?? [],
      }))
      .catch(() => setEvent(null))  // real-only: no fabricated detail on failure
      .finally(() => setLoading(false));
  }, [eventId]);

  if (!can("eventGraph")) {
    return (
      <div className="absolute inset-0 bg-paper border-l border-ink/10">
        <TierGate feature="eventGraph" />
      </div>
    );
  }

  if (loading) {
    return (
      <div className="absolute inset-0 flex items-center justify-center bg-paper border-l border-ink/10">
        <div className="w-5 h-5 border-2 border-ink/10 border-t-crimson rounded-full animate-spin" />
      </div>
    );
  }

  if (!event) return null;

  const map         = event.consequence_map;
  const color       = getCategoryColor(event.category);
  const title       = event.canonical_title || event.title;
  const summary     = event.canonical_summary;
  const statusLabel = event.current_status || event.status;
  const chain       = map?.consequence_chain || [];
  const articles    = event.articles || [];

  const directImpacts   = Array.isArray(map?.direct_impact)   ? map.direct_impact   : map?.direct_impact   ? [map.direct_impact]   : [];
  const indirectImpacts = Array.isArray(map?.indirect_impact) ? map.indirect_impact : map?.indirect_impact ? [map.indirect_impact] : [];
  const allImpacts      = [...directImpacts, ...indirectImpacts];

  // Two concrete scenario arcs from the prediction score (likelihood of continued
  // escalation vs. stabilising) — clearer than a single generic "confidence" arc.
  const predictions = Array.isArray(map?.predictions)
    ? map.predictions
    : map?.prediction_score != null
    ? [
        { label: "Further escalation", confidence: map.prediction_score },
        { label: "Stabilizes", confidence: Math.max(0, 100 - map.prediction_score) },
      ]
    : [];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
      className="bg-paper border-l border-ink/10 flex flex-col overflow-hidden"
      style={{ position: "absolute", inset: 0 }}
    >
      {/* Header */}
      <div className="p-4 border-b border-ink/10 flex-shrink-0">
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              <div className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                style={{ backgroundColor: color }} />
              <span className="text-[9px] font-mono uppercase tracking-widest font-bold" style={{ color }}>
                {event.category}
              </span>
              {statusLabel && (
                <span className="ml-auto text-[9px] font-mono uppercase border border-ink/15 px-2 py-px text-ink/40 tracking-widest">
                  {statusLabel}
                </span>
              )}
            </div>
            <h2 className="font-display font-bold text-xl text-ink leading-tight mb-1">{title}</h2>
            {summary && <p className="text-xs text-ink/55 leading-relaxed">{summary}</p>}
            {event.geography?.length > 0 && (
              <p className="text-[9px] text-ink/35 font-mono mt-1.5 uppercase tracking-wider">
                {event.geography.slice(0, 4).join(" · ")}
              </p>
            )}
          </div>
          <button onClick={onClose} className="flex-shrink-0 text-ink/30 hover:text-crimson transition-colors mt-0.5">
            <svg width="12" height="12" viewBox="0 0 12 12" stroke="currentColor" strokeWidth="1.5">
              <line x1="1" y1="1" x2="11" y2="11" /><line x1="11" y1="1" x2="1" y2="11" />
            </svg>
          </button>
        </div>
      </div>

      {/* Source articles carousel */}
      {articles.length > 0 && (
        <div className="flex-shrink-0 border-b border-ink/10">
          <div className="px-4 pt-3 pb-1 flex items-center justify-between">
            <span className="text-[9px] font-mono uppercase tracking-[0.3em] text-ink/35">
              Source Articles
            </span>
            <span className="text-[9px] font-mono text-ink/25">{articles.length}</span>
          </div>
          <div
            ref={articlesRef}
            className="flex gap-2 px-4 pb-3 overflow-x-auto"
            style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}
          >
            {articles.map((a, i) => <ArticleCard key={i} article={a} index={i} />)}
          </div>
        </div>
      )}

      {/* Tab bar */}
      <div className="flex border-b border-ink/10 flex-shrink-0">
        {TABS.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 py-2.5 text-[9px] font-mono uppercase tracking-widest transition-colors relative ${
              activeTab === tab ? "" : "text-ink/45 hover:text-ink/70"
            }`}
            style={activeTab === tab ? { color: "#C80028" } : undefined}
          >
            {tab}
            {activeTab === tab && (
              <motion.div
                layoutId="eg-tab-indicator"
                className="absolute bottom-0 left-0 right-0 h-px bg-crimson"
              />
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.12 }}
          >
            {/* Intelligence — consequence chain */}
            {activeTab === "Intelligence" && (
              <div className="p-4">
                {chain.length > 0 ? (
                  <div className="space-y-0">
                    {chain.map((node, i) => (
                      <ChainStep key={i} node={node} index={i} categoryColor={color} totalSteps={chain.length} />
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-ink/30 text-center py-8 font-mono uppercase tracking-wider">No chain data.</p>
                )}
                {map?.sources_analyzed?.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-ink/10">
                    <span className="text-[9px] font-mono text-ink/35 uppercase tracking-wider mr-2">Sources</span>
                    {map.sources_analyzed.map(s => (
                      <span key={s} className="inline-block text-[9px] font-mono text-ink/35 border border-ink/10 px-1.5 py-px mr-1 mb-1">{s}</span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Trace — computed directed consequence chain to other events */}
            {activeTab === "Trace" && <ConsequenceTrace eventId={event.id} />}

            {/* Predictions */}
            {activeTab === "Predictions" && (
              <TierGate feature="predictions">
                <div className="p-4">
                  {predictions.length > 0 ? (
                    <>
                      <div className="flex gap-6 justify-center py-5 mb-2">
                        {predictions.map((p, i) => (
                          <PredictionArc key={i} score={p.confidence} label={p.label} />
                        ))}
                      </div>
                      {map?.prediction_reasoning && (
                        <div className="border-t border-ink/10 pt-4">
                          <p className="text-[9px] font-mono uppercase tracking-wider text-ink/35 mb-2">Reasoning</p>
                          <p className="text-xs text-ink/60 leading-relaxed">{map.prediction_reasoning}</p>
                        </div>
                      )}
                    </>
                  ) : (
                    <p className="text-xs text-ink/30 text-center py-8 font-mono uppercase tracking-wider">No predictions.</p>
                  )}
                </div>
              </TierGate>
            )}

            {/* Effects */}
            {activeTab === "Effects" && (
              <TierGate feature="effects">
              <div className="p-4">
                {allImpacts.length > 0 ? (
                  <>
                    {directImpacts.length > 0 && (
                      <div className="mb-4">
                        <p className="text-[9px] font-mono uppercase tracking-[0.3em] text-ink/35 mb-3">Direct Effects</p>
                        <div className="space-y-2">
                          {directImpacts.map((imp, i) => <ImpactCard key={i} impact={imp} index={i} />)}
                        </div>
                      </div>
                    )}
                    {indirectImpacts.length > 0 && (
                      <div>
                        <p className="text-[9px] font-mono uppercase tracking-[0.3em] text-ink/35 mb-3">Indirect Effects</p>
                        <div className="space-y-2">
                          {indirectImpacts.map((imp, i) => <ImpactCard key={i} impact={imp} index={i} />)}
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <p className="text-xs text-ink/30 text-center py-8 font-mono uppercase tracking-wider">No impact data.</p>
                )}
              </div>
              </TierGate>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
