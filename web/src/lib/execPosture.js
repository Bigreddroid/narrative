// ─────────────────────────────────────────────────────────────────────────────
// execPosture — the executive rollup that turns per-site context into a POSITION.
//
// The analyst deck (CustomerDeck) answers "what is happening?". This answers the
// only four questions an executive actually has:
//
//   1. exposure()       Where are we exposed right now — in PEOPLE, not sites.
//   2. delta()          What changed since last look. Executives read deltas.
//   3. decisionQueue()  The few items that need a decision — each one justified.
//   4. suppression()    What we held back, and WHY. The trust surface.
//
//   + travelPosture()   Duty-of-care: who is in motion, who is unaccounted for.
//   + forward()         What is coming, so leadership plans instead of reacts.
//
// Why suppression() matters more than the rest: every incumbent surface only ever
// shows what it ESCALATED. That is how a named office ends up graded "High" off a
// routine monsoon advisory — the escalation is visible and the reasoning is not.
// An executive who is asked to trust a quieter feed has exactly one fair question,
// "what did you miss?", and a suppression log with reasons is the only honest
// answer to it. It is also how we express calibration WITHOUT quoting a Brier
// score at someone who will never ask for one.
//
// Pure + unit-tested (execPosture.test.mjs). No network, no React, no clock of its
// own — `today` is always injected so results are deterministic.
// ─────────────────────────────────────────────────────────────────────────────
import { LEVEL_RANK, LAYER_LABELS, topSignal, extentKm } from "./officeContext.js";

// Signal-layer thresholds, mirroring officeContext.statusFromSignal so one risk
// appetite re-baselines the executive view and the analyst view identically.
export const ALERT_BAR = 70;
export const WATCH_BAR = 40;

// Corroboration gate. A claim reaching an executive must be carried by at least
// two independent sources — the customer's stated #1 requirement ("we won't brief
// leadership on media reports alone"). Single-sourced signals are not discarded,
// they are HELD and shown in the suppression log with that reason.
export const MIN_SOURCES = 2;

// Layers that describe conditions rather than incidents. They colour a site and
// they feed derived traffic, but on their own they never justify an executive
// decision item — this is the specific failure we saw graded "High" elsewhere.
const CONTEXT_ONLY_LAYERS = new Set(["holidays", "festivals", "traffic"]);
// Cyber is deliberately absent: it is organisation-scoped (see officeContext
// .orgCyberStatus), identical across every office, so walking it per-site would emit
// one duplicate row per building. It is handled once, separately.
const SIGNAL_LAYERS = ["geopolitics", "market", "hazards", "weather"];

const dayMs = 86_400_000;
const parseISO = (s) => { const t = Date.parse(s); return Number.isNaN(t) ? null : t; };
const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();

const sourceCount = (e) => (Array.isArray(e?.sources) ? e.sources.length
  : Number.isFinite(e?.source_count) ? e.source_count : 0);

// ── 1. Exposure — people first ───────────────────────────────────────────────
// "3 sites affected" is an operations number. "1,847 people affected" is the
// number a board minutes. Duty-of-care liability attaches to people, not real
// estate, so people is the unit the executive surface counts in.
export function exposure(contexts = []) {
  const out = {
    sites: 0, sitesAlert: 0, sitesWatch: 0, sitesClear: 0,
    people: 0, peopleAlert: 0, peopleWatch: 0, peopleExposed: 0,
    countries: 0, countriesAffected: 0,
  };
  const countries = new Set(), hit = new Set();
  for (const c of contexts) {
    const head = Number(c.office?.headcount) || 0;
    out.sites += 1;
    out.people += head;
    if (c.office?.country) countries.add(c.office.country);
    if (c.worst === "alert") {
      out.sitesAlert += 1; out.peopleAlert += head;
      if (c.office?.country) hit.add(c.office.country);
    } else if (c.worst === "watch") {
      out.sitesWatch += 1; out.peopleWatch += head;
      if (c.office?.country) hit.add(c.office.country);
    } else out.sitesClear += 1;
  }
  out.peopleExposed = out.peopleAlert + out.peopleWatch;
  out.countries = countries.size;
  out.countriesAffected = hit.size;
  return out;
}

// ── 2. Delta — what changed ──────────────────────────────────────────────────
// `prior` is a snapshot of the same rollup: { [officeId]: { worst, layers } }.
// Every incumbent screen in the competitor corpus shows current state only; an
// executive who looked on Monday needs Tuesday's *difference*, not Tuesday's state.
export function delta(contexts = [], prior = {}) {
  const deteriorated = [], improved = [];
  for (const c of contexts) {
    const was = prior?.[c.office?.id];
    if (!was) continue;
    const nowRank = LEVEL_RANK[c.worst] ?? 0;
    const wasRank = LEVEL_RANK[was.worst] ?? 0;
    if (nowRank === wasRank) continue;

    // Attribute the move to the layers that actually moved, so the delta explains
    // itself rather than asserting a direction.
    const drivers = [];
    for (const [key, layer] of Object.entries(c.layers || {})) {
      const before = was.layers?.[key];
      if (before && before !== layer.level) {
        drivers.push({ layer: key, label: LAYER_LABELS[key] || key, from: before, to: layer.level });
      }
    }
    const row = {
      office: c.office, from: was.worst, to: c.worst, drivers,
      people: Number(c.office?.headcount) || 0,
    };
    (nowRank > wasRank ? deteriorated : improved).push(row);
  }
  const bySeverity = (a, b) => (LEVEL_RANK[b.to] - LEVEL_RANK[a.to]) || (b.people - a.people);
  deteriorated.sort(bySeverity);
  improved.sort((a, b) => b.people - a.people);
  return {
    deteriorated, improved,
    net: deteriorated.length - improved.length,
    unchanged: contexts.length - deteriorated.length - improved.length,
  };
}

// ── 3. Decision queue — the few things that need a call ──────────────────────
// Hard rule: an item appears ONLY if it clears every bar — a real incident signal
// (not a condition), above the alert threshold, carried by >= MIN_SOURCES
// independent sources. Everything that fails a bar goes to suppression() with the
// reason it failed. Nothing is silently dropped; nothing unjustified is shown.
// Grouped BY SITUATION, not by building. One event affecting 28 campuses in a city
// is ONE executive decision covering 28 sites — not 28 queue rows. Emitting a row
// per site is precisely the item-spam that fills a 9,000-message mailbox, and it is
// just as wrong when we do it. Travellers attach to the same situation, because
// "unrest in Dubai" is one call covering the sites AND the people flying into it.
export function decisionQueue(contexts = [], travel = null, opts = {}) {
  const { limit = 3, appetite = 50, minSources = MIN_SOURCES } = opts;
  const factor = 0.5 + appetite / 100;
  const bar = ALERT_BAR * factor;
  const byEvent = new Map();

  const situation = (event) => {
    if (!byEvent.has(event.id)) {
      byEvent.set(event.id, {
        id: `sit:${event.id}`,
        event,
        why: event.canonical_title,
        grade: event.admiralty_grade || null,
        layer: event.category || null,
        sources: sourceCount(event),
        consequence: event.consequence_for_site || null,
        recommend: event.recommended_action || null,
        importance: 0, nearestKm: Infinity,
        sites: [], travellers: [],
        people: 0, cities: new Set(), countries: new Set(),
      });
    }
    return byEvent.get(event.id);
  };

  for (const c of contexts) {
    const best = topSignal(c);
    if (!best || best.imp < bar) continue;
    if (sourceCount(best.event) < minSources) continue;   // → suppression: uncorroborated
    const s = situation(best.event);
    s.sites.push({ office: c.office, km: Math.round(best.km) });
    s.people += Number(c.office.headcount) || 0;
    if (c.office.city) s.cities.add(c.office.city);
    if (c.office.country) s.countries.add(c.office.country);
    s.importance = Math.max(s.importance, Math.round(best.imp));
    s.nearestKm = Math.min(s.nearestKm, Math.round(best.km));
  }

  // Travellers heading into, or sitting in, an elevated destination. A person can be
  // moved when a campus cannot, so they carry their own recommended action.
  for (const t of travel?.rows || []) {
    if (t.verdict.key !== "reconsider" || !t.best) continue;
    if (sourceCount(t.best.event) < minSources) continue;
    const s = situation(t.best.event);
    s.travellers.push({
      trip: t.trip, status: t.status, unaccounted: t.unaccounted,
      km: Math.round(t.best.km),
      action: t.status === "active"
        ? "Confirm welfare; brief on movement restrictions."
        : "Defer travel or re-route; issue pre-departure brief.",
    });
    s.people += 1;
    s.importance = Math.max(s.importance, Math.round(t.best.imp));
    s.nearestKm = Math.min(s.nearestKm, Math.round(t.best.km));
    if (t.trip.country) s.countries.add(t.trip.country);
  }

  const items = [...byEvent.values()].map((s) => ({
    ...s,
    kind: s.sites.length ? (s.travellers.length ? "mixed" : "site") : "traveller",
    orgScope: false,
    siteCount: s.sites.length,
    travellerCount: s.travellers.length,
    cities: [...s.cities], countries: [...s.countries],
    nearestKm: s.nearestKm === Infinity ? null : s.nearestKm,
    // Show the largest affected sites; the rest stay behind a count.
    topSites: s.sites.sort((a, b) => (b.office.headcount || 0) - (a.office.headcount || 0)).slice(0, 4),
  }));

  // Organisation-scoped cyber. Identical for every office, so it is read once.
  //
  // It deliberately carries `people: null`. Claiming "organisation-wide, 703,196
  // people" would be a BIGGER overclaim than the 700 km proximity bug we removed —
  // we genuinely do not know which sites a campaign reaches, and inventing the
  // number is exactly the sin this product is built to call out.
  const cyber = contexts[0]?.layers?.cyber;
  if (cyber?.best && cyber.level === "alert" && sourceCount(cyber.best.event) >= minSources) {
    items.push({
      id: `sit:${cyber.best.event.id}`,
      event: cyber.best.event,
      why: cyber.best.event.canonical_title,
      grade: cyber.best.event.admiralty_grade || null,
      layer: "cyber",
      sources: sourceCount(cyber.best.event),
      consequence: cyber.best.event.consequence_for_site || null,
      recommend: cyber.best.event.recommended_action || null,
      importance: Math.round(cyber.imp),
      kind: "organisation", orgScope: true,
      people: null,                       // unknown, and never fabricated
      sites: [], travellers: [], topSites: [],
      siteCount: 0, travellerCount: 0,
      cities: [], countries: [], nearestKm: null,
    });
  }

  // Rank by people at stake, then signal strength — an executive triages by blast
  // radius, not by recency. An organisation-wide compromise has no headcount to sort
  // on and outranks a local incident, so it sorts by importance and leads.
  items.sort((a, b) => {
    if (a.orgScope !== b.orgScope) return a.orgScope ? -1 : 1;
    return (b.people - a.people) || (b.importance - a.importance);
  });
  return { items: items.slice(0, limit), total: items.length };
}

// ── 4. Suppression — what we held, and why ───────────────────────────────────
// The trust surface, and the direct answer to "what did you miss?". Every signal
// that touched a site and did NOT reach the executive is recorded here with a
// machine-checkable reason. If this list is empty we are not filtering; if it is
// unexplained we are just another vendor asking to be trusted.
export const SUPPRESSION_REASONS = {
  context_only: "Condition, not an incident — no disruption threshold crossed",
  below_threshold: "Below your risk-appetite threshold for escalation",
  uncorroborated: "Single source — did not meet the two-source bar",
  superseded: "Site already represented by a higher-severity item",
};

export function suppression(contexts = [], opts = {}) {
  const { appetite = 50, minSources = MIN_SOURCES, escalatedEventIds = new Set() } = opts;
  const factor = 0.5 + appetite / 100;
  const bar = ALERT_BAR * factor;
  const held = [];
  let considered = 0;

  for (const c of contexts) {
    // Did this site's leading signal already reach the executive as a situation? If
    // so, its other qualifying signals are 'superseded' rather than silently gone.
    const lead = topSignal(c);
    const escalated = Boolean(lead && escalatedEventIds.has(lead.event.id));

    for (const key of SIGNAL_LAYERS) {
      const layer = c.layers?.[key];
      const best = layer?.best;
      if (!best) continue;
      considered += 1;
      const srcs = sourceCount(best.event);
      let reason = null;
      if (best.imp < bar) reason = "below_threshold";
      else if (srcs < minSources) reason = "uncorroborated";
      else if (escalated && lead?.event?.id !== best.event.id) reason = "superseded";
      if (!reason) continue;
      held.push({
        id: `${c.office.id}:${key}:${best.event.id}`,
        // Carried explicitly so the UI can open the underlying signal. It is also in
        // `id`, but recovering it by splitting a composite key is the kind of thing
        // that breaks silently the day an office id contains a colon.
        eventId: best.event.id,
        office: c.office, layer: key, layerLabel: LAYER_LABELS[key] || key,
        title: best.event.canonical_title, km: Math.round(best.km),
        importance: Math.round(best.imp), sources: srcs,
        reason, reasonLabel: SUPPRESSION_REASONS[reason],
      });
    }

    // Conditions (holiday / festival / derived traffic) that coloured the site but
    // were correctly not promoted to a decision. This is the row that would have
    // read "office graded High" on an incumbent console.
    for (const key of ["holidays", "festivals", "traffic"]) {
      const layer = c.layers?.[key];
      if (!layer || layer.level === "clear") continue;
      considered += 1;
      const label = key === "traffic"
        ? `Derived road disruption ${layer.pct}%`
        : key === "festivals"
          ? (layer.active?.name || layer.soon?.name || "Gathering in window")
          : (layer.today?.name || layer.next?.name || "Public holiday in window");
      held.push({
        id: `${c.office.id}:${key}`,
        office: c.office, layer: key, layerLabel: LAYER_LABELS[key] || key,
        title: label, km: 0, importance: 0, sources: null,
        reason: "context_only", reasonLabel: SUPPRESSION_REASONS.context_only,
      });
    }
  }

  // Organisation-scoped cyber, considered ONCE rather than once per building — it is
  // the same signal for all 214 sites, and 214 identical held rows would be noise of
  // exactly the kind this panel exists to expose.
  const cyber = contexts[0]?.layers?.cyber;
  if (cyber?.best) {
    considered += 1;
    const srcs = sourceCount(cyber.best.event);
    const reason = cyber.level !== "alert" ? "below_threshold"
      : srcs < minSources ? "uncorroborated"
      : escalatedEventIds.has(cyber.best.event.id) ? null
      : null;
    if (reason) {
      held.push({
        id: `org:cyber:${cyber.best.event.id}`,
        office: { id: "__org", name: "Organisation-wide", city: "", country: "" },
        layer: "cyber", layerLabel: LAYER_LABELS.cyber,
        title: cyber.best.event.canonical_title, km: null,
        importance: Math.round(cyber.imp), sources: srcs,
        orgScope: true,
        reason, reasonLabel: SUPPRESSION_REASONS[reason],
      });
    }
  }

  const byReason = {};
  for (const h of held) byReason[h.reason] = (byReason[h.reason] || 0) + 1;
  held.sort((a, b) => b.importance - a.importance);
  return { held, considered, byReason, suppressed: held.length };
}

// ── 5. Travel posture — duty of care ─────────────────────────────────────────
// Verdict vocabulary is deliberately identical to the analyst deck's
// TravelSecurity panel (Proceed / Advise / Reconsider) so the organisation runs
// ONE dialect. What changes at executive altitude is the aggregation: who is in
// motion, how many are in an elevated-risk location, and — the number no
// incumbent surfaces to a board — who we cannot currently account for.
export const VERDICTS = {
  proceed:    { key: "proceed",    label: "Proceed",    color: "#4E9A5A" },
  advise:     { key: "advise",     label: "Advise",     color: "#C08A2E" },
  reconsider: { key: "reconsider", label: "Reconsider", color: "#B4462F" },
};

export function travelPosture(trips = [], geoEvents = [], opts = {}) {
  // No `radiusKm` option any more: a traveller 290 km from a CBD protest is not
  // affected by it, and a flat destination radius reproduced the same overclaim the
  // site model had. Each event is judged against its own extent.
  const { appetite = 50, today = new Date(), haversineKm, checkInStaleHours = 24 } = opts;
  if (typeof haversineKm !== "function") {
    throw new TypeError("travelPosture requires a haversineKm(lat1,lng1,lat2,lng2) function");
  }
  const factor = 0.5 + appetite / 100;
  const t0 = today.getTime();

  const rows = trips.map((trip) => {
    const depart = parseISO(trip.departISO), ret = parseISO(trip.returnISO);
    const status = depart != null && ret != null && t0 >= depart && t0 <= ret + dayMs ? "active"
      : depart != null && depart > t0 ? "upcoming" : "closed";
    const daysOut = depart != null ? Math.ceil((depart - t0) / dayMs) : null;

    let best = null;
    for (const e of geoEvents) {
      if (e.geo_centroid_lat == null || e.geo_centroid_lng == null) continue;
      const km = haversineKm(trip.toLat, trip.toLng, e.geo_centroid_lat, e.geo_centroid_lng);
      const imp = e.global_importance_score || 0;
      if (km <= extentKm(e) && (!best || imp > best.imp)) best = { event: e, km, imp };
    }
    const verdict = best && best.imp >= ALERT_BAR * factor ? VERDICTS.reconsider
      : best && best.imp >= WATCH_BAR * factor ? VERDICTS.advise
      : VERDICTS.proceed;

    // Reachability. An active traveller in an elevated-risk destination whose last
    // check-in has gone stale is the duty-of-care exposure a board is asked about
    // first, and it is the one number none of the incumbent consoles surface.
    const lastSeen = parseISO(trip.lastCheckInISO);
    const staleMs = checkInStaleHours * 3_600_000;
    const unaccounted = status === "active" && verdict.key !== "proceed"
      && (lastSeen == null || t0 - lastSeen > staleMs);

    return { trip, status, daysOut, best, verdict, lastSeen, unaccounted };
  });

  const active = rows.filter((r) => r.status === "active");
  const upcoming = rows.filter((r) => r.status === "upcoming");
  return {
    rows,
    active, upcoming,
    inMotion: active.length,
    upcomingCount: upcoming.length,
    elevated: rows.filter((r) => r.status !== "closed" && r.verdict.key !== "proceed").length,
    reconsider: rows.filter((r) => r.status !== "closed" && r.verdict.key === "reconsider").length,
    unaccounted: rows.filter((r) => r.unaccounted),
  };
}

// ── 6. Forward posture — what is coming ──────────────────────────────────────
// Aggregates each site's holiday + festival windows into one dated timeline with
// the people behind each date. Lets leadership act ahead of a window rather than
// receive an alert during it.
export function forward(contexts = [], opts = {}) {
  const { today = new Date(), windowDays = 60 } = opts;
  const t0 = startOfDay(today);
  const byDate = new Map();

  const add = (dateISO, name, kind, office, inDays) => {
    if (dateISO == null) return;
    const key = `${dateISO}|${name}`;
    if (!byDate.has(key)) {
      byDate.set(key, { date: dateISO, name, kind, inDays, sites: [], people: 0 });
    }
    const row = byDate.get(key);
    row.sites.push(office);
    row.people += Number(office.headcount) || 0;
  };

  for (const c of contexts) {
    for (const h of c.holidays || []) {
      if (h.in_days >= 0 && h.in_days <= windowDays) add(h.date, h.name, "holiday", c.office, h.in_days);
    }
    for (const f of c.festivals || []) {
      const s = parseISO(f.startISO);
      if (s == null) continue;
      const inDays = Math.floor((s - t0) / dayMs);
      if (inDays >= 0 && inDays <= windowDays) {
        // The gathering's own kind, not a blanket "festival" — the board was
        // calling a stadium fixture and a trade fair the same thing.
        add(f.startISO, f.name, f.kind || "festival", c.office, inDays);
      }
    }
  }
  return [...byDate.values()].sort((a, b) => a.inDays - b.inDays || b.people - a.people);
}

// ── Snapshot helper ──────────────────────────────────────────────────────────
// Reduces a live rollup to the minimal shape delta() consumes. In production this
// is what gets persisted per day; in the sample build it is how the fixture's
// "last look" baseline is expressed.
export function snapshot(contexts = []) {
  const out = {};
  for (const c of contexts) {
    const layers = {};
    for (const [k, v] of Object.entries(c.layers || {})) layers[k] = v.level;
    out[c.office.id] = { worst: c.worst, layers };
  }
  return out;
}
