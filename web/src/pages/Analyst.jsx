import { useState, useRef, useEffect, useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../lib/api.js";
import FeedHeader from "../components/layout/FeedHeader.jsx";
import OsintInvestigate from "../components/OsintInvestigate.jsx";
import OsintFrameworkBrowser from "../components/OsintFrameworkBrowser.jsx";
import { extractEntities } from "../lib/osintEntities.js";

// The Analyst tab — ask a question, the analyst answers grounded in the live event
// graph, and below the answer it taps into the OSINT Framework: the real sources it
// used, plus one-click OSINT lookups for the entities/places involved. The full
// OSINT catalog (the old /osint page) folds in as a browsable section at the bottom.

// OSINT lookups derived from a single answer: hard entities named in the question
// (CVE/IP/crypto/hash/vessel) + the places the grounding events touch → location
// lookups. Each renders the shared investigate surface (/osint/investigate + enrich).
function OsintForTurn({ question, sources }) {
  const targets = useMemo(() => {
    const entities = extractEntities(question);
    const geos = new Set();
    for (const ev of sources || []) {
      for (const g of ev.geography || []) {
        if (g && !g.includes(",")) geos.add(g); // drop sub-region noise ("Clay, MN")
      }
    }
    const locs = [...geos].slice(0, 3).map((g) => ({ value: g, kind: "location" }));
    // de-dup by value; hard entities first
    const seen = new Set();
    return [...entities, ...locs]
      .filter((t) => (seen.has(t.value.toLowerCase()) ? false : seen.add(t.value.toLowerCase())))
      .slice(0, 4);
  }, [question, sources]);

  if (targets.length === 0) return null;
  return (
    <div className="border-t border-ink/10 pt-3 mt-1 space-y-2">
      <div className="text-[10px] uppercase tracking-widest text-ink/35">OSINT lookups</div>
      {targets.map((t, i) => (
        <OsintInvestigate key={`${t.kind}-${t.value}-${i}`} value={t.value} kind={t.kind} compact />
      ))}
    </div>
  );
}

export default function Analyst() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const seedValue = params.get("value") || "";
  const seedKind = params.get("kind") || "";

  const [turns, setTurns] = useState([]); // {q, answer, sources, pressure}
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [hotspots, setHotspots] = useState([]);
  const [showFramework, setShowFramework] = useState(false);
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [turns, loading]);

  // Geographic risk index for the empty-state context. Drop sub-region noise
  // (names with a comma) so the list reads as hotspots.
  useEffect(() => {
    api.get("/exposure/countries?top=40")
      .then((d) => setHotspots((d.countries || []).filter((c) => !c.country.includes(",")).slice(0, 8)))
      .catch(() => {});
  }, []);

  async function ask(e) {
    e?.preventDefault();
    const q = input.trim();
    if (q.length < 3 || loading) return;
    setInput("");
    setError(null);
    setLoading(true);
    try {
      const res = await api.post("/chat", { question: q }, { timeoutMs: 60000 });
      setTurns((t) => [...t, { q, ...res }]);
    } catch (err) {
      if (err.status === 402) setError("The AI analyst is a paid feature. Upgrade to Full Access in Settings.");
      else if (err.status === 503) setError("The analyst isn't enabled yet (no model key configured).");
      else if (err.status === 401) setError("Please sign in to use the analyst.");
      else setError(err.message || "The analyst is unavailable right now.");
      setTurns((t) => [...t, { q, answer: null }]);
    } finally {
      setLoading(false);
    }
  }

  // Tab bar lives in the shared header; Analyst is its own route, so route out.
  const handleTabChange = (tab) => {
    if (tab === "analyst") return;
    if (tab === "following") { navigate("/following"); return; }
    navigate(`/world?tab=${tab}`);
  };

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-paper">
      <FeedHeader
        activeCategory={null}
        onCategoryChange={() => {}}
        activeTab="analyst"
        onTabChange={handleTabChange}
        searchValue=""
        onSearchChange={() => {}}
      />

      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="max-w-[860px] w-full mx-auto px-4 sm:px-6 py-5 pb-28 md:pb-10">
          {/* Back + title */}
          <div className="flex items-center gap-3 mb-4">
            <button onClick={() => navigate(-1)}
              className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-widest text-ink/45 hover:text-crimson transition-colors">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M8 2L4 6l4 4" /></svg>
              Back
            </button>
            <div>
              <h1 className="text-sm font-bold uppercase tracking-widest text-ink/80">Analyst</h1>
              <p className="text-[11px] text-ink/40 mt-0.5">Ask about live risk — answers are grounded in real event data and tap into the OSINT Framework.</p>
            </div>
          </div>

          {/* Deep-linked investigation (from an event chip or the old /osint links) */}
          {seedValue && (
            <div className="mb-6">
              <OsintInvestigate value={seedValue} kind={seedKind} />
            </div>
          )}

          {/* Empty state */}
          {turns.length === 0 && !loading && (
            <div className="space-y-5">
              <div className="text-xs text-ink/40 leading-relaxed">
                Try: <span className="text-crimson">"What's the biggest risk to shipping right now?"</span> ·{" "}
                <span className="text-crimson">"Summarize the Israel-Iran situation and its consequences."</span>
              </div>
              {hotspots.length > 0 && (
                <div className="border border-ink/10 bg-ink/[0.02]">
                  <div className="px-3 py-2 border-b border-ink/10 text-[10px] uppercase tracking-widest text-ink/40">
                    Top Risk Hotspots
                  </div>
                  {hotspots.map((h, i) => (
                    <div key={h.country} className="flex items-center justify-between px-3 py-1.5 text-xs">
                      <span className="text-ink/60"><span className="text-ink/30 mr-2">{i + 1}</span>{h.country}</span>
                      <span className="text-ink/35">{h.events} events · <span className="text-crimson">{Math.round(h.risk)}</span></span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Conversation */}
          <div className="space-y-6 mt-2">
            {turns.map((t, i) => (
              <div key={i} className="space-y-3">
                <div className="text-sm text-ink/80 font-semibold">{t.q}</div>
                {t.answer && (
                  <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
                    className="text-sm text-ink/70 leading-relaxed whitespace-pre-wrap">
                    {t.answer}
                  </motion.div>
                )}
                {Array.isArray(t.sources) && t.sources.length > 0 && (
                  <div className="border-t border-ink/10 pt-3 space-y-1.5">
                    <div className="text-[10px] uppercase tracking-widest text-ink/35">References & sources</div>
                    {t.sources.map((s, n) => (
                      <button key={s.id} onClick={() => navigate(`/event/${s.id}`)}
                        className="block text-left text-xs text-ink/55 hover:text-crimson transition-colors">
                        <span className="text-ink/35">[{n + 1}]</span> {s.title}
                      </button>
                    ))}
                  </div>
                )}
                {t.answer && <OsintForTurn question={t.q} sources={t.sources} />}
              </div>
            ))}

            {loading && <div className="text-xs text-ink/40">Analyzing…</div>}
            <AnimatePresence>
              {error && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                  className="text-xs text-crimson border border-crimson/30 bg-crimson/[0.04] px-3 py-2">
                  {error}
                </motion.div>
              )}
            </AnimatePresence>
            <div ref={endRef} />
          </div>

          {/* Full OSINT Framework — the old /osint catalog, folded in */}
          <div className="mt-8 border-t border-ink/10 pt-5">
            <button onClick={() => setShowFramework((s) => !s)}
              className="w-full flex items-center justify-between text-left group">
              <span className="text-[11px] font-bold uppercase tracking-widest text-ink/70 group-hover:text-crimson transition-colors">
                OSINT Framework
              </span>
              <span className="text-[10px] font-mono text-ink/35">{showFramework ? "− hide" : "+ explore all tools"}</span>
            </button>
            {showFramework && (
              <div className="mt-4">
                <OsintFrameworkBrowser />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Ask box */}
      <form onSubmit={ask} className="flex-shrink-0 border-t border-ink/10 p-3 sm:p-4 mb-20 md:mb-0 max-w-[860px] w-full mx-auto">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask the analyst…"
            className="flex-1 bg-transparent border border-ink/15 px-3 py-2 text-sm text-ink/80 placeholder:text-ink/30 focus:outline-none focus:border-crimson/40"
          />
          <button type="submit" disabled={loading || input.trim().length < 3}
            className="px-4 py-2 text-[11px] font-bold uppercase tracking-widest border border-crimson/40 text-crimson hover:bg-crimson hover:text-paper transition-colors disabled:opacity-30 disabled:cursor-not-allowed">
            Ask
          </button>
        </div>
      </form>
    </div>
  );
}
