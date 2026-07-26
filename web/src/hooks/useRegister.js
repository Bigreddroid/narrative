// ─────────────────────────────────────────────────────────────────────────────
// useRegister — the customer's site register and traveller itineraries, live.
//
// This is the half of the executive deck that used to be invented. Signals were
// always real (useLiveEvents); sites and travellers came from a 214-row fixture
// computed in the browser, so every per-site and per-person number on the board was
// synthetic. GET /sites and GET /people/trips now exist, and this hook reads them.
//
// One rule matters more than the rest, and it is the opposite of the signals rule:
//
//   AN EMPTY REGISTER IS EMPTY. It is never sample data, and it is never all-clear.
//
// useLiveEvents falls back to a sample signal set when the engine is unreachable,
// because an empty board that really means "we could not reach the engine" is the
// most dangerous screen a security product can show. The register inverts that: a
// customer who has uploaded nothing MUST see nothing, because sites they do not have
// cannot be quietly conjured onto a board they will act on. So:
//
//   source "live"    the API answered. These are their sites — even if there are zero.
//   source "sample"  we could not ask (no session, no organization, engine down).
//                    The fixture is shown and the banner says so.
//   source "loading" we do not know yet. The deck renders nothing it cannot stand behind.
//
// 🔴 The load state is EXPLICIT and the caller must gate on it — never on
// `sites.length`. Phase 5's deep-link bug was exactly this: an effect gated on a
// value that was non-empty from first render, so it ran against fallback data,
// failed, and gave up before the real data arrived. A length check here would let
// the board compute on the fixture and then silently disagree with itself.
// ─────────────────────────────────────────────────────────────────────────────
import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "../lib/api.js";

// A register changes when someone edits it, not on a news cadence — so this polls
// far more slowly than the signal feed.
const REFRESH_MS = 600_000; // 10 min

export default function useRegister({ fallbackSites = [], fallbackTrips = [], enabled = true } = {}) {
  const [state, setState] = useState({
    sites: [], trips: [], audit: null,
    source: "loading", reason: null, status: null, error: null, fetchedAt: null,
  });
  const alive = useRef(true);

  const load = useCallback(async () => {
    if (!enabled) {
      setState({
        sites: fallbackSites, trips: fallbackTrips, audit: null, source: "sample",
        reason: "disabled", status: null, error: null, fetchedAt: new Date(),
      });
      return;
    }
    try {
      // 15s, not the 3.5s interactive default: a few hundred rows off a cold local
      // stack routinely exceeds it, and a timeout here reads as "no sites".
      const s = await api.get("/sites", { timeoutMs: 15000 });

      // Itineraries are an enrichment of the register, not a precondition for it.
      // A customer can have sites and no travel programme, and losing the trip call
      // must not take the site board down with it.
      let trips = [];
      try {
        const t = await api.get("/people/trips?window_days=90", { timeoutMs: 15000 });
        trips = t?.trips ?? [];
      } catch {
        trips = [];
      }

      if (!alive.current) return;
      setState({
        sites: s?.sites ?? [],
        trips,
        // The audit travels with the register from the server, so the board can never
        // show the numbers without the caveats that qualify them.
        audit: s?.audit ?? null,
        source: "live", reason: null, status: 200, error: null, fetchedAt: new Date(),
      });
    } catch (err) {
      if (!alive.current) return;
      // Be precise about whose fault it is. "No sites" and "you are not signed in"
      // and "you have no organization yet" are three different screens, and telling
      // a customer the wrong one is itself a defect on a security product.
      const st = err?.status;
      const reason = st === 401 ? "unauthenticated"
        : st === 403 ? "no-organization"
        : (st === 0 || (st >= 500 && st <= 599)) ? "unreachable"
        : "error";
      setState({
        sites: fallbackSites, trips: fallbackTrips, audit: null,
        source: "sample", reason, status: st ?? null,
        error: reason === "unauthenticated" ? "Sign in to load your site register"
          : reason === "no-organization" ? "No organization yet — showing the sample register"
          : reason === "unreachable" ? "Engine not answering"
          : (err?.message || "Register error"),
        fetchedAt: new Date(),
      });
    }
  }, [enabled, fallbackSites, fallbackTrips]);

  useEffect(() => {
    alive.current = true;
    load();
    const t = setInterval(load, REFRESH_MS);
    return () => { alive.current = false; clearInterval(t); };
  }, [load]);

  return { ...state, refresh: load };
}
