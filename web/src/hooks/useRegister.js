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

// GET /context/calendar gatherings → the shape officeContext.festivalsNear already
// consumes (it attaches by proximity, so lat/lng and a date window are all it needs).
//
// `routine: true` is the load-bearing field. Wikidata's dated+located set is
// dominated by scheduled sport, and officeContext.festivalStatus raises an ACTIVE
// festival to ALERT — calibrated for the curated fixture's "Independence Day, Red
// Fort", not for a Tuesday-night ballgame. Letting a regular-season fixture mark an
// office red is precisely the severity inflation this deck exists to beat, so a
// scheduled crowd we cannot size is capped at watch. It is still on the board, and
// still drives derived traffic — it just is not an emergency.
function toGatherings(rows) {
  if (!Array.isArray(rows)) return [];
  return rows
    .filter((g) => g && Number.isFinite(g.lat) && Number.isFinite(g.lng) && g.date)
    .map((g) => ({
      id: `wd-${g.date}-${String(g.name || "").slice(0, 60)}`,
      name: g.name,
      place: g.country || null,
      lat: g.lat,
      lng: g.lng,
      startISO: g.date,
      endISO: g.date,
      routine: true,
      source: g.source || "wikidata",
    }));
}

export default function useRegister({ fallbackSites = [], fallbackTrips = [], enabled = true } = {}) {
  const [state, setState] = useState({
    sites: [], trips: [], audit: null, holidays: {}, countryCodes: {}, noHolidaySource: [], holidayOmitted: [],
    gatherings: [], gatheringsChecked: false, calendarChecked: false,
    source: "loading", reason: null, status: null, error: null, fetchedAt: null,
  });
  const alive = useRef(true);

  const load = useCallback(async () => {
    if (!enabled) {
      setState({
        sites: fallbackSites, trips: fallbackTrips, audit: null,
        holidays: {}, countryCodes: {}, noHolidaySource: [], holidayOmitted: [],
        gatherings: [], gatheringsChecked: false, calendarChecked: false,
        source: "sample", reason: "disabled", status: null, error: null, fetchedAt: new Date(),
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

      // Live public holidays for the register's own countries, keyed by ISO so the
      // deck can attach one to each site. Best-effort for the same reason trips are:
      // Nager.Date being slow must not cost the customer their site board.
      //
      // Gatherings ride the same response. The board used to say outright that no
      // keyless source existed for them; it does (Wikidata, dated + located), so the
      // layer is real now. `gatheringsChecked` is carried separately and deliberately:
      // "we asked and found no crowd near you" and "we never asked" render identically
      // on a calendar, and only one of them is true.
      let holidays = {}, codes = {}, noCoverage = [], omitted = [];
      let gatherings = [], gatheringsChecked = false, calendarChecked = false;
      // 🔴 Not sliced. This used to send the first 20 countries, which silently cut
      // 23 of the register's 43 the moment it stopped being a demo-sized list — and
      // a country whose holiday layer was cut looks exactly like a country with no
      // holidays. The server bounds the list instead, and returns what it dropped.
      const countries = [...new Set((s?.sites ?? [])
        .map((x) => x.country).filter(Boolean))];
      if (countries.length) {
        try {
          const cal = await api.get(
            `/context/calendar?days=60&countries=${encodeURIComponent(countries.join(","))}`,
            { timeoutMs: 15000 });
          holidays = cal?.holidays ?? {};
          codes = cal?.codes ?? {};
          // Countries the holiday SOURCE does not cover (Nager 204s on India
          // and the GCC). Carried through so the board can say so rather than
          // render an empty layer that reads as 'no holidays'.
          noCoverage = cal?.no_source_coverage ?? [];
          // Countries the server's cap dropped. Carried for the same reason as
          // noCoverage: a blank layer must always name its cause.
          omitted = cal?.omitted ?? [];
          gatheringsChecked = cal?.gatherings_checked === true;
          gatherings = toGatherings(cal?.gatherings);
          calendarChecked = true;
        } catch {
          holidays = {};
          codes = {};
          noCoverage = [];
          omitted = [];
          gatherings = [];
          gatheringsChecked = false;
          calendarChecked = false;
        }
      }

      if (!alive.current) return;
      setState({
        sites: s?.sites ?? [],
        trips,
        holidays,
        countryCodes: codes,
        noHolidaySource: noCoverage,
        holidayOmitted: omitted,
        gatherings,
        gatheringsChecked,
        calendarChecked,
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
        holidays: {}, countryCodes: {}, noHolidaySource: [], holidayOmitted: [],
        gatherings: [], gatheringsChecked: false, calendarChecked: false,
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
