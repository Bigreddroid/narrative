import { useEffect, useRef } from "react";
import { getCategoryColor } from "../../lib/colors.js";

export default function EdgeLine({
  x1, y1, x2, y2,
  weight = 0.5,
  categoryA = "geopolitics",
  categoryB = "economy",
  highlighted = false,
  onClick,
}) {
  const pathRef = useRef(null);

  const colorA = getCategoryColor(categoryA);
  const colorB = getCategoryColor(categoryB);
  const strokeWidth = 1 + weight * 2;
  const opacity = highlighted ? 0.8 : 0.25;
  const id = `edge-grad-${categoryA}-${categoryB}`.replace(/[^a-z-]/gi, "");

  // Midpoint for curve
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  const d = `M ${x1} ${y1} Q ${mx} ${my - 20} ${x2} ${y2}`;

  const pathLength = pathRef.current?.getTotalLength?.() || 200;

  return (
    <g onClick={onClick} style={{ cursor: onClick ? "pointer" : "default" }}>
      <defs>
        <linearGradient id={id} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor={colorA} stopOpacity={opacity} />
          <stop offset="100%" stopColor={colorB} stopOpacity={opacity} />
        </linearGradient>
      </defs>

      {/* Invisible hit area */}
      {onClick && (
        <path d={d} stroke="transparent" strokeWidth={16} fill="none" />
      )}

      {/* Visible edge */}
      <path
        ref={pathRef}
        d={d}
        stroke={`url(#${id})`}
        strokeWidth={strokeWidth}
        fill="none"
        strokeLinecap="round"
        style={{
          transition: "opacity 0.2s ease, stroke-width 0.2s ease",
        }}
      />

      {/* Particle animation along edge */}
      {highlighted && (
        <circle r={2} fill={colorA} opacity={0.9}>
          <animateMotion
            dur={`${2 / weight}s`}
            repeatCount="indefinite"
            path={d}
          />
        </circle>
      )}
    </g>
  );
}
