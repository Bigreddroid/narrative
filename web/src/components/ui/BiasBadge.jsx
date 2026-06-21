const BIAS_COLORS = {
  "left": "#2D9CDB",
  "center-left": "#56CCF2",
  "center": "#27AE60",
  "center-right": "#F5A623",
  "right": "#EB5757",
  "unknown": "#4F4F4F",
};

export default function BiasBadge({ rating }) {
  const color = BIAS_COLORS[rating] || BIAS_COLORS.unknown;
  return (
    <span
      className="inline-flex items-center px-1.5 py-0.5 rounded-sm text-2xs font-medium uppercase tracking-wide"
      style={{ color, backgroundColor: `${color}22`, border: `1px solid ${color}44` }}
    >
      {rating || "unknown"}
    </span>
  );
}
