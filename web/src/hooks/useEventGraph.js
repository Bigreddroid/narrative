import { useState, useEffect } from "react";
import { api } from "../lib/api.js";

export function useEventGraph(eventId) {
  const [event, setEvent] = useState(null);
  const [graph, setGraph] = useState(null);
  const [revisions, setRevisions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!eventId) return;

    setLoading(true);
    setError(null);

    // These back the flagship /event/:id drill-in and hit LLM-generated
    // consequence maps/graphs — give them real headroom instead of the 3.5s
    // api.js default, which aborts on any cold cache and blanks the page.
    const opts = { timeoutMs: 15000 };
    Promise.all([
      api.get(`/events/${eventId}`, opts),
      api.get(`/graph/event/${eventId}`, opts),
      api.get(`/events/${eventId}/revisions`, opts).catch(() => ({ revisions: [] })),
    ])
      .then(([eventData, graphData, revisionsData]) => {
        setEvent(eventData);
        setGraph(graphData);
        setRevisions(revisionsData.revisions || []);
      })
      .catch((err) => {
        setError(err);
        console.error("Failed to load event graph:", err);
      })
      .finally(() => setLoading(false));
  }, [eventId]);

  return { event, graph, revisions, loading, error };
}
