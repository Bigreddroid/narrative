import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { api } from "../lib/api.js";
import { useTheme } from "../hooks/useTheme.js";

// Disinfo / Threat surface: events in the disinfo + cyber categories, foregrounding
// OSINT provenance (which keyless feed flagged them) and credibility. Complements
// the headline feed, where cyber CVEs are intentionally filtered out.

const SOURCE_LABELS = {
  osint_gdelt: "GDELT", osint_reddit: "Reddit", osint_threatintel: "Threat Intel",
  osint_disinfo: "Fact-check", osint: "OSINT",
};

const TABS = [
  { id: "all", label: "All", categories: ["disinfo", "cyber"] },
  { id: "disinfo", label: "Disinformation", categories: ["disinfo"] },
  { id: "cyber", label: "Cyber / Threat", categories: ["cyber"] },
];

function sourceLabel(src) {
  if (!src) return null;
  return SOURCE_LABELS[src] || (src.startsWith("osint_") ? src.replace("osint_", "") : src);
}

function EventRow({ ev, onClick }) {
  const isOsint = ev.is_osint || (ev.source || "").startsWith("osint_");
  return (
    <button onClick={onClick}
      className="w-full text-left border border-ink/10 bg-ink/[0.02] p-3 hover:border-crimson/40 transition-colors">
      <div className="flex items-center gap-2 mb-1.5 flex-wrap">
        <span className="text-[8px] font-mono uppercase tracking-wider px-1 py-px border border-ink/12 text-ink/40">
          {ev.category}
        </span>
        {isOsint && (
          <span className="text-[8px] font-mono uppercase tracking-wider px-1 py-px text-emerald-700/80 border border-emerald-700/30"
                title={`OSINT source: ${ev.source}`}>
            OSINT{sourceLabel(ev.source) ? ` · ${sourceLabel(ev.source)}` : ""}
          </span>
        )}
        {ev.global_importance_score > 0 && (
          <span className="ml-auto text-[9px] font-mono font-bold text-ink/45">{Math.round(ev.global_importance_score)}</span>
        )}
      </div>
      <p className="text-[13px] font-semibold text-ink leading-snug mb-1">{ev.canonical_title}</p>
      {ev.canonical_summary && <p className="text-[11px] text-ink/50 leading-snug line-clamp-2">{ev.canonical_summary}</p>}
    </button>
  );
}

export default function DisinfoThreat() {
  const navigate = useNavigate();
  const { isDark, toggle } = useTheme();
  const [tab, setTab] = useState("all");
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(false);
    const cats = TABS.find((t) => t.id === tab).categories;
    Promise.all(cats.map((c) => api.get(`/events/?category=${c}&limit=50`).catch(() => ({ events: [] }))))
      .then((results) => {
        if (!alive) return;
        const merged = [];
        const seen = new Set();
        results.flatMap((r) => r?.events || []).forEach((e) => {
          if (!seen.has(e.id)) { seen.add(e.id); merged.push(e); }
        });
        merged.sort((a, b) => (b.global_importance_score || 0) - (a.global_importance_score || 0));
        setEvents(merged);
      })
      .catch(() => { if (alive) setError(true); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [tab]);

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-paper">
      <header style={{ backgroundColor: "#111111", borderBottom: "1px solid rgba(240,237,232,0.08)", flexShrink: 0 }}>
        <div className="max-w-[920px] mx-auto px-4 sm:px-6 py-3 flex items-center gap-4">
          <button onClick={() => navigate(-1)}
            className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-widest"
            style={{ color: "rgba(240,237,232,0.4)" }}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M8 2L4 6l4 4" /></svg>
            Back
          </button>
          <span className="font-display text-lg leading-none tracking-tighter" style={{ color: "#F0EDE8" }}>
            DISINFO <span style={{ color: "#C80028" }}>/ THREAT</span>
          </span>
          <button onClick={toggle} className="ml-auto" style={{ color: "rgba(240,237,232,0.35)" }} title={isDark ? "Day mode" : "Night mode"}>
            {isDark
              ? <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"><circle cx="7" cy="7" r="2.5"/><line x1="7" y1="1" x2="7" y2="2.5"/><line x1="7" y1="11.5" x2="7" y2="13"/><line x1="1" y1="7" x2="2.5" y2="7"/><line x1="11.5" y1="7" x2="13" y2="7"/></svg>
              : <svg width="12" height="12" viewBox="0 0 13 13" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"><path d="M11 8.5A5.5 5.5 0 1 1 4.5 2a4 4 0 0 0 6.5 6.5z"/></svg>}
          </button>
        </div>
      </header>

      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="max-w-[920px] mx-auto px-4 sm:px-6 pt-6 pb-28 md:pb-10">
          <div className="flex border border-ink/12 mb-5 w-fit">
            {TABS.map((t) => (
              <button key={t.id} onClick={() => setTab(t.id)}
                className={`px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider transition-colors ${
                  tab === t.id ? "bg-crimson/10 text-crimson" : "text-ink/40 hover:text-ink/70"}`}>
                {t.label}
              </button>
            ))}
          </div>

          {loading ? (
            <div className="flex justify-center py-16"><div className="w-5 h-5 border-2 border-ink/10 border-t-crimson rounded-full animate-spin" /></div>
          ) : error ? (
            <p className="text-xs text-ink/30 text-center py-12 font-mono uppercase tracking-wider">Couldn't load events.</p>
          ) : events.length === 0 ? (
            <p className="text-xs text-ink/30 text-center py-12 font-mono uppercase tracking-wider">No disinfo / threat events yet.</p>
          ) : (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }}
              className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {events.map((ev) => (
                <EventRow key={ev.id} ev={ev} onClick={() => navigate(`/event/${ev.id}`)} />
              ))}
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}
