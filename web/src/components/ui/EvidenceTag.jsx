import { TYPE_COLORS } from "../../lib/colors.js";

export default function EvidenceTag({ text, source, type }) {
  const borderColor = TYPE_COLORS[type] || "#8B949E";

  return (
    <blockquote
      className="rounded-sm py-2 px-3"
      style={{
        borderLeft: `2px solid ${borderColor}`,
        backgroundColor: `${borderColor}08`,
      }}
    >
      <p className="text-xs italic text-text-secondary leading-relaxed">
        "{text}"
      </p>
      {source && (
        <footer className="mt-1">
          <span className="text-2xs uppercase tracking-wider font-medium text-text-muted">
            — {source}
          </span>
        </footer>
      )}
    </blockquote>
  );
}
