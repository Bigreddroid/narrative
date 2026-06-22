import { useState, useEffect } from "react";
import { api } from "../lib/api.js";

function normalizeEvent(e) {
  return {
    ...e,
    importance_score: e.importance_score ?? e.global_importance_score ?? 0,
    geography: e.geography ?? e.geographic_relevance ?? [],
  };
}

export function useSearch(query) {
  const [results, setResults]   = useState([]);
  const [loading, setLoading]   = useState(false);
  const [error,   setError]     = useState(null);

  useEffect(() => {
    if (!query || query.trim().length < 2) {
      setResults([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    const t = setTimeout(() => {
      // Trailing slash required: `/search` 307-redirects to `/search/` with an
      // absolute Location, and the cross-origin redirect strips the auth header
      // (same failure as the events feed). Call `/search/` directly.
      api.get(`/search/?q=${encodeURIComponent(query.trim())}&limit=30`)
        .then(d => setResults((d.events || []).map(normalizeEvent)))
        .catch(err => {
          setError(err);
          setResults([]);
        })
        .finally(() => setLoading(false));
    }, 300);

    return () => clearTimeout(t);
  }, [query]);

  return { results, loading, error };
}
