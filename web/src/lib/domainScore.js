// ─────────────────────────────────────────────────────────────────────────────
// domainScore — a 0–5 score per risk domain, per site and per country.
//
// The incumbent everyone rates most highly publishes exactly this shape: a number
// from 0 to 5 for each of several domains, rolled to an overall band. It is genuinely
// legible to an executive, which is why we match the shape.
//
// The difference is what sits underneath. Theirs is an analyst's judgement with no
// visible derivation. Ours is computed from the same importance/appetite ladder the
// rest of the board uses (officeContext.statusFromSignal), so every number drills
// straight through to the signal that produced it — and a quiet domain scores 0
// because nothing was found, not because nobody looked.
//
// One model, not a second opinion: the SAME layer rollup drives the matrix, the
// map, the decision queue and these scores. They cannot disagree.
//
// Pure + unit-tested (domainScore.test.mjs).
// ─────────────────────────────────────────────────────────────────────────────
import { LAYER_KEYS, LAYER_LABELS } from "./officeContext.js";
import { BANDS, bandFor, scoreFrom } from "./severity.js";

// The band scale lives in severity.js — ONE scale for the whole product, and each
// band carries the consequence sentence that defines it. Re-exported here so the
// existing callers of domainScore keep working unchanged.
export { BANDS, bandFor };

// Importance (0–100) → 0–5, re-baselined by organisational tolerance so one setting
// moves these scores exactly as it moves every other number on the board. A cautious
// tolerance (factor < 1) reads the same signal higher, which is the point of it.
export const scoreFromImportance = scoreFrom;

// Context layers → per-domain scores. Context-only layers (holiday, festival,
// derived traffic) score from their own state rather than an importance, because
// they are conditions and have no incident importance to read.
export function domainScores(context, opts = {}) {
  const { appetite = 50 } = opts;
  const factor = 0.5 + appetite / 100;
  const out = {};

  for (const key of LAYER_KEYS) {
    const layer = context?.layers?.[key];
    if (!layer) { out[key] = { key, label: LAYER_LABELS[key], score: 0, level: "clear", evidence: null }; continue; }

    let score;
    if (key === "traffic") {
      // Derived road disruption is already a bounded percentage.
      score = Math.round(Math.min(5, (layer.pct || 0) / 20) * 10) / 10;
    } else if (key === "holidays" || key === "festivals") {
      score = layer.level === "alert" ? 3.0 : layer.level === "watch" ? 1.5 : 0;
    } else {
      score = scoreFromImportance(layer.imp || 0, factor);
    }

    out[key] = {
      key,
      label: LAYER_LABELS[key],
      score,
      level: layer.level,
      scope: layer.scope || "site",
      evidence: layer.best?.event
        ? { id: layer.best.event.id, title: layer.best.event.canonical_title, km: layer.best.km }
        : null,
    };
  }
  return out;
}

// Overall = the worst domain, not the average. Averaging is how a site with one
// severe problem and seven quiet layers reads "Moderate" and gets ignored.
//
// ORGANISATION-SCOPED DOMAINS ARE EXCLUDED. Cyber resolves once for the whole estate
// and is identical at every site, so letting it set a site's overall marked all 214
// sites "Extreme" off one campaign and made the register useless — the same blanket
// overclaim we removed from `worst` in officeContext (SITE_LAYER_KEYS). Cyber is
// still scored, still displayed, and still carried as an organisation-wide posture;
// it just cannot be attributed to a building. Pass { includeOrgScope: true } for a
// genuinely organisation-level rollup.
export function overallScore(scores, opts = {}) {
  const { includeOrgScope = false } = opts;
  const all = Object.values(scores || {});
  const values = includeOrgScope ? all : all.filter((d) => d.scope !== "organisation");
  if (!values.length) return { score: 0, band: bandFor(0), driver: null };
  const top = values.reduce((a, b) => (b.score > a.score ? b : a));
  return { score: top.score, band: bandFor(top.score), driver: top.score > 0 ? top : null };
}

// Country profile: every domain's worst score across that country's sites, so a
// country page reflects its most exposed site rather than a diluted mean.
export function countryProfile(contexts = [], opts = {}) {
  const byCountry = new Map();
  for (const c of contexts) {
    const country = c.office?.country;
    if (!country) continue;
    if (!byCountry.has(country)) {
      byCountry.set(country, { country, sites: 0, people: 0, domains: {}, worstSite: null });
    }
    const row = byCountry.get(country);
    row.sites += 1;
    row.people += Number(c.office.headcount) || 0;

    const scores = domainScores(c, opts);
    for (const [key, d] of Object.entries(scores)) {
      if (!row.domains[key] || d.score > row.domains[key].score) row.domains[key] = { ...d };
    }
    const overall = overallScore(scores);
    if (!row.worstSite || overall.score > row.worstSite.score) {
      row.worstSite = { office: c.office, score: overall.score, driver: overall.driver };
    }
  }
  return [...byCountry.values()].map((row) => {
    const overall = overallScore(row.domains);
    return { ...row, overall: overall.score, band: overall.band, driver: overall.driver };
  }).sort((a, b) => b.overall - a.overall || b.people - a.people);
}
