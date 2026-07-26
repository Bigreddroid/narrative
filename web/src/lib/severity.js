// ─────────────────────────────────────────────────────────────────────────────
// severity — what a signal MEANS, not how big its number is.
//
// The board used to say: importance >= 70 x appetite factor => "alert". That is a
// statement about our model. An executive cannot act on it. Every serious vendor in
// this category instead defines severity BY CONSEQUENCE — "localised, containable
// with timely measures" vs "impact spans regions and persists" — and that is the
// single biggest legibility gap we had.
//
// So this module is the one place that turns a computed number into a sentence about
// the world. Four independent reads travel with every signal:
//
//   1. SEVERITY   — five bands, each defined by the consequence it implies
//   2. ALERT TYPE — informative (awareness) vs intelligence (assessed, decidable)
//   3. VALIDITY   — effective_from -> effective_to; alerts expire instead of
//                   accumulating forever
//   4. TWO-LEVEL  — the country's standing level shown beside this incident's level
//
// These are ORTHOGONAL. A signal can be Moderate + Intelligence + expiring, and each
// axis answers a different question. Collapsing them into one number is what makes a
// console unreadable at 400 alerts.
//
// This module is the single source of the band scale — domainScore imports BANDS
// from here so a "3.4" means "High" everywhere, with the same sentence attached.
//
// Pure + unit-tested (severity.test.mjs).
// ─────────────────────────────────────────────────────────────────────────────
import { extentKm } from "./officeContext.js";
import { haversineKm } from "./geoAssoc.js";

// ── 1 · Severity: five bands, defined by consequence ─────────────────────────
// `min` is the 0-5 score floor. `consequence` is the operative definition — it is
// what the band MEANS, and it is rendered to the user, not kept as a code comment.
// Colours are contrast-checked against the #050505 command surface; never used
// without the label beside them.
export const SEVERITY = [
  {
    key: "minimal", label: "Minimal", index: 0, min: 0, color: "#7FA88C",
    consequence: "No operational effect. Logged so the absence of impact is on the record.",
  },
  {
    key: "low", label: "Low", index: 1, min: 1, color: "#C9CE58",
    consequence: "Noticeable, absorbed by normal routine. No change to travel, staffing or site access.",
  },
  {
    key: "moderate", label: "Moderate", index: 2, min: 2, color: "#E0A93C",
    consequence: "Localised and containable with timely measures. Commute, access or one site's routine is affected for hours to days.",
  },
  {
    key: "high", label: "High", index: 3, min: 3, color: "#FF8A5C",
    consequence: "Disruption holds across a city or region for days. Injury or damage is credible; travel and site access should be reconsidered now.",
  },
  {
    key: "extreme", label: "Extreme", index: 4, min: 4, color: "#FF5C43",
    consequence: "Impact spans regions and persists. Risk to life and property is severe; assume travel in and out of the area stops for an extended period.",
  },
];

export const SEVERITY_BY_KEY = Object.fromEntries(SEVERITY.map((s) => [s.key, s]));

// Descending order for `find`-style lookup. Exported as BANDS so domainScore and the
// deck read one scale — a change here moves every surface at once, by construction.
export const BANDS = [...SEVERITY].sort((a, b) => b.min - a.min);

export function bandFor(score) {
  const n = Number(score);
  if (!Number.isFinite(n)) return SEVERITY_BY_KEY.minimal;
  return BANDS.find((b) => n >= b.min) || SEVERITY_BY_KEY.minimal;
}

// Importance (0-100) -> 0-5, re-baselined by organisational tolerance. Same ladder
// the rest of the deck uses, so one tolerance setting moves every number together.
export function scoreFrom(importance, factor = 1) {
  const imp = Math.max(0, Math.min(100, Number(importance) || 0));
  const f = Number(factor) > 0 ? Number(factor) : 1;
  const scaled = (imp / f) / 100 * 5;
  return Math.round(Math.max(0, Math.min(5, scaled)) * 10) / 10;
}

// The three legacy statuses the map and matrix draw with. Five bands are right for
// reading; three colours are right for a 214-dot globe, so we map rather than keep
// two scales: Extreme/High -> alert, Moderate -> watch, Low/Minimal -> clear.
export const LEVEL_OF_BAND = {
  extreme: "alert", high: "alert", moderate: "watch", low: "clear", minimal: "clear",
};
export const levelOfBand = (key) => LEVEL_OF_BAND[key] || "clear";

// ── 2 · Alert type: awareness vs decision-support ────────────────────────────
// Orthogonal to severity and genuinely different products. Informative answers
// "what happened"; Intelligence answers "what it means for you, and what to do".
//
// We do NOT let an analyst tick a box: the type is EARNED. A signal is Intelligence
// only when it carries a site-specific consequence or a recommended action AND is
// corroborated by at least two sources. Everything else is honestly Informative.
// This is why our Intelligence count is small — the same shape the incumbents show
// (a low-single-digit percentage of the total), arrived at by rule instead of labour.
export const ALERT_TYPES = {
  informative: {
    key: "informative", label: "Informative",
    definition: "Situational awareness. What happened, where, and how well sourced — delivered as soon as it is corroborated.",
  },
  intelligence: {
    key: "intelligence", label: "Intelligence",
    definition: "Assessed for this organisation: what it means for a named site or traveller, and the action it implies. Requires two-source corroboration.",
  },
};

export const MIN_SOURCES_FOR_INTELLIGENCE = 2;

export function alertTypeOf(event) {
  const assessed = Boolean(
    (event?.consequence_for_site && String(event.consequence_for_site).trim()) ||
    (event?.recommended_action && String(event.recommended_action).trim()),
  );
  const corroborated = (Number(event?.source_count) || 0) >= MIN_SOURCES_FOR_INTELLIGENCE;
  return assessed && corroborated ? ALERT_TYPES.intelligence : ALERT_TYPES.informative;
}

// ── 3 · Validity: alerts expire ──────────────────────────────────────────────
// Ours previously persisted forever, so a board slowly filled with resolved weather
// and month-old protests — which is precisely how a feed loses an executive's trust.
//
// An event's own effective_from/effective_to win when the API supplies them (no such
// field today; this is forward-compatible). Otherwise the window is derived from the
// category, because a thunderstorm and a border dispute do not decay at the same rate.
// Covers BOTH engine vocabularies (backend/taxonomy.py: 13 feed CATEGORIES + 7
// LLM_CATEGORIES). Getting this wrong in either direction is a real defect: too
// short and live sanctions drop off the board while still in force; too long and
// resolved weather lingers for a month.
export const VALIDITY_DAYS = {
  storm: 2, unrest: 3, security: 3, space: 3,
  wildfire: 7, flood: 7, disaster: 7,
  volcano: 14, conflict: 14, policy: 14, technology: 14, cyber: 14, disinfo: 14,
  health: 21,
  climate: 30, geopolitics: 30, economics: 30, economy: 30, market: 30,
  drought: 60,
  sanction: 180,   // sanctions stay in force for months — a 7-day window would expire live ones
};
export const VALIDITY_DEFAULT_DAYS = 7;
const DAY_MS = 86_400_000;

export function validityDays(event) {
  return VALIDITY_DAYS[String(event?.category || "").toLowerCase()] ?? VALIDITY_DEFAULT_DAYS;
}

const parseMs = (v) => {
  if (v == null) return null;
  const t = v instanceof Date ? v.getTime() : Date.parse(v);
  return Number.isNaN(t) ? null : t;
};

// -> { state, from, to, days, remainingHours, pctElapsed }
// state: "active" | "expiring" | "expired" | "unknown"
// "expiring" = the last 25% of the window, or under 24h, whichever bites first —
// the point at which an item should be re-confirmed rather than silently trusted.
export function validityOf(event, now = new Date(), opts = {}) {
  const { expiringFraction = 0.25, expiringHours = 24 } = opts;
  const nowMs = now instanceof Date ? now.getTime() : Number(now);
  const from = parseMs(event?.effective_from) ?? parseMs(event?.first_detected_at) ?? parseMs(event?.created_at);
  if (from == null) return { state: "unknown", from: null, to: null, days: null, remainingHours: null, pctElapsed: null };

  const days = validityDays(event);
  const to = parseMs(event?.effective_to) ?? from + days * DAY_MS;
  const span = Math.max(to - from, 1);
  const remainingMs = to - nowMs;
  const pctElapsed = Math.max(0, Math.min(1, (nowMs - from) / span));

  let state;
  if (remainingMs <= 0) state = "expired";
  else if (remainingMs <= Math.min(span * expiringFraction, expiringHours * 3_600_000)) state = "expiring";
  else state = "active";

  return {
    state,
    from: new Date(from),
    to: new Date(to),
    days,
    remainingHours: Math.round(remainingMs / 3_600_000),
    pctElapsed: Math.round(pctElapsed * 100) / 100,
  };
}

export const isExpired = (event, now = new Date()) => validityOf(event, now).state === "expired";

// Drop expired signals before anything counts them. Callers that WANT the expired
// set (the "everything we checked" ledger) simply don't call this.
export function activeOnly(events = [], now = new Date()) {
  return events.filter((e) => !isExpired(e, now));
}

// ── 4 · Two-level risk: country standing beside incident ─────────────────────
// A Moderate incident in a Minimal-risk country and the same incident in an Extreme
// one are different decisions. The category shows both; we had only the incident.
// `gap` is the interesting number: a big positive gap means this incident is
// out of character for where it happened, which is exactly when to look.
export function twoLevelRisk(countryScore, incidentScore) {
  const country = bandFor(countryScore);
  const incident = bandFor(incidentScore);
  return {
    country, incident,
    gap: incident.index - country.index,
    anomalous: incident.index - country.index >= 2,
  };
}

// ── Assets affected ──────────────────────────────────────────────────────────
// Signal -> asset attribution at the item level: which of OUR sites this specific
// event actually reaches, judged against the event's own spatial extent. Returns
// the site list, not just a count, so "Assets affected: 28" is always clickable
// through to the 28. Non-geolocated events return an empty set rather than a guess.
export function assetsAffected(event, contexts = []) {
  const lat = event?.geo_centroid_lat, lng = event?.geo_centroid_lng;
  if (lat == null || lng == null) return { count: 0, people: 0, sites: [] };
  const reach = extentKm(event);
  const sites = [];
  let people = 0;
  for (const c of contexts) {
    const o = c?.office || c;
    if (o?.lat == null || o?.lng == null) continue;
    const km = haversineKm(lng, lat, o.lng, o.lat);
    if (km <= reach) {
      sites.push({ office: o, km: Math.round(km) });
      people += Number(o.headcount) || 0;
    }
  }
  sites.sort((a, b) => a.km - b.km);
  return { count: sites.length, people, sites };
}

// ── The whole classification for one signal, in one call ─────────────────────
// Everything a row needs to render itself honestly.
export function classify(event, opts = {}) {
  const { factor = 1, now = new Date(), countryScore = null, contexts = null } = opts;
  const score = scoreFrom(event?.global_importance_score, factor);
  const band = bandFor(score);
  return {
    score,
    band,
    level: levelOfBand(band.key),
    consequence: band.consequence,
    type: alertTypeOf(event),
    validity: validityOf(event, now),
    risk: countryScore == null ? null : twoLevelRisk(countryScore, score),
    assets: contexts ? assetsAffected(event, contexts) : null,
  };
}
