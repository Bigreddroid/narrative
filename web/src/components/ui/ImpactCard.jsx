import { motion } from "framer-motion";
import { getCategoryColor } from "../../lib/colors.js";
import SeverityPill from "./SeverityPill.jsx";

export default function ImpactCard({ event, onClick }) {
  const color = getCategoryColor(event.category);

  return (
    <motion.button
      onClick={() => onClick && onClick(event)}
      className="w-full text-left bg-bg-elevated border border-border rounded-lg p-4 hover:border-opacity-60 transition-all"
      whileHover={{ y: -2, boxShadow: `0 8px 32px ${color}22` }}
      transition={{ type: "spring", stiffness: 400, damping: 30 }}
      style={{ borderColor: "#21262D" }}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
          <span className="text-2xs uppercase tracking-widest font-medium" style={{ color }}>
            {event.category}
          </span>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {event.prediction_score !== undefined && (
            <span className="font-mono text-xs text-text-secondary">
              {event.prediction_score}
            </span>
          )}
          <span
            className="text-2xs capitalize text-text-muted border border-border px-1.5 py-0.5 rounded-full"
          >
            {event.current_status}
          </span>
        </div>
      </div>

      <h3 className="text-sm font-semibold text-text-primary leading-snug mb-2">
        {event.canonical_title}
      </h3>

      {event.canonical_summary && (
        <p className="text-xs text-text-secondary leading-relaxed mb-3 line-clamp-2">
          {event.canonical_summary}
        </p>
      )}

      {event.direct_impact && (
        <div
          className="text-xs text-text-secondary leading-relaxed p-2 rounded-sm"
          style={{ backgroundColor: `${color}11`, borderLeft: `2px solid ${color}66` }}
        >
          {event.direct_impact.description}
        </div>
      )}

      <div className="flex items-center gap-2 mt-3">
        {event.affected_sectors?.slice(0, 3).map((s) => (
          <span
            key={s}
            className="text-2xs text-text-muted border border-border rounded-sm px-1.5 py-0.5"
          >
            {s}
          </span>
        ))}
        {event.last_updated_at && (
          <span className="ml-auto text-2xs text-text-muted">
            {new Date(event.last_updated_at).toLocaleDateString()}
          </span>
        )}
      </div>
    </motion.button>
  );
}
