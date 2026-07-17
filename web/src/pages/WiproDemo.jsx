import { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import * as d3 from "d3";
import * as topojson from "topojson-client";
import { api } from "../lib/api.js";
import { getDisciplineColor } from "../lib/colors.js";
import { useTheme } from "../hooks/useTheme.js";
import assetsData from "../data/wipro/assets.json";
import travelData from "../data/wipro/travel.json";

// ─────────────────────────────────────────────────────────────────────────────
// Wipro customer demo — a customer-centric dashboard over the SAME live Narrative
// backend the rest of the app runs on. Zero new backend: every panel is computed
// client-side from GET /events/ + GET /exposure plus a static demo asset register
// (assets.json) and travel manifest (travel.json).
//
// Competitive framing (QBR teardown): country risk ratings + a client-set "risk
// appetite" (Canvas parity), asset & travel advisories (GSOC-advisory parity,
// honestly minus physical response), an UNLIMITED ask-the-analyst (vs a 21/yr
// quota), and the wedge — cross-discipline fusion the human-analyst firm could
// only hand-wave. Direct URL only (/wipro); intentionally not in the main nav.
// ─────────────────────────────────────────────────────────────────────────────

const ASSETS = assetsData.assets;
const TRIPS = travelData.trips;

// ── Geometry + region helpers (client-side only — no engine constants) ───────
function haversineKm(lat1, lng1, lat2, lng2) {
  const R = 6371, toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1), dLng = toRad(lng2 - lng1);
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

// Region cards match the client's footprint. Order matters: first match wins
// (UAE/Saudi before the broad Europe/Americas boxes).
const REGIONS = [
  { key: "India", names: ["india"], box: { latMin: 6, latMax: 36, lngMin: 68, lngMax: 98 } },
  { key: "UAE", names: ["united arab emirates", "uae", "dubai", "abu dhabi"], box: { latMin: 22, latMax: 26.5, lngMin: 51, lngMax: 56.5 } },
  { key: "Saudi Arabia", names: ["saudi"], box: { latMin: 16, latMax: 33, lngMin: 34.5, lngMax: 56 } },
  { key: "Europe", names: ["europe", "united kingdom", "uk", "germany", "france", "romania", "poland", "ukraine", "italy", "spain", "netherlands"], box: { latMin: 35, latMax: 71, lngMin: -11, lngMax: 40 } },
  { key: "Americas", names: ["united states", "usa", "canada", "brazil", "mexico"], box: { latMin: -56, latMax: 72, lngMin: -170, lngMax: -30 } },
];

function regionOf(event) {
  const geo = (event.geographic_relevance || []).map((g) => String(g).toLowerCase());
  for (const r of REGIONS) {
    if (r.names.some((n) => geo.some((g) => g.includes(n)))) return r.key;
  }
  const lat = event.geo_centroid_lat, lng = event.geo_centroid_lng;
  if (lat == null || lng == null) return null;
  for (const r of REGIONS) {
    const b = r.box;
    if (lat >= b.latMin && lat <= b.latMax && lng >= b.lngMin && lng <= b.lngMax) return r.key;
  }
  return null;
}

// Rating ladder. The appetite factor rescales thresholds (Canvas parity): a
// higher risk appetite means the same signal reads one notch calmer.
const LEVELS = [
  { name: "LOW", color: "#4E9A5A" },
  { name: "GUARDED", color: "#C08A2E" },
  { name: "ELEVATED", color: "#C2622E" },
  { name: "HIGH", color: "#B4462F" },
];
function ratingFor(score, factor) {
  if (score >= 220 * factor) return LEVELS[3];
  if (score >= 110 * factor) return LEVELS[2];
  if (score >= 40 * factor) return LEVELS[1];
  return LEVELS[0];
}

// ── Shared data layer: one events fetch + one exposure fetch for every panel ─
function useLiveData() {
  const [state, setState] = useState({ loading: true, events: [], corrob: {}, sectors: [], error: null });
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [evs, ex, demo] = await Promise.allSettled([
        api.get("/events/?limit=100"),
        api.get("/exposure", { timeoutMs: 20000 }),
        // The live window is importance-sorted, so a hot news cycle crowds the
        // seeded scenario (importance 55–72, calibrated to the panel thresholds)
        // out of the top-100 — fetch the scenario slice explicitly so the demo
        // beats never depend on a quiet day.
        api.get("/events/?source_prefix=wipro_demo&limit=50"),
      ]);
      if (cancelled) return;
      const parse = (r) => r.status === "fulfilled"
        ? (Array.isArray(r.value) ? r.value : r.value?.events || [])
        : [];
      const live = parse(evs);
      const seen = new Set(live.map((e) => e.id));
      const events = live.concat(parse(demo).filter((e) => !seen.has(e.id)));
      const exposure = ex.status === "fulfilled" ? ex.value : null;
      // Fusion over the events actually in view — /exposure corroborates the
      // global top-importance slice, which can exclude everything this page
      // shows. Falls back to the global map if the scoped call fails.
      let corrob = exposure?.corroboration || {};
      if (events.length) {
        try {
          const vc = await api.get(`/events/corroboration?ids=${events.map((e) => e.id).join(",")}`);
          if (vc?.corroboration) corrob = vc.corroboration;
        } catch { /* keep the global exposure map */ }
      }
      if (cancelled) return;
      // The capped score saturates at 100 across the board when the graph runs
      // hot — rank by the un-capped net signal so "most exposed" stays a real
      // ordering instead of an alphabetical tie.
      const sectors = (exposure?.sectors || exposure?.exposure || [])
        .slice()
        .sort((a, b) => (b.net ?? b.score ?? b.exposure ?? 0) - (a.net ?? a.score ?? a.exposure ?? 0))
        .slice(0, 3);
      const expired = [evs, ex, demo].some((r) => r.status === "rejected" && r.reason?.status === 401);
      setState({
        loading: false,
        events,
        corrob,
        sectors,
        error: expired ? "auth"
          : evs.status === "rejected" && ex.status === "rejected" ? "unreachable" : null,
      });
    })();
    return () => { cancelled = true; };
  }, []);
  return state;
}

// ── Small building blocks (match IntFusion idiom) ────────────────────────────
function DisciplineBadge({ code }) {
  if (!code) return null;
  const color = getDisciplineColor(code);
  return (
    <span className="text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded-sm"
      style={{ color, border: `1px solid ${color}55`, backgroundColor: `${color}12` }}>
      {code}
    </span>
  );
}

function Pill({ label, color }) {
  return (
    <span className="text-[9px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full"
      style={{ color, border: `1px solid ${color}66`, backgroundColor: `${color}14` }}>
      {label}
    </span>
  );
}

function SectionCard({ title, subtitle, right, children }) {
  return (
    <section className="bg-paper border border-ink/10 rounded-sm overflow-hidden">
      <header className="px-5 py-3 border-b border-ink/10 flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="text-[12px] font-bold uppercase tracking-[0.2em] text-ink">{title}</h2>
          {subtitle && <p className="text-[10px] text-ink/45 mt-0.5 leading-snug">{subtitle}</p>}
        </div>
        {right}
      </header>
      {children}
    </section>
  );
}

function EmptyNote({ text }) {
  return <p className="px-5 py-6 text-[11px] text-ink/35 leading-relaxed">{text}</p>;
}

// ── a. C-Suite Executive Brief ───────────────────────────────────────────────
function ExecBrief({ data, fusionCount }) {
  const { loading, events, sectors } = data;
  const activeTrips = TRIPS.filter((t) => new Date(t.returnISO) >= new Date()).length;
  const topEvent = events[0];
  const tiles = [
    { n: ASSETS.length, label: "Assets monitored", so: "Every site checked against the live event graph." },
    { n: activeTrips, label: "Travelers in motion", so: "Each itinerary scored against events at destination." },
    { n: loading ? "…" : fusionCount, label: "Multi-INT convergences", so: "Independent disciplines agreeing in space & time." },
    { n: loading ? "…" : events.length, label: "Live events in view", so: topEvent ? `Top: ${(topEvent.canonical_title || "").slice(0, 60)}` : "No live events reachable." },
  ];
  return (
    <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
      {tiles.map((t) => (
        <div key={t.label} className="bg-paper border border-ink/10 rounded-sm px-5 py-4">
          <div className="text-[28px] font-bold tabular-nums text-ink leading-none">{t.n}</div>
          <div className="text-[10px] font-bold uppercase tracking-widest text-ink/60 mt-2">{t.label}</div>
          <p className="text-[10px] text-ink/40 mt-1 leading-snug">{t.so}</p>
        </div>
      ))}
      {sectors.length > 0 && (
        <div className="col-span-2 xl:col-span-4 bg-paper border border-ink/10 rounded-sm px-5 py-3 flex flex-wrap items-center gap-x-6 gap-y-1">
          <span className="text-[10px] font-bold uppercase tracking-widest text-ink/60">Most exposed sectors</span>
          {sectors.map((s) => (
            <span key={s.sector || s.name} className="text-[11px] text-ink/80">
              {s.sector || s.name}
              <span className="text-ink/35 tabular-nums ml-1.5">signal {Math.round(s.net ?? s.score ?? s.exposure ?? 0)}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ── b. Country risk ratings + risk-appetite slider (Canvas parity) ───────────
function CountryRisk({ data, appetite, setAppetite }) {
  const { loading, events } = data;
  const factor = 0.5 + appetite / 100; // 0.5 (cautious) → 1.5 (tolerant)
  const cards = useMemo(() => {
    const scores = Object.fromEntries(REGIONS.map((r) => [r.key, 0]));
    for (const e of events) {
      const r = regionOf(e);
      if (r) scores[r] += (e.global_importance_score || 0) / 10;
    }
    return REGIONS.map((r) => ({ key: r.key, score: scores[r.key], level: ratingFor(scores[r.key], factor) }));
  }, [events, factor]);

  return (
    <SectionCard
      title="Country risk ratings"
      subtitle="Importance-weighted live events per region — recomputed continuously, timestamped now, not last quarter."
      right={
        <label className="flex items-center gap-2 flex-shrink-0" title="Re-baselines every rating to your organisation's tolerance — your appetite, not the vendor's.">
          <span className="text-[9px] font-bold uppercase tracking-widest text-ink/50">Set your risk appetite</span>
          <input type="range" min="0" max="100" value={appetite}
            onChange={(e) => setAppetite(Number(e.target.value))} className="w-24 accent-crimson" />
        </label>
      }
    >
      {loading ? (
        <EmptyNote text="Scoring regions from the live graph…" />
      ) : events.length === 0 ? (
        <EmptyNote text="No live events reachable — ratings need the event graph. Start the stack and refresh." />
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-5 divide-x divide-ink/8">
          {cards.map((c) => (
            <div key={c.key} className="px-4 py-4 text-center">
              <div className="text-[11px] font-semibold text-ink mb-2">{c.key}</div>
              <Pill label={c.level.name} color={c.level.color} />
              <div className="text-[9px] text-ink/35 mt-2 tabular-nums">signal {Math.round(c.score)}</div>
            </div>
          ))}
        </div>
      )}
    </SectionCard>
  );
}

// ── World presence map — every site, itinerary and signal on one map ─────────
const WORLD_TOPO_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";
const STATUS_COLORS = { Alert: "#B4462F", Watch: "#C08A2E", Clear: "#4E9A5A" };

function nearestGeoSignal(geoEvents, lat, lng, radiusKm) {
  let best = null;
  for (const e of geoEvents) {
    const km = haversineKm(lat, lng, e.geo_centroid_lat, e.geo_centroid_lng);
    if (km <= radiusKm && (!best || (e.global_importance_score || 0) > (best.imp || 0)))
      best = { event: e, km, imp: e.global_importance_score || 0 };
  }
  return best;
}

function WorldPresence({ data, appetite, onOpen }) {
  const { loading, events } = data;
  const factor = 0.5 + appetite / 100;
  const [world, setWorld] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetch(WORLD_TOPO_URL)
      .then((r) => r.json())
      .then((topo) => { if (!cancelled) setWorld(topojson.feature(topo, topo.objects.countries)); })
      .catch(() => { if (!cancelled) setWorld("error"); });
    return () => { cancelled = true; };
  }, []);

  const W = 960, H = 470;
  const { path, project } = useMemo(() => {
    const projection = d3.geoNaturalEarth1().fitSize([W, H], { type: "Sphere" });
    return { path: d3.geoPath(projection), project: projection };
  }, []);

  const geoEvents = useMemo(
    () => events.filter((e) => e.geo_centroid_lat != null && e.geo_centroid_lng != null),
    [events],
  );

  const sites = useMemo(() => ASSETS.map((a) => {
    const best = nearestGeoSignal(geoEvents, a.lat, a.lng, 400);
    const label = !best ? "Clear" : best.imp >= 70 * factor ? "Alert" : best.imp >= 40 * factor ? "Watch" : "Clear";
    return { asset: a, best, label };
  }), [geoEvents, factor]);

  const trips = useMemo(() => TRIPS.map((t) => {
    const best = nearestGeoSignal(geoEvents, t.toLat, t.toLng, 300);
    const label = best && best.imp >= 70 * factor ? "Alert" : best && best.imp >= 40 * factor ? "Watch" : "Clear";
    return { trip: t, best, label };
  }), [geoEvents, factor]);

  return (
    <SectionCard title="World presence"
      subtitle="Every site, itinerary and live signal on one map — sites sized by headcount and coloured by status, signals coloured by discipline and sized by importance."
      right={loading ? null : <Pill label={`${geoEvents.length} signals`} color="#C80028" />}>
      {world === "error" ? (
        <EmptyNote text="World geometry unavailable — the panels above carry the same picture." />
      ) : !world || loading ? (
        <EmptyNote text="Projecting sites and signals…" />
      ) : (
        <div className="px-2 py-2 text-ink">
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto block" role="img"
            aria-label="World map of Wipro sites, travel destinations and live signals">
            <g fill="currentColor" opacity="0.1">
              {world.features.map((f, i) => <path key={i} d={path(f)} />)}
            </g>
            {/* itineraries — great-circle arcs origin → destination, coloured by verdict.
                Trips carry only the destination coordinates; origins are company cities,
                so resolve them from the asset register (skip the arc when none matches). */}
            {trips.map(({ trip, label }) => {
              const origin = ASSETS.find((a) => a.city.startsWith(trip.from));
              const [dx, dy] = project([trip.toLng, trip.toLat]) || [];
              return (
                <g key={trip.id}>
                  {origin && (
                    <path d={path({ type: "LineString", coordinates: [[origin.lng, origin.lat], [trip.toLng, trip.toLat]] })}
                      fill="none" stroke={STATUS_COLORS[label]} strokeWidth="1" strokeDasharray="3 3" opacity="0.55" />
                  )}
                  {dx != null && (
                    <circle cx={dx} cy={dy} r="4.5" fill="none" stroke={STATUS_COLORS[label]} strokeWidth="1.3" opacity="0.85">
                      <title>{`${trip.traveler} — ${trip.from} → ${trip.to} (${trip.departISO})`}</title>
                    </circle>
                  )}
                </g>
              );
            })}
            {/* live signals — discipline colour, sized by importance */}
            {geoEvents.map((e) => {
              const [x, y] = project([e.geo_centroid_lng, e.geo_centroid_lat]) || [];
              if (x == null) return null;
              return (
                <circle key={e.id} cx={x} cy={y} r={1.5 + (e.global_importance_score || 0) / 32}
                  fill={getDisciplineColor(e.int_discipline) || "#888"} opacity="0.5"
                  style={{ cursor: "pointer" }} onClick={() => onOpen(e.id)}>
                  <title>{e.canonical_title}</title>
                </circle>
              );
            })}
            {/* site → nearest-signal links for anything not Clear */}
            {sites.filter((s) => s.best && s.label !== "Clear").map(({ asset, best, label }) => (
              <path key={`link-${asset.id}`}
                d={path({ type: "LineString", coordinates: [[asset.lng, asset.lat], [best.event.geo_centroid_lng, best.event.geo_centroid_lat]] })}
                fill="none" stroke={STATUS_COLORS[label]} strokeWidth="1.2" opacity="0.7" />
            ))}
            {/* sites — diamonds sized by headcount, coloured by status */}
            {sites.map(({ asset, best, label }) => {
              const [x, y] = project([asset.lng, asset.lat]) || [];
              if (x == null) return null;
              const r = 3 + Math.sqrt(asset.headcount) / 45;
              return (
                <g key={asset.id} transform={`translate(${x},${y}) rotate(45)`}
                  style={{ cursor: best ? "pointer" : "default" }}
                  onClick={() => best && onOpen(best.event.id)}>
                  <rect x={-r} y={-r} width={r * 2} height={r * 2}
                    fill={STATUS_COLORS[label]} opacity="0.9" stroke="currentColor" strokeOpacity="0.35" strokeWidth="0.8" />
                  <title>{`${asset.name} — ${label}${best ? ` · ${best.event.canonical_title}` : ""}`}</title>
                </g>
              );
            })}
          </svg>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1 px-3 pb-1">
            {Object.entries(STATUS_COLORS).map(([label, color]) => (
              <span key={label} className="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-widest text-ink/50">
                <span className="w-2 h-2 rotate-45" style={{ backgroundColor: color }} /> {label} site
              </span>
            ))}
            <span className="text-[9px] uppercase tracking-widest text-ink/40">
              · dots = live signals (discipline colour) · dashes = itineraries
            </span>
          </div>
        </div>
      )}
    </SectionCard>
  );
}

// ── c. Real estate & asset exposure ──────────────────────────────────────────
function AssetExposure({ data, appetite, onOpen }) {
  const { loading, events } = data;
  const factor = 0.5 + appetite / 100;
  const rows = useMemo(() => {
    const geoEvents = events.filter((e) => e.geo_centroid_lat != null && e.geo_centroid_lng != null);
    return ASSETS.map((a) => {
      let best = null;
      for (const e of geoEvents) {
        const km = haversineKm(a.lat, a.lng, e.geo_centroid_lat, e.geo_centroid_lng);
        if (km <= 400 && (!best || (e.global_importance_score || 0) > (best.imp || 0)))
          best = { event: e, km, imp: e.global_importance_score || 0 };
      }
      const status = !best ? { label: "Clear", color: "#4E9A5A", rank: 0 }
        : best.imp >= 70 * factor ? { label: "Alert", color: "#B4462F", rank: 2 }
        : best.imp >= 40 * factor ? { label: "Watch", color: "#C08A2E", rank: 1 }
        : { label: "Clear", color: "#4E9A5A", rank: 0 };
      return { asset: a, best, status };
    }).sort((x, y) => y.status.rank - x.status.rank || (y.best?.imp || 0) - (x.best?.imp || 0));
  }, [events, factor]);

  return (
    <SectionCard title="Real estate & asset exposure"
      subtitle={`${ASSETS.length} sites checked against every geolocated live event within 400 km.`}>
      {loading ? <EmptyNote text="Checking sites against the live graph…" /> : (
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="text-[9px] font-bold uppercase tracking-widest text-ink/40 border-b border-ink/8">
                <th className="px-5 py-2">Site</th><th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">Headcount</th><th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Nearest signal</th><th className="px-3 py-2 text-right">Distance</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ asset, best, status }) => (
                <tr key={asset.id} className="border-b border-ink/6 hover:bg-ink/[0.02]">
                  <td className="px-5 py-2.5">
                    <div className="text-[12px] font-medium text-ink">{asset.name}</div>
                    <div className="text-[10px] text-ink/40">{asset.city} · {asset.country}</div>
                  </td>
                  <td className="px-3 py-2.5 text-[10px] text-ink/50 capitalize">{asset.type}</td>
                  <td className="px-3 py-2.5 text-[11px] text-ink/60 tabular-nums">{asset.headcount.toLocaleString()}</td>
                  <td className="px-3 py-2.5"><Pill label={status.label} color={status.color} /></td>
                  <td className="px-3 py-2.5 max-w-[320px]">
                    {best ? (
                      <button type="button" onClick={() => onOpen(best.event.id)}
                        className="text-left group flex items-center gap-2">
                        <DisciplineBadge code={best.event.int_discipline} />
                        <span className="text-[11px] text-ink/70 truncate group-hover:text-crimson transition-colors">
                          {best.event.canonical_title}
                        </span>
                      </button>
                    ) : <span className="text-[10px] text-ink/30">No signal within 400 km</span>}
                  </td>
                  <td className="px-3 py-2.5 text-right text-[11px] text-ink/50 tabular-nums">
                    {best ? `${Math.round(best.km)} km` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  );
}

// ── d. Travel security ───────────────────────────────────────────────────────
function TravelSecurity({ data, appetite, onOpen }) {
  const { loading, events } = data;
  const factor = 0.5 + appetite / 100;
  const rows = useMemo(() => {
    const geoEvents = events.filter((e) => e.geo_centroid_lat != null && e.geo_centroid_lng != null);
    return TRIPS.map((t) => {
      let best = null;
      for (const e of geoEvents) {
        const km = haversineKm(t.toLat, t.toLng, e.geo_centroid_lat, e.geo_centroid_lng);
        if (km <= 300 && (!best || (e.global_importance_score || 0) > (best.imp || 0)))
          best = { event: e, km, imp: e.global_importance_score || 0 };
      }
      const verdict = best && best.imp >= 70 * factor ? { label: "Reconsider", color: "#B4462F" }
        : best && best.imp >= 40 * factor ? { label: "Advise", color: "#C08A2E" }
        : { label: "Proceed", color: "#4E9A5A" };
      return { trip: t, best, verdict };
    });
  }, [events, factor]);

  return (
    <SectionCard title="Travel security"
      subtitle="Each itinerary scored against live events within 300 km of destination.">
      {loading ? <EmptyNote text="Scoring itineraries…" /> : (
        <>
          <div className="divide-y divide-ink/6">
            {rows.map(({ trip, best, verdict }) => (
              <div key={trip.id} className="px-5 py-3 flex flex-wrap items-center gap-x-4 gap-y-1">
                <div className="min-w-[190px]">
                  <div className="text-[12px] font-medium text-ink">{trip.traveler}</div>
                  <div className="text-[10px] text-ink/40">{trip.role}</div>
                </div>
                <div className="min-w-[170px]">
                  <div className="text-[11px] text-ink/75">{trip.from} → {trip.to}</div>
                  <div className="text-[10px] text-ink/40">{trip.departISO} → {trip.returnISO}</div>
                </div>
                <Pill label={verdict.label} color={verdict.color} />
                <div className="flex-1 min-w-[200px]">
                  {best ? (
                    <button type="button" onClick={() => onOpen(best.event.id)}
                      className="text-left flex items-center gap-2 group">
                      <DisciplineBadge code={best.event.int_discipline} />
                      <span className="text-[11px] text-ink/60 truncate group-hover:text-crimson transition-colors">
                        {best.event.canonical_title} · {Math.round(best.km)} km out
                      </span>
                    </button>
                  ) : <span className="text-[10px] text-ink/30">No adverse signal at destination</span>}
                </div>
              </div>
            ))}
          </div>
          <p className="px-5 py-2.5 text-[9px] text-ink/35 border-t border-ink/8">
            Advisory only — physical response (evacuation, ground support) via partner.
          </p>
        </>
      )}
    </SectionCard>
  );
}

// ── e. Cross-domain fusion strip (the wedge) ─────────────────────────────────
function FusionStrip({ data, onOpen }) {
  const { loading, events, corrob } = data;
  const items = useMemo(() => {
    const byId = {};
    for (const e of events) byId[e.id] = e;
    return Object.entries(corrob)
      .map(([id, c]) => ({
        id, index: c.index || 0, count: c.count || 0,
        disciplines: c.disciplines || [], event: byId[id] || null,
      }))
      .filter((r) => (r.disciplines?.length || 0) >= 2)
      // Equal fusion indexes are common (the index saturates fast) — break ties
      // by breadth of disciplines so the widest convergences surface first.
      .sort((a, b) => b.index - a.index
        || (b.disciplines?.length || 0) - (a.disciplines?.length || 0))
      .slice(0, 6);
  }, [events, corrob]);

  return (
    <div style={{ backgroundColor: "#111111" }} className="rounded-sm overflow-hidden">
      <div className="px-5 py-3 flex items-center gap-2" style={{ borderBottom: "1px solid rgba(240,237,232,0.08)" }}>
        <span className="w-1.5 h-1.5 rounded-full bg-crimson animate-pulse" />
        <span className="text-[10px] font-mono font-bold uppercase tracking-[0.35em] text-crimson">
          Cross-domain connections
        </span>
        <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: "rgba(240,237,232,0.3)" }}>
          — structural, not hand-waved: independent disciplines converging in space &amp; time
        </span>
      </div>
      {loading ? (
        <p className="px-5 py-5 text-[11px] font-mono uppercase tracking-wider" style={{ color: "rgba(240,237,232,0.35)" }}>
          Correlating sources…
        </p>
      ) : items.length === 0 ? (
        <p className="px-5 py-5 text-[11px] leading-relaxed" style={{ color: "rgba(240,237,232,0.4)" }}>
          No multi-discipline convergence in the current window. When a market move, a cyber
          campaign and ground reporting land on the same place and time, the connection surfaces
          here automatically — no analyst quota consumed.
        </p>
      ) : (
        <div className="flex overflow-x-auto divide-x" style={{ borderColor: "rgba(240,237,232,0.06)" }}>
          {items.map((row) => (
            <button key={row.id} type="button" onClick={() => row.event && onOpen(row.id)}
              className="flex-shrink-0 w-[270px] text-left px-5 py-4"
              style={{ cursor: row.event ? "pointer" : "default" }}>
              <div className="flex flex-wrap gap-1.5 mb-2">
                {row.disciplines.map((d) => <DisciplineBadge key={d} code={d} />)}
              </div>
              <p className="text-[13px] font-semibold leading-snug line-clamp-2 mb-2"
                style={{ color: "rgba(240,237,232,0.85)" }}>
                {row.event?.canonical_title || `${row.disciplines.length}-discipline convergence`}
              </p>
              <div className="text-[9px] font-mono uppercase tracking-wider" style={{ color: "rgba(240,237,232,0.4)" }}>
                {row.count} sources · <span style={{ color: "#C08A2E" }}>fusion {Math.round(row.index * 100)}%</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── f. Ask the Analyst — unlimited (vs a 21-questions/yr quota) ──────────────
function AskAnalyst() {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [turn, setTurn] = useState(null);
  const [error, setError] = useState(null);

  const ask = useCallback(async () => {
    const question = q.trim();
    if (question.length < 3 || busy) return;
    setBusy(true); setError(null);
    try {
      // Agentic operator loop: the local model calls read-only graph tools
      // mid-reasoning. Cold local inference can take minutes — real headroom.
      const res = await api.post("/chat", { question, agent: true }, { timeoutMs: 300000 });
      setTurn({ q: question, ...res });
      setQ("");
    } catch (err) {
      if (err.status === 402) setError("The analyst is a paid feature on this login.");
      else if (err.status === 503) setError("The analyst model is offline right now.");
      else setError(err.message || "The analyst is unavailable right now.");
    } finally { setBusy(false); }
  }, [q, busy]);

  return (
    <SectionCard title="Ask the analyst"
      subtitle="Unlimited. No annual quota. Answers grounded in the live event graph, with the tool calls shown."
      right={<Pill label="Unlimited" color="#4E9A5A" />}>
      <div className="px-5 py-4 space-y-3">
        <div className="flex gap-2">
          <textarea value={q} onChange={(e) => setQ(e.target.value)} rows={2}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(); } }}
            placeholder="e.g. How do current Middle East events connect to our Europe delivery risk?"
            className="flex-1 bg-transparent border border-ink/15 rounded-sm px-3 py-2 text-[12px] text-ink placeholder:text-ink/30 focus:outline-none focus:border-crimson/60 resize-none" />
          <button type="button" onClick={ask} disabled={busy || q.trim().length < 3}
            className="px-4 text-[10px] font-bold uppercase tracking-widest rounded-sm border border-crimson/60 text-crimson hover:bg-crimson hover:text-paper transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
            {busy ? "Working…" : "Ask"}
          </button>
        </div>
        {busy && (
          <p className="text-[10px] font-mono uppercase tracking-wider text-ink/40 flex items-center gap-2">
            <span className="w-3 h-3 border border-ink/20 border-t-crimson rounded-full animate-spin" />
            Querying the live graph (local model — can take a minute)…
          </p>
        )}
        {error && <p className="text-[11px] text-crimson">{error}</p>}
        {turn && !busy && (
          <div className="border border-ink/10 rounded-sm px-4 py-3 space-y-2">
            <p className="text-[10px] font-bold uppercase tracking-widest text-ink/40">{turn.q}</p>
            <p className="text-[12px] text-ink/85 leading-relaxed whitespace-pre-wrap">{turn.answer}</p>
            <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-ink/8">
              {turn.mode && <Pill label={turn.mode} color="#5BA3D0" />}
              {(turn.tool_trace || []).map((t, i) => (
                <span key={i} className="text-[9px] font-mono text-ink/45 px-1.5 py-0.5 border border-ink/10 rounded-sm">
                  {t.tool || t.name || String(t).slice(0, 30)}
                </span>
              ))}
              {Array.isArray(turn.sources) && turn.sources.length > 0 && (
                <span className="text-[9px] text-ink/35">{turn.sources.length} sources</span>
              )}
            </div>
          </div>
        )}
      </div>
    </SectionCard>
  );
}

// ── g. Event timeline ────────────────────────────────────────────────────────
function EventTimeline({ data, onOpen }) {
  const { loading, events } = data;
  const dots = useMemo(() => {
    const dated = events
      .filter((e) => e.first_detected_at)
      .sort((a, b) => new Date(a.first_detected_at) - new Date(b.first_detected_at))
      .slice(-30);
    if (dated.length === 0) return [];
    const t0 = new Date(dated[0].first_detected_at).getTime();
    const t1 = new Date(dated[dated.length - 1].first_detected_at).getTime();
    const span = Math.max(t1 - t0, 1);
    return dated.map((e) => ({
      e,
      x: ((new Date(e.first_detected_at).getTime() - t0) / span) * 100,
      size: 8 + ((e.global_importance_score || 0) / 100) * 14,
    }));
  }, [events]);

  return (
    <SectionCard title="Event timeline"
      subtitle="The last 30 events as they were detected — size is importance, colour is discipline. Most recent right.">
      {loading ? <EmptyNote text="Loading timeline…" /> : dots.length === 0 ? (
        <EmptyNote text="No dated events in view." />
      ) : (
        <div className="px-6 pt-8 pb-4">
          <div className="relative h-16">
            <div className="absolute left-0 right-0 top-1/2 h-px bg-ink/12" />
            {dots.map(({ e, x, size }) => (
              <button key={e.id} type="button" onClick={() => onOpen(e.id)}
                title={`${e.canonical_title}\n${new Date(e.first_detected_at).toLocaleString()}`}
                className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 rounded-full hover:ring-2 hover:ring-crimson/50 transition-shadow"
                style={{
                  left: `${x}%`, width: size, height: size,
                  backgroundColor: getDisciplineColor(e.int_discipline),
                  opacity: 0.85,
                }} />
            ))}
          </div>
          <div className="flex justify-between text-[9px] font-mono uppercase tracking-wider text-ink/35">
            <span>{new Date(dots[0].e.first_detected_at).toLocaleDateString()}</span>
            <span>{new Date(dots[dots.length - 1].e.first_detected_at).toLocaleDateString()}</span>
          </div>
        </div>
      )}
    </SectionCard>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────
export default function WiproDemo() {
  const navigate = useNavigate();
  const { isDark, toggle } = useTheme();
  const data = useLiveData();
  const [appetite, setAppetiteState] = useState(() => {
    // Number(null) is 0, which passes the range check — an unset key must fall
    // through to the 50 default, not silently pin the slider to most-cautious.
    const raw = localStorage.getItem("wipro_risk_appetite");
    const v = raw === null ? NaN : Number(raw);
    return Number.isFinite(v) && v >= 0 && v <= 100 ? v : 50;
  });
  const setAppetite = (v) => { setAppetiteState(v); localStorage.setItem("wipro_risk_appetite", String(v)); };

  const onOpen = (id) => navigate(`/event/${id}`);
  const fusionCount = useMemo(
    () => Object.values(data.corrob).filter((c) => (c.disciplines?.length || 0) >= 2).length,
    [data.corrob],
  );

  return (
    <div className="min-h-screen bg-paper flex flex-col">
      <header style={{ backgroundColor: "#111111" }} className="sticky top-0 z-40">
        <div className="max-w-[1400px] mx-auto px-4 md:px-6 py-2.5 flex items-center justify-between">
          <div>
            <h1 className="font-display text-[1.5rem] md:text-[2rem] tracking-tighter leading-none" style={{ color: "#F0EDE8" }}>
              WIPRO <span style={{ color: "#C80028" }}>SECURITY PICTURE</span>
            </h1>
            <p className="text-[7px] md:text-[8px] tracking-[0.35em] uppercase mt-0.5 hidden md:block" style={{ color: "rgba(240,237,232,0.3)" }}>
              Customer demo · live Narrative backend · assets, people, connections
            </p>
          </div>
          <div className="flex items-center gap-4">
            <span className="hidden md:flex items-center gap-1.5 text-[9px] uppercase tracking-wider" style={{ color: "rgba(240,237,232,0.3)" }}>
              <span className="w-1.5 h-1.5 rounded-full bg-crimson animate-pulse" /> Live
            </span>
            <button onClick={toggle}
              className="text-[11px] font-mono uppercase tracking-wider hover:text-crimson transition-colors"
              style={{ color: "rgba(240,237,232,0.5)" }} title={isDark ? "Day mode" : "Night mode"}>
              {isDark ? "☀" : "☾"}
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-[1400px] w-full mx-auto px-4 md:px-6 py-6 pb-24 md:pb-8 space-y-5">
        {data.error === "unreachable" && (
          <p className="text-[11px] text-crimson border border-crimson/30 rounded-sm px-4 py-3">
            The Narrative backend is unreachable — every panel below will show its empty state.
            Start the stack and refresh.
          </p>
        )}
        {data.error === "auth" && (
          <p className="text-[11px] text-crimson border border-crimson/30 rounded-sm px-4 py-3">
            Your session has expired — every panel below will show its empty state.{" "}
            <button type="button" onClick={() => navigate("/auth")} className="underline hover:text-ink transition-colors">
              Sign in again
            </button>{" "}
            to load live data.
          </p>
        )}
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }} className="space-y-5">
          <ExecBrief data={data} fusionCount={fusionCount} />
          <FusionStrip data={data} onOpen={onOpen} />
          <WorldPresence data={data} appetite={appetite} onOpen={onOpen} />
          <CountryRisk data={data} appetite={appetite} setAppetite={setAppetite} />
          <AssetExposure data={data} appetite={appetite} onOpen={onOpen} />
          <TravelSecurity data={data} appetite={appetite} onOpen={onOpen} />
          <div className="grid gap-5 lg:grid-cols-2">
            <AskAnalyst />
            <EventTimeline data={data} onOpen={onOpen} />
          </div>
        </motion.div>
        <p className="text-[10px] text-ink/30 leading-relaxed max-w-3xl">
          Demo scope, stated honestly: asset register and travel manifest are illustrative demo
          data; every rating, advisory and connection is computed live from the same event graph
          the rest of Narrative runs on. Physical ground response (GSOC, evacuation) is out of
          scope — delivered via partner, not pretended here.
        </p>
      </main>
    </div>
  );
}
