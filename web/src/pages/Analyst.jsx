import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../lib/api.js";
import { useUser } from "../hooks/useUser.js";
import FeedHeader from "../components/layout/FeedHeader.jsx";

// The Analyst tab — ask a question, the analyst answers grounded in the live event
// graph, and below the answer it shows the consequence readout an enterprise
// geopolitics / trade / shipping desk actually needs: exposure (pressure, affected
// sectors + regions, personalised to the user's profile) and the real source articles.

const titleCase = (s) => String(s).replace(/\b\w/g, (c) => c.toUpperCase());

// ── personalised consequence readout ─────────────────────────────────────────
function ImpactReadout({ pressure, sectors = [], regions = [], user }) {
  if (pressure == null && sectors.length === 0 && regions.length === 0) return null;

  const mySectors = (user?.spending_categories || user?.sectors || []).map((s) => String(s).toLowerCase());
  const myCountry = String(user?.country || "").toLowerCase();
  const myProfession = String(user?.profession || "");
  const sectorMine = (s) => mySectors.some((m) => m && (s.toLowerCase().includes(m) || m.includes(s.toLowerCase())));
  const regionMine = (r) => myCountry && (r.toLowerCase().includes(myCountry) || myCountry.includes(r.toLowerCase()));

  const hitSectors = sectors.filter(sectorMine);
  const hitRegions = regions.filter(regionMine);
  const hasProfile = mySectors.length > 0 || myCountry || myProfession;

  const Chip = ({ label, mine }) => (
    <span className={`text-[11px] px-1.5 py-0.5 border ${mine ? "border-crimson/50 text-crimson bg-crimson/[0.05]" : "border-ink/15 text-ink/55"}`}>
      {label}{mine ? " ●" : ""}
    </span>
  );

  return (
    <div className="border border-ink/10 bg-ink/[0.02] p-3 space-y-2.5">
      <div className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-widest text-ink/40">Consequence · exposure</span>
        {pressure != null && (
          <span className="text-[11px] text-ink/55">pressure <span className="text-crimson font-semibold">{Math.round(pressure)}</span></span>
        )}
      </div>
      {sectors.length > 0 && (
        <div className="flex flex-wrap gap-1.5 items-center">
          <span className="text-[9px] font-mono uppercase tracking-wider text-ink/30 w-14">Sectors</span>
          {sectors.map((s) => <Chip key={s} label={titleCase(s)} mine={sectorMine(s)} />)}
        </div>
      )}
      {regions.length > 0 && (
        <div className="flex flex-wrap gap-1.5 items-center">
          <span className="text-[9px] font-mono uppercase tracking-wider text-ink/30 w-14">Regions</span>
          {regions.map((r) => <Chip key={r} label={titleCase(r)} mine={regionMine(r)} />)}
        </div>
      )}
      {hasProfile ? (
        (hitSectors.length > 0 || hitRegions.length > 0) ? (
          <p className="text-[11px] text-crimson/90 leading-snug">
            Relevant to you{myProfession ? ` (${myProfession})` : ""}:{" "}
            {[...hitSectors, ...hitRegions].join(", ")} — in your exposure profile.
          </p>
        ) : (
          <p className="text-[11px] text-ink/40 leading-snug">No direct hit on your profile’s sectors/region — monitoring for second-order effects.</p>
        )
      ) : (
        <p className="text-[11px] text-ink/40 leading-snug">
          Set your sectors & region in{" "}
          <button onClick={() => window.location.assign("/settings")} className="text-crimson hover:underline">Settings</button>{" "}
          to personalise exposure to your desk.
        </p>
      )}
    </div>
  );
}

export default function Analyst() {
  const navigate = useNavigate();
  const { user } = useUser();

  const [turns, setTurns] = useState([]); // {q, answer, sources, pressure, sectors, regions}
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [hotspots, setHotspots] = useState([]);
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [turns, loading]);

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
          <div className="flex items-center gap-3 mb-4">
            <button onClick={() => navigate(-1)}
              className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-widest text-ink/45 hover:text-crimson transition-colors">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M8 2L4 6l4 4" /></svg>
              Back
            </button>
            <div>
              <h1 className="text-sm font-bold uppercase tracking-widest text-ink/80">Analyst</h1>
              <p className="text-[11px] text-ink/40 mt-0.5">Ask about geopolitics, threats, shipping & trade — grounded in live events, scored for consequence, personalised to your desk.</p>
            </div>
          </div>

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
                {t.answer && <ImpactReadout pressure={t.pressure} sectors={t.sectors} regions={t.regions} user={user} />}
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
        </div>
      </div>

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
