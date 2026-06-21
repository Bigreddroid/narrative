// ─────────────────────────────────────────────────────────────────────────────
//  Air-traffic data — simulated flights + OpenSky state-vector parsing.
//
//  Powers the live air-traffic overlay (sibling of the maritime layer). With no
//  reachable source the app shows a simulated fleet flying real corridors; the
//  backend /api/v1/aircraft route upgrades it to live OpenSky positions.
// ─────────────────────────────────────────────────────────────────────────────

export const AIRCRAFT_TYPES = {
  commercial: { label: "Commercial", color: "#5BA3D0" },
  cargo:      { label: "Cargo",      color: "#C9A227" },
  private:    { label: "Private",    color: "#9B7FC0" },
  military:   { label: "Military",   color: "#C84A4A" },
  other:      { label: "Other",      color: "#8B8B80" },
};

// Top-down plane glyph, nose pointing north (rotated by heading at render).
export const AIRCRAFT_GLYPH =
  "M0,-6 L1.2,-1 L6,1.6 L6,3 L1.2,2.2 L0.9,5 L2.6,6.4 L2.6,7.2 L0,6.2 L-2.6,7.2 L-2.6,6.4 L-0.9,5 L-1.2,2.2 L-6,3 L-6,1.6 L-1.2,-1 Z";

// Major air corridors — ordered [lng,lat] waypoints.
const CORRIDORS = [
  { name: "JFK → London (NAT)",   bias: "commercial", points: [[-73.8, 40.6], [-60, 45], [-40, 50], [-20, 52], [-8, 51], [-0.4, 51.5]] },
  { name: "LAX → Tokyo",          bias: "commercial", points: [[-118.4, 33.9], [-150, 38], [-180, 42], [165, 42], [150, 38], [140, 35.7]] },
  { name: "Frankfurt → Dubai",    bias: "commercial", points: [[8.5, 50], [15, 46], [28, 38], [40, 32], [48, 28], [55.3, 25.2]] },
  { name: "LAX → JFK",            bias: "commercial", points: [[-118.4, 33.9], [-104, 36], [-90, 39], [-77, 40], [-73.8, 40.6]] },
  { name: "Singapore → Hong Kong",bias: "cargo",      points: [[104.0, 1.35], [106, 6], [110, 13], [113, 19], [114.2, 22.3]] },
  { name: "Dubai → Delhi",        bias: "commercial", points: [[55.3, 25.2], [62, 26], [70, 28], [77, 28.5]] },
  { name: "São Paulo → Santiago", bias: "commercial", points: [[-46.5, -23.4], [-58, -30], [-70, -33.4]] },
  { name: "Sydney → Singapore",   bias: "cargo",      points: [[151.2, -33.9], [140, -25], [128, -12], [115, -3], [104, 1.35]] },
  { name: "Johannesburg → Cairo", bias: "commercial", points: [[28, -26.1], [30, -15], [32, 0], [31, 18], [31.4, 30]] },
  { name: "Hong Kong → Frankfurt",bias: "cargo",      points: [[114.2, 22.3], [100, 30], [75, 42], [45, 48], [15, 50], [8.5, 50]] },
];

const R = 6371;
const toRad = (d) => (d * Math.PI) / 180;
const toDeg = (r) => (r * 180) / Math.PI;

function haversineKm([lng1, lat1], [lng2, lat2]) {
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
}

function bearingDeg([lng1, lat1], [lng2, lat2]) {
  const φ1 = toRad(lat1), φ2 = toRad(lat2), Δλ = toRad(lng2 - lng1);
  const y = Math.sin(Δλ) * Math.cos(φ2);
  const x = Math.cos(φ1) * Math.sin(φ2) - Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ);
  return (toDeg(Math.atan2(y, x)) + 360) % 360;
}

const CORRIDOR_METRICS = CORRIDORS.map((c) => {
  const segs = [];
  let cum = 0;
  for (let i = 0; i < c.points.length - 1; i++) {
    const a = c.points[i], b = c.points[i + 1];
    const len = Math.max(haversineKm(a, b), 1);
    segs.push({ a, b, start: cum, len, bearing: bearingDeg(a, b) });
    cum += len;
  }
  return { total: cum, segs };
});

function positionAtDistance(idx, d) {
  const m = CORRIDOR_METRICS[idx];
  const dist = ((d % m.total) + m.total) % m.total;
  const seg = m.segs.find((s) => dist >= s.start && dist < s.start + s.len) || m.segs[m.segs.length - 1];
  const f = (dist - seg.start) / seg.len;
  return { lng: seg.a[0] + (seg.b[0] - seg.a[0]) * f, lat: seg.a[1] + (seg.b[1] - seg.a[1]) * f, heading: seg.bearing };
}

const AIRLINES = ["UAL", "DAL", "AAL", "BAW", "DLH", "AFR", "UAE", "SIA", "QFA", "ANA", "KLM", "FDX", "UPS", "CPA"];
const rand = (a, b) => a + Math.random() * (b - a);
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];

function pickType(bias) {
  const r = Math.random();
  if (r < 0.55) return bias;
  return pick(["commercial", "cargo", "private", "military", "other"]);
}

// Build static descriptors; positions are computed from elapsed time at render.
export function buildSimFlights(perCorridor = 6) {
  const flights = [];
  let n = 0;
  CORRIDORS.forEach((c, idx) => {
    for (let i = 0; i < perCorridor; i++) {
      const type = pickType(c.bias);
      flights.push({
        icao: `SIM${(n).toString(16).padStart(4, "0")}`,
        callsign: `${pick(AIRLINES)}${Math.floor(rand(100, 999))}`,
        type,
        corridorIdx: idx,
        dist0: rand(0, CORRIDOR_METRICS[idx].total),
        speed: rand(8, 16),                    // km/s (exaggerated for a lively demo)
        dir: Math.random() < 0.5 ? 1 : -1,
        velocity: Math.round(rand(420, 520)),  // displayed knots
        alt: Math.round(rand(31000, 41000)),   // feet
        route: c.name,
      });
      n++;
    }
  });
  return flights;
}

export function flightPosition(f, t) {
  const { lng, lat, heading } = positionAtDistance(f.corridorIdx, f.dist0 + f.dir * f.speed * t);
  return { ...f, lng, lat, heading: f.dir > 0 ? heading : (heading + 180) % 360 };
}

// ─── OpenSky parsing ──────────────────────────────────────────────────────────
// Coarse type bucket from callsign prefix (OpenSky has no type field).
const CARGO_PREFIXES = ["FDX", "UPS", "GTI", "CLX", "BOX", "CKS"];

function bucketFromCallsign(callsign) {
  const cs = (callsign || "").trim().toUpperCase();
  if (!cs) return "other";
  if (CARGO_PREFIXES.some((p) => cs.startsWith(p))) return "cargo";
  if (/^[A-Z]{3}\d/.test(cs)) return "commercial";  // ICAO airline + flight number
  if (/^N\d/.test(cs)) return "private";            // US tail number
  return "other";
}

// Normalise a backend/OpenSky aircraft record → render object (or null).
export function parseAircraft(rec) {
  if (rec == null) return null;
  const lat = rec.lat ?? rec.latitude;
  const lng = rec.lng ?? rec.longitude;
  if (lat == null || lng == null) return null;
  const callsign = (rec.callsign || "").trim();
  return {
    icao: rec.icao || rec.icao24,
    callsign: callsign || rec.icao || "—",
    type: rec.type || bucketFromCallsign(callsign),
    lat, lng,
    heading: rec.heading ?? rec.true_track ?? 0,
    velocity: Math.round(rec.velocity ?? 0),   // knots (already converted server-side)
    alt: Math.round(rec.alt ?? rec.baro_altitude ?? 0),
    country: rec.country || rec.origin_country,
  };
}
