import { useEffect, useRef, useState, useCallback } from "react";
import * as d3 from "d3";
import * as topojson from "topojson-client";
import { getCategoryColor } from "../../lib/colors.js";
import { getMapColors } from "../../lib/theme.js";

const WORLD_TOPO_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";
const CRIMSON      = "#C80028";
const CRIMSON_GLOW = "#FF1040";
const CYAN         = "#00D4FF";

// Region → globe rotation center [lambda, phi]
// projection.rotate([-lambda, -phi]) centers that location on screen
const REGION_CENTERS = {
  world:    [20,   25],
  americas: [-85,  15],
  europe:   [15,   52],
  asia:     [95,   32],
  india:    [80,   22],
  africa:   [20,    5],
};

export default function WorldMap({
  nodes = [],
  edges = [],
  selectedNodeId = null,
  onNodeClick,
  region = "world",
  isDark = false,
}) {
  const svgRef    = useRef(null);
  const wrapRef   = useRef(null);
  const geoRef    = useRef(null);
  const projRef   = useRef(null);
  const rotateRef = useRef([-20, -25, 0]);
  const isDragRef = useRef(false);
  const timerRef  = useRef(null);

  const [ready,   setReady]   = useState(false);
  const [hovered, setHovered] = useState(null);
  const [tipPos,  setTipPos]  = useState({ x: 0, y: 0 });
  const [dims,    setDims]    = useState({ w: 900, h: 560 });

  // Responsive resize
  useEffect(() => {
    if (!wrapRef.current) return;
    const ro = new ResizeObserver(([e]) => {
      setDims({ w: e.contentRect.width, h: e.contentRect.height });
    });
    ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, []);

  // Load topology once
  useEffect(() => {
    d3.json(WORLD_TOPO_URL).then(world => {
      geoRef.current = {
        countries: topojson.feature(world, world.objects.countries),
        borders:   topojson.mesh(world, world.objects.countries, (a, b) => a !== b),
      };
      setReady(true);
    }).catch(console.error);
  }, []);

  // Lightweight path update — just reprojects existing .geo paths (no DOM rebuild)
  const updatePaths = useCallback(() => {
    if (!projRef.current || !svgRef.current) return;
    projRef.current.rotate(rotateRef.current);
    const newPath = d3.geoPath(projRef.current);
    d3.select(svgRef.current).selectAll("path.geo").attr("d", function () {
      const d = d3.select(this).datum();
      return d ? newPath(d) : null;
    });
  }, []);

  // Full rebuild when nodes / edges / theme / dimensions change
  const buildGlobe = useCallback(() => {
    if (!ready || !svgRef.current || !geoRef.current || dims.w === 0) return;

    const { w, h } = dims;
    const radius   = Math.min(w, h) * 0.48;
    const DOT_COLOR = isDark ? CYAN    : CRIMSON;
    const mc        = getMapColors(isDark);

    const projection = d3.geoOrthographic()
      .scale(radius)
      .translate([w / 2, h / 2])
      .rotate(rotateRef.current)
      .clipAngle(90)
      .precision(0.3);

    projRef.current = projection;
    const path = d3.geoPath(projection);

    const svg = d3.select(svgRef.current);
    svg.attr("width", w).attr("height", h);
    svg.selectAll("*").remove();

    // ── SVG Defs ────────────────────────────────────────────────────
    const defs = svg.append("defs");

    // Dot glow filter
    const dotGlow = defs.append("filter").attr("id", "dot-glow")
      .attr("x", "-200%").attr("y", "-200%").attr("width", "500%").attr("height", "500%");
    dotGlow.append("feGaussianBlur").attr("stdDeviation", isDark ? "5" : "3").attr("result", "blur");
    const dm = dotGlow.append("feMerge");
    dm.append("feMergeNode").attr("in", "blur");
    dm.append("feMergeNode").attr("in", "SourceGraphic");

    // Globe-edge atmosphere glow
    const atmoF = defs.append("filter").attr("id", "atmo-glow")
      .attr("x", "-15%").attr("y", "-15%").attr("width", "130%").attr("height", "130%");
    atmoF.append("feGaussianBlur").attr("stdDeviation", "10").attr("result", "blur");
    const am = atmoF.append("feMerge");
    am.append("feMergeNode").attr("in", "blur");
    am.append("feMergeNode").attr("in", "SourceGraphic");

    // Radial gradient — subtle atmosphere halo at globe edge
    const grad = defs.append("radialGradient").attr("id", "globe-atmo")
      .attr("cx", "50%").attr("cy", "50%").attr("r", "50%");
    grad.append("stop").attr("offset", "68%").attr("stop-color", "transparent");
    grad.append("stop").attr("offset", "100%")
      .attr("stop-color", isDark ? `${CYAN}28` : `${CRIMSON}18`);

    // ── Background ───────────────────────────────────────────────────
    svg.append("rect").attr("width", w).attr("height", h).attr("fill", mc.bg);

    const globe = svg.append("g").attr("class", "globe-root");

    // Atmosphere ring (cosmetic circle, not a geo path)
    globe.append("circle")
      .attr("cx", w / 2).attr("cy", h / 2).attr("r", radius + 10)
      .attr("fill", "none")
      .attr("stroke", DOT_COLOR)
      .attr("stroke-width", isDark ? 2.5 : 1.5)
      .attr("stroke-opacity", isDark ? 0.28 : 0.10)
      .attr("filter", "url(#atmo-glow)");

    // ── Ocean sphere ─────────────────────────────────────────────────
    globe.append("path")
      .datum({ type: "Sphere" })
      .attr("class", "geo sphere")
      .attr("d", path)
      .attr("fill", mc.ocean)
      .attr("stroke", DOT_COLOR)
      .attr("stroke-width", 0.6)
      .attr("stroke-opacity", isDark ? 0.3 : 0.12);

    // Atmosphere overlay on the sphere surface
    globe.append("circle")
      .attr("cx", w / 2).attr("cy", h / 2).attr("r", radius)
      .attr("fill", "url(#globe-atmo)")
      .style("pointer-events", "none");

    // ── Graticule ────────────────────────────────────────────────────
    globe.append("path")
      .datum(d3.geoGraticule().step([30, 30])())
      .attr("class", "geo graticule")
      .attr("d", path)
      .attr("fill", "none")
      .attr("stroke", mc.graticule)
      .attr("stroke-width", 0.25)
      .attr("stroke-opacity", isDark ? 0.4 : 0.3);

    // ── Countries ───────────────────────────────────────────────────
    const shades = [mc.country0, mc.country1, mc.country2];
    globe.append("g").attr("class", "countries")
      .selectAll("path")
      .data(geoRef.current.countries.features)
      .join("path")
      .attr("class", "geo country")
      .attr("d", path)
      .attr("fill", d => shades[(+d.id || 0) % 3]);

    // ── Borders ──────────────────────────────────────────────────────
    globe.append("path")
      .datum(geoRef.current.borders)
      .attr("class", "geo borders")
      .attr("d", path)
      .attr("fill", "none")
      .attr("stroke", mc.border)
      .attr("stroke-width", 0.4);

    // ── Connection arcs ──────────────────────────────────────────────
    const arcGroup = globe.append("g").attr("class", "arcs");
    edges.forEach(edge => {
      const src = nodes.find(n => n.id === edge.source_event_id);
      const tgt = nodes.find(n => n.id === edge.target_event_id);
      if (!src?.lat || !tgt?.lat) return;
      const arc = {
        type: "Feature",
        geometry: {
          type: "LineString",
          coordinates: Array.from({ length: 60 }, (_, i) =>
            d3.geoInterpolate([src.lng, src.lat], [tgt.lng, tgt.lat])(i / 59)
          ),
        },
      };
      arcGroup.append("path")
        .datum(arc)
        .attr("class", "geo arc")
        .attr("d", path)
        .attr("fill", "none")
        .attr("stroke", DOT_COLOR)
        .attr("stroke-width", isDark ? 0.9 : 0.7)
        .attr("stroke-opacity", isDark ? 0.30 : 0.20)
        .attr("stroke-dasharray", "4 3");
    });

    // ── Hotspot dots (geoCircle — auto-clipped by orthographic) ──────
    const dotGroup = globe.append("g").attr("class", "dots");
    nodes.forEach(node => {
      if (node.lat == null || node.lng == null) return;
      const sel  = node.id === selectedNodeId;
      const esc  = node.current_status === "escalating";
      const baseR = sel ? 2.8 : esc ? 2.2 : 1.5; // angular radius in degrees

      const mkCircle = r => d3.geoCircle().center([node.lng, node.lat]).radius(r)();
      const g = dotGroup.append("g").attr("class", "hotspot");

      // Outer diffuse halo
      g.append("path").datum(mkCircle(baseR * 6.5))
        .attr("class", "geo dot-halo")
        .attr("fill", DOT_COLOR)
        .attr("opacity", isDark ? 0.08 : 0.05)
        .attr("filter", "url(#dot-glow)")
        .style("pointer-events", "none");

      // Middle glow ring
      g.append("path").datum(mkCircle(baseR * 2.8))
        .attr("class", "geo dot-mid")
        .attr("fill", DOT_COLOR)
        .attr("opacity", isDark ? 0.35 : 0.22)
        .style("pointer-events", "none");

      // Core dot
      g.append("path").datum(mkCircle(baseR))
        .attr("class", "geo dot-core")
        .attr("fill", sel ? CRIMSON_GLOW : DOT_COLOR)
        .attr("opacity", sel ? 1.0 : 0.88)
        .attr("filter", "url(#dot-glow)");

      // Bright center highlight
      g.append("path").datum(mkCircle(baseR * 0.3))
        .attr("class", "geo dot-bright")
        .attr("fill", "#ffffff")
        .attr("opacity", isDark ? 0.7 : 0.5)
        .style("pointer-events", "none");

      // Hit area (transparent, larger)
      g.append("path").datum(mkCircle(baseR * 4))
        .attr("class", "geo dot-hit")
        .attr("fill", "transparent")
        .style("cursor", "pointer")
        .on("click", () => onNodeClick?.(node))
        .on("mouseenter", (event) => {
          setHovered(node);
          setTipPos({ x: event.clientX, y: event.clientY });
        })
        .on("mousemove", (event) => setTipPos({ x: event.clientX, y: event.clientY }))
        .on("mouseleave", () => setHovered(null));
    });

    // ── Drag to rotate ───────────────────────────────────────────────
    // Remove any previous drag listeners before attaching a fresh one
    svg.on(".drag", null);
    let lastPos = null;
    svg.call(
      d3.drag()
        .on("start", (event) => {
          isDragRef.current = true;
          lastPos = [event.x, event.y];
        })
        .on("drag", (event) => {
          if (!lastPos) return;
          const dx = event.x - lastPos[0];
          const dy = event.y - lastPos[1];
          lastPos = [event.x, event.y];
          const r = rotateRef.current;
          rotateRef.current = [
            r[0] + dx * 0.35,
            Math.max(-88, Math.min(88, r[1] - dy * 0.35)),
            r[2],
          ];
          updatePaths();
        })
        .on("end", () => {
          isDragRef.current = false;
          lastPos = null;
        })
    );
  }, [ready, dims, nodes, edges, selectedNodeId, isDark, onNodeClick, updatePaths]);

  // Rebuild when anything changes
  useEffect(() => { buildGlobe(); }, [buildGlobe]);

  // Auto-spin
  useEffect(() => {
    if (!ready) return;
    if (timerRef.current) { timerRef.current.stop(); timerRef.current = null; }
    timerRef.current = d3.timer(() => {
      if (isDragRef.current) return;
      rotateRef.current[0] += 0.10;
      updatePaths();
    });
    return () => { timerRef.current?.stop(); timerRef.current = null; };
  }, [ready, updatePaths]);

  // Region tab → rotate globe to face that region
  useEffect(() => {
    const c = REGION_CENTERS[region] || REGION_CENTERS.world;
    // Smooth rotation via interpolation (3 frames)
    const target = [-c[0], -c[1], 0];
    const start  = [...rotateRef.current];
    let step = 0;
    const transition = d3.timer(() => {
      step++;
      const t = Math.min(step / 20, 1);
      const ease = 1 - Math.pow(1 - t, 3); // cubic ease-out
      rotateRef.current = [
        start[0] + (target[0] - start[0]) * ease,
        start[1] + (target[1] - start[1]) * ease,
        0,
      ];
      updatePaths();
      if (t >= 1) transition.stop();
    });
    return () => transition.stop();
  }, [region, updatePaths]);

  const mc = getMapColors(isDark);
  const DOT_COLOR = isDark ? CYAN : CRIMSON;

  return (
    <div ref={wrapRef} className="relative w-full h-full overflow-hidden" style={{ backgroundColor: mc.bg }}>
      <svg ref={svgRef} style={{ display: "block", width: "100%", height: "100%" }} />

      {/* Drag hint */}
      {ready && (
        <div
          className="absolute top-3 left-1/2 -translate-x-1/2 text-[9px] font-mono uppercase tracking-[0.2em] pointer-events-none select-none"
          style={{ color: isDark ? "rgba(0,212,255,0.3)" : "rgba(200,0,40,0.3)" }}
        >
          Drag to rotate
        </div>
      )}

      {/* Tooltip */}
      {hovered && (
        <div
          style={{
            position: "fixed",
            left: tipPos.x + 14,
            top:  tipPos.y - 10,
            pointerEvents: "none",
            zIndex: 50,
            maxWidth: 250,
          }}
        >
          <div
            className="rounded-xl px-3 py-2.5 text-xs shadow-xl"
            style={{
              backgroundColor: isDark ? "#0F1520" : "#FFFFFF",
              border: `1px solid ${DOT_COLOR}40`,
              color: isDark ? "#E8E4DC" : "#1A1A1A",
            }}
          >
            <div className="font-bold text-[9px] uppercase tracking-widest mb-1"
              style={{ color: getCategoryColor(hovered.category) }}>
              {hovered.category}
            </div>
            <div className="font-semibold leading-snug text-[12px]">
              {hovered.title || hovered.canonical_title}
            </div>
            {hovered.geography?.length > 0 && (
              <div className="mt-1 text-[10px] opacity-50">
                {hovered.geography.slice(0, 2).join(" · ")}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Legend */}
      <div
        className="absolute bottom-3 right-3 flex items-center gap-3 text-[9px] font-mono uppercase tracking-wider"
        style={{ color: isDark ? "rgba(232,228,220,0.35)" : "rgba(26,26,26,0.35)" }}
      >
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full"
            style={{ backgroundColor: DOT_COLOR, boxShadow: `0 0 6px ${DOT_COLOR}` }} />
          Escalating
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-amber-400 opacity-70" />
          Developing
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-500 opacity-70" />
          Stable
        </span>
      </div>
    </div>
  );
}
