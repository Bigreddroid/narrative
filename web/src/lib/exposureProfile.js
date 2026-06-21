// ─────────────────────────────────────────────────────────────────────────────
//  Exposure — client-safe display helpers (NO trade-secret constants).
//
//  Everything here operates on an ALREADY-COMPUTED exposure model (the output of
//  the server's CPE at /api/v1/exposure). It contains no engine parameters, so it
//  is safe to ship in the production bundle. The actual propagation engine and its
//  tuned constants live server-side (backend/consequence_engine/propagation.py)
//  and — for the offline demo only — in ./propagation.js, which is loaded lazily.
// ─────────────────────────────────────────────────────────────────────────────

// Canonical entity aliases — collapse common sector/commodity name variants so
// exposure aggregates instead of fragmenting. Display-only; mirrors the server.
export const ENTITY_ALIASES = {
  "shipping and logistics": "shipping",
  "logistics": "shipping",
  "maritime shipping": "shipping",
  "oil and gas": "energy",
  "fuel": "energy",
  "consumer prices": "consumer goods",
  "semiconductor supply": "semiconductors",
  "tech industry": "technology",
  "ai": "technology",
};

// Canonicalise an entity name: lowercase, normalise punctuation, apply aliases.
export function canonicalize(name) {
  const s = String(name || "")
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9 ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return ENTITY_ALIASES[s] || s;
}

/**
 * Exposure for a specific user profile — the personalized output.
 * Pure post-processing over a computed model; uses no engine constants.
 * @param {{sectors?: string[], regions?: string[]}} profile
 * @param {{sectors, regions}} model  output of the exposure engine (server or demo)
 * @returns {{score, drivers}}  blended exposure with attribution
 */
export function profileExposure(profile, model) {
  const wanted = new Set([...(profile.sectors || []), ...(profile.regions || [])].map(canonicalize));
  const matches = [...model.sectors, ...model.regions].filter((x) => wanted.has(x.key));
  if (!matches.length) return { score: 0, drivers: [] };
  // Profile exposure = the worst single exposure blended toward the mean (you
  // feel your most-exposed dimension most, but diversification dampens it).
  const max = Math.max(...matches.map((m) => m.score));
  const mean = matches.reduce((s, m) => s + m.score, 0) / matches.length;
  const score = Math.round(0.65 * max + 0.35 * mean);
  const drivers = matches.flatMap((m) => m.drivers)
    .reduce((acc, d) => { (acc[d.id] ||= { ...d, pct: 0 }).pct += d.pct; return acc; }, {});
  const top = Object.values(drivers).sort((a, b) => b.pct - a.pct).slice(0, 3);
  return { score, drivers: top };
}
