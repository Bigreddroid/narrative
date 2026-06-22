import { useState, useEffect } from "react";
import { api } from "../lib/api.js";
import { MOCK_EVENTS } from "../lib/mockData.js";
import { DEMO_MODE } from "../lib/demoMode.js";

function normalizeEvent(e) {
  return {
    ...e,
    importance_score: e.importance_score ?? e.global_importance_score ?? 0,
    geography:        e.geography ?? e.geographic_relevance ?? [],
  };
}

export function useEventFeed({ category = null, status = null, limit = 50 } = {}) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const q = new URLSearchParams();
    if (category) q.set("category", category);
    if (status)   q.set("status", status);
    q.set("limit", limit);

    setLoading(true);
    // Trailing slash is required: `/events` 307-redirects to `/events/`, and
    // FastAPI emits an absolute Location (the API origin). Cross-origin
    // redirects (dev proxy :5173→:8000, prod Vercel→Railway) strip the
    // Authorization header per the fetch spec, yielding a 401.
    api.get(`/events/?${q}`)
      .then((data) => {
        const raw = Array.isArray(data) ? data : data.events || [];
        setEvents(raw.map(normalizeEvent));
      })
      .catch((err) => {
        if (DEMO_MODE) {
          let mock = MOCK_EVENTS;
          if (category) mock = mock.filter(e => e.category === category);
          if (status)   mock = mock.filter(e => e.current_status === status);
          setEvents(mock.slice(0, limit).map(normalizeEvent));
          return;
        }
        // Real-only: surface an honest error instead of fabricated events.
        setEvents([]);
        setError(err);
      })
      .finally(() => setLoading(false));
  }, [category, status, limit]);

  return { events, loading, error };
}
