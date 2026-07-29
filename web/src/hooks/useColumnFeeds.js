// ─────────────────────────────────────────────────────────────────────────────
// useColumnFeeds — one server-side query per deck column that has a filter.
//
// The deck used to pull a single top-100-by-importance window and filter it in the
// browser. That made the whole status dimension decorative: all 100 of the top
// events are `escalating`, so the "Escalating" column was a byte-for-byte duplicate
// of "All Signals", while "Developing" and "Stable" rendered EMPTY over a table
// holding 30,255 developing events. A column that silently shows a slice of a slice
// is worse than no column — the reader has no way to tell that "0" means "none in
// the top 100" rather than "none exist".
//
// So each filtered column asks the API for its own set. /events/ already supports
// ?status=, ?category= and ?discipline=, and does the ranking server-side over the
// whole table rather than over whatever happened to be in one window.
//
// Unfiltered ("all") and profile-ranked ("lens") columns are NOT fetched here: they
// legitimately operate on the shared feed the deck already holds.
// ─────────────────────────────────────────────────────────────────────────────
import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api.js";

const PARAM = { status: "status", category: "category", discipline: "discipline" };

// Identity of the QUERY, not of the column. Two columns filtering on the same thing
// share one request, and reordering or renaming a column does not refetch.
export const columnKey = (col) =>
  PARAM[col?.kind] ? `${col.kind}:${String(col.value ?? "").toLowerCase()}` : null;

export function useColumnFeeds(columns, { limit = 100 } = {}) {
  const [byKey, setByKey] = useState({});      // key -> { events, loading, error }
  const inFlight = useRef(new Set());

  const keys = columns.map(columnKey).filter(Boolean);
  const signature = [...new Set(keys)].sort().join("|");

  useEffect(() => {
    const wanted = [...new Set(signature ? signature.split("|") : [])];

    for (const key of wanted) {
      if (inFlight.current.has(key)) continue;
      const [kind, value] = [key.slice(0, key.indexOf(":")), key.slice(key.indexOf(":") + 1)];
      inFlight.current.add(key);
      setByKey((m) => (m[key] ? m : { ...m, [key]: { events: [], loading: true, error: null } }));

      const q = new URLSearchParams({ [PARAM[kind]]: value, limit: String(limit) });
      // Same headroom as the main feed: a cold DB query can exceed the 3.5s
      // api.js default and abort into an empty column, which would read as
      // "nothing matches" — the exact lie this hook exists to remove.
      api.get(`/events/?${q}`, { timeoutMs: 12000 })
        .then((data) => {
          const raw = Array.isArray(data) ? data : data?.events || [];
          setByKey((m) => ({ ...m, [key]: { events: raw, loading: false, error: null } }));
        })
        .catch((err) => {
          // An error must NOT leave an empty list that renders as a real zero.
          setByKey((m) => ({ ...m, [key]: { events: [], loading: false, error: err } }));
        })
        .finally(() => { inFlight.current.delete(key); });
    }
    // NO per-run "cancelled" flag, deliberately. StrictMode double-invokes effects:
    // run #1 starts the fetches and registers them in inFlight, cleanup marks that
    // run cancelled, run #2 sees the keys already in flight and skips — then run #1's
    // results arrive and a cancelled-guard would DISCARD them, with nothing left to
    // refetch. Every column stuck on "Loading…" forever, over an API answering 200.
    // Results are keyed by the FILTER, not by a component instance, so a late result
    // is still the right answer for that key and is safe to keep.
  }, [signature, limit]);

  return byKey;
}

export default useColumnFeeds;
