import { useState, useEffect } from "react";
import { api } from "../lib/api.js";

// Loads the curated OSINT Framework catalog from the backend (tier-aware: free
// gets a capped taster, paid+ the full set). $0, keyless — the backend serves a
// vendored snapshot. Degrades to an empty catalog with an error flag.
export function useOsintFramework() {
  const [data, setData] = useState({ tools: [], categories: [], templates: {}, limited: false });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    api.get("/osint/framework")
      .then((d) => {
        if (!alive) return;
        setData({
          tools: Array.isArray(d?.tools) ? d.tools : [],
          categories: Array.isArray(d?.categories) ? d.categories : [],
          templates: d?.templates || {},
          limited: !!d?.limited,
          total_available: d?.total_available,
        });
      })
      .catch((err) => { if (alive) setError(err); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  return { ...data, loading, error };
}
