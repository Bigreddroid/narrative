import { useState, useEffect } from "react";
import { api } from "../lib/api.js";
import { MOCK_EVENTS, MOCK_EDGES } from "../lib/mockData.js";
import { DEMO_MODE } from "../lib/demoMode.js";

// Exposure Index feed. Prefers the server-computed model (/api/v1/exposure, where
// the tuned CPE params stay secret). ONLY in the offline demo build does it lazily
// load the engine (./propagation.js) to compute over the mock graph — that import
// is dead-code-eliminated from production builds, so the trade-secret constants
// never ship to real users.
export function useExposure() {
  const [model, setModel]     = useState(null);
  const [loading, setLoading] = useState(true);
  const [live, setLive]       = useState(false);
  const [error, setError]     = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    api.get("/exposure")
      .then((data) => {
        if (cancelled) return;
        if (!data || !Array.isArray(data.sectors)) throw new Error("empty exposure model");
        setModel(data);
        setLive(true);
      })
      .catch(async (err) => {
        if (cancelled) return;
        if (DEMO_MODE) {
          const { computeExposureModel } = await import("../lib/propagation.js");
          if (cancelled) return;
          setModel(computeExposureModel(MOCK_EVENTS, MOCK_EDGES));
          setLive(false);
          return;
        }
        // Real-only: no fabricated model — surface the error.
        setModel(null);
        setError(err);
      })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, []);

  return { model, loading, live, error };
}
