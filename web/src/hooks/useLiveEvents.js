// ─────────────────────────────────────────────────────────────────────────────
// useLiveEvents — the executive deck's signals come off the live engine.
//
// The site register and the traveller list are sample data until the real campus
// list lands. THE NEWS IS NOT. Every signal on this board is a real event the
// pipeline ingested, geolocated, graded and corroborated — because a security
// product demoed on invented incidents is indistinguishable from a mockup, and the
// whole argument we make to this buyer is that our sourcing is auditable.
//
// So the split is explicit and shown in the banner:
//   sites + travellers  -> sample (synthetic, seeded, labelled)
//   signals             -> live   (GET /events/, refreshed on an interval)
//
// If the backend is unreachable we say so plainly and fall back to the sample
// signal set rather than rendering an empty all-clear board — an all-clear that
// really means "we couldn't reach the engine" is the most dangerous screen a
// security product can show.
//
// Long timeout on purpose: api.js fail-fasts at 3.5s for interactive REST, which is
// too tight for a 100-event page off a cold local stack (see CustomerDeck).
// ─────────────────────────────────────────────────────────────────────────────
import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "../lib/api.js";

const REFRESH_MS = 120_000;   // 2 min — the ingest cadence is 5 min; polling faster buys nothing

export default function useLiveEvents({ limit = 100, fallback = [], enabled = true } = {}) {
  const [state, setState] = useState({
    events: fallback, source: "loading", reason: null, status: null,
    error: null, fetchedAt: null, count: 0,
  });
  const alive = useRef(true);

  const load = useCallback(async () => {
    if (!enabled) {
      setState({ events: fallback, source: "sample", error: null, fetchedAt: new Date(), count: fallback.length });
      return;
    }
    try {
      const data = await api.get(`/events/?limit=${limit}`, { timeoutMs: 15000 });
      const raw = Array.isArray(data) ? data : (data?.events ?? data?.items ?? []);

      // The list payload carries no `source_count` — corroboration is served by its
      // own endpoint. Without this join every live signal would look single-sourced,
      // the two-source gate would reject all of them, and the decision queue would be
      // permanently empty for reasons no one could see. A silent zero is worse than a
      // visible gap, so a signal we could not corroborate keeps source_count
      // UNDEFINED (unknown) rather than being asserted as 1.
      let events = raw;
      if (raw.length) {
        try {
          const ids = raw.map((e) => e.id).join(",");
          const c = await api.get(`/events/corroboration?ids=${ids}`, { timeoutMs: 15000 });
          const map = c?.corroboration || {};
          if (Object.keys(map).length) {
            events = raw.map((e) => (map[e.id] != null ? { ...e, source_count: map[e.id] } : e));
          }
        } catch {
          // Corroboration is an enrichment, not a precondition. Losing it must not
          // take the whole board down with it.
        }
      }
      if (!alive.current) return;
      // An empty live response is a real answer — a quiet world — but it is NOT the
      // same as a dead backend, so it keeps the "live" label and reports zero.
      const corroborated = events.filter((e) => Number(e.source_count) > 0).length;
      setState({
        events, source: "live", reason: null, status: 200, error: null,
        fetchedAt: new Date(), count: events.length, corroborated,
      });
    } catch (err) {
      if (!alive.current) return;
      // Be precise about WHOSE fault it is — "engine unreachable" when the engine
      // answered perfectly well and simply rejected our credentials is a misleading
      // diagnosis, and on a security board a misleading diagnosis is a defect.
      //   0 / 5xx -> no answer (dead API, or the dev proxy could not reach it)
      //   401/403 -> the engine is fine; the session is not
      const s = err?.status;
      const reason = s === 401 || s === 403 ? "unauthenticated"
        : (s === 0 || (s >= 500 && s <= 599)) ? "unreachable"
        : "error";
      setState({
        events: fallback,
        source: "offline",
        reason,
        status: s ?? null,
        error: reason === "unauthenticated" ? "Session expired — sign in to load live signals"
          : reason === "unreachable" ? "Engine not answering"
          : (err?.message || "Feed error"),
        fetchedAt: new Date(),
        count: fallback.length,
      });
    }
  }, [limit, enabled, fallback]);

  useEffect(() => {
    alive.current = true;
    load();
    const t = setInterval(load, REFRESH_MS);
    return () => { alive.current = false; clearInterval(t); };
  }, [load]);

  return { ...state, refresh: load };
}
