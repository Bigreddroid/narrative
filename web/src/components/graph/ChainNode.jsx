import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { TYPE_COLORS } from "../../lib/colors.js";

function TypeLabel({ type }) {
  const color = TYPE_COLORS[type] || "#4E6E8E";
  const short = type === "VERIFIED FACT" ? "VERIFIED"
    : type === "INFERRED MECHANISM" ? "INFERRED"
    : type === "SPECULATIVE EFFECT" ? "SPECULATIVE"
    : type;
  return (
    <span
      className="inline-flex items-center px-1.5 py-px text-2xs font-mono uppercase tracking-wider flex-shrink-0 border"
      style={{ color, borderColor: color + "30" }}
    >
      {short}
    </span>
  );
}

export default function ChainNode({ node, step, categoryColor, depth = 0 }) {
  const [expanded, setExpanded] = useState(depth === 0);

  const text = node.content || node.description || node.node || node.canonical_title || "";
  const evidence = node.evidence;
  const children = node.children || node.sub_steps || [];
  const typeColor = TYPE_COLORS[node.type] || "#4E6E8E";

  return (
    <div style={{ marginLeft: depth * 16 }}>
      <div
        className="border overflow-hidden"
        style={{ borderColor: "#152338", borderLeftColor: typeColor, borderLeftWidth: 2 }}
      >
        <button
          onClick={() => setExpanded((v) => !v)}
          className="w-full flex items-start gap-3 p-3 text-left transition-colors"
          style={{ cursor: children.length ? "pointer" : "default", backgroundColor: "#081526" }}
        >
          {depth === 0 && (
            <div
              className="flex-shrink-0 w-5 h-5 flex items-center justify-center text-2xs font-mono font-bold"
              style={{ backgroundColor: categoryColor + "20", color: categoryColor, border: `1px solid ${categoryColor}40` }}
            >
              {step}
            </div>
          )}

          <div className="flex-1 min-w-0">
            {node.type && <TypeLabel type={node.type} />}
            <p className="text-xs text-text-primary leading-snug mt-1.5">{text}</p>
          </div>

          {children.length > 0 && (
            <svg
              width="12" height="12" viewBox="0 0 12 12"
              className="flex-shrink-0 mt-1 text-text-muted transition-transform"
              style={{ transform: expanded ? "rotate(180deg)" : "rotate(0deg)" }}
              fill="none" stroke="currentColor" strokeWidth="1.5"
            >
              <polyline points="2,4 6,8 10,4" />
            </svg>
          )}
        </button>

        <AnimatePresence initial={false}>
          {expanded && evidence && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="overflow-hidden"
            >
              <blockquote
                className="mx-3 mb-3 px-3 py-2 text-2xs text-text-secondary leading-relaxed"
                style={{ borderLeft: `1px solid ${typeColor}50`, backgroundColor: "#050E1C" }}
              >
                {evidence}
              </blockquote>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <AnimatePresence initial={false}>
        {expanded && children.length > 0 && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden mt-1.5 space-y-1.5"
          >
            {children.map((child, i) => (
              <ChainNode key={i} node={child} step={i + 1} categoryColor={categoryColor} depth={depth + 1} />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
