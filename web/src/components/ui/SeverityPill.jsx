import { SEVERITY_COLORS } from "../../lib/colors.js";

export default function SeverityPill({ severity }) {
  const color = SEVERITY_COLORS[severity] || "#4F4F4F";
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-sm text-2xs font-semibold uppercase tracking-wider"
      style={{ color, backgroundColor: `${color}22`, border: `1px solid ${color}44` }}
    >
      {severity}
    </span>
  );
}
