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

// The backend scheduler produces fresh events continuously. Re-poll so an
// open tab surfaces new events on its own instead of needing a manual reload.
const POLL_MS = 90000;

export function useEventFeed({ category = null, status = null, limit = 50 } = {}) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    // `background` refreshes (the poll) must not flip the UI back to a loading
    // spinner or blank the list — only the first fetch for these filters does.
    const fetchEvents = (background = false) => {
      const q = new URLSearchParams();
      if (category) q.set("category", category);
      if (status)   q.set("status", status);
      q.set("limit", limit);

      if (!background) setLoading(true);
      // Trailing slash is required: `/events` 307-redirects to `/events/`, and
      // FastAPI emits an absolute Location (the API origin). Cross-origin
      // redirects (dev proxy :5173→:8000, prod Vercel→Railway) strip the
      // Authorization header per the fetch spec, yielding a 401.
      // The main /world feed; a cold DB query can exceed the 3.5s api.js default
      // and abort into an empty feed. Give it headroom.
      return api.get(`/events/?${q}`, { timeoutMs: 12000 })
        .then((data) => {
          if (cancelled) return;
          const raw = Array.isArray(data) ? data : data.events || [];
          setEvents(raw.map(normalizeEvent));
          setError(null);
        })
        .catch((err) => {
          if (cancelled) return;
          if (DEMO_MODE) {
            let mock = MOCK_EVENTS;
            if (category) mock = mock.filter(e => e.category === category);
            if (status)   mock = mock.filter(e => e.current_status === status);
            setEvents(mock.slice(0, limit).map(normalizeEvent));
            return;
          }
          // On a background refresh, keep the events already on screen rather
          // than blanking them on a transient error; only surface the error.
          if (!background) setEvents([]);
          setError(err);
        })
        .finally(() => { if (!background && !cancelled) setLoading(false); });
    };

    fetchEvents(false);
    const id = setInterval(() => fetchEvents(true), POLL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, [category, status, limit]);

  return { events, loading, error };
}
