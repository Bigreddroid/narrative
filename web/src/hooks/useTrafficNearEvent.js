import { useMemo } from "react";
import { buildSimVessels, vesselPosition } from "../lib/vesselData.js";
import { buildSimFlights, flightPosition } from "../lib/aircraftData.js";
import { haversineKm, eventRadiusKm } from "../lib/geoAssoc.js";

// Build the simulated fleets once and reuse (counts are a modeled estimate offline).
let _vessels, _flights;
function fleets() {
  if (!_vessels) _vessels = buildSimVessels(6);
  if (!_flights) _flights = buildSimFlights(6);
  return { vessels: _vessels, flights: _flights };
}

// Count ships/planes within an event's impact zone. Returns {vessels, aircraft, radiusKm}.
// Zero when the event has no map coordinates.
export function useTrafficNearEvent(event) {
  const lat = event?.geo_centroid_lat ?? event?.lat;
  const lng = event?.geo_centroid_lng ?? event?.lng;
  const imp = event?.global_importance_score ?? event?.importance_score ?? event?.importance ?? 50;

  return useMemo(() => {
    if (lat == null || lng == null) return { vessels: 0, aircraft: 0, radiusKm: 0 };
    const r = eventRadiusKm({ importance: imp });
    const t = performance.now() / 1000;
    const { vessels, flights } = fleets();
    const inZone = (p) => haversineKm(p.lng, p.lat, lng, lat) <= r;
    const v = vessels.reduce((n, x) => n + (inZone(vesselPosition(x, t)) ? 1 : 0), 0);
    const a = flights.reduce((n, x) => n + (inZone(flightPosition(x, t)) ? 1 : 0), 0);
    return { vessels: v, aircraft: a, radiusKm: Math.round(r) };
  }, [lat, lng, imp]);
}
