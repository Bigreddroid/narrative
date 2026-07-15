// Frontend mirror of backend/taxonomy.py. The backend serves the authoritative
// copy at GET /api/v1/meta/taxonomy; useTaxonomy() fetches it and falls back to
// this checked-in mirror if the request fails (offline/first paint). Keep the
// DISCIPLINES list in sync with the backend — it's small and rarely changes.
import { useEffect, useState } from "react";
import { api } from "./api.js";

// The 7 intelligence disciplines (multi-INT). Order = display order.
export const DISCIPLINES = [
  "HUMINT", "SIGINT", "IMINT", "GEOINT", "MASINT", "FININT", "CYBINT",
];

// Short human labels for the discipline chips/columns.
export const DISCIPLINE_LABELS = {
  HUMINT: "HUMINT", SIGINT: "SIGINT", IMINT: "IMINT", GEOINT: "GEOINT",
  MASINT: "MASINT", FININT: "FININT", CYBINT: "CYBINT",
};

// One-line "what it is" tooltips — used on the discipline dashboard/badges so the
// $0 ceiling is stated honestly (SIGINT = emitter tracking only, etc.).
export const DISCIPLINE_BLURB = {
  HUMINT: "Human-sourced reporting — news, OSINT posts, graded by reliability.",
  SIGINT: "Emitter tracking — ADS-B aircraft + AIS vessel transponders (no RF).",
  IMINT:  "Imagery interpretation of provided photos (no satellite tasking).",
  GEOINT: "Geospatial — geolocation + mapping of existing signals.",
  MASINT: "Measurement & signature — seismic, space-weather, multi-hazard.",
  FININT: "Financial — markets, FX, VIX, sanctions, on-chain.",
  CYBINT: "Cyber — CVEs, ransomware, threat-intel enrichment.",
};

const FALLBACK = {
  disciplines: DISCIPLINES,
  categories: [
    "disaster", "wildfire", "storm", "flood", "drought", "volcano",
    "conflict", "unrest", "cyber", "sanction", "space", "market", "disinfo",
  ],
};

let _cache = null; // module-level cache so the fetch happens once per session.

// Hook: returns { disciplines, categories, loading }. Non-blocking — renders the
// mirror immediately, then swaps in the served copy when it arrives.
export function useTaxonomy() {
  const [tax, setTax] = useState(_cache || FALLBACK);
  useEffect(() => {
    if (_cache) return;
    let alive = true;
    api.get("/meta/taxonomy")
      .then((d) => {
        if (!d || !Array.isArray(d.disciplines)) return;
        _cache = d;
        if (alive) setTax(d);
      })
      .catch(() => { /* keep the mirror */ });
    return () => { alive = false; };
  }, []);
  return { ...tax, loading: !_cache };
}
