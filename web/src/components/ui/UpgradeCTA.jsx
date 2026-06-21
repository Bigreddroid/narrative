import { motion } from "framer-motion";
import { useState } from "react";
import { api } from "../../lib/api.js";

const FEATURES = [
  "Full consequence chains — every causal node",
  "Prediction confidence scores with calibration history",
  "Unlimited follows — track any event",
  "Push alerts when followed events escalate",
  "Deep sector and geographic impact analysis",
  "Event evolution timeline with revision history",
];

export default function UpgradeCTA({ onUpgraded }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleUpgrade = async () => {
    setLoading(true);
    setError(null);
    try {
      const { checkout_url } = await api.post("/stripe/checkout", {});
      window.location.href = checkout_url;
    } catch (err) {
      setError(err.message || "Failed to start checkout. Try again.");
      setLoading(false);
    }
  };

  return (
    <motion.div
      className="rounded-2xl border border-border p-6"
      style={{ background: "linear-gradient(135deg, #0D1117 0%, #161B22 100%)" }}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-5">
        <div>
          <div className="text-xs font-semibold uppercase tracking-widest mb-1" style={{ color: "#F5A623" }}>
            Full Access
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-3xl font-bold text-text-primary">$6.99</span>
            <span className="text-sm text-text-muted">/month</span>
          </div>
          <p className="text-xs text-text-muted mt-1">Cancel anytime. No lock-in.</p>
        </div>
        <div
          className="text-2xl w-12 h-12 rounded-xl flex items-center justify-center"
          style={{ background: "#F5A62318" }}
        >
          ⬡
        </div>
      </div>

      {/* Feature list */}
      <ul className="space-y-2.5 mb-6">
        {FEATURES.map((feat) => (
          <li key={feat} className="flex items-start gap-2.5 text-sm text-text-secondary">
            <span className="mt-0.5 flex-shrink-0 w-4 h-4 rounded-full flex items-center justify-center text-xs"
              style={{ background: "#F5A62320", color: "#F5A623" }}>✓</span>
            {feat}
          </li>
        ))}
      </ul>

      {error && (
        <p className="text-xs text-red-400 mb-3">{error}</p>
      )}

      <motion.button
        onClick={handleUpgrade}
        disabled={loading}
        className="w-full py-3 rounded-xl text-sm font-semibold text-white disabled:opacity-50 transition-opacity"
        style={{ background: "linear-gradient(135deg, #F5A623 0%, #E8941A 100%)" }}
        whileHover={{ scale: 1.01 }}
        whileTap={{ scale: 0.98 }}
      >
        {loading ? "Redirecting to checkout..." : "Upgrade to Full Access"}
      </motion.button>

      <p className="text-xs text-text-muted text-center mt-3">
        Secured by Stripe. Your card is never stored here.
      </p>
    </motion.div>
  );
}
