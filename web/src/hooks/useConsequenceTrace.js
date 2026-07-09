import { useState, useEffect } from "react";
import { api } from "../lib/api.js";

// Fetches the directed, multi-hop consequence chain FROM an event.
// Backed by GET /graph/event/{id}/trace (deterministic, no LLM) which returns
// { root, nodes[], hops[], limited, depth }. Re-runs when eventId / depth /
// groundedOnly change. Fail-closed: on error we surface nothing rather than a
// fabricated trace (repo real-data convention).
export function useConsequenceTrace(eventId, { depth = 3, groundedOnly = false } = {}) {
  const [trace, setTrace] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!eventId) return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    api
      .get(`/graph/event/${eventId}/trace?depth=${depth}&grounded_only=${groundedOnly}`)
      .then((data) => {
        if (!cancelled) setTrace(data);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err);
        setTrace(null); // no fabricated trace on failure
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [eventId, depth, groundedOnly]);

  return { trace, loading, error };
}
