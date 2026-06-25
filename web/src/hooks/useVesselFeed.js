import { useEffect, useRef, useState, useCallback } from "react";
import { buildSimVessels, vesselPosition, parseAisMessage, parseAisStatic } from "../lib/vesselData.js";
import { DEMO_MODE } from "../lib/demoMode.js";

const AIS_KEY = import.meta.env.VITE_AISSTREAM_KEY;
const AIS_URL = "wss://stream.aisstream.io/v0/stream";
const BACKEND_URL = "/api/v1/vessels?latmin=-90&latmax=90&lonmin=-180&lonmax=180";
const BACKEND_POLL_MS = 60000;

// AISStream bounding boxes ([[latMin,lonMin],[latMax,lonMax]] per box). By
// default we subscribe to the maritime chokepoints the consequence model cares
// about (mirrors backend/feeds/chokepoints.py) — this keeps the live feed
// focused and the globe fluid. Set VITE_AIS_GLOBAL=true to stream every active
// vessel worldwide instead (heavier; raise the render cap in tandem).
const CHOKEPOINT_BOXES = [
  [[24, 53], [29, 59]],     // Strait of Hormuz
  [[27, 31], [33, 35]],     // Suez Canal / N. Red Sea
  [[10, 41], [15, 46]],     // Bab-el-Mandeb
  [[-2, 99], [6, 106]],     // Strait of Malacca / Singapore
  [[6, -82], [12, -77]],    // Panama Canal
  [[39, 27], [43, 31]],     // Bosphorus / Dardanelles
];
const GLOBAL_BOX = [[[-90, -180], [90, 180]]];
const AIS_BOXES = import.meta.env.VITE_AIS_GLOBAL === "true" ? GLOBAL_BOX : CHOKEPOINT_BOXES;

// Maritime vessel feed with graceful source preference:
//   1. backend /api/v1/vessels  (server-side AIS — AISHub/etc, no CORS, creds hidden)
//   2. AISStream WebSocket       (live, when VITE_AISSTREAM_KEY is set)
//   3. simulated fleet           (offline-safe default, shown instantly)
//
// The simulated fleet starts immediately so vessels are always visible; if a
// real source is reachable it transparently upgrades. Positions are read each
// render via getVessels() to keep motion smooth without React re-renders.
export function useVesselFeed(enabled = true) {
  const simRef     = useRef(null);          // simulated descriptors
  const startRef   = useRef(0);             // sim epoch (ms)
  const liveMapRef = useRef(new Map());     // mmsi -> vessel (AISStream)
  const staticRef  = useRef(new Map());     // mmsi -> { type, name } (ShipStaticData)
  const backendRef = useRef([]);            // vessels from backend
  const sourceRef  = useRef("sim");         // "sim" | "aishub" | "aisstream"
  const [live, setLive]               = useState(false);
  const [vesselCount, setVesselCount] = useState(0);

  useEffect(() => {
    if (!enabled) {
      liveMapRef.current = new Map();
      staticRef.current = new Map();
      backendRef.current = [];
      sourceRef.current = "sim";
      setVesselCount(0);
      setLive(false);
      return;
    }

    let ws, countTimer, pollTimer, cancelled = false;

    const startSim = () => {
      // Real-only: never show a fabricated fleet outside explicit demo mode.
      // Real sources (backend AIS / AISStream) still upgrade this below.
      if (!DEMO_MODE) {
        sourceRef.current = "none";
        setLive(false);
        setVesselCount(0);
        return;
      }
      if (!simRef.current) simRef.current = buildSimVessels(6);
      startRef.current = performance.now();
      sourceRef.current = "sim";
      setLive(false);
      setVesselCount(simRef.current.length);
    };

    // 1 — backend AIS source (preferred when it returns data)
    const probeBackend = async () => {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 3000);
      try {
        const res = await fetch(BACKEND_URL, { signal: ctrl.signal });
        if (!res.ok) return false;
        const data = await res.json();
        if (data?.source === "none" || !Array.isArray(data?.vessels) || data.vessels.length === 0) return false;
        backendRef.current = data.vessels;
        sourceRef.current = "aishub";
        setLive(true);
        setVesselCount(data.vessels.length);
        pollTimer = setInterval(async () => {
          try {
            const r = await fetch(BACKEND_URL);
            const d = await r.json();
            if (!cancelled && Array.isArray(d?.vessels)) {
              backendRef.current = d.vessels;
              setVesselCount(d.vessels.length);
            }
          } catch {}
        }, BACKEND_POLL_MS);
        return true;
      } catch {
        return false;
      } finally {
        clearTimeout(timer);
      }
    };

    // 2 — AISStream WebSocket
    const tryLive = () => {
      try { ws = new WebSocket(AIS_URL); }
      catch { return; }
      // AISStream pushes JSON as binary frames; read them as ArrayBuffers so we
      // can decode to text (a Blob would arrive as an object and never parse).
      ws.binaryType = "arraybuffer";
      let opened = false;
      const fallbackTimer = setTimeout(() => { if (!opened) { try { ws.close(); } catch {} } }, 4000);
      ws.onopen = () => {
        opened = true;
        clearTimeout(fallbackTimer);
        sourceRef.current = "aisstream";
        setLive(true);
        ws.send(JSON.stringify({
          APIKey: AIS_KEY,
          BoundingBoxes: AIS_BOXES,
          FilterMessageTypes: ["PositionReport", "ShipStaticData"],
        }));
        countTimer = setInterval(() => { if (!cancelled) setVesselCount(liveMapRef.current.size); }, 1500);
      };
      ws.onmessage = (ev) => {
        // Frames arrive as ArrayBuffer (binaryType above); decode to JSON text.
        const raw = typeof ev.data === "string" ? ev.data : new TextDecoder().decode(ev.data);
        // Position update — enrich type from any known static data for this vessel.
        const v = parseAisMessage(raw);
        if (v && v.mmsi != null) {
          const known = staticRef.current.get(v.mmsi);
          if (known?.type) v.type = known.type;
          v._ts = performance.now();
          liveMapRef.current.set(v.mmsi, v);
          if (liveMapRef.current.size > 600) {
            const cutoff = performance.now() - 120000;
            for (const [k, val] of liveMapRef.current) if (val._ts < cutoff) liveMapRef.current.delete(k);
          }
          return;
        }
        // Static data — record ship type and backfill any live vessel already plotted.
        const s = parseAisStatic(raw);
        if (s && s.mmsi != null) {
          const prev = staticRef.current.get(s.mmsi) || {};
          staticRef.current.set(s.mmsi, { type: s.type || prev.type, name: s.name || prev.name });
          if (staticRef.current.size > 2000) staticRef.current.delete(staticRef.current.keys().next().value);
          const existing = liveMapRef.current.get(s.mmsi);
          if (existing && s.type && s.type !== "other") existing.type = s.type;
        }
      };
    };

    // Start simulated instantly, then try to upgrade to a real source.
    startSim();
    (async () => {
      const usedBackend = await probeBackend();
      if (cancelled || usedBackend) return;
      if (AIS_KEY && (typeof navigator === "undefined" || navigator.onLine !== false)) tryLive();
    })();

    return () => {
      cancelled = true;
      clearInterval(countTimer);
      clearInterval(pollTimer);
      if (ws) { try { ws.onclose = null; ws.close(); } catch {} }
    };
  }, [enabled]);

  const getVessels = useCallback(() => {
    if (sourceRef.current === "aishub") return backendRef.current;
    if (sourceRef.current === "aisstream") return Array.from(liveMapRef.current.values());
    if (!simRef.current) return [];
    const t = (performance.now() - startRef.current) / 1000;
    return simRef.current.map((v) => vesselPosition(v, t));
  }, []);

  return { getVessels, vesselCount, live };
}
