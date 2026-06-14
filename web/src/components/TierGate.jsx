import { motion } from "framer-motion";
import { TIERS, ACCESS } from "../lib/tiers.js";
import { useUser } from "../hooks/useUser.js";

const FEATURE_LABELS = {
  eventGraph:    { name: "Consequence Chain Analysis", plan: "Pro" },
  worldRegions:  { name: "Regional Drill-Down",        plan: "Pro" },
  predictions:   { name: "Prediction Arcs",            plan: "Pro" },
  effects:       { name: "Impact Analysis",            plan: "Pro" },
  articleSources:{ name: "Source Articles",            plan: "Pro" },
  apiAccess:     { name: "API Access",                 plan: "Intelligence" },
  realTimeAlerts:{ name: "Real-Time Alerts",           plan: "Intelligence" },
  export:        { name: "Export",                     plan: "Intelligence" },
};

export default function TierGate({ feature, children, inline = false }) {
  const { can } = useUser();
  if (can(feature)) return children;

  const meta = FEATURE_LABELS[feature] || { name: feature, plan: "Pro" };

  if (inline) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 border border-ink/10 bg-ink/[0.03]">
        <span className="w-1 h-1 rounded-full bg-crimson flex-shrink-0" />
        <span className="text-[10px] text-ink/40 tracking-wide">
          {meta.name} · <span className="text-crimson">{meta.plan}+</span>
        </span>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex flex-col items-center justify-center h-full p-8 text-center"
    >
      <div className="w-8 h-8 border border-crimson/30 flex items-center justify-center mb-5">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="#C80028" strokeWidth="1.4">
          <rect x="2" y="6" width="10" height="7" rx="1" />
          <path d="M4.5 6V4.5a2.5 2.5 0 0 1 5 0V6" />
        </svg>
      </div>
      <p className="text-[11px] font-bold uppercase tracking-widest text-ink/50 mb-1">{meta.name}</p>
      <p className="text-xs text-ink/35 mb-5 leading-relaxed max-w-[200px]">
        Available on <span className="text-crimson font-semibold">{meta.plan}</span> and above.
      </p>
      <a
        href="/settings"
        className="text-[10px] font-bold uppercase tracking-widest text-crimson border border-crimson/30 px-4 py-2 hover:bg-crimson hover:text-paper transition-colors"
      >
        Upgrade
      </a>
    </motion.div>
  );
}
