// ─────────────────────────────────────────────────────────────────────────────
//  TEMPORAL LAYER — history, timelines & patterns over the exposure signals.
//  Pure (no React/DOM), unit-testable. Turns snapshot scores into trajectories:
//  momentum/trend, deterministic synthetic history (offline demo), historical
//  analogs (pattern match), and causal lead-lag. This is the compounding IP —
//  the more history accrues, the sharper these become.
// ─────────────────────────────────────────────────────────────────────────────

// Deterministic PRNG so the offline demo's synthetic history is stable per seed.
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function hashSeed(str) {
  let h = 2166136261;
  for (let i = 0; i < String(str).length; i++) { h ^= String(str).charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

// Exponential moving average over a series (oldest → newest).
export function ema(series, alpha = 0.4) {
  if (!series.length) return 0;
  let e = series[0];
  for (let i = 1; i < series.length; i++) e = alpha * series[i] + (1 - alpha) * e;
  return e;
}

// Momentum = latest value minus the EMA of everything before it. >0 rising.
export function momentum(series, alpha = 0.4) {
  if (series.length < 2) return 0;
  return series[series.length - 1] - ema(series.slice(0, -1), alpha);
}

export function trendLabel(m, eps = 2) {
  return m > eps ? "rising" : m < -eps ? "falling" : "stable";
}

// Deterministic synthetic history ending exactly at `current` (modeled, for offline demo).
export function synthHistory(current, points = 12, seed = 1) {
  const rnd = mulberry32(seed || 1);
  const out = [];
  let v = Math.max(0, Math.min(100, current + (rnd() - 0.5) * 40));
  for (let i = 0; i < points - 1; i++) {
    out.push(Math.round(v));
    v += (current - v) * 0.25 + (rnd() - 0.5) * 12;
    v = Math.max(0, Math.min(100, v));
  }
  out.push(Math.round(current));
  return out;
}

const setOf = (x) => new Set((x || []).map((s) => String(s).toLowerCase()));
function jaccard(a, b) {
  if (!a.size || !b.size) return 0;
  let inter = 0;
  for (const x of a) if (b.has(x)) inter++;
  return inter / (a.size + b.size - inter);
}

// Historical analogs: rank past events by similarity to the target (category +
// sectors + geography). Each carries its realised outcome → a predictive signal.
export function findAnalogs(target, history, k = 3) {
  const tcat = String(target.category || "").toLowerCase();
  const tsec = setOf(target.affected_sectors || target.sectors);
  const tgeo = setOf(target.geography || target.geographic_relevance);
  return (history || [])
    .filter((h) => h.id !== target.id)
    .map((h) => {
      const sim =
        0.4 * (String(h.category || "").toLowerCase() === tcat ? 1 : 0) +
        0.35 * jaccard(tsec, setOf(h.sectors || h.affected_sectors)) +
        0.25 * jaccard(tgeo, setOf(h.geography || h.geographic_relevance));
      return { event: h, similarity: Math.round(sim * 100) };
    })
    .filter((x) => x.similarity > 0)
    .sort((a, b) => b.similarity - a.similarity)
    .slice(0, k);
}

// Causal lead-lag: median days between a cause event and its effect, over the
// directed graph. Answers "effects typically surface in ~N days." null if unknown.
export function leadLag(events, edges) {
  const t = new Map(events.map((e) => [String(e.id), new Date(e.first_detected_at || e.last_updated_at || 0).getTime()]));
  const lags = [];
  for (const ed of edges || []) {
    const a = String(ed.source_event_id ?? ed.source);
    const b = String(ed.target_event_id ?? ed.target);
    const ta = t.get(a), tb = t.get(b);
    if (!ta || !tb || Number.isNaN(ta) || Number.isNaN(tb)) continue;
    const days = Math.abs(tb - ta) / 86_400_000;
    if (days > 0) lags.push(days);
  }
  if (!lags.length) return null;
  lags.sort((x, y) => x - y);
  const mid = Math.floor(lags.length / 2);
  const med = lags.length % 2 ? lags[mid] : (lags[mid - 1] + lags[mid]) / 2;
  return Math.round(med);
}
