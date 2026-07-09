import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { getCategoryColor } from "../../lib/colors.js";
import { useConsequenceTrace } from "../../hooks/useConsequenceTrace.js";

// ─── hops → nested tree ────────────────────────────────────────────────────────
// The trace `hops` array is the winning INCOMING edge per node (from → to), so every
// reached event has exactly one parent: the data is already a tree rooted at root.id.
// Build a parent→children map, then DFS from the root. Pure + exported for unit tests.
export function buildTraceTree(trace) {
  if (!trace || !trace.root) return null;

  const nodeById = new Map((trace.nodes || []).map((n) => [String(n.id), n]));
  const childrenByParent = new Map();

  for (const hop of trace.hops || []) {
    const from = String(hop.from);
    const node = nodeById.get(String(hop.to));
    if (!node) continue; // hop points outside the returned node set — skip
    if (!childrenByParent.has(from)) childrenByParent.set(from, []);
    childrenByParent.get(from).push({ ...node, hop });
  }

  // Grounded consequences first, then strongest path (mirrors the backend node order).
  for (const arr of childrenByParent.values()) {
    arr.sort((a, b) => Number(b.grounded) - Number(a.grounded) || b.score - a.score);
  }

  const visited = new Set([String(trace.root.id)]);
  const attach = (id) =>
    (childrenByParent.get(String(id)) || [])
      .filter((k) => !visited.has(String(k.id))) // defensive cycle guard (should be a tree)
      .map((k) => {
        visited.add(String(k.id));
        return { ...k, children: attach(k.id) };
      });

  return {
    id: String(trace.root.id),
    title: trace.root.title,
    category: trace.root.category,
    isRoot: true,
    children: attach(trace.root.id),
  };
}

const KIND_LABEL = {
  semantic: "SEMANTIC",
  geographic: "GEOGRAPHIC",
  sectoral: "SECTORAL",
  co_occurrence: "CO-OCCUR",
};

// ─── one hop node (recursive) ──────────────────────────────────────────────────
function TraceHop({ node }) {
  const color = getCategoryColor(node.category);
  const grounded = node.grounded;
  const label = KIND_LABEL[node.hop?.kind] || KIND_LABEL.co_occurrence;
  const mechanism = node.hop?.mechanism;

  return (
    <motion.div
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.2 }}
    >
      <div className="flex gap-2.5">
        <div className="flex flex-col items-center flex-shrink-0 pt-1">
          <div
            className="w-2 h-2 rounded-full flex-shrink-0"
            style={{
              backgroundColor: grounded ? color : "transparent",
              border: `1px solid ${grounded ? color : "rgba(136,136,136,0.6)"}`,
            }}
          />
        </div>

        <div className="flex-1 min-w-0 pb-3">
          <div className="flex items-center gap-2 mb-0.5 flex-wrap">
            <span
              className="text-[8px] font-mono uppercase tracking-widest border px-1 py-px"
              style={{
                color: grounded ? color : "rgba(136,136,136,0.9)",
                borderColor: (grounded ? color : "#888") + "40",
              }}
            >
              {label}
            </span>
            <span className="text-[8px] font-mono text-ink/30">{node.score}</span>
          </div>

          <p className={`text-xs leading-snug ${grounded ? "text-ink" : "text-ink/40"}`}>
            {node.title || "Untitled event"}
          </p>

          {mechanism && mechanism !== "related" && (
            <p className="text-[9px] font-mono text-ink/35 mt-0.5 leading-relaxed">{mechanism}</p>
          )}

          {node.children?.length > 0 && (
            <div
              className="mt-2 pl-3 border-l border-dashed"
              style={{ borderColor: "rgba(136,136,136,0.28)" }}
            >
              {node.children.map((c) => (
                <TraceHop key={c.id} node={c} />
              ))}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}

// ─── panel ──────────────────────────────────────────────────────────────────────
export default function ConsequenceTrace({ eventId }) {
  const [depth, setDepth] = useState(3);
  const [groundedOnly, setGroundedOnly] = useState(false);
  const { trace, loading, error } = useConsequenceTrace(eventId, { depth, groundedOnly });

  const tree = buildTraceTree(trace);
  const isEmpty = !tree || trace?.limited || (tree.children?.length ?? 0) === 0;

  return (
    <div className="p-4">
      {/* Controls */}
      <div className="flex items-center gap-4 mb-4 flex-wrap">
        <label className="flex items-center gap-1.5 text-[9px] font-mono uppercase tracking-widest text-ink/45">
          Depth
          <select
            value={depth}
            onChange={(e) => setDepth(Number(e.target.value))}
            className="bg-transparent border border-ink/15 text-ink px-1.5 py-0.5 text-[10px] font-mono focus:outline-none focus:border-crimson"
          >
            {[1, 2, 3, 4].map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </label>

        <label className="flex items-center gap-1.5 text-[9px] font-mono uppercase tracking-widest text-ink/45 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={groundedOnly}
            onChange={(e) => setGroundedOnly(e.target.checked)}
            className="accent-crimson"
          />
          Grounded only
        </label>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={`${depth}-${groundedOnly}`}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.12 }}
        >
          {loading ? (
            <div className="flex items-center justify-center py-10">
              <div className="w-5 h-5 border-2 border-ink/10 border-t-crimson rounded-full animate-spin" />
            </div>
          ) : error ? (
            <p className="text-xs text-ink/30 text-center py-8 font-mono uppercase tracking-wider">
              Trace unavailable.
            </p>
          ) : isEmpty ? (
            <p className="text-xs text-ink/30 text-center py-8 font-mono uppercase tracking-wider">
              No downstream consequences traced.
            </p>
          ) : (
            <>
              {/* Root */}
              <div className="flex items-center gap-2 mb-3">
                <div
                  className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                  style={{ backgroundColor: getCategoryColor(tree.category) }}
                />
                <span className="text-[8px] font-mono uppercase tracking-widest text-ink/40">Root</span>
                <p className="text-xs font-medium text-ink leading-snug flex-1 min-w-0">{tree.title}</p>
              </div>

              <div className="pl-3 border-l border-dashed" style={{ borderColor: "rgba(136,136,136,0.28)" }}>
                {tree.children.map((c) => (
                  <TraceHop key={c.id} node={c} />
                ))}
              </div>

              <p className="text-[9px] font-mono text-ink/30 mt-3 pt-3 border-t border-ink/10 leading-relaxed">
                Directed consequence chain · grounded links solid, co-occurrence hollow · deterministic (no LLM)
              </p>
            </>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
