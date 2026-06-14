import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

export default function AlertBanner({ message, type = "info", onDismiss }) {
  const [visible, setVisible] = useState(true);

  const COLORS = {
    info: "#56CCF2",
    warning: "#F5A623",
    error: "#FF4B4B",
    success: "#27AE60",
  };
  const color = COLORS[type] || COLORS.info;

  const dismiss = () => {
    setVisible(false);
    onDismiss?.();
  };

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ type: "spring", stiffness: 400, damping: 30 }}
          className="flex items-center gap-3 px-4 py-3 rounded-lg border text-sm"
          style={{
            backgroundColor: `${color}11`,
            borderColor: `${color}44`,
            color,
          }}
        >
          <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
          <span className="flex-1 text-text-primary text-xs leading-relaxed">{message}</span>
          <button
            onClick={dismiss}
            className="text-text-muted hover:text-text-primary transition-colors ml-2 text-base leading-none"
          >
            ×
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
