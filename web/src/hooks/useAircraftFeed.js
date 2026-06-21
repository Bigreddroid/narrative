import { useEffect, useRef, useState, useCallback } from "react";
import { buildSimFlights, flightPosition, parseAircraft } from "../lib/aircraftData.js";
import { DEMO_MODE } from "../lib/demoMode.js";

const BACKEND_URL = "/api/v1/aircraft?lamin=-90&lamax=90&lomin=-180&lomax=180";
const BACKEND_POLL_MS = 15000; // OpenSky anonymous rate limits — poll gently

// Air-traffic feed with graceful source preference:
//   1. backend /api/v1/aircraft  (server-side OpenSky — no CORS, creds hidden)
//   2. simulated fleet           (offline-safe default, shown instantly)
//
// The simulated fleet starts immediately so planes are always visible; if the
// backend returns live data it transparently upgrades. Positions are read each
// render via getAircraft() to keep motion smooth without React re-renders.
export function useAircraftFeed(enabled = true) {
  const simRef     = useRef(null);
  const startRef   = useRef(0);
  const backendRef = useRef([]);
  const sourceRef  = useRef("sim");          // "sim" | "opensky"
  const [live, setLive]               = useState(false);
  const [aircraftCount, setCount]     = useState(0);

  useEffect(() => {
    if (!enabled) {
      backendRef.current = [];
      sourceRef.current = "sim";
      setCount(0);
      setLive(false);
      return;
    }

    let pollTimer, cancelled = false;

    const startSim = () => {
      // Real-only: no fabricated flights outside demo mode. The backend OpenSky
      // source (keyless, anonymous) still upgrades this below when reachable.
      if (!DEMO_MODE) {
        sourceRef.current = "none";
        setLive(false);
        setCount(0);
        return;
      }
      if (!simRef.current) simRef.current = buildSimFlights(6);
      startRef.current = performance.now();
      sourceRef.current = "sim";
      setLive(false);
      setCount(simRef.current.length);
    };

    const ingest = (data) => {
      if (!data || !Array.isArray(data.aircraft) || data.aircraft.length === 0) return false;
      backendRef.current = data.aircraft.map(parseAircraft).filter(Boolean);
      sourceRef.current = "opensky";
      setLive(true);
      setCount(backendRef.current.length);
      return true;
    };

    const probeBackend = async () => {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 3000);
      try {
        const res = await fetch(BACKEND_URL, { signal: ctrl.signal });
        if (!res.ok) return false;
        return ingest(await res.json());
      } catch {
        return false;
      } finally {
        clearTimeout(timer);
      }
    };

    startSim();
    (async () => {
      const usedBackend = await probeBackend();
      if (cancelled || !usedBackend) return;
      pollTimer = setInterval(async () => {
        try {
          const r = await fetch(BACKEND_URL);
          if (!cancelled && r.ok) ingest(await r.json());
        } catch {}
      }, BACKEND_POLL_MS);
    })();

    return () => {
      cancelled = true;
      clearInterval(pollTimer);
    };
  }, [enabled]);

  const getAircraft = useCallback(() => {
    if (sourceRef.current === "opensky") return backendRef.current;
    if (!simRef.current) return [];
    const t = (performance.now() - startRef.current) / 1000;
    return simRef.current.map((f) => flightPosition(f, t));
  }, []);

  return { getAircraft, aircraftCount, live };
}
