import { useState, useEffect, useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { api } from "../lib/api.js";
import { useTheme } from "../hooks/useTheme.js";
import { useOsintFramework } from "../hooks/useOsintFramework.js";
import TierGate from "../components/TierGate.jsx";

const KIND_LABELS = {
  username: "Username", domain: "Domain / URL", ip: "IP / MAC", email: "Email",
  name: "Person / Org", location: "Location", phone: "Phone", image: "Image",
  crypto: "Crypto Address", hash: "File Hash", cve: "CVE", vehicle: "Vessel / Aircraft",
  media: "Media / Image URL",
};
const PRICING_COLORS = { free: "#2E8B57", freemium: "#B07020", paid: "#C80028", unknown: "#6A6A60" };

// ── Investigate panel: templated lookups for an entity passed via ?value=&kind= ──
function InvestigatePanel({ value, kind }) {
  const [tools, setTools] = useState([]);
  const [resolvedKind, setResolvedKind] = useState(kind);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    const qs = new URLSearchParams({ value, ...(kind ? { kind } : {}) }).toString();
    api.get(`/osint/investigate?${qs}`)
      .then((d) => { if (!alive) return; setTools(d?.tools || []); setResolvedKind(d?.kind || kind); })
      .catch(() => { if (alive) setTools([]); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [value, kind]);

  return (
    <TierGate feature="osintInvestigate">
      <div className="mb-8 border border-crimson/30 bg-crimson/[0.03] p-4">
        <div className="flex items-center gap-2 mb-3 flex-wrap">
          <span className="text-[9px] font-mono uppercase tracking-[0.3em] text-crimson">Investigate</span>
          <span className="text-sm font-semibold text-ink">{value}</span>
          {resolvedKind && (
            <span className="text-[9px] font-mono uppercase tracking-wider border border-ink/15 px-1.5 py-px text-ink/45">
              {KIND_LABELS[resolvedKind] || resolvedKind}
            </span>
          )}
        </div>
        {loading ? (
          <p className="text-[11px] font-mono text-ink/30 py-3">Resolving lookups…</p>
        ) : tools.length === 0 ? (
          <p className="text-[11px] font-mono text-ink/30 py-3">No templated lookups for this entity kind.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {tools.map((t) => (
              <a key={t.name} href={t.url} target="_blank" rel="noopener noreferrer"
                 className="text-[12px] border border-ink/15 px-3 py-1.5 hover:border-crimson hover:text-crimson transition-colors text-ink/75"
                 title={t.note || t.url}>
                {t.name}{t.note ? " ↗" : ""}
              </a>
            ))}
          </div>
        )}
      </div>
    </TierGate>
  );
}

function ToolCard({ tool }) {
  const pc = PRICING_COLORS[tool.pricing] || PRICING_COLORS.unknown;
  return (
    <a href={tool.url} target="_blank" rel="noopener noreferrer"
       className="block border border-ink/10 bg-ink/[0.02] p-3 hover:border-ink/25 transition-colors">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-[12px] font-semibold text-ink leading-tight flex-1">{tool.name}</span>
        <span className="text-[8px] font-mono uppercase tracking-wide flex-shrink-0" style={{ color: pc }}>{tool.pricing}</span>
      </div>
      {tool.description && <p className="text-[11px] text-ink/55 leading-snug line-clamp-3 mb-2">{tool.description}</p>}
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-[8px] font-mono uppercase tracking-wider text-ink/30 border border-ink/10 px-1 py-px">{tool.category}</span>
        {tool.opsec && tool.opsec !== "unknown" && (
          <span className="text-[8px] font-mono uppercase tracking-wider px-1 py-px"
                style={{ color: tool.opsec === "passive" ? "#2E8B57" : "#B07020" }}>
            {tool.opsec}
          </span>
        )}
        {tool.entityKinds?.map((k) => (
          <span key={k} className="text-[8px] font-mono uppercase tracking-wider text-ink/30">{k}</span>
        ))}
      </div>
    </a>
  );
}

export default function Osint() {
  const navigate = useNavigate();
  const { isDark, toggle } = useTheme();
  const { tools, categories, limited, total_available, loading, error } = useOsintFramework();
  const [params] = useSearchParams();
  const value = params.get("value") || "";
  const kind = params.get("kind") || "";

  const [q, setQ] = useState("");
  const [cat, setCat] = useState("all");
  const [pricing, setPricing] = useState("all");
  const [opsec, setOpsec] = useState("all");

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return tools.filter((t) => {
      if (cat !== "all" && t.category !== cat) return false;
      if (pricing !== "all" && t.pricing !== pricing) return false;
      if (opsec !== "all" && t.opsec !== opsec) return false;
      if (needle && !(`${t.name} ${t.description} ${t.bestFor}`.toLowerCase().includes(needle))) return false;
      return true;
    });
  }, [tools, q, cat, pricing, opsec]);

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-paper">
      {/* Header */}
      <header style={{ backgroundColor: "#111111", borderBottom: "1px solid rgba(240,237,232,0.08)", flexShrink: 0 }}>
        <div className="max-w-[920px] mx-auto px-4 sm:px-6 py-3 flex items-center gap-4">
          <button onClick={() => navigate(-1)}
            className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-widest"
            style={{ color: "rgba(240,237,232,0.4)" }}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M8 2L4 6l4 4" /></svg>
            Back
          </button>
          <span className="font-display text-lg leading-none tracking-tighter" style={{ color: "#F0EDE8" }}>
            OSINT <span style={{ color: "#C80028" }}>FRAMEWORK</span>
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

          {value && <InvestigatePanel value={value} kind={kind} />}

          {/* Controls */}
          <div className="flex flex-wrap gap-2 mb-5">
            <input
              value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search tools…"
              className="flex-1 min-w-[180px] bg-ink/[0.03] border border-ink/12 px-3 py-2 text-[13px] text-ink placeholder:text-ink/30 focus:border-crimson outline-none"
            />
            <select value={cat} onChange={(e) => setCat(e.target.value)} className="bg-ink/[0.03] border border-ink/12 px-2 py-2 text-[12px] text-ink/70 outline-none">
              <option value="all">All categories</option>
              {categories.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <select value={pricing} onChange={(e) => setPricing(e.target.value)} className="bg-ink/[0.03] border border-ink/12 px-2 py-2 text-[12px] text-ink/70 outline-none">
              <option value="all">Any price</option>
              <option value="free">Free</option>
              <option value="freemium">Freemium</option>
              <option value="paid">Paid</option>
            </select>
            <select value={opsec} onChange={(e) => setOpsec(e.target.value)} className="bg-ink/[0.03] border border-ink/12 px-2 py-2 text-[12px] text-ink/70 outline-none">
              <option value="all">Any opsec</option>
              <option value="passive">Passive</option>
              <option value="active">Active</option>
            </select>
          </div>

          <div className="flex items-center justify-between mb-3">
            <span className="text-[9px] font-mono uppercase tracking-[0.3em] text-ink/35">
              {filtered.length} {filtered.length === 1 ? "tool" : "tools"}
            </span>
            {limited && (
              <span className="text-[9px] font-mono text-ink/35">
                Taster — {total_available}+ tools on paid plans
              </span>
            )}
          </div>

          {loading ? (
            <div className="flex justify-center py-16"><div className="w-5 h-5 border-2 border-ink/10 border-t-crimson rounded-full animate-spin" /></div>
          ) : error ? (
            <p className="text-xs text-ink/30 text-center py-12 font-mono uppercase tracking-wider">Couldn't load the OSINT catalog.</p>
          ) : filtered.length === 0 ? (
            <p className="text-xs text-ink/30 text-center py-12 font-mono uppercase tracking-wider">No tools match these filters.</p>
          ) : (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }}
              className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
              {filtered.map((t) => <ToolCard key={t.id} tool={t} />)}
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}
