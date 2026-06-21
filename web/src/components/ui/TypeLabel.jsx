import { TYPE_COLORS } from "../../lib/colors.js";

const TYPE_SHORT = {
  "VERIFIED FACT": "VERIFIED",
  "INFERRED MECHANISM": "INFERRED",
  "SPECULATIVE EFFECT": "SPECULATIVE",
};

export default function TypeLabel({ type, size = "sm" }) {
  const color = TYPE_COLORS[type] || "#8B949E";
  const label = TYPE_SHORT[type] || type;

  return (
    <span
      className="inline-flex items-center rounded-sm font-semibold uppercase tracking-wider"
      style={{
        color,
        backgroundColor: `${color}11`,
        border: `1px solid ${color}33`,
        fontSize: size === "xs" ? "0.6rem" : "0.625rem",
        padding: size === "xs" ? "1px 5px" : "2px 6px",
        letterSpacing: "0.12em",
      }}
    >
      {label}
    </span>
  );
}
