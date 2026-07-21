import { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import * as d3 from "d3";
import * as topojson from "topojson-client";
import { api } from "../lib/api.js";
import DeckView from "../components/DeckView.jsx";
import { getDisciplineColor } from "../lib/colors.js";
import { haversineKm as _havKm } from "../lib/geoAssoc.js";
import { officeContext, topSignal, LAYER_KEYS, LAYER_LABELS, levelColor } from "../lib/officeContext.js";
import { useTheme } from "../hooks/useTheme.js";

// ─────────────────────────────────────────────────────────────────────────────
// CustomerDeck — a config-driven customer dashboard over the SAME live Narrative
// backend the rest of the app runs on. Zero customer-specific backend: every panel
// is computed client-side from GET /events/ + GET /exposure, driven entirely by a
// customer config object (branding / assets / trips / regions / advisories / flags).
// `/wipro` is just <CustomerDeck config={wipro} />; the next tenant is a new JSON.
//
// Competitive framing (QBR teardown): country risk ratings + a client-set "risk
// appetite" (Canvas parity), asset & travel advisories (GSOC-advisory parity,
// honestly minus physical response), an UNLIMITED ask-the-analyst (vs a 21/yr
// quota), and the wedge — cross-discipline fusion the human-analyst firm could
// only hand-wave. 100% live: no seed slice, honest "clear" offices allowed.
// ─────────────────────────────────────────────────────────────────────────────

// ── Geometry + region helpers (client-side only — no engine constants) ───────
// (lat,lng) adapter over the shared (lng,lat) core in geoAssoc.js — one copy of
// the great-circle math app-wide (adds the domain clamp the local copy lacked).
const haversineKm = (lat1, lng1, lat2, lng2) => _havKm(lng1, lat1, lng2, lat2);

// Region assignment for an event, scoped to the customer's footprint (config
// `regions`). Order matters: first match wins (UAE/Saudi before broad boxes) —
// so the config lists the narrow regions first.
function regionOf(event, regions) {
  const geo = (event.geographic_relevance || []).map((g) => String(g).toLowerCase());
  for (const r of regions) {
    if (r.names.some((n) => geo.some((g) => g.includes(n)))) return r.key;
  }
  const lat = event.geo_centroid_lat, lng = event.geo_centroid_lng;
  if (lat == null || lng == null) return null;
  for (const r of regions) {
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
// 100% live — no seed slice. Offices with no nearby signal read an honest "clear".
// Also pulls the per-country public-holiday calendar (GET /context/calendar) so the
// office layers can carry holidays; a missing calendar degrades to the curated map.
function useLiveData(countryCodes) {
  const [state, setState] = useState({ loading: true, events: [], corrob: {}, sectors: [], holidaysByCode: {}, error: null });
  const codes = useMemo(
    () => [...new Set(Object.values(countryCodes || {}))].join(","),
    [countryCodes],
  );
  useEffect(() => {
    let cancelled = false;
    (async () => {
      // Events gets a generous timeout (not the api client's 3.5s fail-fast): it
      // shares the proxy with the heavy /exposure call and must not abort under load.
      const [evs, ex] = await Promise.allSettled([
        api.get("/events/?limit=100", { timeoutMs: 15000 }),
        api.get("/exposure", { timeoutMs: 20000 }),
      ]);
      if (cancelled) return;
      const parse = (r) => r.status === "fulfilled"
        ? (Array.isArray(r.value) ? r.value : r.value?.events || [])
        : [];
      const events = parse(evs);
      const exposure = ex.status === "fulfilled" ? ex.value : null;
      // Fusion over the events actually in view — /exposure corroborates the
      // global top-importance slice, which can exclude everything this page
      // shows. Falls back to the global map if the scoped call fails.
      let corrob = exposure?.corroboration || {};
      if (events.length) {
        try {
          const vc = await api.get(`/events/corroboration?ids=${events.map((e) => e.id).join(",")}`, { timeoutMs: 15000 });
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
      const expired = [evs, ex].some((r) => r.status === "rejected" && r.reason?.status === 401);
      // Functional update so the decoupled calendar effect's holidaysByCode isn't clobbered.
      setState((s) => ({
        ...s,
        loading: false,
        events,
        corrob,
        sectors,
        error: expired ? "auth"
          : evs.status === "rejected" && ex.status === "rejected" ? "unreachable" : null,
      }));
    })();
    return () => { cancelled = true; };
  }, []);

  // Public-holiday calendar — decoupled from the critical events/exposure batch so
  // its slow cold-cache upstream (Nager.Date across ~7 countries) can neither delay
  // nor abort the events fetch. A miss degrades to the config's curated holidays.
  useEffect(() => {
    if (!codes) return undefined;
    let cancelled = false;
    api.get(`/context/calendar?countries=${codes}&days=60`, { timeoutMs: 15000 })
      .then((cal) => { if (!cancelled && cal?.holidays) setState((s) => ({ ...s, holidaysByCode: cal.holidays })); })
      .catch(() => { /* curated map covers the footprint */ });
    return () => { cancelled = true; };
  }, [codes]);

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

// NATO Admiralty grade chip (Phase 2e), e.g. "B2" — letter = source reliability,
// digit = information credibility, graded server-side from provenance + how many
// independent feeds corroborated the event. The full rationale rides in the tooltip
// so the call is auditable. Colour tracks the credibility digit. Mirrors the chip on
// /int (IntFusion) so the two fusion surfaces read identically.
const _GRADE_COLOR = { 1: "#4E9A5A", 2: "#4E9A5A", 3: "#C08A2E", 4: "#C08A2E", 5: "#B4462F", 6: "#8A8A8A" };

function AdmiraltyGrade({ grade }) {
  if (!grade?.grade) return null;
  const color = _GRADE_COLOR[grade.credibility?.code] || "#8A8A8A";
  const tip = [
    `${grade.reliability?.code} — ${grade.reliability?.label}`,
    `${grade.credibility?.code} — ${grade.credibility?.label}`,
    ...(grade.rationale || []),
  ].join("\n");
  return (
    <span className="font-bold" style={{ color }} title={`NATO Admiralty grade ${grade.grade}\n${tip}`}>
      {grade.grade}
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
function ExecBrief({ data, fusionCount, assets, trips }) {
  const { loading, events, sectors } = data;
  const activeTrips = trips.filter((t) => new Date(t.returnISO) >= new Date()).length;
  const topEvent = events[0];
  const tiles = [
    { n: assets.length, label: "Assets monitored", so: "Every site checked against the live event graph." },
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
function CountryRisk({ data, appetite, setAppetite, regions }) {
  const { loading, events } = data;
  const factor = 0.5 + appetite / 100; // 0.5 (cautious) → 1.5 (tolerant)
  const cards = useMemo(() => {
    const scores = Object.fromEntries(regions.map((r) => [r.key, 0]));
    for (const e of events) {
      const r = regionOf(e, regions);
      if (r) scores[r] += (e.global_importance_score || 0) / 10;
    }
    return regions.map((r) => ({ key: r.key, score: scores[r.key], level: ratingFor(scores[r.key], factor) }));
  }, [events, factor, regions]);

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
const CAP = { alert: "Alert", watch: "Watch", clear: "Clear" };
const DISCIPLINE_LABELS = { HUMINT: "HUMINT", SIGINT: "SIGINT", IMINT: "IMINT", GEOINT: "GEOINT", MASINT: "MASINT", FININT: "FININT", CYBINT: "CYBINT" };

function nearestGeoSignal(geoEvents, lat, lng, radiusKm) {
  let best = null;
  for (const e of geoEvents) {
    const km = haversineKm(lat, lng, e.geo_centroid_lat, e.geo_centroid_lng);
    if (km <= radiusKm && (!best || (e.global_importance_score || 0) > (best.imp || 0)))
      best = { event: e, km, imp: e.global_importance_score || 0 };
  }
  return best;
}

// A compact metric for the summary strip above the map.
function Stat({ n, label, tint }) {
  return (
    <div className="flex flex-col">
      <span className="text-[20px] font-bold tabular-nums leading-none" style={{ color: tint || "currentColor" }}>{n}</span>
      <span className="text-[9px] font-bold uppercase tracking-widest text-ink/45 mt-1">{label}</span>
    </div>
  );
}

function WorldPresence({ data, appetite, onOpen, assets, trips, contexts }) {
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
  const { path, project, graticule } = useMemo(() => {
    const projection = d3.geoNaturalEarth1().fitSize([W, H], { type: "Sphere" });
    return { path: d3.geoPath(projection), project: projection, graticule: d3.geoGraticule10() };
  }, []);

  const geoEvents = useMemo(
    () => events.filter((e) => e.geo_centroid_lat != null && e.geo_centroid_lng != null),
    [events],
  );

  // Site status now comes from the SAME per-office rollup the matrix uses (worst of
  // all eight layers), so the map and the matrix can never disagree.
  const sites = useMemo(() => contexts.map((c) => ({
    asset: c.office, label: CAP[c.worst], top: topSignal(c),
  })), [contexts]);

  const tripDots = useMemo(() => trips.map((t) => {
    const best = nearestGeoSignal(geoEvents, t.toLat, t.toLng, 300);
    const label = best && best.imp >= 70 * factor ? "Alert" : best && best.imp >= 40 * factor ? "Watch" : "Clear";
    return { trip: t, best, label };
  }), [geoEvents, factor, trips]);

  // Unique festivals that are active or imminent, for map markers + the tally.
  const festMarkers = useMemo(() => {
    const seen = new Map();
    for (const c of contexts) for (const f of c.festivals) {
      if ((f.active || f.soon) && f.lat != null && !seen.has(f.id)) seen.set(f.id, f);
    }
    return [...seen.values()];
  }, [contexts]);

  // Discipline tally + site status counts for the summary strip.
  const summary = useMemo(() => {
    const disc = {};
    for (const e of geoEvents) { const d = (e.int_discipline || "").toUpperCase(); if (DISCIPLINE_LABELS[d]) disc[d] = (disc[d] || 0) + 1; }
    const status = { Alert: 0, Watch: 0, Clear: 0 };
    for (const s of sites) status[s.label] = (status[s.label] || 0) + 1;
    const activeTrips = trips.filter((t) => new Date(t.returnISO) >= new Date()).length;
    return {
      status, activeTrips,
      disc: Object.entries(disc).sort((a, b) => b[1] - a[1]),
    };
  }, [geoEvents, sites, trips]);

  return (
    <SectionCard title="World presence"
      subtitle="Every site, itinerary and live signal on one map — sites sized by headcount and coloured by their worst live layer; signals coloured by discipline and sized by importance; ✦ marks a festival or gathering underway."
      right={loading ? null : <Pill label={`${geoEvents.length} signals`} color="#C80028" />}>
      {world === "error" ? (
        <EmptyNote text="World geometry unavailable — the panels above carry the same picture." />
      ) : !world || loading ? (
        <EmptyNote text="Projecting sites and signals…" />
      ) : (
        <div className="px-2 py-2 text-ink">
          {/* summary strip — the picture in numbers before the map */}
          <div className="flex flex-wrap items-center gap-x-8 gap-y-3 px-3 py-3 mb-1 border-b border-ink/8">
            <Stat n={sites.length} label="Sites monitored" />
            <Stat n={summary.status.Alert} label="Sites in alert" tint={summary.status.Alert ? STATUS_COLORS.Alert : undefined} />
            <Stat n={summary.status.Watch} label="Sites on watch" tint={summary.status.Watch ? STATUS_COLORS.Watch : undefined} />
            <Stat n={summary.activeTrips} label="Travelers in motion" />
            <Stat n={geoEvents.length} label="Live signals" />
            <Stat n={festMarkers.length} label="Gatherings active" tint={festMarkers.length ? "#C08A2E" : undefined} />
            {summary.disc.length > 0 && (
              <div className="flex flex-col gap-1 min-w-0">
                <span className="text-[9px] font-bold uppercase tracking-widest text-ink/45">Signals by discipline</span>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  {summary.disc.map(([d, n]) => (
                    <span key={d} className="flex items-center gap-1 text-[10px] text-ink/70">
                      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: getDisciplineColor(d) }} />
                      {d}<span className="text-ink/35 tabular-nums">{n}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto block" role="img"
            aria-label="World map of customer sites, travel destinations and live signals">
            <g fill="currentColor" opacity="0.1">
              {world.features.map((f, i) => <path key={i} d={path(f)} />)}
            </g>
            {/* graticule — a faint operational grid behind the land */}
            <path d={path(graticule)} fill="none" stroke="currentColor" strokeOpacity="0.06" strokeWidth="0.5" />
            {/* itineraries — great-circle arcs origin → destination, coloured by verdict.
                Trips carry only the destination coordinates; origins are company cities,
                so resolve them from the asset register (skip the arc when none matches). */}
            {tripDots.map(({ trip, label }) => {
              const origin = assets.find((a) => a.city.startsWith(trip.from));
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
            {/* festivals / gatherings underway — amber stars near the affected sites */}
            {festMarkers.map((f) => {
              const [x, y] = project([f.lng, f.lat]) || [];
              if (x == null) return null;
              return (
                <text key={f.id} x={x} y={y + 3} textAnchor="middle" fontSize="11" fill="#C08A2E" opacity="0.9"
                  style={{ cursor: "default", pointerEvents: "all" }}>
                  ✦<title>{`${f.name} — ${f.place || ""}${f.active ? " (underway)" : ` (in ${f.startsIn}d)`}`}</title>
                </text>
              );
            })}
            {/* site → nearest-signal links for anything not Clear */}
            {sites.filter((s) => s.top && s.label !== "Clear").map(({ asset, top, label }) => (
              <path key={`link-${asset.id}`}
                d={path({ type: "LineString", coordinates: [[asset.lng, asset.lat], [top.event.geo_centroid_lng, top.event.geo_centroid_lat]] })}
                fill="none" stroke={STATUS_COLORS[label]} strokeWidth="1.2" opacity="0.7" />
            ))}
            {/* sites — diamonds sized by headcount, coloured by status */}
            {sites.map(({ asset, top, label }) => {
              const [x, y] = project([asset.lng, asset.lat]) || [];
              if (x == null) return null;
              const r = 3 + Math.sqrt(asset.headcount) / 45;
              return (
                <g key={asset.id} transform={`translate(${x},${y}) rotate(45)`}
                  style={{ cursor: top ? "pointer" : "default" }}
                  onClick={() => top && onOpen(top.event.id)}>
                  <rect x={-r} y={-r} width={r * 2} height={r * 2}
                    fill={STATUS_COLORS[label]} opacity="0.9" stroke="currentColor" strokeOpacity="0.35" strokeWidth="0.8" />
                  <title>{`${asset.name} — ${label}${top ? ` · ${top.event.canonical_title}` : ""}`}</title>
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
              · dots = live signals (discipline colour) · ✦ = gathering · dashes = itineraries
            </span>
          </div>
        </div>
      )}
    </SectionCard>
  );
}

// ── World presence · Site security matrix (the "no-gap" per-office rollup) ────
// Every office carried across all eight layers to a single status. A quiet layer
// reads "clear ✓", never blank — the founder's "no reason not to get in". This is
// where the derived-traffic layer (slice 6) and the holiday/festival calendar
// (slice 5) surface; incidents come straight off the live graph.
const LEVEL_WORD = { clear: "Clear", watch: "Watch", alert: "Alert" };

// One layer → its cell: status level, short display text, hover detail, and the
// event to open (if any). Keeps the classification logic out of the JSX.
function cellFor(key, layer) {
  if (key === "traffic") {
    const detail = layer.drivers.length
      ? `Derived road disruption ~${layer.pct}%\n${layer.drivers.map((d) => `• ${d.label}`).join("\n")}`
      : "No road-disruption drivers near this site";
    return { level: layer.level, text: layer.level === "clear" ? "Clear" : `~${layer.pct}%`, title: detail,
      eventId: layer.drivers.find((d) => d.id)?.id || null };
  }
  if (key === "holidays") {
    if (layer.today) return { level: layer.level, text: layer.today.name, title: `${layer.today.name} — public holiday today` };
    if (layer.next) return { level: "clear", text: `+${layer.next.in_days}d`, title: `Next holiday: ${layer.next.name} in ${layer.next.in_days} day(s)` };
    return { level: "clear", text: "Clear", title: "No public holiday in the next 60 days" };
  }
  if (key === "festivals") {
    if (layer.active) return { level: layer.level, text: layer.active.name, title: `${layer.active.name} underway — ${layer.active.note || "crowds & closures"}` };
    if (layer.soon) return { level: layer.level, text: `${layer.soon.name} +${layer.soon.startsIn}d`, title: layer.soon.note || layer.soon.name };
    return { level: "clear", text: "Clear", title: "No gathering near this site in the window" };
  }
  const b = layer.best;
  if (!b) return { level: "clear", text: "Clear", title: "No signal in range" };
  return { level: layer.level, text: LEVEL_WORD[layer.level], eventId: b.event.id,
    title: `${b.event.canonical_title}\n${Math.round(b.km)} km · importance ${Math.round(b.imp)}` };
}

function LayerCell({ cell, onOpen }) {
  const color = levelColor(cell.level);
  const clear = cell.level === "clear";
  const body = (
    <span className="flex items-center gap-1.5 min-w-0">
      <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
      <span className="truncate text-[10px]" style={{ color: clear ? "rgba(0,0,0,0)" : color }}>
        {clear ? "" : cell.text}
      </span>
      {clear && <span className="text-[10px] text-ink/25">✓</span>}
    </span>
  );
  if (cell.eventId) {
    return (
      <button type="button" title={cell.title} onClick={() => onOpen(cell.eventId)}
        className="w-full text-left hover:opacity-80 transition-opacity">{body}</button>
    );
  }
  return <span title={cell.title} className="block">{body}</span>;
}

function SiteMatrix({ contexts, onOpen }) {
  const rows = useMemo(
    () => contexts.slice().sort((a, b) => {
      const rank = { alert: 2, watch: 1, clear: 0 };
      return rank[b.worst] - rank[a.worst];
    }),
    [contexts],
  );
  const counts = useMemo(() => {
    const c = { alert: 0, watch: 0, clear: 0 };
    for (const r of rows) c[r.worst] += 1;
    return c;
  }, [rows]);

  return (
    <SectionCard
      title="Site security matrix"
      subtitle="Every office carried across all eight layers to one status — geopolitics · cyber · market · hazards · weather · holiday · festival · derived road traffic. A quiet layer reads clear ✓, never blank."
      right={
        <div className="flex items-center gap-2 flex-shrink-0">
          {counts.alert > 0 && <Pill label={`${counts.alert} alert`} color="#B4462F" />}
          {counts.watch > 0 && <Pill label={`${counts.watch} watch`} color="#C08A2E" />}
          <Pill label={`${counts.clear} clear`} color="#4E9A5A" />
        </div>
      }
    >
      {contexts.length === 0 ? (
        <EmptyNote text="No offices in this customer config." />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="text-[9px] font-bold uppercase tracking-widest text-ink/40 border-b border-ink/8">
                <th className="px-4 py-2 sticky left-0 bg-paper z-10">Office</th>
                <th className="px-3 py-2">Status</th>
                {LAYER_KEYS.map((k) => <th key={k} className="px-2.5 py-2">{LAYER_LABELS[k]}</th>)}
              </tr>
            </thead>
            <tbody>
              {rows.map(({ office, layers, worst }) => (
                <tr key={office.id} className="border-b border-ink/6 hover:bg-ink/[0.02]">
                  <td className="px-4 py-2.5 sticky left-0 bg-paper z-10">
                    <div className="text-[12px] font-medium text-ink whitespace-nowrap">{office.name}</div>
                    <div className="text-[10px] text-ink/40 whitespace-nowrap">{office.city} · {office.country}</div>
                  </td>
                  <td className="px-3 py-2.5"><Pill label={LEVEL_WORD[worst]} color={levelColor(worst)} /></td>
                  {LAYER_KEYS.map((k) => (
                    <td key={k} className="px-2.5 py-2.5 max-w-[130px]">
                      <LayerCell cell={cellFor(k, layers[k])} onOpen={onOpen} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="px-4 py-2.5 text-[9px] text-ink/35 border-t border-ink/8 leading-relaxed">
        Incidents (geopolitics/cyber/market/hazards/weather) are the nearest live graph event in range, scored against your risk appetite.
        Holiday &amp; festival layers come from the public-holiday calendar and the curated gathering list. Traffic is <em>derived</em> — road
        disruption implied by festivals, holidays, severe weather and major incidents near the site (bounded, never a paid live feed here).
      </p>
    </SectionCard>
  );
}

// ── c. Real estate & asset exposure ──────────────────────────────────────────
function AssetExposure({ data, appetite, onOpen, assets }) {
  const { loading, events } = data;
  const factor = 0.5 + appetite / 100;
  const rows = useMemo(() => {
    const geoEvents = events.filter((e) => e.geo_centroid_lat != null && e.geo_centroid_lng != null);
    return assets.map((a) => {
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
  }, [events, factor, assets]);

  return (
    <SectionCard title="Real estate & asset exposure"
      subtitle={`${assets.length} sites checked against every geolocated live event within 400 km.`}>
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
function TravelSecurity({ data, appetite, onOpen, trips }) {
  const { loading, events } = data;
  const factor = 0.5 + appetite / 100;
  const rows = useMemo(() => {
    const geoEvents = events.filter((e) => e.geo_centroid_lat != null && e.geo_centroid_lng != null);
    return trips.map((t) => {
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
  }, [events, factor, trips]);

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
        // NATO Admiralty grade attached server-side to the view-scoped
        // corroboration map — the digit rises with the very convergence shown here.
        reliability: c.reliability || null,
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
              <div className="text-[9px] font-mono uppercase tracking-wider flex items-center gap-1.5" style={{ color: "rgba(240,237,232,0.4)" }}>
                {row.count} sources · <span style={{ color: "#C08A2E" }}>fusion {Math.round(row.index * 100)}%</span>
                {row.reliability?.grade && (
                  <>
                    <span style={{ color: "rgba(240,237,232,0.25)" }}>·</span>
                    <AdmiraltyGrade grade={row.reliability} />
                  </>
                )}
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
              {(turn.trace || turn.tool_trace || []).map((t, i) => (
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

// ── i. Signal deck — TweetDeck-style live board over the same event graph ──────
function SignalDeck({ onOpen }) {
  // The full DeckView is a flex-1 board; give it a bounded height so it lives
  // inside the scrolling dashboard instead of taking the whole viewport. Clicking
  // a card opens the event (no in-deck overlay), matching every other panel here.
  return (
    <SectionCard
      title="Signal deck"
      subtitle="The live event graph as an operator board — independently-scrolling columns by status, category and INT discipline. Add or drop columns; click any signal to open it."
      right={<Pill label="Live" color="#C80028" />}
    >
      <div className="flex flex-col" style={{ height: 600 }}>
        <DeckView selectedEventId={null} onEventSelect={onOpen} onEventClose={() => {}} />
      </div>
    </SectionCard>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────
export default function CustomerDeck({ config }) {
  const navigate = useNavigate();
  const { isDark, toggle } = useTheme();

  const branding = config.branding || {};
  const accent = branding.accent || "#C80028";
  const assets = config.assets || [];
  const trips = config.flags?.travel === false ? [] : (config.trips || []);
  const regions = config.regions || [];
  const flags = config.flags || {};
  const countryCodes = config.countryCodes || {};

  const data = useLiveData(countryCodes);

  // Per-tenant appetite key so two customers on one browser don't share a slider.
  const appetiteKey = `deck_risk_appetite_${config.id || "default"}`;
  const [appetite, setAppetiteState] = useState(() => {
    // Number(null) is 0, which passes the range check — an unset key must fall
    // through to the 50 default, not silently pin the slider to most-cautious.
    const raw = localStorage.getItem(appetiteKey);
    const v = raw === null ? NaN : Number(raw);
    return Number.isFinite(v) && v >= 0 && v <= 100 ? v : 50;
  });
  const setAppetite = (v) => { setAppetiteState(v); localStorage.setItem(appetiteKey, String(v)); };

  const onOpen = (id) => navigate(`/event/${id}`);
  const fusionCount = useMemo(
    () => Object.values(data.corrob).filter((c) => (c.disciplines?.length || 0) >= 2).length,
    [data.corrob],
  );

  // One per-office rollup snapshot, shared by the world map and the site matrix so
  // the two surfaces always agree on a site's status.
  const contexts = useMemo(() => {
    const ctx = {
      events: data.events,
      festivals: config.festivals || [],
      holidaysByCode: data.holidaysByCode || {},
      countryCodes,
      curatedHolidays: config.curatedHolidays || {},
      appetite,
    };
    return assets.map((a) => officeContext(a, ctx));
  }, [data.events, data.holidaysByCode, config, countryCodes, assets, appetite]);

  return (
    <div className="min-h-screen bg-paper flex flex-col">
      <header style={{ backgroundColor: "#111111" }} className="sticky top-0 z-40">
        <div className="max-w-[1400px] mx-auto px-4 md:px-6 py-2.5 flex items-center justify-between">
          <div>
            <h1 className="font-display text-[1.5rem] md:text-[2rem] tracking-tighter leading-none" style={{ color: "#F0EDE8" }}>
              {branding.name} <span style={{ color: accent }}>{branding.accentTitle}</span>
            </h1>
            {branding.tagline && (
              <p className="text-[7px] md:text-[8px] tracking-[0.35em] uppercase mt-0.5 hidden md:block" style={{ color: "rgba(240,237,232,0.3)" }}>
                {branding.tagline}
              </p>
            )}
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
          <ExecBrief data={data} fusionCount={fusionCount} assets={assets} trips={trips} />
          <FusionStrip data={data} onOpen={onOpen} />
          <WorldPresence data={data} appetite={appetite} onOpen={onOpen} assets={assets} trips={trips} contexts={contexts} />
          <SiteMatrix contexts={contexts} onOpen={onOpen} />
          <CountryRisk data={data} appetite={appetite} setAppetite={setAppetite} regions={regions} />
          <AssetExposure data={data} appetite={appetite} onOpen={onOpen} assets={assets} />
          {flags.travel !== false && (
            <TravelSecurity data={data} appetite={appetite} onOpen={onOpen} trips={trips} />
          )}
          <SignalDeck onOpen={onOpen} />
          <div className="grid gap-5 lg:grid-cols-2">
            {flags.askAnalyst !== false && <AskAnalyst />}
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
