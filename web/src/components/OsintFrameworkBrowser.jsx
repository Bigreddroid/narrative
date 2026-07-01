import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { useOsintFramework } from "../hooks/useOsintFramework.js";
import { buildTree } from "../lib/osintTree.js";

// The browsable OSINT Framework catalog (search / filter / tree · grid), extracted
// from the old standalone /osint page so it can live inside the Analyst tab. Fully
// self-contained: pulls the tier-aware catalog from /osint/framework itself.

const CAP_DOT = { live: "#2E8B57", pivot: "#1E5FA8", launch: "#B07020" };
const PRICING_COLORS = { free: "#2E8B57", freemium: "#B07020", paid: "#C80028", unknown: "#6A6A60" };

function ToolCard({ tool }) {
  const pc = PRICING_COLORS[tool.pricing] || PRICING_COLORS.unknown;
  const capColor = CAP_DOT[tool.capability];
  return (
    <a href={tool.url} target="_blank" rel="noopener noreferrer"
       className="block border border-ink/10 bg-ink/[0.02] p-3 hover:border-ink/25 transition-colors">
      <div className="flex items-center gap-2 mb-1.5">
        {capColor && (
          <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: capColor }}
                title={`capability: ${tool.capability}`} />
        )}
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

function TreeView({ tools, forceExpand }) {
  const tree = useMemo(() => buildTree(tools), [tools]);
  const [open, setOpen] = useState(() => new Set());
  const isOpen = (c) => forceExpand || open.has(c);
  const toggle = (c) =>
    setOpen((prev) => {
      const next = new Set(prev);
      next.has(c) ? next.delete(c) : next.add(c);
      return next;
    });

  return (
    <div className="flex flex-col gap-1.5">
      {tree.map(({ category, count, subs }) => (
        <div key={category} className="border border-ink/10">
          <button
            onClick={() => toggle(category)}
            className="w-full flex items-center justify-between px-3 py-2.5 bg-ink/[0.02] hover:bg-ink/[0.05] transition-colors text-left">
            <span className="flex items-center gap-2">
              <span className="text-ink/30 text-[10px] font-mono w-2">{isOpen(category) ? "−" : "+"}</span>
              <span className="text-[13px] font-semibold text-ink">{category}</span>
            </span>
            <span className="text-[9px] font-mono text-ink/35">{count}</span>
          </button>
          {isOpen(category) && (
            <div className="p-2.5 flex flex-col gap-3">
              {subs.map(({ name, tools: subTools }) => (
                <div key={name || "_root"}>
                  {name && (
                    <p className="text-[9px] font-mono uppercase tracking-[0.2em] text-ink/35 px-0.5 mb-1.5">{name}</p>
                  )}
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
                    {subTools.map((t) => <ToolCard key={t.id} tool={t} />)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default function OsintFrameworkBrowser() {
  const { tools, categories, limited, total_available, loading, error } = useOsintFramework();
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("all");
  const [pricing, setPricing] = useState("all");
  const [opsec, setOpsec] = useState("all");
  const [cap, setCap] = useState("all");
  const [view, setView] = useState("tree");
  const filtersActive = q.trim() !== "" || cat !== "all" || pricing !== "all" || opsec !== "all" || cap !== "all";

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return tools.filter((t) => {
      if (cat !== "all" && t.category !== cat) return false;
      if (pricing !== "all" && t.pricing !== pricing) return false;
      if (opsec !== "all" && t.opsec !== opsec) return false;
      if (cap !== "all" && t.capability !== cap) return false;
      if (needle && !(`${t.name} ${t.description} ${t.bestFor}`.toLowerCase().includes(needle))) return false;
      return true;
    });
  }, [tools, q, cat, pricing, opsec, cap]);

  return (
    <div>
      {/* Controls */}
      <div className="flex flex-wrap gap-2 mb-4">
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
        <select value={cap} onChange={(e) => setCap(e.target.value)} className="bg-ink/[0.03] border border-ink/12 px-2 py-2 text-[12px] text-ink/70 outline-none" title="Filter by what the tool can do in-app">
          <option value="all">Any capability</option>
          <option value="live">Live facts</option>
          <option value="pivot">One-click</option>
          <option value="launch">Launch</option>
        </select>
      </div>

      {/* Capability legend */}
      <div className="flex items-center gap-3 mb-3 text-[9px] font-mono text-ink/40">
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: CAP_DOT.live }} />live facts</span>
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: CAP_DOT.pivot }} />one-click pivot</span>
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: CAP_DOT.launch }} />launch + copy</span>
      </div>

      <div className="flex items-center justify-between mb-3">
        <span className="text-[9px] font-mono uppercase tracking-[0.3em] text-ink/35">
          {filtered.length} {filtered.length === 1 ? "tool" : "tools"}
          {limited && total_available ? ` of ${total_available}` : ""}
        </span>
        <div className="flex border border-ink/12">
          {["tree", "grid"].map((v) => (
            <button key={v} onClick={() => setView(v)}
              className={`px-2.5 py-1 text-[9px] font-mono uppercase tracking-wider transition-colors ${
                view === v ? "bg-crimson/10 text-crimson" : "text-ink/40 hover:text-ink/70"}`}>
              {v}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><div className="w-5 h-5 border-2 border-ink/10 border-t-crimson rounded-full animate-spin" /></div>
      ) : error ? (
        <p className="text-xs text-ink/30 text-center py-10 font-mono uppercase tracking-wider">Couldn't load the OSINT catalog.</p>
      ) : filtered.length === 0 ? (
        <p className="text-xs text-ink/30 text-center py-10 font-mono uppercase tracking-wider">No tools match these filters.</p>
      ) : view === "tree" ? (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }}>
          <TreeView tools={filtered} forceExpand={filtersActive} />
        </motion.div>
      ) : (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }}
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
          {filtered.map((t) => <ToolCard key={t.id} tool={t} />)}
        </motion.div>
      )}
    </div>
  );
}
