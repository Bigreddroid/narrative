import { CATEGORY_COLORS } from "../../lib/colors.js";

const STATUS_CONFIG = {
  developing: { color: "#F5A623", animation: "pulse-slow" },
  escalating: { color: "#FF4B4B", animation: "pulse-fast" },
  stable: { color: "#27AE60", animation: null },
  resolved: { color: "#4F4F4F", animation: null },
};

export default function StatusPulse({ status, size = 8 }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.stable;

  return (
    <span className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      {config.animation && (
        <span
          className={`absolute inset-0 rounded-full opacity-60 animate-${config.animation}`}
          style={{ backgroundColor: config.color }}
        />
      )}
      <span
        className="relative rounded-full"
        style={{
          width: size,
          height: size,
          backgroundColor: config.color,
          opacity: status === "resolved" ? 0.4 : 1,
        }}
      />
    </span>
  );
}
