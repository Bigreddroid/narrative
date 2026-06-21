import { motion } from "framer-motion";

// Globe control rail — zoom, reset, auto-spin toggle. Dark translucent panel
// matching the map's legend/count chips. Adapted from the legacy GraphControls.
export default function GlobeControls({ onZoomIn, onZoomOut, onReset, spinning, onToggleSpin }) {
  const panel = {
    backgroundColor: "rgba(14,21,32,0.85)",
    borderColor: "rgba(232,228,220,0.12)",
  };
  const fg = "rgba(232,228,220,0.55)";

  const Btn = ({ title, onClick, children, active }) => (
    <motion.button
      onClick={onClick}
      title={title}
      whileTap={{ scale: 0.9 }}
      className="w-9 h-9 flex items-center justify-center transition-colors"
      style={{ color: active ? "#C80028" : fg }}
      onMouseEnter={(e) => { if (!active) e.currentTarget.style.color = "#E8E4DC"; }}
      onMouseLeave={(e) => { if (!active) e.currentTarget.style.color = fg; }}
    >
      {children}
    </motion.button>
  );

  return (
    <div className="absolute top-3 left-3 z-20 flex flex-col gap-2">
      <div className="flex flex-col backdrop-blur-sm border overflow-hidden shadow-sm" style={panel}>
        <Btn title="Zoom in" onClick={onZoomIn}>
          <svg width="14" height="14" viewBox="0 0 14 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            <line x1="7" y1="2.5" x2="7" y2="11.5" /><line x1="2.5" y1="7" x2="11.5" y2="7" />
          </svg>
        </Btn>
        <div style={{ height: 1, backgroundColor: "rgba(232,228,220,0.10)" }} />
        <Btn title="Reset view" onClick={onReset}>
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
            <circle cx="8" cy="8" r="5.5" /><circle cx="8" cy="8" r="1.4" fill="currentColor" stroke="none" />
          </svg>
        </Btn>
        <div style={{ height: 1, backgroundColor: "rgba(232,228,220,0.10)" }} />
        <Btn title="Zoom out" onClick={onZoomOut}>
          <svg width="14" height="14" viewBox="0 0 14 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            <line x1="2.5" y1="7" x2="11.5" y2="7" />
          </svg>
        </Btn>
      </div>

      <div className="backdrop-blur-sm border overflow-hidden shadow-sm" style={panel}>
        <Btn title={spinning ? "Pause rotation" : "Auto-rotate"} onClick={onToggleSpin} active={spinning}>
          {spinning ? (
            <svg width="13" height="13" viewBox="0 0 14 14" fill="currentColor">
              <rect x="3" y="2.5" width="2.5" height="9" rx="0.5" /><rect x="8.5" y="2.5" width="2.5" height="9" rx="0.5" />
            </svg>
          ) : (
            <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 7a5 5 0 1 1-1.5-3.6" /><path d="M12 1.5V4H9.5" />
            </svg>
          )}
        </Btn>
      </div>
    </div>
  );
}
