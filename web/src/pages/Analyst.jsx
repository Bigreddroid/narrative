import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../lib/api.js";

// AI analyst chat — natural-language Q&A grounded in the live event graph +
// exposure model (backend POST /api/v1/chat). Renders the answer plus the real
// events it was grounded in ([n] citations map to this sources list).
export default function Analyst() {
  const navigate = useNavigate();
  const [turns, setTurns] = useState([]); // {q, answer, sources, pressure}
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [hotspots, setHotspots] = useState([]);
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [turns, loading]);

  // Geographic risk index for the empty-state context. Drop sub-region noise
  // (names with a comma, e.g. "Coffee, GA") so the list reads as hotspots.
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

  return (
    <div className="flex flex-col h-screen bg-paper">
      <header className="px-4 sm:px-6 py-4 border-b border-ink/10 flex-shrink-0">
        <h1 className="text-sm font-bold uppercase tracking-widest text-ink/80">Analyst</h1>
        <p className="text-[11px] text-ink/40 mt-0.5">Ask about live risk — answers are grounded only in our real event data.</p>
      </header>

      <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-5 space-y-6 max-w-[820px] w-full mx-auto">
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
                <div className="text-[10px] uppercase tracking-widest text-ink/35">Sources</div>
                {t.sources.map((s, n) => (
                  <button key={s.id} onClick={() => navigate(`/event/${s.id}`)}
                    className="block text-left text-xs text-ink/55 hover:text-crimson transition-colors">
                    <span className="text-ink/35">[{n + 1}]</span> {s.title}
                  </button>
                ))}
              </div>
            )}
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

      <form onSubmit={ask} className="flex-shrink-0 border-t border-ink/10 p-3 sm:p-4 max-w-[820px] w-full mx-auto">
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
