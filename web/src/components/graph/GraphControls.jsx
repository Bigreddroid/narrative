import { motion } from "framer-motion";

export default function GraphControls({
  onZoomIn,
  onZoomOut,
  onReset,
  filterCategory,
  onFilterCategory,
  categories = [],
}) {
  const CATEGORY_COLORS = {
    geopolitics: "#FF4B4B",
    economy: "#F5A623",
    climate: "#27AE60",
    health: "#2D9CDB",
    technology: "#9B51E0",
    conflict: "#EB5757",
    policy: "#56CCF2",
  };

  return (
    <div className="flex flex-col gap-2">
      {/* Zoom controls */}
      <div className="flex flex-col bg-bg-elevated border border-border rounded-lg overflow-hidden">
        {[
          { label: "+", title: "Zoom in", onClick: onZoomIn },
          { label: "⊙", title: "Reset view", onClick: onReset },
          { label: "−", title: "Zoom out", onClick: onZoomOut },
        ].map(({ label, title, onClick }) => (
          <motion.button
            key={label}
            onClick={onClick}
            title={title}
            className="w-10 h-10 flex items-center justify-center text-text-secondary hover:text-text-primary hover:bg-bg-elevated transition-colors border-b border-border last:border-0 text-sm font-medium"
            whileTap={{ scale: 0.9 }}
          >
            {label}
          </motion.button>
        ))}
      </div>

      {/* Category filter pills */}
      {categories.length > 0 && (
        <div className="flex flex-col gap-1.5">
          {categories.map((cat) => {
            const color = CATEGORY_COLORS[cat] || "#8B949E";
            const active = filterCategory === cat;
            return (
              <motion.button
                key={cat}
                onClick={() => onFilterCategory?.(active ? null : cat)}
                title={cat}
                className="w-10 h-3 rounded-full transition-all"
                style={{
                  backgroundColor: active ? color : `${color}33`,
                  boxShadow: active ? `0 0 8px ${color}66` : "none",
                }}
                whileHover={{ backgroundColor: color }}
                whileTap={{ scale: 0.9 }}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
