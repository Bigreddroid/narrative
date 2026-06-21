import { motion } from "framer-motion";

function getColor(score) {
  if (score >= 70) return "#FF4B4B";
  if (score >= 40) return "#F5A623";
  return "#27AE60";
}

export default function PredictionMeter({ score = 0, confidence, reasoning, size = 96 }) {
  const radius = (size / 2) - 8;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (Math.max(0, Math.min(100, score)) / 100) * circumference;
  const color = getColor(score);
  const center = size / 2;

  return (
    <div className="flex flex-col items-center gap-2 group relative">
      <div style={{ width: size, height: size }} className="relative">
        <svg
          viewBox={`0 0 ${size} ${size}`}
          className="w-full h-full -rotate-90"
        >
          {/* Track */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="#21262D"
            strokeWidth="6"
          />
          {/* Confidence band (lighter, wider) */}
          {confidence && (
            <circle
              cx={center}
              cy={center}
              r={radius}
              fill="none"
              stroke={`${color}33`}
              strokeWidth="10"
              strokeDasharray={circumference}
              strokeDashoffset={circumference * (1 - (score + 10) / 100)}
              strokeLinecap="round"
            />
          )}
          {/* Score arc */}
          <motion.circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 1, ease: "easeOut", delay: 0.2 }}
          />
        </svg>

        {/* Center score */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className="font-mono font-bold leading-none"
            style={{ fontSize: size * 0.22, color }}
          >
            {score}
          </span>
          {confidence && (
            <span className="text-2xs text-text-muted capitalize mt-0.5">{confidence}</span>
          )}
        </div>
      </div>

      {/* Reasoning tooltip on hover */}
      {reasoning && (
        <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 w-56 bg-bg-elevated border border-border rounded-lg p-3 text-xs text-text-secondary leading-relaxed opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-2xl">
          {reasoning}
        </div>
      )}
    </div>
  );
}
