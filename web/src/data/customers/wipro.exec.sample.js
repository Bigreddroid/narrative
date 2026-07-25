// ─────────────────────────────────────────────────────────────────────────────
//  SAMPLE DATASET — executive deck (/wipro/exec)
//
//  ⚠️  EVERY value in this file is SYNTHETIC. No customer data, no live engine
//      output, nothing derived from any third-party product. Site names are
//      deliberately generic placeholders ("Site 47 · Bengaluru") and are replaced
//      wholesale when the real campus list arrives.
//
//  Two rules this file exists to honour:
//
//  1. MOCK THE DATA, NEVER THE SHAPE. Events carry the field names the real API
//     serves — geo_centroid_lat/lng, global_importance_score, category,
//     int_discipline — because officeContext() consumes exactly those. (Note the
//     older lib/mockData.js uses lat/lng and would silently produce an all-clear
//     board here.) Swapping to live is then a data-source change, not a rewrite.
//
//  2. NO FABRICATED ACCURACY. Sites, events and itineraries are invented; engine
//     accuracy is never invented. Nothing here feeds a Brier/BSS number, and the
//     benchmark surface stays honestly gated.
//
//  Scale is deliberate: the incumbent consoles carry 199 sites / 216 locations for
//  this footprint. A tidy 8-office fixture looks good and collapses on the real
//  list, so we generate ~200 from the start.
// ─────────────────────────────────────────────────────────────────────────────

export const SAMPLE = true;
export const SAMPLE_NOTICE = "Sample data — synthetic sites, signals and itineraries. Not live.";

// Deterministic PRNG (mulberry32) so every render, test and screenshot is identical.
function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Real coordinates for real cities — the footprint declared in wipro.json's
// countryCodes. The *sites* placed at them are invented.
const CITIES = [
  { city: "Bengaluru",   country: "India",                lat: 12.9716, lng: 77.5946, w: 14 },
  { city: "Hyderabad",   country: "India",                lat: 17.3850, lng: 78.4867, w: 10 },
  { city: "Pune",        country: "India",                lat: 18.5204, lng: 73.8567, w: 10 },
  { city: "Chennai",     country: "India",                lat: 13.0827, lng: 80.2707, w: 8 },
  { city: "Mumbai",      country: "India",                lat: 19.0760, lng: 72.8777, w: 7 },
  { city: "Kolkata",     country: "India",                lat: 22.5726, lng: 88.3639, w: 4 },
  { city: "Noida",       country: "India",                lat: 28.5355, lng: 77.3910, w: 6 },
  { city: "Kochi",       country: "India",                lat: 9.9312,  lng: 76.2673, w: 3 },
  { city: "Coimbatore",  country: "India",                lat: 11.0168, lng: 76.9558, w: 3 },
  { city: "Ahmedabad",   country: "India",                lat: 23.0225, lng: 72.5714, w: 3 },
  { city: "Dallas",      country: "United States",        lat: 32.7767, lng: -96.7970, w: 5 },
  { city: "East Brunswick", country: "United States",     lat: 40.4279, lng: -74.4160, w: 4 },
  { city: "Atlanta",     country: "United States",        lat: 33.7490, lng: -84.3880, w: 3 },
  { city: "Mountain View", country: "United States",      lat: 37.3861, lng: -122.0839, w: 3 },
  { city: "Chicago",     country: "United States",        lat: 41.8781, lng: -87.6298, w: 3 },
  { city: "London",      country: "United Kingdom",       lat: 51.5072, lng: -0.1276, w: 5 },
  { city: "Reading",     country: "United Kingdom",       lat: 51.4543, lng: -0.9781, w: 3 },
  { city: "Manchester",  country: "United Kingdom",       lat: 53.4808, lng: -2.2426, w: 2 },
  { city: "Frankfurt",   country: "Germany",              lat: 50.1109, lng: 8.6821,  w: 3 },
  { city: "Düsseldorf",  country: "Germany",              lat: 51.2277, lng: 6.7735,  w: 2 },
  { city: "Munich",      country: "Germany",              lat: 48.1351, lng: 11.5820, w: 2 },
  { city: "Bucharest",   country: "Romania",              lat: 44.4268, lng: 26.1025, w: 4 },
  { city: "Timișoara",   country: "Romania",              lat: 45.7489, lng: 21.2087, w: 2 },
  { city: "Dubai",       country: "United Arab Emirates", lat: 25.2048, lng: 55.2708, w: 4 },
  { city: "Abu Dhabi",   country: "United Arab Emirates", lat: 24.4539, lng: 54.3773, w: 2 },
  { city: "Riyadh",      country: "Saudi Arabia",         lat: 24.7136, lng: 46.6753, w: 3 },
  { city: "Jeddah",      country: "Saudi Arabia",         lat: 21.4858, lng: 39.1925, w: 2 },
];

const TYPES = [
  { type: "campus",    weight: 3, headMin: 4000, headMax: 28000, criticality: "tier-1" },
  { type: "office",    weight: 8, headMin: 120,  headMax: 2600,  criticality: "tier-2" },
  { type: "delivery",  weight: 4, headMin: 300,  headMax: 5200,  criticality: "tier-2" },
  { type: "datacentre",weight: 1, headMin: 20,   headMax: 140,   criticality: "tier-1" },
  { type: "vendor",    weight: 2, headMin: 15,   headMax: 300,   criticality: "tier-3" },
];

function pickWeighted(list, r) {
  const total = list.reduce((s, x) => s + (x.w ?? x.weight), 0);
  let k = r() * total;
  for (const x of list) { k -= (x.w ?? x.weight); if (k <= 0) return x; }
  return list[list.length - 1];
}

// ~200 sites: the scale the incumbents actually carry for this footprint.
export const SAMPLE_SITES = (() => {
  const r = rng(20260725);
  const sites = [];
  for (let i = 1; i <= 214; i++) {
    const c = pickWeighted(CITIES, r);
    const t = pickWeighted(TYPES, r);
    // Scatter within ~25 km of the city centre so per-site radii differ honestly.
    const dLat = (r() - 0.5) * 0.45;
    const dLng = (r() - 0.5) * 0.45;
    sites.push({
      id: `site-${String(i).padStart(3, "0")}`,
      name: `Site ${i} · ${c.city}`,
      city: c.city,
      country: c.country,
      lat: +(c.lat + dLat).toFixed(4),
      lng: +(c.lng + dLng).toFixed(4),
      type: t.type,
      criticality: t.criticality,
      headcount: Math.round(t.headMin + r() * (t.headMax - t.headMin)),
    });
  }
  return sites;
})();

// ── Signals ──────────────────────────────────────────────────────────────────
// API shape. `source_count` drives the two-source corroboration gate; the sample
// deliberately includes signals that FAIL it, so the suppression log is populated
// by real logic rather than by decoration.
const ev = (o) => ({
  int_discipline: "OSINT", source_count: 3, admiralty_grade: "B2",
  first_detected_at: "2026-07-25T04:00:00Z", ...o,
});

export const SAMPLE_EVENTS = [
  // ── Escalating: corroborated, high importance, near dense sites ─────────────
  ev({
    id: "s-101", category: "conflict", canonical_title: "Coordinated protest action closes arterial roads in Bengaluru CBD",
    geo_centroid_lat: 12.9750, geo_centroid_lng: 77.6050, global_importance_score: 88,
    source_count: 5, admiralty_grade: "A2",
    consequence_for_site: "Primary and secondary access routes to the campus are affected during the evening shift change.",
    recommended_action: "Shift transport window earlier by 90 minutes; brief night-shift leads.",
  }),
  // Organisation-scoped: cyber is no longer distance-scored, so this is free to be a
  // genuine alert-grade signal without implying a false geography. It surfaces as
  // "Organisation-wide" and deliberately claims no headcount.
  ev({
    id: "s-102", category: "cyber", canonical_title: "Credential-stuffing campaign targeting IT services suppliers",
    int_discipline: "CYBINT", geo_centroid_lat: 17.4100, geo_centroid_lng: 78.4400,
    global_importance_score: 86, source_count: 4, admiralty_grade: "B2",
    consequence_for_site: "Shared VPN concentrators and contractor accounts are in the reported target set. Which sites are reachable is not yet established.",
    recommended_action: "Force re-auth on external concentrators; confirm MFA coverage for contractor accounts.",
  }),
  ev({
    id: "s-103", category: "conflict", canonical_title: "Civil unrest with road closures reported across central Dubai",
    geo_centroid_lat: 25.2300, geo_centroid_lng: 55.3200, global_importance_score: 84,
    source_count: 3, admiralty_grade: "B2",
    consequence_for_site: "Movement between hotel districts and the office corridor is intermittently restricted.",
    recommended_action: "Confirm welfare of travellers in-country; hold non-essential movement.",
  }),
  ev({
    id: "s-104", category: "disaster", canonical_title: "Flash flooding closes two access roads in Chennai industrial corridor",
    geo_centroid_lat: 13.0500, geo_centroid_lng: 80.2200, global_importance_score: 76,
    source_count: 4, admiralty_grade: "B1",
    consequence_for_site: "Ground-floor facilities and the primary generator room sit below the flood line.",
    recommended_action: "Pre-position pumps; validate generator elevation before the next high-tide window.",
  }),

  // ── HELD: single-sourced. Above threshold, but fails the two-source bar. ─────
  ev({
    id: "s-201", category: "conflict", canonical_title: "Unverified report of security incident near Pune tech park",
    geo_centroid_lat: 18.5900, geo_centroid_lng: 73.7400, global_importance_score: 79,
    source_count: 1, admiralty_grade: "D4",
  }),
  ev({
    id: "s-202", category: "cyber", canonical_title: "Claimed data-leak post naming a European services provider",
    int_discipline: "CYBINT", geo_centroid_lat: 50.1200, geo_centroid_lng: 8.6700,
    global_importance_score: 74, source_count: 1, admiralty_grade: "F6",
  }),

  // ── HELD: routine conditions. THE rebuttal case — these must colour a site but
  //    must NEVER become an executive decision item. An incumbent console graded a
  //    named office "High" off exactly this class of signal.
  ev({
    id: "s-301", category: "storm", canonical_title: "Moderate to heavy rain expected across Telangana",
    geo_centroid_lat: 17.3900, geo_centroid_lng: 78.4900, global_importance_score: 38,
    source_count: 3, admiralty_grade: "B2",
  }),
  ev({
    id: "s-302", category: "storm", canonical_title: "India Metro City Weather Update",
    geo_centroid_lat: 19.0800, geo_centroid_lng: 72.8800, global_importance_score: 31,
    source_count: 2, admiralty_grade: "C3",
  }),
  ev({
    id: "s-303", category: "climate", canonical_title: "Seasonal heat advisory issued for Gulf coastal districts",
    geo_centroid_lat: 24.4600, geo_centroid_lng: 54.3800, global_importance_score: 34,
    source_count: 3, admiralty_grade: "B2",
  }),
  ev({
    id: "s-304", category: "economics", canonical_title: "Port handling delays reported at western India terminals",
    int_discipline: "FININT", geo_centroid_lat: 19.0000, geo_centroid_lng: 72.9500,
    global_importance_score: 44, source_count: 3, admiralty_grade: "B2",
  }),
  ev({
    id: "s-305", category: "conflict", canonical_title: "Localised demonstration announced near Noida sector boundary",
    geo_centroid_lat: 28.5400, geo_centroid_lng: 77.3800, global_importance_score: 52,
    source_count: 3, admiralty_grade: "B2",
  }),
  ev({
    id: "s-306", category: "cyber", canonical_title: "Phishing lure impersonating a UK payroll provider",
    int_discipline: "CYBINT", geo_centroid_lat: 51.5000, geo_centroid_lng: -0.1300,
    global_importance_score: 41, source_count: 4, admiralty_grade: "B2",
  }),
  ev({
    id: "s-307", category: "economics", canonical_title: "Transit strike ballot opens in Bucharest municipal services",
    int_discipline: "FININT", geo_centroid_lat: 44.4300, geo_centroid_lng: 26.1000,
    global_importance_score: 47, source_count: 3, admiralty_grade: "B2",
  }),
];

// Yesterday's picture — the baseline delta() diffs against. Deliberately different:
// Bengaluru had not yet escalated, and a Chennai signal has since cleared. This is
// how "what changed" is computed rather than asserted.
export const SAMPLE_EVENTS_PRIOR = [
  ...SAMPLE_EVENTS.filter((e) => !["s-101", "s-104"].includes(e.id)),
  ev({
    id: "s-901", category: "conflict", canonical_title: "Police advisory ahead of planned gathering, Kolkata",
    geo_centroid_lat: 22.5700, geo_centroid_lng: 88.3600, global_importance_score: 81,
    source_count: 3, admiralty_grade: "B2",
  }),
];

// ── Travellers ───────────────────────────────────────────────────────────────
// `lastCheckInISO` drives the unaccounted-for number — the duty-of-care exposure a
// board asks about first, and the one none of the incumbent consoles surface.
// Some are deliberately stale.
const TRAVELLER_ROLES = [
  "SVP, Middle East Business", "Director, Delivery Assurance", "VP, Client Partner",
  "Principal Consultant", "Head of Infrastructure", "Regional Finance Lead",
  "Senior Manager, Transitions", "Programme Director", "Lead Architect",
  "Global Account Executive",
];
const DESTS = [
  { to: "Dubai",     country: "United Arab Emirates", toLat: 25.2532, toLng: 55.3657 },
  { to: "Riyadh",    country: "Saudi Arabia",         toLat: 24.7136, toLng: 46.6753 },
  { to: "London",    country: "United Kingdom",       toLat: 51.5072, toLng: -0.1276 },
  { to: "Frankfurt", country: "Germany",              toLat: 50.1109, toLng: 8.6821 },
  { to: "Dallas",    country: "United States",        toLat: 32.7767, toLng: -96.7970 },
  { to: "Bucharest", country: "Romania",              toLat: 44.4268, toLng: 26.1025 },
  { to: "Chennai",   country: "India",                toLat: 13.0827, toLng: 80.2707 },
  { to: "Bengaluru", country: "India",                toLat: 12.9716, toLng: 77.5946 },
];
const ORIGINS = ["Bengaluru", "Pune", "Hyderabad", "Chennai", "London", "Dallas"];

export const SAMPLE_TRIPS = (() => {
  const r = rng(4242);
  const trips = [];
  for (let i = 1; i <= 42; i++) {
    const d = DESTS[Math.floor(r() * DESTS.length)];
    // Departures spread from 10 days ago to 25 days out, around the fixed "today".
    const offset = Math.floor(r() * 35) - 10;
    const depart = new Date(Date.UTC(2026, 6, 25) + offset * 86_400_000);
    const ret = new Date(depart.getTime() + (2 + Math.floor(r() * 9)) * 86_400_000);
    const active = depart <= new Date(Date.UTC(2026, 6, 25)) && ret >= new Date(Date.UTC(2026, 6, 25));
    // ~1 in 4 active travellers has a stale check-in.
    const checkedIn = !active ? null : r() > 0.25
      ? new Date(Date.UTC(2026, 6, 25, 3) - Math.floor(r() * 10) * 3_600_000).toISOString()
      : new Date(Date.UTC(2026, 6, 22) - Math.floor(r() * 24) * 3_600_000).toISOString();
    trips.push({
      id: `t-${String(i).padStart(3, "0")}`,
      traveler: `Traveller ${i}`,
      role: TRAVELLER_ROLES[Math.floor(r() * TRAVELLER_ROLES.length)],
      from: ORIGINS[Math.floor(r() * ORIGINS.length)],
      to: d.to, country: d.country, toLat: d.toLat, toLng: d.toLng,
      departISO: depart.toISOString().slice(0, 10),
      returnISO: ret.toISOString().slice(0, 10),
      lastCheckInISO: checkedIn,
    });
  }
  return trips;
})();

// Forward-window context. Curated public holidays and gatherings drive forward()
// and the derived-traffic layer.
export const SAMPLE_COUNTRY_CODES = {
  India: "IN", "United States": "US", "United Kingdom": "GB", Germany: "DE",
  Romania: "RO", "United Arab Emirates": "AE", "Saudi Arabia": "SA",
};

export const SAMPLE_HOLIDAYS = {
  IN: [
    { date: "2026-08-15", name: "Independence Day" },
    { date: "2026-09-14", name: "Ganesh Chaturthi" },
  ],
  AE: [{ date: "2026-08-01", name: "Islamic New Year" }],
  SA: [{ date: "2026-09-23", name: "Saudi National Day" }],
  GB: [{ date: "2026-08-31", name: "Summer Bank Holiday" }],
  RO: [{ date: "2026-08-15", name: "Dormition of the Mother of God" }],
};

export const SAMPLE_FESTIVALS = [
  {
    id: "f-ganesh-pune", name: "Ganesh Chaturthi processions", place: "Pune",
    lat: 18.5204, lng: 73.8567, startISO: "2026-09-14", endISO: "2026-09-24",
    note: "Multi-day processions on arterial routes; sustained road impact.",
  },
  {
    id: "f-independence-noida", name: "Independence Day gatherings", place: "Delhi NCR",
    lat: 28.6139, lng: 77.2090, startISO: "2026-08-15", endISO: "2026-08-15",
    note: "Central-Delhi movement restrictions and secured corridors.",
  },
  {
    id: "f-onam-kochi", name: "Onam celebrations", place: "Kochi",
    lat: 9.9312, lng: 76.2673, startISO: "2026-08-26", endISO: "2026-09-05",
    note: "Extended regional holiday window; reduced local staffing.",
  },
];

// Fixed "today" so the sample board is deterministic across renders and reviews.
export const SAMPLE_TODAY = new Date("2026-07-25T09:00:00Z");
