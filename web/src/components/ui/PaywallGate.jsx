import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";

/**
 * Wraps any content that requires paid tier.
 * Shows blurred preview + upgrade prompt for free users.
 */
export default function PaywallGate({ user, children, feature = "This feature" }) {
  const navigate = useNavigate();

  if (!user || user.tier === "paid") {
    return children;
  }

  return (
    <div className="relative">
      {/* Blurred content preview */}
      <div className="pointer-events-none select-none" style={{ filter: "blur(4px)", opacity: 0.4 }}>
        {children}
      </div>

      {/* Lock overlay */}
      <motion.div
        className="absolute inset-0 flex flex-col items-center justify-center"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3 }}
      >
        <div
          className="rounded-2xl border border-border px-8 py-6 flex flex-col items-center gap-4 text-center max-w-xs"
          style={{ background: "rgba(13, 17, 23, 0.92)", backdropFilter: "blur(8px)" }}
        >
          <div className="w-10 h-10 rounded-full flex items-center justify-center text-xl"
            style={{ background: "#F5A62320", color: "#F5A623" }}>
            ⬡
          </div>
          <div>
            <p className="text-sm font-semibold text-text-primary mb-1">{feature} is paid-only</p>
            <p className="text-xs text-text-muted leading-relaxed">
              Unlock the full consequence chain, prediction scores, and deep impact analysis.
            </p>
          </div>
          <motion.button
            onClick={() => navigate("/settings?upgrade=1")}
            className="w-full py-2.5 rounded-lg text-sm font-semibold text-white"
            style={{ background: "linear-gradient(135deg, #F5A623 0%, #E8941A 100%)" }}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.97 }}
          >
            Upgrade — $6.99/mo
          </motion.button>
        </div>
      </motion.div>
    </div>
  );
}
