// ─────────────────────────────────────────────────────────────────────────────
//  Lens relevance — how much a single event matters to YOUR profile.
//
//  This is the client-side "does this event hit my lens?" scorer that ranks the
//  feed, tints the World heat layer, and flags Analyst context. It is NOT the CPE:
//  it does no propagation and carries no tuned engine constants — it's a plain
//  keyword/geo overlap between an event and the chosen lens. Safe to ship.
// ─────────────────────────────────────────────────────────────────────────────

import { canonicalize } from "./exposureProfile.js";

// Collapse a profile's sector/region names to a canonical, deduped token set.
function tokenSet(list) {
  const s = new Set();
  for (const item of list || []) {
    const c = canonicalize(item);
    if (c) s.add(c);
  }
  return s;
}

// Split a canonicalized phrase into words so "shipping and logistics" can match an
// event tagged just "shipping". One-and-two-char words are dropped as noise.
function words(phrase) {
  return canonicalize(phrase).split(" ").filter((w) => w.length > 2);
}

// Does `haystack` (already lowercased) contain the phrase, whole or word-wise?
function phraseHits(haystack, phrase) {
  const c = canonicalize(phrase);
  if (!c) return false;
  if (haystack.includes(c)) return true;
  const ws = words(phrase);
  return ws.length > 0 && ws.some((w) => haystack.includes(w));
}

/**
 * Score how relevant an event is to a profile lens, 0–100, with attribution.
 *
 * The three dimensions of a lens each contribute independently and additively
 * (capped at 100): SECTOR match (category/entities ↔ your sectors), GEO match
 * (event geography ↔ your regions/country), and ASSET match (your watched
 * suppliers/ports/firms named in the headline). An event that hits your sector
 * *and* sits on your route scores far higher than one that grazes a single axis.
 *
 * @param {object} event    normalized event (category, geography[], title, summary, entities?)
 * @param {{sectors,regions,assets}} profile
 * @returns {{score:number, reasons:string[]}}
 */
export function eventRelevance(event, profile) {
  if (!event || !profile) return { score: 0, reasons: [] };

  const reasons = [];
  let score = 0;

  // Text blob the event exposes for keyword matching.
  const text = [
    event.canonical_title, event.title,
    event.canonical_summary, event.summary,
    ...(event.affected_sectors || []),
    ...(event.entities || []).map((e) => (typeof e === "string" ? e : e?.name)),
  ].filter(Boolean).join(" ").toLowerCase();

  // Where the event is, as canonical tokens.
  const geo = (event.geography || event.geographic_relevance || []);
  const geoTokens = tokenSet(geo);
  const category = canonicalize(event.category || "");

  // ── Sectors: match your industries against the event's category + text ──────
  const sectorTokens = tokenSet(profile.sectors);
  for (const s of sectorTokens) {
    const catHit = category && (category === s || category.includes(s) || s.includes(category));
    if (catHit || phraseHits(text, s)) {
      score += catHit ? 34 : 22;
      reasons.push(`sector: ${s}`);
      break; // one sector hit is enough signal; avoid double-counting synonyms
    }
  }

  // ── Regions: match your routes/chokepoints/home against the event geography ─
  const regionTokens = tokenSet(profile.regions);
  let geoHit = false;
  for (const r of regionTokens) {
    const onGeo = [...geoTokens].some((g) => g === r || g.includes(r) || r.includes(g));
    if (onGeo || phraseHits(text, r)) {
      geoHit = true;
      reasons.push(`region: ${r}`);
      if (score < 100) score += onGeo ? 40 : 26;
      break;
    }
  }

  // ── Watched assets: a named supplier/port/firm in the headline is a direct hit ─
  for (const a of profile.assets || []) {
    if (phraseHits(text, a)) {
      score += 30;
      reasons.push(`asset: ${a}`);
      break;
    }
  }

  // Small nudge for how big the event is, so among equally-relevant hits the
  // more consequential one ranks first. Never enough to promote an off-lens event.
  const importance = event.importance_score ?? event.global_importance_score ?? 0;
  if (score > 0) score += Math.min(8, importance / 12.5);

  return { score: Math.min(100, Math.round(score)), reasons };
}

// Convenience: build a {eventId: score} map for the World heat layer.
export function relevanceScores(events, profile) {
  const out = {};
  for (const e of events || []) {
    if (e?.id == null) continue;
    out[e.id] = eventRelevance(e, profile).score;
  }
  return out;
}

// Convenience: rank a list of events by lens relevance, most-relevant first.
// Ties (and fully off-lens events) keep their incoming importance order.
export function rankByLens(events, profile) {
  return [...(events || [])]
    .map((e) => ({ e, r: eventRelevance(e, profile).score }))
    .sort((a, b) =>
      b.r - a.r ||
      (b.e.importance_score || 0) - (a.e.importance_score || 0))
    .map((x) => x.e);
}
