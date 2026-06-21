import { useState } from "react";
import { motion } from "framer-motion";

export default function EvolutionTimeline({ revisions = [], onSelectRevision }) {
  const [selected, setSelected] = useState(null);

  if (!revisions || revisions.length === 0) return null;

  const maxScore = Math.max(...revisions.map((r) => r.prediction_score || 0), 1);

  const handleSelect = (revision) => {
    setSelected(revision.version);
    onSelectRevision?.(revision);
  };

  return (
    <div className="border-t border-border pt-4">
      <p className="text-2xs uppercase tracking-wider text-text-muted mb-3">
        Evolution History — {revisions.length} revision{revisions.length !== 1 ? "s" : ""}
      </p>

      <div className="relative">
        {/* Baseline */}
        <div className="absolute left-0 right-0 h-px bg-border" style={{ top: "50%" }} />

        <div className="flex items-end gap-4 overflow-x-auto pb-2 relative">
          {revisions.map((revision, i) => {
            const height = Math.max(8, ((revision.prediction_score || 0) / maxScore) * 40);
            const isSelected = selected === revision.version;
            const isLatest = i === revisions.length - 1;

            return (
              <motion.button
                key={revision.version}
                onClick={() => handleSelect(revision)}
                className="flex flex-col items-center gap-1 flex-shrink-0 group"
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.95 }}
              >
                {/* Score bar */}
                <motion.div
                  className="w-1.5 rounded-full transition-colors"
                  style={{
                    height,
                    backgroundColor: isSelected
                      ? "#F0F6FC"
                      : isLatest
                      ? "#F5A623"
                      : "#21262D",
                  }}
                  initial={{ height: 0 }}
                  animate={{ height }}
                  transition={{ duration: 0.4, delay: i * 0.05 }}
                />

                {/* Dot */}
                <div
                  className="w-2 h-2 rounded-full border transition-colors"
                  style={{
                    backgroundColor: isSelected ? "#F0F6FC" : "#161B22",
                    borderColor: isSelected
                      ? "#F0F6FC"
                      : isLatest
                      ? "#F5A623"
                      : "#21262D",
                  }}
                />

                {/* Date */}
                <span className="text-2xs font-mono text-text-muted group-hover:text-text-secondary transition-colors whitespace-nowrap">
                  {new Date(revision.created_at).toLocaleDateString("en", {
                    month: "short",
                    day: "numeric",
                  })}
                </span>

                {/* Score */}
                {isSelected && (
                  <motion.span
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-2xs font-mono text-text-primary font-bold"
                  >
                    {revision.prediction_score}
                  </motion.span>
                )}

                {/* Tooltip */}
                <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                  <div className="bg-bg-elevated border border-border rounded-lg px-2 py-1.5 text-2xs text-text-secondary whitespace-nowrap shadow-xl">
                    v{revision.version} · {revision.confidence} confidence
                    {revision.change_summary && (
                      <div className="text-text-muted mt-0.5 max-w-40 truncate">
                        {revision.change_summary}
                      </div>
                    )}
                  </div>
                </div>
              </motion.button>
            );
          })}
        </div>
      </div>

      {selected && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="mt-2 text-2xs text-text-muted"
        >
          Viewing v{selected} — click another point to compare
        </motion.p>
      )}
    </div>
  );
}
