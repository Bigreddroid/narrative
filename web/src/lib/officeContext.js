// ─────────────────────────────────────────────────────────────────────────────
// officeContext — the per-site "no-gap" rollup that carries EVERY layer around a
// customer office to a single status, computed client-side from data already on
// the deck: the live event graph (GET /events/), the customer's curated festivals,
// and public holidays (GET /context/calendar + curated supplement).
//
// Eight layers per office, each resolving to clear | watch | alert:
//   geopolitics · cyber · market · hazards · weather · holidays · festivals · traffic
// "traffic" is DERIVED (no paid Mapbox feed): festivals underway, a public holiday,
// severe weather and a major nearby incident each add saturating road "load", ported
// from the server engine's DISRUPTION_K / TAU_TRAFFIC (propagation.py) so the number
// is bounded and honest — a site's road disruption never reads a false 100%.
//
// Pure + unit-tested (officeContext.test.mjs). No network, no React — the deck calls
// officeContext(office, ctx) once per site and renders the result.
// ─────────────────────────────────────────────────────────────────────────────
import { haversineKm as _havKm } from "./geoAssoc.js";

// (lat,lng) adapter over the shared (lng,lat) great-circle core — one copy of the
// math app-wide (mirrors the adapter in CustomerDeck.jsx).
const haversineKm = (lat1, lng1, lat2, lng2) => _havKm(lng1, lat1, lng2, lat2);

// Derived-traffic saturation, ported from the server CPE (propagation.py
// DISRUPTION_K / TAU_TRAFFIC): combined road "load" near a site saturates to a
// bounded ceiling, so no single input can imply total gridlock.
export const DISRUPTION_K = 0.8;  // ceiling — derived traffic confidence tops out at 80%
const TAU_LOAD = 3.0;             // load units to reach ~63% of the ceiling

// Per-layer fallback ceilings (km). Retained for festivals and as documentation of
// the old flat model; incident layers now use a PER-EVENT extent (see EXTENT_KM).
export const RADII = { weather: 150, hazard: 250, incident: 300, festival: 70, market: 450, cyber: 700 };

// ── Per-event spatial extent ─────────────────────────────────────────────────
// One radius per LAYER was wrong: events inside a layer differ enormously in reach.
// A road-blocking protest is felt for ~25 km; a regional flood for ~150 km. Scoring
// both at 300 km made a CBD protest "affect" offices 290 km away and pushed a
// 214-site board to 55% alerting — the same severity inflation we exist to beat.
//
// An event's own `impact_radius_km` wins when the API supplies one (no such field
// today — this is forward-compatible); otherwise we fall back per category.
// Covers BOTH engine vocabularies — the 13 feed/OSINT CATEGORIES and the 7
// LLM_CATEGORIES in backend/taxonomy.py. The first version of this table was written
// against the sample fixture and silently defaulted the live feed's most common
// categories (wildfire, sanction, unrest, market — 48 of 100 events) to 50 km.
export const EXTENT_KM = {
  // ── Localised: felt within a city ──
  unrest: 25, security: 25, policy: 25,   // protest, closure, localised disorder
  conflict: 50,                            // armed incident — wider, still local
  wildfire: 75,                            // fire front plus immediate smoke plume
  // ── Regional ──
  geopolitics: 100, technology: 100, disinfo: 100, space: 100,
  volcano: 150,                            // ashfall and exclusion zones reach far
  disaster: 150, storm: 150, flood: 150,   // weather fronts are genuinely wide
  climate: 200, health: 200,
  // ── Systemic: economic and legal reach, not a blast radius ──
  economics: 300, economy: 300, market: 300, drought: 300,
  sanction: 500,                           // national in scope; the effect is legal, not spatial
  cyber: 100,                              // not distance-scored in practice (org-scoped) — see orgCyberStatus
};
export const EXTENT_DEFAULT = 50;

export function extentKm(event) {
  const explicit = Number(event?.impact_radius_km);
  if (Number.isFinite(explicit) && explicit > 0) return explicit;
  return EXTENT_KM[String(event?.category || "").toLowerCase()] ?? EXTENT_DEFAULT;
}

export const LAYER_KEYS = ["geopolitics", "cyber", "market", "hazards", "weather", "holidays", "festivals", "traffic"];

// Layers that describe THIS SITE, and so may drive its rolled-up status. Cyber is
// excluded: it is organisation-scoped, identical everywhere, and letting it roll up
// would mark all 214 sites "alert" for a campaign that is not attributable to any one
// of them — replacing a geographic overclaim with a blanket one. It still appears in
// `layers` for display, and surfaces separately as an organisation-wide posture.
export const SITE_LAYER_KEYS = LAYER_KEYS.filter((k) => k !== "cyber");
export const LAYER_LABELS = {
  geopolitics: "Geopolitics", cyber: "Cyber", market: "Market", hazards: "Hazards",
  weather: "Weather", holidays: "Holiday", festivals: "Festival", traffic: "Traffic",
};
const LEVEL_COLOR = { clear: "#4E9A5A", watch: "#C08A2E", alert: "#B4462F" };
export const levelColor = (level) => LEVEL_COLOR[level] || LEVEL_COLOR.clear;
const LEVEL_RANK = { clear: 0, watch: 1, alert: 2 };

// Event category / INT discipline → office layer. First matching rule wins; a
// geolocated event we can't classify still counts as regional geopolitics rather
// than vanishing from the site's picture.
export function layerOf(e) {
  const c = String(e.category || "").toLowerCase();
  const d = String(e.int_discipline || "").toUpperCase();
  if (c === "cyber" || d === "CYBINT") return "cyber";
  if (c === "economics" || c === "economy" || d === "FININT") return "market";
  if (c === "storm") return "weather";
  if (["climate", "health", "disaster"].includes(c)) return "hazard";
  return "geopolitics";
}

// ── Proximity attenuation ────────────────────────────────────────────────────
// Being inside an event's extent was previously binary: a site 24 km from a 25 km
// protest scored exactly the same as one 1 km away, because the raw importance was
// carried through untouched. That is not how consequence works, and it had a visible
// cost — with the live feed returning only the top-100 by importance (every event
// scoring 80-95), the five-band scale collapsed to two populated bands: 44 Extreme,
// 170 Minimal, and nothing at all in High, Moderate or Low.
//
// So importance decays with distance INSIDE the extent:
//
//   attenuated = imp × (FLOOR + (1 − FLOOR) × (1 − r)^FALLOFF),  r = km / extent
//
// FLOOR is deliberately non-zero. Reaching the edge of an event's extent does not
// mean "unaffected" — the extent is precisely the distance at which we stop counting
// it, so the boundary should hand over a real-but-small residue rather than a zero
// that would erase a site we just decided was in range.
//
// FALLOFF > 1 keeps the near field close to full strength and drops away faster
// further out, which matches how a cordon, a flood plain or a road closure actually
// behaves: little relief until you are well clear of it.
//
//   90-importance event, 25 km extent →  at 0 km: 90 · at 12 km: 46 · at 25 km: 23
//
// Non-geolocated and organisation-scoped layers (cyber) never come through here;
// distance is meaningless for them and pretending otherwise was a separate bug.
// CALIBRATION NOTE. These began at 0.25 / 1.5, which decayed a 90-importance storm
// 100 km out (150 km extent) to 35 and reclassified it from alert to CLEAR. That is
// self-contradictory: storms carry a 150 km extent precisely because large weather
// systems are felt that far, so the attenuation curve must not overturn the judgement
// the extent encodes. An existing assertion — "a weather front 100 km away still
// reaches the site" — caught it. Softened so the far field lands in watch rather than
// falling off the board, while the near field keeps its full weight.
export const ATTENUATION_FLOOR = 0.35;
export const ATTENUATION_FALLOFF = 1.3;

export function attenuate(importance, km, extent) {
  const imp = Number(importance) || 0;
  const d = Number(km);
  const ext = Number(extent);
  // No distance, no extent, or a nonsensical extent → carry importance unchanged
  // rather than inventing a discount.
  if (!Number.isFinite(d) || !Number.isFinite(ext) || ext <= 0) return imp;
  const r = Math.max(0, Math.min(1, d / ext));
  return imp * (ATTENUATION_FLOOR + (1 - ATTENUATION_FLOOR) * (1 - r) ** ATTENUATION_FALLOFF);
}

// Strongest geolocated event of one layer that actually reaches this office — judged
// against each EVENT's own extent, and ranked by ATTENUATED importance so a severe
// event at the edge of its reach no longer outranks a nearby one that will actually
// be felt. `raw` is retained so the UI can always show what the underlying event
// scored before distance was applied.
function nearestFor(office, geoEvents, layer) {
  let best = null;
  for (const e of geoEvents) {
    if (layerOf(e) !== layer) continue;
    const km = haversineKm(office.lat, office.lng, e.geo_centroid_lat, e.geo_centroid_lng);
    const ext = extentKm(e);
    if (km > ext) continue;
    const raw = e.global_importance_score || 0;
    const imp = attenuate(raw, km, ext);
    if (!best || imp > best.imp) best = { event: e, km, imp, raw, extent: ext };
  }
  return best;
}

// ── Cyber is not a distance problem ──────────────────────────────────────────
// A credential-stuffing campaign against "IT services suppliers" either targets the
// organisation or it does not; how far the reporting centroid sits from a given
// building says nothing useful. Scored by proximity at the old 700 km ceiling, one
// report lit up 56 sites across three cities and implied 238,493 people were exposed.
//
// So cyber resolves ONCE, organisation-wide, from the strongest cyber signal anywhere,
// and every office carries the same level. `scope: "organisation"` lets callers label
// it honestly and — critically — stops them attributing a headcount we cannot know.
function orgCyberStatus(geoEvents, factor) {
  let best = null;
  for (const e of geoEvents) {
    if (layerOf(e) !== "cyber") continue;
    const imp = e.global_importance_score || 0;
    if (!best || imp > best.imp) best = { event: e, km: null, imp };
  }
  if (!best) return { level: "clear", best: null, imp: 0, scope: "organisation" };
  const level = best.imp >= 70 * factor ? "alert" : best.imp >= 40 * factor ? "watch" : "clear";
  return { level, best, imp: Math.round(best.imp), scope: "organisation" };
}

// Importance + risk-appetite → a layer status. Mirrors the 70/40 · factor ladder
// used by every other panel so one appetite slider re-baselines the whole deck.
function statusFromSignal(best, factor) {
  if (!best) return { level: "clear", best: null, imp: 0 };
  const imp = best.imp;
  const level = imp >= 70 * factor ? "alert" : imp >= 40 * factor ? "watch" : "clear";
  return { level, best, imp: Math.round(imp) };
}

const dayMs = 86_400_000;
const parseISO = (s) => { const t = Date.parse(s); return Number.isNaN(t) ? null : t; };
const daysBetween = (fromMs, toMs) => Math.floor((toMs - fromMs) / dayMs);

// Curated holidays carry no in_days; live ones (from /context/calendar) already do.
// Normalise both to { date, name, in_days } inside a forward window, soonest first.
export function upcomingHolidays(list, today, windowDays = 60) {
  const t0 = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime();
  const out = [];
  for (const h of list || []) {
    let inDays = Number.isFinite(h.in_days) ? h.in_days : null;
    if (inDays == null) {
      const hd = parseISO(h.date);
      if (hd == null) continue;
      inDays = daysBetween(t0, hd);
    }
    if (inDays >= 0 && inDays <= windowDays) out.push({ date: h.date, name: h.name, localName: h.localName, in_days: inDays });
  }
  // De-dupe a curated + live overlap on the same date, keeping the richer name.
  const byDate = new Map();
  for (const h of out) if (!byDate.has(h.date) || (h.localName && !byDate.get(h.date).localName)) byDate.set(h.date, h);
  return [...byDate.values()].sort((a, b) => a.in_days - b.in_days);
}

function holidaysFor(office, holidaysByCode, countryCodes, curated, today) {
  const code = countryCodes?.[office.country];
  if (!code) return [];
  return upcomingHolidays([...(holidaysByCode?.[code] || []), ...(curated?.[code] || [])], today);
}

// Festivals attached to this office (by explicit nearAssets, else proximity), each
// flagged active (window contains today) or soon (starts within two weeks).
function festivalsNear(office, festivals, today) {
  const t0 = today.getTime();
  return (festivals || []).filter((f) =>
    (f.nearAssets || []).includes(office.id) ||
    (f.lat != null && f.lng != null && haversineKm(office.lat, office.lng, f.lat, f.lng) <= RADII.festival),
  ).map((f) => {
    const s = parseISO(f.startISO), e = parseISO(f.endISO) ?? parseISO(f.startISO);
    const active = s != null && t0 >= s - dayMs && t0 <= (e ?? s) + dayMs;
    const startsIn = s != null ? daysBetween(t0, s) : null;
    return { ...f, active, soon: !active && startsIn != null && startsIn >= 0 && startsIn <= 14, startsIn };
  });
}

// DERIVED road disruption near a site. Each stressor adds saturating "load"; the
// bounded curve (DISRUPTION_K ceiling) keeps the % honest. Drivers explain the call.
export function deriveTraffic({ festivals, holidays, weatherBest, incidentBest }, factor) {
  const drivers = [];
  let load = 0;
  for (const f of festivals) {
    if (f.active) { load += 1.5; drivers.push({ kind: "festival", label: `${f.name} underway` }); }
    else if (f.soon) { load += 0.4; drivers.push({ kind: "festival", label: `${f.name} in ${f.startsIn}d` }); }
  }
  const holToday = holidays.find((h) => h.in_days === 0);
  const holSoon = holidays.find((h) => h.in_days > 0 && h.in_days <= 2);
  if (holToday) { load += 1.0; drivers.push({ kind: "holiday", label: `${holToday.name} — public holiday` }); }
  else if (holSoon) { load += 0.4; drivers.push({ kind: "holiday", label: `${holSoon.name} in ${holSoon.in_days}d` }); }
  if (weatherBest && weatherBest.imp >= 40 * factor) {
    load += 1.2; drivers.push({ kind: "weather", label: "severe weather nearby", id: weatherBest.event.id });
  }
  if (incidentBest && incidentBest.imp >= 60 * factor) {
    load += 1.0; drivers.push({ kind: "incident", label: incidentBest.event.canonical_title, id: incidentBest.event.id });
  }
  const pct = Math.round(100 * DISRUPTION_K * (1 - Math.exp(-load / TAU_LOAD)));
  const level = pct >= 40 ? "alert" : pct >= 18 ? "watch" : "clear";
  return { level, pct, load, drivers };
}

// Holidays/festivals are context, not incidents: a holiday today (or a festival
// underway) is a "watch"; imminent is a soft watch; otherwise clear.
function holidayStatus(hols) {
  const now = hols.find((h) => h.in_days === 0);
  const soon = hols.find((h) => h.in_days > 0 && h.in_days <= 3);
  return { level: now ? "watch" : "clear", next: hols[0] || null, today: now || null, soon: soon || null };
}
// A gathering we cannot size is capped at "watch". The live Wikidata set is mostly
// scheduled sport, and this function's alert-on-active rule was calibrated against the
// curated fixture ("Independence Day gatherings, Red Fort" — a genuine central-Delhi
// lockdown). Applying that rule to a regular-season fixture would mark every office
// near a stadium red on game day, which is the severity inflation this deck exists to
// beat. `routine` is set by whoever supplies the gathering (useRegister.toGatherings
// for the live feed); a curated entry that omits it still escalates as before.
function festivalStatus(fests) {
  const active = fests.find((f) => f.active);
  const soon = fests.find((f) => f.soon);
  const level = active ? (active.routine ? "watch" : "alert") : soon ? "watch" : "clear";
  return { level, active: active || null, soon: soon || null, all: fests };
}

// The full per-site rollup. `ctx` bundles the shared deck data so every office is
// scored against one snapshot.
export function officeContext(office, ctx = {}) {
  const {
    events = [], festivals = [], holidaysByCode = {}, countryCodes = {},
    curatedHolidays = {}, appetite = 50, today = new Date(),
  } = ctx;
  const factor = 0.5 + appetite / 100;
  const geoEvents = events.filter((e) => e.geo_centroid_lat != null && e.geo_centroid_lng != null);

  const geopolitics = nearestFor(office, geoEvents, "geopolitics");
  const market = nearestFor(office, geoEvents, "market");
  const hazard = nearestFor(office, geoEvents, "hazard");
  const weather = nearestFor(office, geoEvents, "weather");
  const cyber = orgCyberStatus(geoEvents, factor);   // organisation-scoped, not proximity
  const fests = festivalsNear(office, festivals, today);
  const hols = holidaysFor(office, holidaysByCode, countryCodes, curatedHolidays, today);
  const traffic = deriveTraffic(
    { festivals: fests, holidays: hols, weatherBest: weather, incidentBest: geopolitics || hazard },
    factor,
  );

  const layers = {
    geopolitics: statusFromSignal(geopolitics, factor),
    cyber,                                            // already resolved, org-scoped
    market: statusFromSignal(market, factor),
    hazards: statusFromSignal(hazard, factor),
    weather: statusFromSignal(weather, factor),
    holidays: holidayStatus(hols),
    festivals: festivalStatus(fests),
    traffic,
  };
  const worst = SITE_LAYER_KEYS.reduce((w, k) => (LEVEL_RANK[layers[k].level] > LEVEL_RANK[w] ? layers[k].level : w), "clear");
  return { office, layers, worst, holidays: hols, festivals: fests };
}

// The single highest-importance incident driving a site — what the map diamond and
// the site row should open when clicked. Ignores the context-only layers, and ignores
// CYBER: that layer is organisation-scoped and carries no distance, so it must never
// be drawn as a line to this building or counted as a site-proximate signal.
export function topSignal(context) {
  let best = null;
  for (const k of ["geopolitics", "market", "hazards", "weather"]) {
    const b = context.layers[k].best;
    if (b && (!best || b.imp > best.imp)) best = b;
  }
  return best;
}

export { LEVEL_RANK };
