// ─────────────────────────────────────────────────────────────────────────────
// ExecGlobe — the interactive globe for the executive deck.
//
// Uses Narrative's own map treatment (components/graph/WorldMap.jsx): an
// orthographic projection with a radial ocean gradient, a 20° graticule and a
// three-shade landmass — not a flat grey projection. Sites are plotted by severity
// and sized by headcount.
//
// Everything here is real interaction over real state — drag to rotate, wheel to
// zoom, hover for the site's actual driving signal, click to select. No decorative
// controls.
// ─────────────────────────────────────────────────────────────────────────────
import { useMemo, useRef, useState, useEffect, useCallback } from "react";
import * as d3 from "d3";
import * as topojson from "topojson-client";
import { useTheme } from "../../hooks/useTheme.js";

const WORLD_TOPO_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

// Dark-surface severity steps, contrast-checked against #050505:
// clear 8.92:1 · watch 9.62:1 · alert 6.66:1. Never used without a label.
export const SEV = {
  clear: { c: "#5FBF74", label: "Clear" },
  watch: { c: "#E0A93C", label: "Watch" },
  alert: { c: "#FF5C43", label: "Alert" },
};

// Landmass shading from the same three-tone treatment WorldMap uses, so the two
// surfaces read as one product.
//
// These are SVG presentation attributes (fill=, stroke=), which do NOT resolve
// CSS custom properties — so unlike the rest of the deck the globe cannot ride
// the --xd-* variables and needs its palette picked in JS. Day mode is a paper
// map: cream land on a pale-blue ocean. The severity hues are shared by both and
// live in SEV above, unchanged, because a band must not shift meaning with theme.
const GLOBE = {
  dark: {
    shades: ["#171B22", "#1B2029", "#14181E"],
    ocean: "#0A1018", oceanEdge: "#05070C",
    sphere: "#252A33", graticule: "#1A2029", coast: "#232A34",
    halo: "#F0EDE8", pinEdge: "#05070C",
  },
  light: {
    shades: ["#EDE7DA", "#E5DED0", "#F3EEE4"],
    ocean: "#DCE8F2", oceanEdge: "#C2D6E8",
    sphere: "#A9B6C2", graticule: "#CBDAE6", coast: "#C3B9A6",
    halo: "#1A1A1A", pinEdge: "#FFFFFF",
  },
};

export default function ExecGlobe({
  contexts, topSignalOf, selectedId, onSelect, filter = null, height = 520,
}) {
  const { isDark } = useTheme();
  const g = isDark ? GLOBE.dark : GLOBE.light;
  const [world, setWorld] = useState(null);
  const [rotation, setRotation] = useState([-20, -12]);
  const [scale, setScale] = useState(1);
  const [hover, setHover] = useState(null);
  const drag = useRef(null);
  const wrap = useRef(null);

  useEffect(() => {
    let cancelled = false;
    fetch(WORLD_TOPO_URL)
      .then((r) => r.json())
      .then((t) => { if (!cancelled) setWorld(topojson.feature(t, t.objects.countries)); })
      .catch(() => { if (!cancelled) setWorld("error"); });
    return () => { cancelled = true; };
  }, []);

  const W = 620, H = 620;
  const projection = useMemo(() => d3.geoOrthographic()
    .fitExtent([[18, 18], [W - 18, H - 18]], { type: "Sphere" })
    .rotate([rotation[0], rotation[1]])
    .scale(((Math.min(W, H) / 2) - 18) * scale)
    .translate([W / 2, H / 2]), [rotation, scale]);

  const path = useMemo(() => d3.geoPath(projection), [projection]);
  const graticule = useMemo(() => d3.geoGraticule().step([20, 20])(), []);

  // A site is drawn only when it is on the visible hemisphere — an orthographic
  // projection happily projects points behind the globe, which would otherwise
  // paint India onto the Pacific.
  const visible = useCallback((lng, lat) => {
    const r = projection.rotate();
    const c = d3.geoDistance([lng, lat], [-r[0], -r[1]]);
    return c < Math.PI / 2;
  }, [projection]);

  const dots = useMemo(() => {
    const rank = { clear: 0, watch: 1, alert: 2 };
    return contexts
      .filter((c) => !filter || c.worst === filter)
      .map((c) => {
        if (!visible(c.office.lng, c.office.lat)) return null;
        const p = projection([c.office.lng, c.office.lat]);
        if (!p) return null;
        return {
          ctx: c, id: c.office.id, x: p[0], y: p[1],
          r: 2.4 + Math.sqrt(Math.max(c.office.headcount || 0, 1)) / 30,
          level: c.worst,
        };
      })
      .filter(Boolean)
      .sort((a, b) => rank[a.level] - rank[b.level]);
  }, [contexts, projection, visible, filter]);

  const onPointerDown = (e) => {
    drag.current = { x: e.clientX, y: e.clientY, rot: rotation };
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const onPointerMove = (e) => {
    if (!drag.current) return;
    const k = 0.35 / scale;
    const dx = (e.clientX - drag.current.x) * k;
    const dy = (e.clientY - drag.current.y) * k;
    setRotation([drag.current.rot[0] + dx, Math.max(-85, Math.min(85, drag.current.rot[1] - dy))]);
  };
  const endDrag = () => { drag.current = null; };
  const onWheel = (e) => {
    // Non-passive listener attached below so preventDefault is honoured.
    setScale((s) => Math.max(0.75, Math.min(3.2, s * (e.deltaY < 0 ? 1.12 : 0.89))));
  };
  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const h = (e) => { e.preventDefault(); onWheel(e); };
    el.addEventListener("wheel", h, { passive: false });
    return () => el.removeEventListener("wheel", h);
  }, []);

  if (world === "error") {
    return (
      <div style={{ height }} className="flex items-center justify-center">
        <p className="font-mono text-[10px] text-[var(--xd-16)] max-w-xs text-center leading-relaxed">
          World geometry unavailable — the figures alongside carry the same picture.
        </p>
      </div>
    );
  }

  const hoveredSignal = hover ? topSignalOf?.(hover.ctx) : null;

  return (
    <div ref={wrap} className="relative select-none" style={{ height }}>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-full touch-none cursor-grab active:cursor-grabbing"
        onPointerDown={onPointerDown} onPointerMove={onPointerMove}
        onPointerUp={endDrag} onPointerLeave={() => { endDrag(); setHover(null); }}>
        <defs>
          <radialGradient id="exec-ocean" cx="42%" cy="38%" r="72%">
            <stop offset="0%" stopColor={g.ocean} stopOpacity="1" />
            <stop offset="100%" stopColor={g.oceanEdge} stopOpacity="1" />
          </radialGradient>
          <filter id="exec-glow" x="-70%" y="-70%" width="240%" height="240%">
            <feGaussianBlur stdDeviation="3.2" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        <path d={path({ type: "Sphere" })} fill="url(#exec-ocean)" stroke={g.sphere} strokeWidth={0.6} />
        <path d={path(graticule)} fill="none" stroke={g.graticule} strokeWidth={0.3} />
        {world && world.features.map((f, i) => (
          <path key={i} d={path(f)} fill={g.shades[(+f.id || i) % 3]} stroke={g.coast} strokeWidth={0.3} />
        ))}

        {dots.map((d) => {
          const isSel = selectedId === d.id;
          return (
            <g key={d.id} style={{ cursor: "pointer" }}
              onPointerEnter={() => setHover(d)}
              onClick={(e) => { e.stopPropagation(); onSelect?.(d.ctx); }}>
              {d.level === "alert" && (
                <circle cx={d.x} cy={d.y} r={d.r * 3.4} fill={SEV.alert.c} opacity={0.12} />
              )}
              {isSel && (
                <circle cx={d.x} cy={d.y} r={d.r + 7} fill="none"
                  stroke={g.halo} strokeWidth={1} opacity={0.85} />
              )}
              <circle cx={d.x} cy={d.y} r={d.r} fill={SEV[d.level].c}
                opacity={d.level === "clear" ? 0.6 : 1}
                stroke={g.pinEdge} strokeWidth={0.7}
                filter={d.level === "alert" ? "url(#exec-glow)" : undefined} />
              {/* Hit target larger than the mark. */}
              <circle cx={d.x} cy={d.y} r={Math.max(d.r + 6, 11)} fill="transparent" />
            </g>
          );
        })}
      </svg>

      {hover && (
        <div className="absolute pointer-events-none bg-[var(--xd-3)] border border-[var(--xd-12)] px-3 py-2 rounded-[2px] shadow-xl max-w-[260px] z-10"
          style={{
            left: `${Math.min((hover.x / W) * 100, 62)}%`,
            top: `${Math.max((hover.y / H) * 100 - 4, 2)}%`,
          }}>
          <div className="text-[12px] text-[var(--xd-23)]">{hover.ctx.office.name}</div>
          <div className="font-mono text-[10px] text-[var(--xd-19)] mt-0.5">
            {hover.ctx.office.city} · {hover.ctx.office.country} · {(hover.ctx.office.headcount || 0).toLocaleString()} people
          </div>
          <div className="flex items-center gap-1.5 mt-1.5">
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: SEV[hover.level].c }} />
            <span className="font-mono text-[10px] uppercase tracking-[0.1em]" style={{ color: SEV[hover.level].c }}>
              {SEV[hover.level].label}
            </span>
          </div>
          {hoveredSignal && (
            <div className="text-[11px] text-[var(--xd-20)] mt-1.5 leading-snug border-t border-[var(--xd-10)] pt-1.5">
              {hoveredSignal.event.canonical_title}
              <span className="font-mono text-[10px] text-[var(--xd-18)]"> · {Math.round(hoveredSignal.km)} km</span>
            </div>
          )}
        </div>
      )}

      <div className="absolute bottom-2 right-3 font-mono text-[9px] text-[var(--xd-14)] tracking-[0.1em] uppercase">
        drag to rotate · scroll to zoom
      </div>
    </div>
  );
}
