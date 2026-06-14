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

    Promise.all([
      api.get(`/events/${eventId}`),
      api.get(`/graph/event/${eventId}`),
      api.get(`/events/${eventId}/revisions`).catch(() => ({ revisions: [] })),
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
