// ─────────────────────────────────────────────────────────────────────────────
//  Maritime vessel data — simulated shipping traffic + AISStream parsing.
//
//  Powers the WMT-style live ship-tracking overlay. With no AIS key the app
//  shows a simulated fleet moving along real shipping lanes (chokepoint-heavy);
//  with VITE_AISSTREAM_KEY set, useVesselFeed streams real positions instead.
// ─────────────────────────────────────────────────────────────────────────────
import { haversineKm as _havKm, bearingDeg as _bearDeg } from "./geoAssoc.js";

export const VESSEL_TYPES = {
  cargo:     { label: "Cargo",     color: "#3FA7A0" },
  tanker:    { label: "Tanker",    color: "#C84020" },
  passenger: { label: "Passenger", color: "#4A8FC0" },
  fishing:   { label: "Fishing",   color: "#B07820" },
  other:     { label: "Other",     color: "#8B8B80" },
};

// ─── Shipping lanes (chokepoint-focused) ──────────────────────────────────────
// Each lane is an ordered list of [lng, lat] waypoints.
const LANES = [
  { name: "Bab-el-Mandeb → Suez", bias: "tanker",
    points: [[45.0, 12.5], [43.3, 13.6], [40.5, 16.0], [37.5, 20.0], [35.0, 24.0], [33.5, 27.0], [32.6, 29.9]] },
  { name: "Suez → Gibraltar", bias: "cargo",
    points: [[32.6, 31.2], [29.0, 32.0], [22.0, 34.5], [14.0, 37.0], [5.0, 37.5], [-1.0, 36.1], [-6.5, 36.0]] },
  { name: "Strait of Hormuz", bias: "tanker",
    points: [[50.0, 28.5], [52.0, 27.0], [54.5, 26.3], [56.3, 26.6], [57.5, 25.2], [60.0, 24.0]] },
  { name: "Strait of Malacca", bias: "cargo",
    points: [[98.0, 6.5], [100.0, 3.5], [102.5, 1.8], [103.8, 1.3], [105.0, 2.2], [108.0, 5.0]] },
  { name: "English Channel", bias: "cargo",
    points: [[-5.5, 48.4], [-2.0, 49.5], [0.5, 50.4], [1.6, 50.9], [3.0, 51.3], [4.2, 51.9]] },
  { name: "Panama Approaches", bias: "cargo",
    points: [[-79.9, 9.4], [-79.6, 9.1], [-79.5, 8.95], [-79.3, 8.7], [-78.5, 8.3]] },
  { name: "Trans-Pacific", bias: "cargo",
    points: [[121.5, 31.2], [140.0, 35.0], [165.0, 40.0], [-170.0, 41.0], [-140.0, 38.0], [-122.4, 37.7]] },
  { name: "Trans-Atlantic", bias: "passenger",
    points: [[-74.0, 40.5], [-55.0, 43.5], [-35.0, 47.5], [-15.0, 49.5], [-5.0, 49.0]] },
  { name: "South China Sea", bias: "cargo",
    points: [[114.2, 22.3], [112.0, 17.5], [110.0, 12.5], [107.5, 8.0], [105.0, 3.0]] },
  { name: "Gulf of Aden", bias: "tanker",
    points: [[43.3, 12.6], [47.0, 12.0], [51.0, 11.5], [55.0, 12.5], [60.0, 14.0]] },
];

// ─── Geo helpers ───────────────────────────────────────────────────────────────
// Great-circle math lives once in geoAssoc.js; these are [lng,lat]-array adapters
// over its (lng,lat) scalar core so the lane call sites below stay unchanged.
const haversineKm = ([lng1, lat1], [lng2, lat2]) => _havKm(lng1, lat1, lng2, lat2);
const bearingDeg = ([lng1, lat1], [lng2, lat2]) => _bearDeg(lng1, lat1, lng2, lat2);

// Precompute per-lane segment metrics (cumulative distance + bearing).
const LANE_METRICS = LANES.map((lane) => {
  const segs = [];
  let cum = 0;
  for (let i = 0; i < lane.points.length - 1; i++) {
    const a = lane.points[i], b = lane.points[i + 1];
    const len = Math.max(haversineKm(a, b), 1);
    segs.push({ a, b, start: cum, len, bearing: bearingDeg(a, b) });
    cum += len;
  }
  return { total: cum, segs };
});

// Position [lng,lat] + heading at distance d (km) along a lane (wraps around).
function positionAtDistance(laneIdx, d) {
  const m = LANE_METRICS[laneIdx];
  let dist = ((d % m.total) + m.total) % m.total;
  const seg = m.segs.find((s) => dist >= s.start && dist < s.start + s.len) || m.segs[m.segs.length - 1];
  const f = (dist - seg.start) / seg.len;
  return {
    lng: seg.a[0] + (seg.b[0] - seg.a[0]) * f,
    lat: seg.a[1] + (seg.b[1] - seg.a[1]) * f,
    heading: seg.bearing,
  };
}

// ─── Simulated fleet ───────────────────────────────────────────────────────────
const PREFIX = {
  cargo:     ["MAERSK", "EVERGREEN", "MSC", "COSCO", "HAPAG", "ONE", "CMA CGM", "YANG MING"],
  tanker:    ["FRONT", "NORDIC", "GULF", "STENA", "TORM", "EURONAV", "ADNOC"],
  passenger: ["AURORA", "OCEANIC", "PACIFIC", "NORWEGIAN", "CELEBRITY"],
  fishing:   ["NORTHERN", "SEA", "ATLANTIC", "PACIFIC"],
  other:     ["SURVEYOR", "GUARDIAN", "PIONEER"],
};
const SUFFIX = ["SPIRIT", "STAR", "VOYAGER", "TRADER", "PIONEER", "HORIZON", "EXPRESS", "GLORY", "MARINER", "ENDEAVOR", "SELETAR", "ALTAIR", "MERIDIAN"];

const rand = (a, b) => a + Math.random() * (b - a);
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];

function pickType(bias) {
  const r = Math.random();
  if (r < 0.5) return bias;
  return pick(["cargo", "tanker", "passenger", "fishing", "other"]);
}

// Build static descriptors; positions are computed from elapsed time at render.
export function buildSimVessels(perLane = 6) {
  const vessels = [];
  let n = 0;
  LANES.forEach((lane, laneIdx) => {
    for (let i = 0; i < perLane; i++) {
      const type = pickType(lane.bias);
      vessels.push({
        mmsi: 200000000 + n,
        name: `${pick(PREFIX[type])} ${pick(SUFFIX)}`,
        type,
        laneIdx,
        dist0: rand(0, LANE_METRICS[laneIdx].total),
        speed: rand(4, 11),                 // km/s (exaggerated for a lively demo)
        dir: Math.random() < 0.5 ? 1 : -1,
        sog: Math.round(rand(8, 22)),       // displayed knots
        lane: lane.name,
      });
      n++;
    }
  });
  return vessels;
}

// Resolve a descriptor to a live position at time t (seconds).
export function vesselPosition(v, t) {
  const { lng, lat, heading } = positionAtDistance(v.laneIdx, v.dist0 + v.dir * v.speed * t);
  return { ...v, lng, lat, heading: v.dir > 0 ? heading : (heading + 180) % 360 };
}

// ─── AISStream parsing ──────────────────────────────────────────────────────────
// Map AIS ship-type code ranges → our coarse buckets.
function aisTypeBucket(code) {
  if (code == null) return "other";
  if (code >= 60 && code <= 69) return "passenger";
  if (code >= 70 && code <= 79) return "cargo";
  if (code >= 80 && code <= 89) return "tanker";
  if (code === 30) return "fishing";
  return "other";
}

// Parse an AISStream WebSocket message → vessel object (or null).
export function parseAisMessage(raw) {
  let msg;
  try { msg = typeof raw === "string" ? JSON.parse(raw) : raw; } catch { return null; }
  if (!msg || msg.MessageType !== "PositionReport") return null;

  const meta = msg.MetaData || {};
  const pr = msg.Message?.PositionReport || {};
  const lat = pr.Latitude ?? meta.latitude;
  const lng = pr.Longitude ?? meta.longitude;
  if (lat == null || lng == null) return null;

  const heading = pr.TrueHeading != null && pr.TrueHeading < 360 ? pr.TrueHeading : (pr.Cog ?? 0);
  return {
    mmsi: meta.MMSI ?? pr.UserID,
    name: (meta.ShipName || "").trim() || `MMSI ${meta.MMSI ?? "?"}`,
    type: "other", // PositionReport carries no ship type — enriched from ShipStaticData
    lat, lng,
    heading,
    sog: Math.round(pr.Sog ?? 0),
  };
}

// Parse an AISStream ShipStaticData (type 5) message → { mmsi, type, name }.
// PositionReports lack ship type; this is the only message carrying it.
export function parseAisStatic(raw) {
  let msg;
  try { msg = typeof raw === "string" ? JSON.parse(raw) : raw; } catch { return null; }
  if (!msg || msg.MessageType !== "ShipStaticData") return null;
  const meta = msg.MetaData || {};
  const sd = msg.Message?.ShipStaticData || {};
  const mmsi = meta.MMSI ?? sd.UserID;
  if (mmsi == null) return null;
  return {
    mmsi,
    type: aisTypeBucket(sd.Type),
    name: (meta.ShipName || sd.Name || "").trim() || undefined,
    destination: (sd.Destination || "").trim() || undefined,  // "where it's going" (AIS-reported)
  };
}
