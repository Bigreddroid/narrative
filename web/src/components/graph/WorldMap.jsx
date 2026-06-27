import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import * as topojson from "topojson-client";
import { getCategoryColor } from "../../lib/colors.js";
import { getMapColors } from "../../lib/theme.js";
import { VESSEL_TYPES } from "../../lib/vesselData.js";
import { AIRCRAFT_TYPES, AIRCRAFT_GLYPH } from "../../lib/aircraftData.js";
import { associate, eventRadiusKm } from "../../lib/geoAssoc.js";
import { exposureColor } from "../../lib/exposureColor.js";
import GlobeControls from "./GlobeControls.jsx";

const WORLD_TOPO_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";
const CRIMSON = "#C80028";
const CRIMSON_GLOW = "#FF1040";

// Region presets — rotate centers the orthographic globe on [lng,lat]; scale zooms.
const REGIONS = {
  world:    { rotate: [ 15,  -25], scale: 1.0 },
  americas: { rotate: [ 90,  -15], scale: 1.7 },
  europe:   { rotate: [-15,  -50], scale: 2.6 },
  asia:     { rotate: [-100, -30], scale: 1.9 },
  india:    { rotate: [-78,  -22], scale: 3.0 },
  africa:   { rotate: [-20,    0], scale: 2.0 },
};

const CONTINENTS = [
  { name: "NORTH AMERICA", lng: -100, lat: 45 },
  { name: "SOUTH AMERICA", lng: -60,  lat: -15 },
  { name: "EUROPE",        lng: 15,   lat: 50 },
  { name: "AFRICA",        lng: 20,   lat: 4 },
  { name: "ASIA",          lng: 90,   lat: 45 },
  { name: "OCEANIA",       lng: 134,  lat: -25 },
];

const VESSEL_ARROW = "M0,-5.2 L3.1,4.4 L0,2.2 L-3.1,4.4 Z";

function arcCoords(from, to) {
  const interp = d3.geoInterpolate(from, to);
  return Array.from({ length: 50 }, (_, i) => interp(i / 49));
}

export default function WorldMap({
  nodes = [], edges = [], selectedNodeId = null, onNodeClick,
  region = "world", isDark = false, getVessels = null, showVessels = false,
  getAircraft = null, showAircraft = false,
  eventScores = null, exposureLayer = false, anomalies = null,
}) {
  const wrapRef  = useRef(null);
  const svgRef   = useRef(null);
  const geoRef   = useRef(null);
  const selRef   = useRef({});
  const projRef  = useRef(null);
  const pathRef  = useRef(null);

  // Interaction state (refs — mutated in the rAF loop without re-rendering)
  const rotateRef       = useRef([...REGIONS.world.rotate]);
  const targetRotateRef = useRef([...REGIONS.world.rotate]);
  const scaleRef        = useRef(0);
  const targetScaleRef  = useRef(0);
  const baseScaleRef    = useRef(0);
  const spinRef         = useRef(true);
  const draggingRef     = useRef(false);
  const hoverRef        = useRef(false);
  const getVesselsRef   = useRef(getVessels);
  const showVesselsRef  = useRef(showVessels);
  const getAircraftRef  = useRef(getAircraft);
  const showAircraftRef = useRef(showAircraft);
  const eventScoresRef  = useRef(eventScores);
  const exposureLayerRef = useRef(exposureLayer);
  const anomaliesRef    = useRef(anomalies);
  const assocRef        = useRef({ nearestByItem: new Map(), zonesByEvent: new Map() });
  const assocTickRef    = useRef(0);
  const zoneCountRef    = useRef({ vessels: 0, aircraft: 0 });
  const lastTransformRef = useRef("");
  const rafRef          = useRef(0);

  const [ready, setReady]       = useState(false);
  const [dims, setDims]         = useState({ w: 1200, h: 700 });
  const [spinning, setSpinning] = useState(true);
  const [hoverNode, setHoverNode]     = useState(null);
  const [hoverVessel, setHoverVessel] = useState(null);
  const [selVessel, setSelVessel]     = useState(null);
  const [hoverAircraft, setHoverAircraft] = useState(null);
  const [selAircraft, setSelAircraft]     = useState(null);
  const [zoneCount, setZoneCount] = useState({ vessels: 0, aircraft: 0 });
  const [tip, setTip]           = useState({ x: 0, y: 0 });

  useEffect(() => { getVesselsRef.current = getVessels; }, [getVessels]);
  useEffect(() => { showVesselsRef.current = showVessels; }, [showVessels]);
  useEffect(() => { getAircraftRef.current = getAircraft; }, [getAircraft]);
  useEffect(() => { showAircraftRef.current = showAircraft; }, [showAircraft]);
  useEffect(() => { eventScoresRef.current = eventScores; }, [eventScores]);
  useEffect(() => { exposureLayerRef.current = exposureLayer; }, [exposureLayer]);
  useEffect(() => { anomaliesRef.current = anomalies; }, [anomalies]);

  // Responsive resize
  useEffect(() => {
    if (!wrapRef.current) return;
    // Round + bail when unchanged: ResizeObserver can fire spuriously during
    // heavy repaints (live AIS/aircraft), and a fresh dims object would re-run
    // the scene/fly-to effects and snap zoom back to the region default.
    const ro = new ResizeObserver(([e]) => {
      const w = Math.round(e.contentRect.width), h = Math.round(e.contentRect.height);
      setDims((d) => (d.w === w && d.h === h ? d : { w, h }));
    });
    ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, []);

  // Load topology once
  useEffect(() => {
    d3.json(WORLD_TOPO_URL).then((world) => {
      geoRef.current = {
        countries: topojson.feature(world, world.objects.countries),
        borders:   topojson.mesh(world, world.objects.countries, (a, b) => a !== b),
      };
      setReady(true);
    }).catch(console.error);
  }, []);

  // Fly to region when it changes
  useEffect(() => {
    const reg = REGIONS[region] || REGIONS.world;
    targetRotateRef.current = [...reg.rotate];
    if (baseScaleRef.current) targetScaleRef.current = baseScaleRef.current * reg.scale;
    const spin = region === "world";
    spinRef.current = spin;
    setSpinning(spin);
    // NB: intentionally not keyed on `dims` — re-flying on resize would reset
    // the user's zoom. baseScaleRef is recomputed by the scene effect on resize.
  }, [region, ready]);

  // ── Build the scene + interaction + render loop ──────────────────────────────
  useEffect(() => {
    if (!ready || !svgRef.current || dims.w === 0) return;
    const { w, h } = dims;
    const mc = getMapColors(isDark);

    const base = (Math.min(w, h) / 2.1);
    baseScaleRef.current = base;
    if (!scaleRef.current) {
      const reg = REGIONS[region] || REGIONS.world;
      scaleRef.current = base * reg.scale;
      targetScaleRef.current = scaleRef.current;
    }

    const projection = d3.geoOrthographic()
      .translate([w / 2, h / 2])
      .clipAngle(90)
      .precision(0.4);
    projRef.current = projection;
    const path = d3.geoPath(projection);
    pathRef.current = path;

    const svg = d3.select(svgRef.current).attr("width", w).attr("height", h);
    svg.selectAll("*").remove();

    // Glow filters
    const defs = svg.append("defs");
    const mkGlow = (id, dev, double) => {
      const f = defs.append("filter").attr("id", id).attr("x", "-100%").attr("y", "-100%").attr("width", "300%").attr("height", "300%");
      f.append("feGaussianBlur").attr("stdDeviation", dev).attr("result", "b");
      const m = f.append("feMerge");
      m.append("feMergeNode").attr("in", "b");
      if (double) m.append("feMergeNode").attr("in", "b");
      m.append("feMergeNode").attr("in", "SourceGraphic");
    };
    mkGlow("arc-glow", 3.5, true);
    mkGlow("dot-glow", 2.5, false);
    mkGlow("sel-glow", 5, true);
    // Radial ocean shading for depth
    const grad = defs.append("radialGradient").attr("id", "ocean-grad").attr("cx", "42%").attr("cy", "38%").attr("r", "72%");
    grad.append("stop").attr("offset", "0%").attr("stop-color", mc.ocean).attr("stop-opacity", 1);
    grad.append("stop").attr("offset", "100%").attr("stop-color", "#05070C").attr("stop-opacity", 1);

    svg.append("rect").attr("width", w).attr("height", h).attr("fill", mc.bg);
    const globe = svg.append("g");

    const sphere     = globe.append("path").datum({ type: "Sphere" }).attr("fill", "url(#ocean-grad)").attr("stroke", mc.border).attr("stroke-width", 0.5);
    const graticule  = globe.append("path").datum(d3.geoGraticule().step([20, 20])()).attr("fill", "none").attr("stroke", mc.graticule).attr("stroke-width", 0.3);
    const shades     = [mc.country0, mc.country1, mc.country2];
    const countries  = globe.append("g").selectAll("path").data(geoRef.current.countries.features).join("path").attr("fill", (d) => shades[(+d.id || 0) % 3]).attr("stroke", "none");
    const borders    = globe.append("path").datum(geoRef.current.borders).attr("fill", "none").attr("stroke", mc.border).attr("stroke-width", 0.5);
    const labelsG    = globe.append("g").attr("class", "labels");
    const arcsG      = globe.append("g").attr("class", "arcs");
    const zoneG      = globe.append("g").attr("class", "zone-layer");
    const dotsG      = globe.append("g").attr("class", "dots");
    const anomalyG   = globe.append("g").attr("class", "anomaly-layer");
    const nodeById   = new Map(nodes.map((n) => [String(n.id), n]));
    const vesselsG   = globe.append("g").attr("class", "vessels");
    const aircraftG  = globe.append("g").attr("class", "aircraft");

    // Continent labels (static set, repositioned each frame)
    labelsG.selectAll("text").data(CONTINENTS).join("text")
      .text((d) => d.name)
      .attr("text-anchor", "middle")
      .attr("font-family", "ui-monospace, monospace")
      .attr("font-size", 11).attr("letter-spacing", 2.5).attr("font-weight", 600)
      .attr("fill", "rgba(232,228,220,0.45)")
      .attr("pointer-events", "none");

    selRef.current = { sphere, graticule, countries, borders, labelsG, arcsG, dotsG, vesselsG, aircraftG };

    // ── Interaction: drag to rotate ──
    const drag = d3.drag()
      .on("start", () => { draggingRef.current = true; })
      .on("drag", (e) => {
        const k = 76 / scaleRef.current;
        const r = rotateRef.current;
        let lat = r[1] - e.dy * k;
        lat = Math.max(-89, Math.min(89, lat));
        rotateRef.current = [r[0] + e.dx * k, lat];
        targetRotateRef.current = [...rotateRef.current];
      })
      .on("end", () => { draggingRef.current = false; });
    svg.call(drag).style("cursor", "grab")
      .on("mousedown.cursor", () => svg.style("cursor", "grabbing"))
      .on("mouseup.cursor", () => svg.style("cursor", "grab"));

    // Wheel to zoom
    const onWheel = (e) => {
      e.preventDefault();
      const factor = e.deltaY < 0 ? 1.12 : 0.89;
      const next = scaleRef.current * factor;
      scaleRef.current = Math.max(base * 0.55, Math.min(base * 9, next));
      targetScaleRef.current = scaleRef.current;
    };
    const wrap = wrapRef.current;
    wrap.addEventListener("wheel", onWheel, { passive: false });

    // ── Build data-bound dots + arcs ──
    rebuildDots();
    rebuildArcs();

    // ── Render loop ──
    const render = () => {
      // Ease toward targets + auto-spin
      if (!draggingRef.current) {
        const r = rotateRef.current, tr = targetRotateRef.current;
        rotateRef.current = [r[0] + (tr[0] - r[0]) * 0.12, r[1] + (tr[1] - r[1]) * 0.12];
        scaleRef.current += (targetScaleRef.current - scaleRef.current) * 0.12;
        if (spinRef.current && !hoverRef.current) {
          rotateRef.current[0] += 0.12;
          targetRotateRef.current[0] += 0.12;
        }
      }

      projection.rotate(rotateRef.current).scale(scaleRef.current);
      const transform = rotateRef.current.map((v) => v.toFixed(2)).join(",") + ":" + scaleRef.current.toFixed(1);
      const moved = transform !== lastTransformRef.current;
      lastTransformRef.current = transform;

      if (moved) {
        sphere.attr("d", path);
        graticule.attr("d", path);
        countries.attr("d", path);
        borders.attr("d", path);
        positionLabels();
        positionDots();
        positionArcs();
      }
      if (showVesselsRef.current && getVesselsRef.current) renderVessels();
      else vesselsG.selectAll("*").remove();
      if (showAircraftRef.current && getAircraftRef.current) renderAircraft();
      else aircraftG.selectAll("*").remove();
      updateAssoc();
      drawZone();
      colorDots();
      drawAnomalies();

      rafRef.current = requestAnimationFrame(render);
    };

    const center = () => [-rotateRef.current[0], -rotateRef.current[1]];
    const visible = (lng, lat) => d3.geoDistance([lng, lat], center()) < 1.55;

    function positionLabels() {
      labelsG.selectAll("text")
        .attr("transform", (d) => { const p = projection([d.lng, d.lat]); return p ? `translate(${p[0]},${p[1]})` : null; })
        .attr("display", (d) => (visible(d.lng, d.lat) ? null : "none"));
    }

    function positionDots() {
      // Raw DOM (no per-dot d3.select) — this runs for every dot every moved frame,
      // so avoiding a selection allocation per dot keeps rotation/zoom fluid.
      dotsG.selectAll("g.dot").each(function (d) {
        const p = visible(d.lng, d.lat) ? projection([d.lng, d.lat]) : null;
        if (!p) { this.style.display = "none"; return; }
        this.style.display = "";
        this.setAttribute("transform", `translate(${p[0]},${p[1]})`);
      });
    }

    function positionArcs() {
      arcsG.selectAll("path.arc").attr("d", (d) => path({ type: "LineString", coordinates: d.coords }));
    }

    // Reconcile the DOM set + per-vessel styling at ~3 Hz (data identity,
    // selection and exposure tint change far slower than the 60fps loop); then
    // reposition every frame in a cheap single pass so motion stays fluid even
    // with hundreds of live AIS vessels.
    let vesselStyleT = 0;
    function renderVessels() {
      let sel = vesselsG.selectAll("path.vessel");
      const now = performance.now();
      if (now - vesselStyleT > 300) {
        vesselStyleT = now;
        const data = getVesselsRef.current() || [];
        sel = sel.data(data, (d) => d.mmsi);
        sel.exit().remove();
        const enter = sel.enter().append("path")
          .attr("class", "vessel")
          .attr("d", VESSEL_ARROW)
          .attr("stroke", "rgba(0,0,0,0.35)").attr("stroke-width", 0.4)
          .style("cursor", "pointer")
          .on("pointerdown", (e) => e.stopPropagation())
          .on("mouseenter", function (e, d) { hoverRef.current = true; setHoverVessel(d); setTip({ x: e.clientX, y: e.clientY }); })
          .on("mousemove", (e) => setTip({ x: e.clientX, y: e.clientY }))
          .on("mouseleave", function () { hoverRef.current = false; setHoverVessel(null); })
          .on("click", (e, d) => { e.stopPropagation(); setSelVessel(d); setSelAircraft(null); });
        const vScores = eventScoresRef.current, vAssoc = assocRef.current.nearestByItem;
        sel = enter.merge(sel)
          .attr("fill", (d) => {
            const near = vAssoc.get(d.mmsi);
            if (exposureLayerRef.current && near && vScores && vScores[near.eventId] != null) return exposureColor(vScores[near.eventId]);
            return (VESSEL_TYPES[d.type] || VESSEL_TYPES.other).color;
          })
          .attr("fill-opacity", (d) => {
            if (!selectedNodeId) return 1;
            const near = vAssoc.get(d.mmsi);
            return near && near.eventId === String(selectedNodeId) ? 1 : 0.18;
          });
      }
      sel.each(function (d) {
        if (!visible(d.lng, d.lat)) { this.style.display = "none"; return; }
        const p = projection([d.lng, d.lat]);
        if (!p) { this.style.display = "none"; return; }
        this.style.display = "";
        this.setAttribute("transform", `translate(${p[0]},${p[1]}) rotate(${d.heading || 0})`);
      });
    }

    let aircraftStyleT = 0;
    function renderAircraft() {
      let sel = aircraftG.selectAll("path.aircraft");
      const now = performance.now();
      if (now - aircraftStyleT > 300) {
        aircraftStyleT = now;
        const data = getAircraftRef.current() || [];
        sel = sel.data(data, (d) => d.icao);
        sel.exit().remove();
        const enter = sel.enter().append("path")
          .attr("class", "aircraft")
          .attr("d", AIRCRAFT_GLYPH)
          .attr("stroke", "rgba(0,0,0,0.3)").attr("stroke-width", 0.4)
          .style("cursor", "pointer")
          .on("pointerdown", (e) => e.stopPropagation())
          .on("mouseenter", function (e, d) { hoverRef.current = true; setHoverAircraft(d); setTip({ x: e.clientX, y: e.clientY }); })
          .on("mousemove", (e) => setTip({ x: e.clientX, y: e.clientY }))
          .on("mouseleave", function () { hoverRef.current = false; setHoverAircraft(null); })
          .on("click", (e, d) => { e.stopPropagation(); setSelAircraft(d); setSelVessel(null); });
        const aScores = eventScoresRef.current, aAssoc = assocRef.current.nearestByItem;
        sel = enter.merge(sel)
          .attr("fill", (d) => {
            const near = aAssoc.get(d.icao);
            if (exposureLayerRef.current && near && aScores && aScores[near.eventId] != null) return exposureColor(aScores[near.eventId]);
            return (AIRCRAFT_TYPES[d.type] || AIRCRAFT_TYPES.other).color;
          })
          .attr("fill-opacity", (d) => {
            if (!selectedNodeId) return 1;
            const near = aAssoc.get(d.icao);
            return near && near.eventId === String(selectedNodeId) ? 1 : 0.18;
          });
      }
      sel.each(function (d) {
        if (!visible(d.lng, d.lat)) { this.style.display = "none"; return; }
        const p = projection([d.lng, d.lat]);
        if (!p) { this.style.display = "none"; return; }
        this.style.display = "";
        this.setAttribute("transform", `translate(${p[0]},${p[1]}) rotate(${d.heading || 0})`);
      });
    }

    // Throttled (2 Hz) association of live traffic to events — powers tint/dim/counts.
    function updateAssoc() {
      const now = performance.now();
      if (now - assocTickRef.current < 500) return;
      assocTickRef.current = now;
      const vessels = (showVesselsRef.current && getVesselsRef.current) ? (getVesselsRef.current() || []) : [];
      const aircraft = (showAircraftRef.current && getAircraftRef.current) ? (getAircraftRef.current() || []) : [];
      const items = [];
      for (const v of vessels) items.push({ id: v.mmsi, lat: v.lat, lng: v.lng, kind: "vessel" });
      for (const a of aircraft) items.push({ id: a.icao, lat: a.lat, lng: a.lng, kind: "aircraft" });
      const evs = nodes.map((n) => ({ id: n.id, lat: n.lat, lng: n.lng, importance: n.importance ?? n.global_importance_score }));
      assocRef.current = associate(evs, items);
      if (selectedNodeId) {
        const z = assocRef.current.zonesByEvent.get(String(selectedNodeId));
        const nv = z ? z.vessels : 0, na = z ? z.aircraft : 0;
        if (nv !== zoneCountRef.current.vessels || na !== zoneCountRef.current.aircraft) {
          zoneCountRef.current = { vessels: nv, aircraft: na };
          setZoneCount({ vessels: nv, aircraft: na });
        }
      }
    }

    // Impact-zone ring around the selected event.
    function drawZone() {
      const node = selectedNodeId ? nodeById.get(String(selectedNodeId)) : null;
      if (!node || node.lat == null || node.lng == null) { zoneG.selectAll("*").remove(); return; }
      const rkm = eventRadiusKm({ importance: node.importance ?? node.global_importance_score ?? 50 });
      const circle = d3.geoCircle().center([node.lng, node.lat]).radius(rkm / 111.32)();
      const sel = zoneG.selectAll("path.zone").data([circle]);
      sel.enter().append("path").attr("class", "zone").merge(sel)
        .attr("d", path)
        .attr("fill", CRIMSON).attr("fill-opacity", 0.05)
        .attr("stroke", CRIMSON).attr("stroke-opacity", 0.45).attr("stroke-width", 1).attr("stroke-dasharray", "3 3");
      sel.exit().remove();
    }

    // Tint event dots by exposure heat when the exposure layer is on. Fill only
    // changes on selection/exposure/score changes (never during rotation), so cap
    // this restyle of all dots at ~7 Hz instead of running it every frame.
    let colorTick = 0;
    function colorDots() {
      const now = performance.now();
      if (now - colorTick < 140) return;
      colorTick = now;
      const scores = eventScoresRef.current;
      const on = exposureLayerRef.current;
      dotsG.selectAll("g.dot").select("circle.core").attr("fill", (d) => {
        if (d.id === selectedNodeId) return CRIMSON_GLOW;
        if (on && scores && scores[d.id] != null) return exposureColor(scores[d.id]);
        return CRIMSON;
      });
    }

    // Pulsing amber ring on events whose nearby traffic is anomalous (rerouting/surge).
    function drawAnomalies() {
      const an = anomaliesRef.current || {};
      const data = Object.keys(an).map((id) => nodeById.get(id)).filter(Boolean);
      const sel = anomalyG.selectAll("circle.anom").data(data, (d) => d.id);
      sel.exit().remove();
      sel.enter().append("circle").attr("class", "anom pulse-ring")
        .attr("r", 15).attr("fill", "none").attr("stroke", "#D9A227").attr("stroke-width", 1.5).attr("stroke-opacity", 0.75)
        .merge(sel)
        .attr("display", (d) => (visible(d.lng, d.lat) ? null : "none"))
        .attr("transform", (d) => { const p = projection([d.lng, d.lat]); return p ? `translate(${p[0]},${p[1]})` : "translate(-9999,-9999)"; });
    }

    function rebuildDots() {
      dotsG.selectAll("*").remove();
      const chain = new Set();
      if (selectedNodeId) edges.forEach((e) => {
        if (e.source_event_id === selectedNodeId) chain.add(e.target_event_id);
        if (e.target_event_id === selectedNodeId) chain.add(e.source_event_id);
      });
      nodes.forEach((node) => {
        if (node.lat == null || node.lng == null) return;
        const selected = node.id === selectedNodeId;
        const escalating = node.current_status === "escalating";
        const developing = node.current_status === "developing";
        const r = selected ? 9 : escalating ? 7 : 5;
        const g = dotsG.append("g").attr("class", "dot").datum(node).style("cursor", "pointer");
        if (escalating || selected) g.append("circle").attr("r", r + 6).attr("fill", "none").attr("stroke", CRIMSON).attr("stroke-width", 1).attr("stroke-opacity", 0.5).attr("class", "pulse-ring");
        if (selected) g.append("circle").attr("r", r + 12).attr("fill", "none").attr("stroke", CRIMSON).attr("stroke-width", 0.6).attr("stroke-opacity", 0.25);
        g.append("circle").attr("r", r).attr("fill", selected ? CRIMSON_GLOW : CRIMSON).attr("filter", selected ? "url(#sel-glow)" : "url(#dot-glow)").attr("class", "core " + (escalating ? "dot-escalate" : developing ? "dot-develop" : ""));
        g.append("circle").attr("r", Math.max(r + 8, 14)).attr("fill", "transparent")
          .on("pointerdown", (e) => e.stopPropagation())
          .on("mouseenter", (e) => { hoverRef.current = true; setHoverNode(node); setTip({ x: e.clientX, y: e.clientY }); })
          .on("mousemove", (e) => setTip({ x: e.clientX, y: e.clientY }))
          .on("mouseleave", () => { hoverRef.current = false; setHoverNode(null); })
          .on("click", (e) => { e.stopPropagation(); onNodeClick?.(node); });
      });
    }

    function rebuildArcs() {
      arcsG.selectAll("*").remove();
      const byId = new Map(nodes.map((n) => [n.id, n]));

      // Base network — every causal link drawn as a faint connecting line
      edges.forEach((edge) => {
        const a = byId.get(edge.source_event_id);
        const b = byId.get(edge.target_event_id);
        if (!a || !b || a.lat == null || b.lat == null) return;
        const touchesSel = selectedNodeId && (edge.source_event_id === selectedNodeId || edge.target_event_id === selectedNodeId);
        const coords = arcCoords([a.lng, a.lat], [b.lng, b.lat]);
        arcsG.append("path").datum({ coords }).attr("class", "arc")
          .attr("fill", "none").attr("stroke", CRIMSON)
          .attr("stroke-width", 0.8 + (edge.weight || 0.3) * 1.4)
          .attr("stroke-opacity", selectedNodeId ? (touchesSel ? 0.5 : 0.08) : 0.2);
      });

      // Selected node — bright glowing beams to its connected events
      if (!selectedNodeId) return;
      const sel = byId.get(selectedNodeId);
      if (!sel || sel.lat == null) return;
      edges.filter((e) => e.source_event_id === selectedNodeId || e.target_event_id === selectedNodeId).forEach((edge) => {
        const otherId = edge.source_event_id === selectedNodeId ? edge.target_event_id : edge.source_event_id;
        const other = byId.get(otherId);
        if (!other || other.lat == null) return;
        const coords = arcCoords([sel.lng, sel.lat], [other.lng, other.lat]);
        arcsG.append("path").datum({ coords }).attr("class", "arc").attr("fill", "none").attr("stroke", CRIMSON).attr("stroke-width", 6).attr("stroke-opacity", 0.15).attr("filter", "url(#arc-glow)");
        arcsG.append("path").datum({ coords }).attr("class", "arc arc-dash").attr("fill", "none").attr("stroke", CRIMSON_GLOW).attr("stroke-width", 1.2).attr("stroke-opacity", 0.85).attr("stroke-dasharray", "4 2");
      });
    }

    lastTransformRef.current = "";   // force a full draw on first frame after any (re)build
    rafRef.current = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(rafRef.current);
      wrap.removeEventListener("wheel", onWheel);
      svg.on(".drag", null);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, dims, isDark, nodes, edges, selectedNodeId]);

  const mc = getMapColors(isDark);

  // Control handlers
  const clampScale = (s) => Math.max(baseScaleRef.current * 0.55, Math.min(baseScaleRef.current * 9, s));
  const zoomIn  = () => { targetScaleRef.current = clampScale(scaleRef.current * 1.4); };
  const zoomOut = () => { targetScaleRef.current = clampScale(scaleRef.current * 0.7); };
  const reset   = () => { targetRotateRef.current = [...REGIONS.world.rotate]; targetScaleRef.current = baseScaleRef.current; spinRef.current = true; setSpinning(true); };
  const toggleSpin = () => { const s = !spinRef.current; spinRef.current = s; setSpinning(s); };

  return (
    <div ref={wrapRef} className="relative w-full h-full overflow-hidden" style={{ backgroundColor: mc.bg }}>
      <style>{`
        @keyframes escalatePulse { 0%,100%{opacity:1} 50%{opacity:.4} }
        @keyframes developPulse  { 0%,100%{opacity:.9} 50%{opacity:.5} }
        @keyframes pulseRing     { 0%{r:6;opacity:.6} 70%{r:18;opacity:0} 100%{r:6;opacity:0} }
        @keyframes arcDash       { to { stroke-dashoffset:-24 } }
        .dot-escalate { animation: escalatePulse 1.5s ease-in-out infinite }
        .dot-develop  { animation: developPulse 2.8s ease-in-out infinite }
        .pulse-ring   { animation: pulseRing 2s ease-out infinite }
        .arc-dash     { animation: arcDash 1.2s linear infinite }
      `}</style>

      {!ready && (
        <div className="absolute inset-0 flex items-center justify-center z-10" style={{ backgroundColor: mc.bg }}>
          <div className="text-center">
            <div className="w-5 h-5 border-2 border-t-crimson rounded-full animate-spin mx-auto mb-3" style={{ borderColor: "rgba(232,228,220,0.1)", borderTopColor: "#C80028" }} />
            <p className="text-[11px] tracking-widest uppercase" style={{ color: "rgba(232,228,220,0.35)" }}>Loading globe</p>
          </div>
        </div>
      )}

      <svg ref={svgRef} className="absolute inset-0" style={{ width: "100%", height: "100%" }} />

      {ready && (
        <GlobeControls onZoomIn={zoomIn} onZoomOut={zoomOut} onReset={reset} spinning={spinning} onToggleSpin={toggleSpin} />
      )}

      {/* Event hover tooltip */}
      {hoverNode && (
        <div className="fixed z-50 pointer-events-none" style={{ left: tip.x + 16, top: tip.y - 12 }}>
          <div className="bg-ink/90 border-l-2 px-3 py-2.5 max-w-[220px] shadow-lg" style={{ borderLeftColor: getCategoryColor(hoverNode.category) }}>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[9px] font-bold uppercase tracking-wider" style={{ color: getCategoryColor(hoverNode.category) }}>{hoverNode.category}</span>
              <span className="ml-auto text-[9px] text-paper/40 capitalize">{hoverNode.current_status}</span>
            </div>
            <p className="text-[11px] font-semibold text-paper leading-snug">{hoverNode.title}</p>
          </div>
        </div>
      )}

      {/* Vessel hover tooltip */}
      {hoverVessel && (
        <div className="fixed z-50 pointer-events-none" style={{ left: tip.x + 16, top: tip.y - 12 }}>
          <div className="bg-ink/90 border-l-2 px-3 py-2.5 max-w-[200px] shadow-lg" style={{ borderLeftColor: (VESSEL_TYPES[hoverVessel.type] || VESSEL_TYPES.other).color }}>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[9px] font-bold uppercase tracking-wider" style={{ color: (VESSEL_TYPES[hoverVessel.type] || VESSEL_TYPES.other).color }}>
                {(VESSEL_TYPES[hoverVessel.type] || VESSEL_TYPES.other).label}
              </span>
              <span className="ml-auto text-[9px] text-paper/40">{hoverVessel.sog ?? 0} kn</span>
            </div>
            <p className="text-[11px] font-semibold text-paper leading-snug">{hoverVessel.name}</p>
            {hoverVessel.lane && <p className="text-[9px] text-paper/40 mt-0.5 font-mono">{hoverVessel.lane}</p>}
          </div>
        </div>
      )}

      {/* Aircraft hover tooltip */}
      {hoverAircraft && (
        <div className="fixed z-50 pointer-events-none" style={{ left: tip.x + 16, top: tip.y - 12 }}>
          <div className="bg-ink/90 border-l-2 px-3 py-2.5 max-w-[200px] shadow-lg" style={{ borderLeftColor: (AIRCRAFT_TYPES[hoverAircraft.type] || AIRCRAFT_TYPES.other).color }}>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[9px] font-bold uppercase tracking-wider" style={{ color: (AIRCRAFT_TYPES[hoverAircraft.type] || AIRCRAFT_TYPES.other).color }}>
                {(AIRCRAFT_TYPES[hoverAircraft.type] || AIRCRAFT_TYPES.other).label}
              </span>
              <span className="ml-auto text-[9px] text-paper/40">{hoverAircraft.alt ? `FL${Math.round(hoverAircraft.alt / 100)}` : ""}</span>
            </div>
            <p className="text-[11px] font-semibold text-paper leading-snug">{hoverAircraft.callsign}</p>
            {hoverAircraft.route && <p className="text-[9px] text-paper/40 mt-0.5 font-mono">{hoverAircraft.route}</p>}
          </div>
        </div>
      )}

      {/* Vessel detail panel (click a boat) */}
      {selVessel && (() => {
        const vt = VESSEL_TYPES[selVessel.type] || VESSEL_TYPES.other;
        const rows = [
          ["MMSI", selVessel.mmsi ?? "—"],
          ["Speed", `${selVessel.sog ?? 0} kn`],
          ["Heading", `${Math.round(selVessel.heading ?? 0)}°`],
          ["Latitude", (selVessel.lat ?? 0).toFixed(3)],
          ["Longitude", (selVessel.lng ?? 0).toFixed(3)],
          ["Route", selVessel.lane || "—"],
        ];
        return (
          <div className="absolute bottom-3 left-3 z-30 w-64 backdrop-blur-sm border shadow-xl"
            style={{ backgroundColor: "rgba(11,14,19,0.94)", borderColor: "rgba(232,228,220,0.14)" }}>
            <div className="flex items-center gap-2 px-3 py-2.5" style={{ borderBottom: "1px solid rgba(232,228,220,0.10)" }}>
              <span style={{ width: 0, height: 0, borderLeft: "4px solid transparent", borderRight: "4px solid transparent", borderBottom: `8px solid ${vt.color}` }} />
              <span className="text-[10px] font-mono font-bold uppercase tracking-widest" style={{ color: vt.color }}>{vt.label}</span>
              <span className="ml-auto text-[9px] font-mono uppercase tracking-wider" style={{ color: "rgba(232,228,220,0.35)" }}>
                {selVessel.lane ? "Simulated" : "Live AIS"}
              </span>
              <button onClick={() => setSelVessel(null)} className="ml-1" style={{ color: "rgba(232,228,220,0.4)" }}>
                <svg width="11" height="11" viewBox="0 0 12 12" stroke="currentColor" strokeWidth="1.5"><line x1="1" y1="1" x2="11" y2="11" /><line x1="11" y1="1" x2="1" y2="11" /></svg>
              </button>
            </div>
            <div className="px-3 py-2.5">
              <p className="text-[13px] font-semibold leading-snug mb-2.5" style={{ color: "#E8E4DC" }}>{selVessel.name}</p>
              <div className="grid grid-cols-2 gap-y-1.5 gap-x-3">
                {rows.map(([k, v]) => (
                  <div key={k} className="flex flex-col">
                    <span className="text-[8px] font-mono uppercase tracking-widest" style={{ color: "rgba(232,228,220,0.35)" }}>{k}</span>
                    <span className="text-[11px] font-mono" style={{ color: "rgba(232,228,220,0.85)" }}>{v}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        );
      })()}

      {/* Aircraft detail panel (click a plane) */}
      {selAircraft && (() => {
        const at = AIRCRAFT_TYPES[selAircraft.type] || AIRCRAFT_TYPES.other;
        const rows = [
          ["ICAO", selAircraft.icao ?? "—"],
          ["Altitude", selAircraft.alt ? `${selAircraft.alt.toLocaleString()} ft` : "—"],
          ["Speed", `${selAircraft.velocity ?? 0} kn`],
          ["Heading", `${Math.round(selAircraft.heading ?? 0)}°`],
          ["Latitude", (selAircraft.lat ?? 0).toFixed(3)],
          ["Longitude", (selAircraft.lng ?? 0).toFixed(3)],
        ];
        return (
          <div className="absolute bottom-3 left-3 z-30 w-64 backdrop-blur-sm border shadow-xl"
            style={{ backgroundColor: "rgba(11,14,19,0.94)", borderColor: "rgba(232,228,220,0.14)" }}>
            <div className="flex items-center gap-2 px-3 py-2.5" style={{ borderBottom: "1px solid rgba(232,228,220,0.10)" }}>
              <span className="text-[11px] leading-none" style={{ color: at.color }}>✈</span>
              <span className="text-[10px] font-mono font-bold uppercase tracking-widest" style={{ color: at.color }}>{at.label}</span>
              <span className="ml-auto text-[9px] font-mono uppercase tracking-wider" style={{ color: "rgba(232,228,220,0.35)" }}>
                {selAircraft.route ? "Simulated" : "Live OpenSky"}
              </span>
              <button onClick={() => setSelAircraft(null)} className="ml-1" style={{ color: "rgba(232,228,220,0.4)" }}>
                <svg width="11" height="11" viewBox="0 0 12 12" stroke="currentColor" strokeWidth="1.5"><line x1="1" y1="1" x2="11" y2="11" /><line x1="11" y1="1" x2="1" y2="11" /></svg>
              </button>
            </div>
            <div className="px-3 py-2.5">
              <p className="text-[13px] font-semibold leading-snug mb-2.5" style={{ color: "#E8E4DC" }}>
                {selAircraft.callsign}{selAircraft.country ? ` · ${selAircraft.country}` : ""}
              </p>
              <div className="grid grid-cols-2 gap-y-1.5 gap-x-3">
                {rows.map(([k, v]) => (
                  <div key={k} className="flex flex-col">
                    <span className="text-[8px] font-mono uppercase tracking-widest" style={{ color: "rgba(232,228,220,0.35)" }}>{k}</span>
                    <span className="text-[11px] font-mono" style={{ color: "rgba(232,228,220,0.85)" }}>{v}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        );
      })()}

      {/* Impact-zone traffic count (selected event) */}
      {ready && selectedNodeId && (zoneCount.vessels + zoneCount.aircraft) > 0 && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-20">
          <div className="backdrop-blur-sm border px-3 py-1.5 flex items-center gap-2 shadow-sm" style={{ backgroundColor: "rgba(14,21,32,0.9)", borderColor: "rgba(232,228,220,0.14)" }}>
            <span className="w-1.5 h-1.5 rounded-full bg-crimson animate-pulse" />
            <span className="text-[10px] tracking-wide" style={{ color: "rgba(232,228,220,0.75)" }}>
              {zoneCount.vessels} vessels · {zoneCount.aircraft} flights in impact zone
            </span>
          </div>
        </div>
      )}

      {/* Event count */}
      {ready && nodes.length > 0 && (
        <div className="absolute top-3 right-3 z-20">
          <div className="backdrop-blur-sm border px-3 py-1.5 flex items-center gap-2 shadow-sm" style={{ backgroundColor: "rgba(14,21,32,0.85)", borderColor: "rgba(232,228,220,0.12)" }}>
            <span className="w-1.5 h-1.5 rounded-full bg-crimson" style={{ boxShadow: "0 0 6px #C80028AA" }} />
            <span className="text-[10px] tracking-wide" style={{ color: "rgba(232,228,220,0.5)" }}>{nodes.length} active events</span>
          </div>
        </div>
      )}

      {/* Legend */}
      {ready && (
        <div className="absolute bottom-3 right-3 z-20 flex flex-col gap-2 items-end">
          {showVessels && (
            <div className="flex items-center gap-3 backdrop-blur-sm border px-3 py-2 shadow-sm" style={{ backgroundColor: "rgba(14,21,32,0.85)", borderColor: "rgba(232,228,220,0.12)" }}>
              {Object.values(VESSEL_TYPES).slice(0, 4).map((t) => (
                <div key={t.label} className="flex items-center gap-1.5">
                  <span style={{ width: 0, height: 0, borderLeft: "3px solid transparent", borderRight: "3px solid transparent", borderBottom: `6px solid ${t.color}` }} />
                  <span className="text-[9px] tracking-wide" style={{ color: "rgba(232,228,220,0.5)" }}>{t.label}</span>
                </div>
              ))}
            </div>
          )}
          {showAircraft && (
            <div className="flex items-center gap-3 backdrop-blur-sm border px-3 py-2 shadow-sm" style={{ backgroundColor: "rgba(14,21,32,0.85)", borderColor: "rgba(232,228,220,0.12)" }}>
              {Object.values(AIRCRAFT_TYPES).slice(0, 4).map((t) => (
                <div key={t.label} className="flex items-center gap-1.5">
                  <span style={{ color: t.color, fontSize: 10, lineHeight: 1 }}>✈</span>
                  <span className="text-[9px] tracking-wide" style={{ color: "rgba(232,228,220,0.5)" }}>{t.label}</span>
                </div>
              ))}
            </div>
          )}
          <div className="flex items-center gap-4 backdrop-blur-sm border px-4 py-2 shadow-sm" style={{ backgroundColor: "rgba(14,21,32,0.85)", borderColor: "rgba(232,228,220,0.12)" }}>
            {[{ label: "Escalating", opacity: 1 }, { label: "Developing", opacity: 0.7 }, { label: "Stable", opacity: 0.35 }].map(({ label, opacity }) => (
              <div key={label} className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full bg-crimson" style={{ opacity, boxShadow: opacity > 0.5 ? `0 0 5px ${CRIMSON}99` : "none" }} />
                <span className="text-[10px] tracking-wide" style={{ color: "rgba(232,228,220,0.5)" }}>{label}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
