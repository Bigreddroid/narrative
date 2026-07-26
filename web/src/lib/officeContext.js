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

// Per-layer search radius (km). Gatherings and weather fronts are local; incidents,
// market and cyber signals radiate wider before they stop being "near this office".
export const RADII = { weather: 150, hazard: 250, incident: 300, festival: 70, market: 450, cyber: 700 };

export const LAYER_KEYS = ["geopolitics", "cyber", "market", "hazards", "weather", "holidays", "festivals", "traffic"];
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

// Nearest (highest-importance) geolocated event of one layer within a radius.
function nearestFor(office, geoEvents, layer, radiusKm) {
  let best = null;
  for (const e of geoEvents) {
    if (layerOf(e) !== layer) continue;
    const km = haversineKm(office.lat, office.lng, e.geo_centroid_lat, e.geo_centroid_lng);
    if (km <= radiusKm && (!best || (e.global_importance_score || 0) > best.imp))
      best = { event: e, km, imp: e.global_importance_score || 0 };
  }
  return best;
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
function festivalStatus(fests) {
  const active = fests.find((f) => f.active);
  const soon = fests.find((f) => f.soon);
  return { level: active ? "alert" : soon ? "watch" : "clear", active: active || null, soon: soon || null, all: fests };
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

  const geopolitics = nearestFor(office, geoEvents, "geopolitics", RADII.incident);
  const cyber = nearestFor(office, geoEvents, "cyber", RADII.cyber);
  const market = nearestFor(office, geoEvents, "market", RADII.market);
  const hazard = nearestFor(office, geoEvents, "hazard", RADII.hazard);
  const weather = nearestFor(office, geoEvents, "weather", RADII.weather);
  const fests = festivalsNear(office, festivals, today);
  const hols = holidaysFor(office, holidaysByCode, countryCodes, curatedHolidays, today);
  const traffic = deriveTraffic(
    { festivals: fests, holidays: hols, weatherBest: weather, incidentBest: geopolitics || hazard },
    factor,
  );

  const layers = {
    geopolitics: statusFromSignal(geopolitics, factor),
    cyber: statusFromSignal(cyber, factor),
    market: statusFromSignal(market, factor),
    hazards: statusFromSignal(hazard, factor),
    weather: statusFromSignal(weather, factor),
    holidays: holidayStatus(hols),
    festivals: festivalStatus(fests),
    traffic,
  };
  const worst = LAYER_KEYS.reduce((w, k) => (LEVEL_RANK[layers[k].level] > LEVEL_RANK[w] ? layers[k].level : w), "clear");
  return { office, layers, worst, holidays: hols, festivals: fests };
}

// The single highest-importance incident driving a site — what the map diamond and
// the site row should open when clicked. Ignores the context-only layers.
export function topSignal(context) {
  let best = null;
  for (const k of ["geopolitics", "cyber", "market", "hazards", "weather"]) {
    const b = context.layers[k].best;
    if (b && (!best || b.imp > best.imp)) best = b;
  }
  return best;
}

export { LEVEL_RANK };
