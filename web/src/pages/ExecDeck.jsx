// ─────────────────────────────────────────────────────────────────────────────
//  ExecDeck — the C-suite command surface (/wipro/exec)
//
//  Answers "are we OK?" and drills into the evidence behind every figure.
//  Deliberately NOT a denser analyst deck: exposure-first, people not sites,
//  situations not rows, deltas not state, and what we HELD shown beside what we
//  escalated — the only honest answer to "what did you miss?".
//
//  DATA SPLIT — deliberate, and stated in the banner:
//    sites + travellers  ->  sample (synthetic, seeded, labelled) until the real
//                            campus register lands
//    signals             ->  LIVE, off the engine (GET /events/)
//  Demoing a security product on invented incidents is indistinguishable from a
//  mockup. The news is real; only the customer's own asset list is stand-in.
//
//  RULE FOR THIS FILE: every control does something real. No placeholder buttons,
//  no panels of sample prose. Each view computes from data we actually hold
//  (214 sites, 42 itineraries, live graded signals, holidays, festivals) through the
//  pure libs — officeContext · execPosture · registryAudit · domainScore · severity ·
//  deckFilters — which carry 367 assertions between them. Capabilities we cannot
//  compute (mass-comms delivery) are absent rather than faked.
// ─────────────────────────────────────────────────────────────────────────────
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { officeContext, topSignal, LAYER_KEYS, LAYER_LABELS } from "../lib/officeContext.js";
import { haversineKm as _havKm } from "../lib/geoAssoc.js";
import {
  exposure, delta, decisionQueue, suppression, travelPosture, forward, snapshot,
  SUPPRESSION_REASONS,
} from "../lib/execPosture.js";
import { auditRegister } from "../lib/registryAudit.js";
import { domainScores, overallScore, countryProfile, bandFor } from "../lib/domainScore.js";
import {
  SEVERITY, ALERT_TYPES, classify, activeOnly, levelOfBand,
} from "../lib/severity.js";
import {
  emptyFilters, toggleValue, clearAll, clearDimension, countActive, hasAnyFilter,
  applyFilters, facets,
} from "../lib/deckFilters.js";
import useLiveEvents from "../hooks/useLiveEvents.js";
import ExecGlobe, { SEV } from "../components/exec/ExecGlobe.jsx";
import FilterBar from "../components/exec/FilterBar.jsx";
import DataTable from "../components/exec/DataTable.jsx";
import SignalDrawer from "../components/exec/SignalDrawer.jsx";
import * as SAMPLE from "../data/customers/wipro.exec.sample.js";

const haversineKm = (lat1, lng1, lat2, lng2) => _havKm(lng1, lat1, lng2, lat2);
const n = (x) => (x ?? 0).toLocaleString("en-US");
const VIEWS = ["Overview", "Sites", "People", "Countries", "Calendar"];

const rise = (i = 0) => ({
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.45, delay: 0.04 * i, ease: [0.22, 1, 0.36, 1] },
});

function Band({ label, note, children, right }) {
  return (
    <section className="border-t border-[#1C1C1C]">
      <div className="px-6 lg:px-10 pt-5 pb-2 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h2 className="font-mono text-[10px] tracking-[0.22em] uppercase text-[#8A8A82]">{label}</h2>
        {note && <p className="text-[11px] text-[#5A5A55] max-w-2xl leading-snug flex-1">{note}</p>}
        {right}
      </div>
      {children}
    </section>
  );
}

function Grade({ grade }) {
  if (!grade) return null;
  const strong = /^[AB][12]$/.test(grade);
  return (
    <span title={`NATO-Admiralty ${grade} — source reliability ${grade[0]}, information credibility ${grade[1]}`}
      className="font-mono text-[10px] px-1.5 py-0.5 border rounded-[2px]"
      style={{ color: strong ? "#5FBF74" : "#E0A93C", borderColor: strong ? "rgba(95,191,116,.4)" : "rgba(224,169,60,.4)" }}>
      {grade}
    </span>
  );
}

function ScoreBar({ score }) {
  const b = bandFor(score);
  return (
    <span className="inline-flex items-center gap-2">
      <span className="font-mono text-[11px] tabular-nums w-6 text-right" style={{ color: b.color }}>
        {score.toFixed(1)}
      </span>
      <span className="w-16 h-1.5 bg-[#1C1C1C] rounded-[1px] overflow-hidden inline-block">
        <span className="block h-full rounded-[1px]" style={{ width: `${(score / 5) * 100}%`, background: b.color }} />
      </span>
    </span>
  );
}

// ── Register columns ─────────────────────────────────────────────────────────
// Each column declares how it RENDERS and how it SORTS separately. The severity
// column renders a coloured word and sorts on the underlying 0–5 score, so the
// register ranks correctly instead of alphabetically by band name.
const SITE_COLUMNS = [
  {
    key: "name", label: "Site", defaultDir: "asc",
    value: (r) => r.office.name,
    render: (r) => (
      <span className="flex items-center gap-2 min-w-0">
        <span className="w-1 h-5 shrink-0" style={{ background: SEV[r.ctx.worst].c }} />
        <span className="truncate">{r.office.name}</span>
      </span>
    ),
  },
  { key: "city", label: "City", defaultDir: "asc", value: (r) => r.office.city },
  { key: "country", label: "Country", defaultDir: "asc", value: (r) => r.office.country },
  { key: "type", label: "Type", defaultDir: "asc", value: (r) => r.office.type },
  { key: "crit", label: "Criticality", defaultDir: "asc", value: (r) => r.office.criticality },
  {
    key: "people", label: "People", align: "right", mono: true,
    value: (r) => r.office.headcount,
    render: (r) => n(r.office.headcount),
  },
  {
    key: "score", label: "Severity",
    value: (r) => r.band.label,
    sortValue: (r) => r.overall.score,
    csvValue: (r) => `${r.band.label} (${r.overall.score.toFixed(1)})`,
    render: (r) => (
      <span className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.08em]">
        <span style={{ color: r.band.color }}>{r.band.label}</span>
        <span className="tabular-nums text-[#5A5A55]">{r.overall.score.toFixed(1)}</span>
      </span>
    ),
  },
  {
    key: "driver", label: "Driven by",
    value: (r) => r.overall.driver?.label ?? "—",
    render: (r) => <span className="text-[#8A8A82]">{r.overall.driver?.label ?? "—"}</span>,
  },
];

// Organisational risk tolerance. This is a POSTURE, set once by the security team,
// not a control on the briefing surface — see components/exec/FilterBar.jsx for why
// the slider that used to live here was removed.
const ORG_TOLERANCE = 50;
const TOLERANCE_WORD = ORG_TOLERANCE <= 33 ? "Cautious" : ORG_TOLERANCE >= 67 ? "Tolerant" : "Balanced";
const DAY_MS = 86_400_000;

export default function ExecDeck() {
  const [view, setView] = useState("Overview");
  const [filters, setFilters] = useState(emptyFilters());
  const [selected, setSelected] = useState(null);   // site id
  const [signal, setSignal] = useState(null);       // event object open in the drawer
  const [mapFilter, setMapFilter] = useState(null); // "alert" | "watch" | "clear" | null
  const [query, setQuery] = useState("");

  const appetite = ORG_TOLERANCE;

  // Signals are LIVE. Sites and itineraries are sample until the real register
  // lands. If the engine is unreachable we fall back to the sample signal set and
  // say so — an all-clear board that actually means "we couldn't reach the engine"
  // is the most dangerous screen a security product can show.
  const feed = useLiveEvents({ limit: 100, fallback: SAMPLE.SAMPLE_EVENTS });

  // Most rows carry only an event ID (domainScore projects evidence down to
  // {id,title,km}; suppression rows embed it in the row id). The drawer needs the whole
  // event, so resolve through the feed we already hold rather than refetching per row.
  const eventById = useMemo(() => {
    const m = new Map();
    for (const e of feed.events || []) m.set(String(e.id), e);
    return m;
  }, [feed.events]);
  // Opens the drawer for an id, and does NOTHING if the event isn't in the current feed
  // — better a dead click than a drawer full of blanks pretending to be a record.
  const openSignal = (id) => {
    const e = id != null && eventById.get(String(id));
    if (e) setSignal(e);
  };
  const isLive = feed.source === "live";
  const today = useMemo(
    () => (isLive ? (feed.fetchedAt || new Date()) : SAMPLE.SAMPLE_TODAY),
    [isLive, feed.fetchedAt],
  );

  const model = useMemo(() => {
    // Expired signals never reach a count. A month-old protest sitting on the board
    // is how a feed loses an executive's trust (lib/severity.js).
    const events = activeOnly(feed.events, today);
    const base = {
      festivals: SAMPLE.SAMPLE_FESTIVALS, holidaysByCode: SAMPLE.SAMPLE_HOLIDAYS,
      countryCodes: SAMPLE.SAMPLE_COUNTRY_CODES, curatedHolidays: {},
      appetite, today,
    };
    const contexts = SAMPLE.SAMPLE_SITES.map((o) => officeContext(o, { ...base, events }));

    // "Since your last look" needs a real prior. On live data that is the board as
    // it stood 24h ago — the same sites scored against only the signals we already
    // had then. On the sample set it is the curated prior fixture.
    const priorEvents = isLive
      ? events.filter((e) => {
          const t = Date.parse(e.first_detected_at || e.created_at);
          return Number.isFinite(t) && t < today.getTime() - DAY_MS;
        })
      : SAMPLE.SAMPLE_EVENTS_PRIOR;
    const prior = snapshot(SAMPLE.SAMPLE_SITES.map((o) => officeContext(o, { ...base, events: priorEvents })));

    const geoEvents = events.filter((e) => e.geo_centroid_lat != null);
    const travel = travelPosture(SAMPLE.SAMPLE_TRIPS, geoEvents, { appetite, today, haversineKm });
    const queue = decisionQueue(contexts, travel, { appetite, limit: 3 });
    const held = suppression(contexts, { appetite, escalatedEventIds: new Set(queue.items.map((i) => i.event.id)) });

    // Every site carries its own 0–5 domain scores and banded overall, computed once
    // so the table, the globe and the filter facets can never disagree.
    const siteRows = contexts.map((c) => {
      const scores = domainScores(c, { appetite });
      const overall = overallScore(scores);
      return { ctx: c, office: c.office, scores, overall, band: overall.band, top: topSignal(c) };
    });

    return {
      events, contexts, siteRows, travel, queue, held,
      exp: exposure(contexts),
      change: delta(contexts, prior),
      ahead: forward(contexts, { today, windowDays: 60 }),
      audit: auditRegister(SAMPLE.SAMPLE_SITES, { countryCodes: SAMPLE.SAMPLE_COUNTRY_CODES }),
      byId: new Map(contexts.map((c) => [c.office.id, c])),
    };
  }, [feed.events, isLive, today, appetite]);

  const { events, exp, change, queue, held, travel, ahead, contexts, siteRows, audit, byId } = model;

  // ── Filter dimensions, per view ────────────────────────────────────────────
  // Keys are namespaced, so one filter object serves every view without collision;
  // each view simply declares which dimensions it understands.
  const SITE_DIMS = useMemo(() => [
    { key: "band", label: "Severity", values: (r) => r.band.key,
      options: [...SEVERITY].reverse().map((s) => ({ value: s.key, label: s.label, color: s.color })) },
    { key: "domain", label: "Domain", values: (r) => r.overall.driver?.key ?? null },
    { key: "country", label: "Country", values: (r) => r.office.country },
    { key: "type", label: "Site type", values: (r) => r.office.type },
    { key: "crit", label: "Criticality", values: (r) => r.office.criticality },
  ], []);

  const TRAVEL_DIMS = useMemo(() => [
    { key: "verdict", label: "Verdict", values: (r) => r.verdict },
    { key: "dest", label: "Destination", values: (r) => r.trip?.country ?? r.country ?? null },
  ], []);


  // Free-text search composes with the filters rather than replacing them.
  const q = query.trim().toLowerCase();
  const searched = useMemo(() => (!q ? siteRows : siteRows.filter((r) =>
    r.office.name.toLowerCase().includes(q) || r.office.city.toLowerCase().includes(q)
    || r.office.country.toLowerCase().includes(q))), [siteRows, q]);

  const visibleRows = useMemo(() => applyFilters(searched, filters, SITE_DIMS), [searched, filters, SITE_DIMS]);
  const visibleContexts = useMemo(() => visibleRows.map((r) => r.ctx), [visibleRows]);
  const travelRows = useMemo(() => applyFilters(travel.trips || [], filters, TRAVEL_DIMS), [travel, filters, TRAVEL_DIMS]);

  const facetList = useMemo(
    () => (view === "People" ? facets(travel.trips || [], filters, TRAVEL_DIMS) : facets(searched, filters, SITE_DIMS)),
    [view, travel, searched, filters, SITE_DIMS, TRAVEL_DIMS],
  );
  const shown = view === "People" ? travelRows.length : visibleRows.length;
  const totalRows = view === "People" ? (travel.trips || []).length : searched.length;

  // Countries recompute from what is actually visible, so a filtered board's country
  // table agrees with its map instead of quietly reporting the unfiltered world.
  const countries = useMemo(() => countryProfile(visibleContexts, { appetite }), [visibleContexts, appetite]);

  const matchSites = visibleRows;
  const posture = change.net > 0 ? { label: "Deteriorating", c: "#FF5C43" }
    : change.net < 0 ? { label: "Improving", c: "#5FBF74" }
    : { label: "Stable", c: "#E0A93C" };
  const sel = selected ? byId.get(selected) : null;

  const onToggle = (dim, value) => setFilters((f) => toggleValue(f, dim, value));
  const activeCount = countActive(filters);

  return (
    <div className="min-h-screen bg-[#050505] text-[#F0EDE8]">
      <style>{`@media print{.no-print{display:none!important}body{background:#fff}}`}</style>

      {/* ── Provenance bar ───────────────────────────────────────────────────
          The split is the honest part: the SIGNALS are live off the engine, the
          ASSET REGISTER is sample until the real campus list lands. Stating which
          half is which is the whole reason this bar exists. */}
      <div className="border-b px-6 lg:px-10 py-2 flex flex-wrap items-center gap-x-4 gap-y-1 no-print"
        style={{
          borderColor: isLive ? "rgba(95,191,116,0.22)" : "rgba(200,0,40,0.30)",
          background: isLive ? "rgba(95,191,116,0.05)" : "rgba(200,0,40,0.08)",
        }}>
        <span className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full"
            style={{ background: isLive ? "#5FBF74" : feed.source === "loading" ? "#E0A93C" : "#FF5C43" }} />
          <span className="font-mono text-[10px] tracking-[0.2em] uppercase"
            style={{ color: isLive ? "#5FBF74" : "#FF7A63" }}>
            {isLive ? "Live signals"
              : feed.source === "loading" ? "Connecting"
              : feed.reason === "unauthenticated" ? "Not signed in"
              : "Engine not answering"}
          </span>
        </span>
        <span className="text-[11px] text-[#8A8A82] tabular-nums">
          {isLive
            ? <>{feed.count} ingested · <span className="text-[#F0EDE8]">{events.length}</span> in force · {feed.fetchedAt?.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</>
            : <>{feed.error || "…"} — showing the sample signal set so the board is never falsely all-clear</>}
        </span>
        <span className="text-[11px] text-[#5A5A55]">
          Sites and itineraries are sample data; signals are not.
        </span>
        <button type="button" onClick={feed.refresh}
          className="font-mono text-[10px] tracking-[0.14em] uppercase text-[#6A6A64] hover:text-[#F0EDE8] border border-[#242424] px-2 py-0.5 rounded-[2px]">
          Refresh
        </button>
      </div>

      {/* ── Header ───────────────────────────────────────────────────────────── */}
      <header className="px-6 lg:px-10 pt-7">
        <p className="font-mono text-[10px] tracking-[0.28em] uppercase text-[#6A6A64]">
          Wipro · Global Security · {today.toISOString().slice(0, 10)}
        </p>
        <h1 className="font-display leading-[0.85] tracking-tight mt-2" style={{ fontSize: "clamp(2.6rem, 6vw, 4.6rem)" }}>
          EXECUTIVE <span className="text-crimson-light">DECK</span>
        </h1>

        <div className="mt-5 flex flex-wrap items-center gap-x-6 gap-y-3 no-print">
          <nav className="flex gap-px bg-[#1C1C1C] rounded-[2px] overflow-hidden">
            {VIEWS.map((v) => (
              <button key={v} type="button" onClick={() => setView(v)}
                className="px-4 py-2 font-mono text-[10px] tracking-[0.14em] uppercase transition-colors"
                style={{ background: view === v ? "#1F1F1F" : "#0A0A0A", color: view === v ? "#F0EDE8" : "#6A6A64" }}>
                {v}
              </button>
            ))}
          </nav>

          <input value={query} onChange={(e) => setQuery(e.target.value)}
            placeholder="Search sites, cities, countries…"
            className="bg-[#0E0E0E] border border-[#242424] rounded-[2px] px-3 py-1.5 text-[12px] w-56 focus:outline-none focus:border-[#3A3A3A]" />

          <button type="button" onClick={() => window.print()}
            className="font-mono text-[10px] tracking-[0.14em] uppercase text-[#8A8A82] border border-[#242424] px-3 py-2 rounded-[2px] hover:text-[#F0EDE8] hover:border-[#3A3A3A]">
            Print brief
          </button>

          {/* Tolerance is a stated organisational posture, not a dial to drag during
              a briefing. It still sets every threshold on the board. */}
          <span className="font-mono text-[10px] tracking-[0.14em] uppercase text-[#5A5A55] ml-auto"
            title="Organisational risk tolerance — a settings-level posture, held constant for the duration of a briefing so the board you read is the board that was assessed.">
            Tolerance · <span className="text-[#B8B5AE]">{TOLERANCE_WORD}</span>
          </span>
        </div>
      </header>

      {/* ── Filters ──────────────────────────────────────────────────────────── */}
      <div className="mt-6">
        <FilterBar
          facets={facetList}
          activeCount={activeCount}
          shown={shown}
          total={totalRows}
          onToggle={onToggle}
          onClearDimension={(k) => setFilters((f) => clearDimension(f, k))}
          onClearAll={() => setFilters(clearAll())}
          note={hasAnyFilter(filters)
            ? "Filters change what you see. Nothing is re-scored — the assessment underneath is unchanged."
            : "Counts show what each filter would return, with every other filter still applied."}
        />
      </div>

      {/* ══ OVERVIEW ═════════════════════════════════════════════════════════ */}
      {view === "Overview" && (
        <motion.div {...rise(0)}>
          <section className="grid lg:grid-cols-2 items-center gap-2 px-6 lg:px-10 pt-6 pb-2">
            <div>
              <div className="grid grid-cols-2 gap-x-8 gap-y-6 max-w-lg">
                {[
                  { v: queue.total, l: "situations need a decision", c: "#FF5C43" },
                  { v: n(exp.peopleExposed), l: `of ${n(exp.people)} people exposed` },
                  { v: `${exp.countriesAffected}/${exp.countries}`, l: "countries affected" },
                  { v: travel.unaccounted.length, l: "travellers unaccounted for", c: travel.unaccounted.length ? "#FF5C43" : "#5FBF74" },
                ].map((t) => (
                  <div key={t.l}>
                    <div className="font-display leading-none tabular-nums" style={{ fontSize: "clamp(2rem,3.4vw,3.2rem)", color: t.c || "#F0EDE8" }}>{t.v}</div>
                    <div className="font-mono text-[10px] tracking-[0.14em] uppercase text-[#8A8A82] mt-2">{t.l}</div>
                  </div>
                ))}
              </div>
              <div className="mt-7 pt-5 border-t border-[#1C1C1C] flex flex-wrap items-center gap-x-6 gap-y-3">
                <span className="font-display text-[1.5rem] leading-none" style={{ color: posture.c }}>{posture.label}</span>
                <span className="font-mono text-[10px] tracking-[0.12em] uppercase text-[#6A6A64]">
                  vs last look · {change.deteriorated.length} worse, {change.improved.length} better
                </span>
              </div>
              {/* Map key. Filtering lives in the bar above — five bands there, three
                  colours here, because 214 dots cannot carry five hues legibly.
                  Counts follow the filtered view so the key never contradicts the map. */}
              {/* These chips carry the same border, dot, count and uppercase label as the
                  real filter chips in the bar above, so they read as controls. They were
                  inert — the most misleading affordance on the page. ExecGlobe already
                  accepted a `filter` prop that nothing was driving; now they drive it.
                  Click again to clear. This dims the MAP only and never touches the
                  assessment or the counts. */}
              <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2">
                {["alert", "watch", "clear"].map((k) => {
                  const count = visibleContexts.filter((c) => c.worst === k).length;
                  const on = mapFilter === k;
                  return (
                    <button
                      key={k} type="button"
                      onClick={() => setMapFilter(on ? null : k)}
                      aria-pressed={on}
                      disabled={count === 0 && !on}
                      title={count === 0 && !on ? `No ${SEV[k].label} sites in view`
                        : on ? "Show all sites on the map" : `Show only ${SEV[k].label} sites on the map`}
                      className={[
                        "flex items-center gap-1.5 px-2 py-1 rounded-[2px] border transition-colors",
                        count === 0 && !on ? "border-[#1A1A1A] cursor-default opacity-50"
                          : on ? "border-[#6A6A64] bg-[#141414]" : "border-[#242424] hover:border-[#4A4A47]",
                      ].join(" ")}
                    >
                      <span className="w-2 h-2 rounded-full" style={{ background: SEV[k].c }} />
                      <span className="font-mono text-[10px] tabular-nums text-[#B8B5AE]">{count}</span>
                      <span className="font-mono text-[10px] tracking-[0.1em] uppercase text-[#6A6A64]">{SEV[k].label}</span>
                    </button>
                  );
                })}
                {mapFilter ? (
                  <button type="button" onClick={() => setMapFilter(null)}
                    className="font-mono text-[9px] self-center tracking-[0.1em] uppercase text-[#C80028] hover:underline">
                    Showing {SEV[mapFilter].label} only · show all
                  </button>
                ) : (
                  <span className="font-mono text-[9px] text-[#3A3A38] self-center tracking-[0.1em] uppercase">
                    Extreme + High = Alert · Moderate = Watch · Low + Minimal = Clear
                  </span>
                )}
              </div>
            </div>

            <ExecGlobe contexts={visibleContexts} topSignalOf={topSignal} filter={mapFilter}
              selectedId={selected} onSelect={(c) => { setSelected(c.office.id); setView("Sites"); }} />
          </section>

          <Band label="All eight layers"
            note="Nothing is hidden: every domain we carry, scored 0–5 across the whole estate, with the site driving it. A quiet layer reads 0 because nothing was found — never because it wasn't checked.">
            <LayerStrip contexts={visibleContexts} appetite={appetite}
              onPick={(id) => { setSelected(id); setView("Sites"); }} />
          </Band>

          <Band label="Needs a decision"
            note="Grouped by situation, not by building. Every item clears the same bar: a real incident, above your threshold, carried by at least two independent sources."
            right={<span className="font-mono text-[10px] text-[#5A5A55] tabular-nums">{queue.items.length} of {queue.total}</span>}>
            {queue.items.length === 0 ? (
              <p className="px-6 lg:px-10 pb-8 pt-2 text-[12px] text-[#5A5A55]">
                Nothing clears the escalation bar at this appetite. Everything considered is in the held list below, with its reason.
              </p>
            ) : (
              <div className="grid lg:grid-cols-3 gap-px bg-[#1C1C1C] mt-3">
                {queue.items.map((it) => (
                  <article key={it.id} className="bg-[#0A0A0A] p-6 border-t-2" style={{ borderColor: "#FF5C43" }}>
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="font-mono text-[10px] tracking-[0.16em] uppercase text-[#8A8A82]">
                        {it.orgScope ? "Organisation" : it.cities[0] || "Multiple"}
                      </span>
                      <span className="font-mono text-[10px]" style={{ color: SEV.alert.c }}>Alert</span>
                    </div>
                    <div className="font-display leading-none tabular-nums mt-3" style={{ fontSize: "clamp(2rem,3.2vw,2.8rem)" }}>
                      {it.orgScope ? <span className="text-[#5A5A55]">—</span> : n(it.people)}
                    </div>
                    <div className="font-mono text-[10px] tracking-[0.14em] uppercase text-[#8A8A82] mt-1.5">
                      {it.orgScope ? "not yet scoped" : "people"}
                    </div>
                    {/* The card's headline is the way into the evidence. It used to be
                        inert text on a card that looked entirely clickable — the single
                        most misleading affordance on the page. */}
                    {it.event ? (
                      <button
                        type="button"
                        onClick={() => setSignal(it.event)}
                        className="block w-full text-left text-[14px] leading-snug mt-5 hover:text-[#F0EDE8] text-[#E8E4DC] group"
                      >
                        {it.why}
                        <span className="font-mono text-[10px] text-[#6A6A64] group-hover:text-crimson-light ml-1.5">
                          — sources ↗
                        </span>
                      </button>
                    ) : (
                      <h3 className="text-[14px] leading-snug mt-5">{it.why}</h3>
                    )}
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 mt-3">
                      <Grade grade={it.grade} />
                      <span className="font-mono text-[10px] text-[#6A6A64]">{it.sources} sources</span>
                      <span className="font-mono text-[10px] text-[#6A6A64]">
                        {it.orgScope ? "no distance claimed"
                          : `${it.siteCount} site${it.siteCount === 1 ? "" : "s"} in range${it.travellerCount ? ` · ${it.travellerCount} travelling` : ""}`}
                      </span>
                    </div>
                    {it.consequence && <p className="text-[12px] text-[#B8B5AE] leading-relaxed mt-4 pl-3 border-l border-[#2A2A2A]">{it.consequence}</p>}
                    {it.recommend && (
                      <p className="text-[12px] mt-3">
                        <span className="font-mono text-[9px] tracking-[0.18em] uppercase text-[#6A6A64] block mb-1">Recommend</span>
                        <span>{it.recommend}</span>
                      </p>
                    )}
                    {it.topSites?.length > 0 && (
                      <div className="mt-4 pt-3 border-t border-[#1C1C1C] flex flex-wrap gap-x-3 gap-y-1 no-print">
                        {it.topSites.map((s) => (
                          <button key={s.office.id} type="button"
                            onClick={() => { setSelected(s.office.id); setView("Sites"); }}
                            className="font-mono text-[10px] text-[#6A6A64] hover:text-crimson-light underline decoration-dotted">
                            {s.office.name}
                          </button>
                        ))}
                      </div>
                    )}
                  </article>
                ))}
              </div>
            )}
          </Band>

          {/* Framing matters here more than anywhere else on the board.
              "What we held back" reads as "we filtered your intelligence without
              asking" — and the person reading this is professionally liable if
              something they were not told about hurts someone. Nothing is actually
              hidden: every row is listed below with its reason. So this is a
              COMPLETENESS record, not a withholding notice, and it says so. */}
          <Band label="Everything we checked"
            note="The full ledger, not a summary. Every signal that touched a site today is accounted for here — the ones that need you, and the ones that were checked and cleared, each with the reason it was cleared. Nothing is removed from the record; you can read every line."
            right={<span className="font-mono text-[10px] text-[#5A5A55] tabular-nums">{held.considered} accounted for</span>}>
            <div className="px-6 lg:px-10 pb-8 pt-2">
              <div className="space-y-2.5">
                {[
                  { v: held.considered, l: "Signals checked", c: "#2E2E2E" },
                  { v: held.suppressed, l: "Checked and cleared", c: "#4A4845" },
                  { v: queue.total, l: "Needs your decision", c: "#FF5C43" },
                ].map((r) => (
                  <div key={r.l} className="flex items-center gap-4">
                    <span className="font-display text-[2rem] leading-none tabular-nums w-[4.5rem] text-right"
                      style={{ color: r.l === "Needs your decision" ? "#FF5C43" : "#F0EDE8" }}>{r.v}</span>
                    <div className="flex-1 h-7 relative">
                      <div className="absolute inset-y-0 left-0 rounded-r-[3px]"
                        style={{ width: `${Math.max((r.v / Math.max(held.considered, 1)) * 100, 0.8)}%`, background: r.c }} />
                    </div>
                    <span className="font-mono text-[10px] tracking-[0.14em] uppercase text-[#8A8A82] w-[10.5rem]">{r.l}</span>
                  </div>
                ))}
              </div>
              <p className="text-[11px] text-[#5A5A55] mt-4 leading-relaxed max-w-3xl">
                Cleared does not mean discarded. Every one is listed on its site with the reason it
                was cleared, and opens to its sources — select a site to read them. Thresholds follow
                the organisation's stated tolerance ({TOLERANCE_WORD.toLowerCase()}), set by your
                security team rather than adjusted while reading this board.
              </p>
              <div className="flex flex-wrap gap-x-7 gap-y-1.5 mt-5 pt-4 border-t border-[#1C1C1C]">
                {Object.entries(held.byReason).map(([k, v]) => (
                  <span key={k} className="text-[11px] text-[#6A6A64]">
                    <span className="font-mono tabular-nums text-[#B8B5AE]">{v}</span> {SUPPRESSION_REASONS[k]?.toLowerCase()}
                  </span>
                ))}
              </div>
            </div>
          </Band>

          <Band label="Movement">
            <div className="grid lg:grid-cols-2 gap-px bg-[#1C1C1C] mt-3">
              <div className="bg-[#0A0A0A] p-6">
                <p className="font-mono text-[10px] tracking-[0.16em] uppercase text-[#8A8A82]">Changed since last look</p>
                <div className="mt-4 space-y-2.5 max-h-[280px] overflow-y-auto pr-1">
                  {change.deteriorated.length + change.improved.length === 0
                    ? <p className="text-[12px] text-[#5A5A55]">No site changed status.</p>
                    : [...change.deteriorated.slice(0, 8), ...change.improved.slice(0, 4)].map((r) => (
                      <button key={r.office.id} type="button"
                        onClick={() => { setSelected(r.office.id); setView("Sites"); }}
                        className="w-full text-left flex items-center gap-3 hover:bg-[#111] rounded-[2px] px-1 py-0.5">
                        <span className="w-1 h-6 flex-shrink-0" style={{ background: SEV[r.to].c }} />
                        <div className="min-w-0 flex-1">
                          <div className="text-[12px] truncate">{r.office.name}</div>
                          <div className="font-mono text-[10px] text-[#6A6A64] truncate">
                            {r.from} → {r.to} · {r.drivers.map((d) => d.label).join(", ") || "—"}
                          </div>
                        </div>
                        <span className="font-mono text-[11px] tabular-nums text-[#8A8A82]">{n(r.people)}</span>
                      </button>
                    ))}
                </div>
              </div>
              <div className="bg-[#0A0A0A] p-6">
                <p className="font-mono text-[10px] tracking-[0.16em] uppercase text-[#8A8A82]">What's coming · 60 days</p>
                <div className="mt-4 space-y-2.5 max-h-[280px] overflow-y-auto pr-1">
                  {/* These sat inert directly beside the "changed since last look" rows,
                      which ARE buttons and look identical — an asymmetry inside one panel
                      pair. Forward items are scheduled context (holidays, festivals,
                      departures), not signals, so they open the affected SITE rather than
                      a signal drawer. */}
                  {ahead.slice(0, 10).map((f) => {
                    const siteId = f.sites?.[0]?.office?.id ?? f.sites?.[0]?.id ?? null;
                    const Tag = siteId ? "button" : "div";
                    return (
                      <Tag
                        key={`${f.date}|${f.name}`}
                        {...(siteId ? {
                          type: "button",
                          onClick: () => { setSelected(siteId); setView("Sites"); },
                          title: `Open ${f.sites.length} affected site${f.sites.length === 1 ? "" : "s"}`,
                        } : {})}
                        className={[
                          "w-full text-left flex items-baseline gap-3",
                          siteId ? "hover:text-[#F0EDE8] group" : "",
                        ].join(" ")}
                      >
                        <span className="font-mono text-[11px] tabular-nums text-[#8A8A82] w-12 flex-shrink-0">{f.inDays}d</span>
                        <div className="min-w-0 flex-1">
                          <div className={["text-[12px] truncate", siteId ? "group-hover:text-[#F0EDE8]" : ""].join(" ")}>{f.name}</div>
                          <div className="font-mono text-[10px] text-[#6A6A64]">{n(f.people)} people · {f.sites.length} sites</div>
                        </div>
                      </Tag>
                    );
                  })}
                </div>
              </div>
            </div>
          </Band>

          <Band label="Prove it"
            note="The last question, not the first. Every figure above traces to graded, corroborated signals — and our own accuracy is published rather than asserted.">
            <div className="px-6 lg:px-10 pb-10 grid md:grid-cols-3 gap-8 mt-2">
              <div>
                <div className="font-mono text-[10px] tracking-[0.16em] uppercase text-[#8A8A82]">Source grading</div>
                <p className="text-[12px] text-[#6A6A64] mt-2 leading-relaxed">Every signal carries a NATO-Admiralty grade — source reliability and information credibility, scored separately.</p>
              </div>
              <div>
                <div className="font-mono text-[10px] tracking-[0.16em] uppercase text-[#8A8A82]">Corroboration gate</div>
                <p className="text-[12px] text-[#6A6A64] mt-2 leading-relaxed">
                  Nothing reaches this screen on a single source — {held.byReason.uncorroborated || 0} held on that basis today.
                </p>
              </div>
              <div>
                <div className="font-mono text-[10px] tracking-[0.16em] uppercase text-[#8A8A82]">Our own track record</div>
                <p className="text-[12px] text-[#6A6A64] mt-2 leading-relaxed">
                  Published, and honestly withheld until enough forecasts resolve to earn a number.{" "}
                  <Link to="/benchmark" className="text-crimson-light hover:underline">See the benchmark →</Link>
                </p>
              </div>
            </div>
          </Band>
        </motion.div>
      )}

      {/* ══ SITES ════════════════════════════════════════════════════════════ */}
      {view === "Sites" && (
        <motion.div {...rise(0)}>
          <Band label="Register integrity"
            note="The site register is the join key for every per-site figure. A duplicated row or a wrong country propagates into everything downstream — so it is checked before anything is scored."
            right={<span className="font-mono text-[10px] tabular-nums" style={{ color: audit.clean ? SEV.clear.c : SEV.alert.c }}>
              {audit.clean ? "clean" : `${audit.findings.length} findings`}
            </span>}>
            <div className="px-6 lg:px-10 pb-6 pt-2">
              <div className="flex flex-wrap gap-x-8 gap-y-3">
                {[
                  { v: audit.checked, l: "rows checked" },
                  { v: audit.critical, l: "critical", c: audit.critical ? SEV.alert.c : undefined },
                  { v: audit.warnings, l: "warnings", c: audit.warnings ? SEV.watch.c : undefined },
                  { v: audit.affectedSites, l: "rows affected" },
                ].map((s) => (
                  <div key={s.l}>
                    <div className="font-display text-[1.7rem] leading-none tabular-nums" style={{ color: s.c || "#F0EDE8" }}>{s.v}</div>
                    <div className="font-mono text-[9px] tracking-[0.12em] uppercase text-[#6A6A64] mt-1.5">{s.l}</div>
                  </div>
                ))}
              </div>
              {audit.findings.length > 0 && (
                <div className="mt-5 space-y-1.5 max-h-[200px] overflow-y-auto">
                  {/* Each finding names an offending row and already carries its siteId.
                      Reporting a data-integrity problem without a way to reach the record
                      makes the audit an accusation rather than a tool. */}
                  {audit.findings.slice(0, 40).map((f, i) => {
                    const Tag = f.siteId ? "button" : "div";
                    return (
                      <Tag
                        key={`${f.check}-${f.siteId}-${i}`}
                        {...(f.siteId ? {
                          type: "button",
                          onClick: () => setSelected(f.siteId),
                          title: "Open the affected site",
                        } : {})}
                        className={[
                          "w-full text-left flex flex-wrap items-baseline gap-x-3 text-[11px]",
                          f.siteId ? "hover:bg-[#0E0E0E] group" : "",
                        ].join(" ")}
                      >
                        <span className="font-mono text-[10px] uppercase tracking-[0.1em] w-[130px] flex-shrink-0"
                          style={{ color: f.severity === "critical" ? SEV.alert.c : SEV.watch.c }}>{f.severity}</span>
                        <span className={["text-[#B8B5AE] w-[210px] flex-shrink-0 truncate", f.siteId ? "group-hover:text-[#F0EDE8]" : ""].join(" ")}>{f.label}</span>
                        <span className="text-[#5A5A55] flex-1 min-w-[220px]">{f.detail}</span>
                      </Tag>
                    );
                  })}
                </div>
              )}
              {audit.clean && (
                <p className="text-[12px] text-[#5A5A55] mt-4">
                  No duplicates, no missing or out-of-range coordinates, no unmapped countries, every row carries a headcount.
                </p>
              )}
            </div>
          </Band>

          <Band label={`Site register · ${matchSites.length} of ${contexts.length}`}
            note="Sortable on every column, paginated, and exportable. Click any row to open its full picture.">
            <div className="grid lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] gap-px bg-[#1C1C1C] mt-3">
              <DataTable
                rows={matchSites}
                rowKey={(r) => r.office.id}
                selectedKey={selected}
                onRowClick={(r) => setSelected(r.office.id)}
                defaultSort={{ key: "score", dir: "desc" }}
                filename={`wipro-site-register-${today.toISOString().slice(0, 10)}.csv`}
                empty={q ? `No site matches "${query}".` : "No site matches the current filters."}
                caption="Export carries every filtered row, not just this page."
                columns={SITE_COLUMNS}
              />

              <div className="bg-[#0A0A0A] p-6">
                {!sel ? (
                  <p className="text-[12px] text-[#5A5A55]">Select a site — or click a dot on the globe — to see all eight layers, its domain scores, and everything held for it.</p>
                ) : (() => {
                  const scores = domainScores(sel, { appetite });
                  const overall = overallScore(scores);
                  const heldHere = held.held.filter((h) => h.office.id === sel.office.id);
                  const tripsHere = travel.rows.filter((r) => r.trip.to === sel.office.city);
                  return (
                    <>
                      <div className="flex flex-wrap items-start justify-between gap-4">
                        <div>
                          <h3 className="text-[16px]">{sel.office.name}</h3>
                          <p className="font-mono text-[10px] text-[#6A6A64] mt-1">
                            {sel.office.city} · {sel.office.country} · {sel.office.type} · {sel.office.criticality} · {n(sel.office.headcount)} people
                          </p>
                          <p className="font-mono text-[10px] text-[#4A4845] mt-0.5">
                            {sel.office.lat.toFixed(3)}, {sel.office.lng.toFixed(3)}
                          </p>
                        </div>
                        <div className="text-right">
                          <div className="font-display text-[2.2rem] leading-none" style={{ color: overall.band.color }}>
                            {overall.score.toFixed(1)}
                          </div>
                          <div className="font-mono text-[10px] tracking-[0.12em] uppercase mt-1" style={{ color: overall.band.color }}>
                            {overall.band.label}
                          </div>
                        </div>
                      </div>

                      <div className="mt-6 space-y-2">
                        {LAYER_KEYS.map((k) => (
                          <div key={k} className="flex items-center gap-3">
                            <span className="font-mono text-[10px] tracking-[0.1em] uppercase text-[#8A8A82] w-[86px]">{LAYER_LABELS[k]}</span>
                            <ScoreBar score={scores[k].score} />
                            {scores[k].evidence ? (
                              <button
                                type="button"
                                onClick={() => openSignal(scores[k].evidence.id)}
                                className="text-[11px] text-[#6A6A64] hover:text-crimson-light truncate flex-1 text-left underline decoration-dotted decoration-[#2E2E2C]"
                                title="Open the signal driving this score"
                              >
                                {scores[k].evidence.title}
                                {scores[k].evidence.km != null ? ` · ${Math.round(scores[k].evidence.km)} km` : ""}
                              </button>
                            ) : (
                              <span className="text-[11px] text-[#6A6A64] truncate flex-1">
                                {scores[k].scope === "organisation" ? "organisation-wide" : "nothing found"}
                              </span>
                            )}
                          </div>
                        ))}
                      </div>

                      {tripsHere.length > 0 && (
                        <div className="mt-6 pt-4 border-t border-[#1C1C1C]">
                          <p className="font-mono text-[10px] tracking-[0.14em] uppercase text-[#8A8A82]">Travellers here · {tripsHere.length}</p>
                          <div className="mt-2 space-y-1">
                            {tripsHere.slice(0, 5).map((r) => (
                              <div key={r.trip.id} className="text-[11px] flex items-center gap-2">
                                <span style={{ color: r.verdict.color }} className="font-mono text-[10px] w-[76px]">{r.verdict.label}</span>
                                <span className="text-[#B8B5AE]">{r.trip.traveler}</span>
                                <span className="text-[#5A5A55]">· {r.trip.departISO} → {r.trip.returnISO}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      <div className="mt-6 pt-4 border-t border-[#1C1C1C]">
                        <p className="font-mono text-[10px] tracking-[0.14em] uppercase text-[#8A8A82]">Checked and cleared here · {heldHere.length}</p>
                        {heldHere.length === 0 ? <p className="text-[11px] text-[#5A5A55] mt-2">Nothing else reached this site today.</p> : (
                          <div className="mt-2 space-y-1 max-h-[160px] overflow-y-auto">
                            {/* The trust surface: what we saw and chose NOT to escalate.
                                It is the first thing a sceptical buyer interrogates, so
                                every row must open its evidence. */}
                            {heldHere.map((h) => (
                              <button
                                key={h.id} type="button"
                                onClick={() => openSignal(h.eventId)}
                                className="w-full text-left text-[11px] flex flex-wrap gap-x-2 hover:text-[#F0EDE8] group"
                              >
                                <span className="text-[#B8B5AE] group-hover:text-[#F0EDE8] flex-1 min-w-[160px] truncate">{h.title}</span>
                                <span className="text-[#5A5A55]">{h.reasonLabel}</span>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </>
                  );
                })()}
              </div>
            </div>
          </Band>
        </motion.div>
      )}

      {/* ══ PEOPLE ═══════════════════════════════════════════════════════════ */}
      {view === "People" && (
        <motion.div {...rise(0)}>
          <Band label="People in motion"
            note="Duty of care. Verdicts use the analyst deck's vocabulary — Proceed · Advise · Reconsider — so the organisation runs one dialect.">
            <div className="px-6 lg:px-10 pb-5 pt-2 flex flex-wrap gap-x-10 gap-y-4">
              {[
                { v: travel.inMotion, l: "in motion" },
                { v: travel.upcomingCount, l: "upcoming" },
                { v: travel.reconsider, l: "reconsider", c: travel.reconsider ? SEV.alert.c : undefined },
                { v: travel.unaccounted.length, l: "unaccounted for", c: travel.unaccounted.length ? SEV.alert.c : SEV.clear.c },
                { v: n(exp.peopleAlert), l: "resident people at elevated sites" },
              ].map((s) => (
                <div key={s.l}>
                  <div className="font-display text-[2rem] leading-none tabular-nums" style={{ color: s.c || "#F0EDE8" }}>{s.v}</div>
                  <div className="font-mono text-[9px] tracking-[0.12em] uppercase text-[#6A6A64] mt-1.5">{s.l}</div>
                </div>
              ))}
            </div>
          </Band>

          <Band label={`Itineraries · ${travel.rows.length}`} note="Every trip scored against signals within each event's own reach. Sorted by verdict, then departure.">
            <div className="mt-3 max-h-[640px] overflow-y-auto">
              <table className="w-full text-left">
                <thead className="sticky top-0 bg-[#0E0E0E]">
                  <tr className="font-mono text-[9px] tracking-[0.14em] uppercase text-[#6A6A64]">
                    {["Verdict", "Traveller", "Route", "Dates", "Status", "Driving signal", "Last check-in"].map((h) => (
                      <th key={h} className="px-4 py-2.5 font-normal border-b border-[#1C1C1C]">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[...travel.rows]
                    .filter((r) => !q || r.trip.traveler.toLowerCase().includes(q) || r.trip.to.toLowerCase().includes(q) || r.trip.country.toLowerCase().includes(q))
                    .sort((a, b) => ({ proceed: 0, advise: 1, reconsider: 2 })[b.verdict.key] - ({ proceed: 0, advise: 1, reconsider: 2 })[a.verdict.key]
                      || a.trip.departISO.localeCompare(b.trip.departISO))
                    .map((r) => (
                      <tr key={r.trip.id} className="border-b border-[#151515] hover:bg-[#0E0E0E]">
                        <td className="px-4 py-2.5"><span className="font-mono text-[10px]" style={{ color: r.verdict.color }}>{r.verdict.label}</span></td>
                        <td className="px-4 py-2.5 text-[12px]">{r.trip.traveler}<div className="font-mono text-[10px] text-[#5A5A55]">{r.trip.role}</div></td>
                        <td className="px-4 py-2.5 text-[12px] text-[#B8B5AE]">{r.trip.from} → {r.trip.to}</td>
                        <td className="px-4 py-2.5 font-mono text-[10px] text-[#6A6A64]">{r.trip.departISO} → {r.trip.returnISO}</td>
                        <td className="px-4 py-2.5 font-mono text-[10px] text-[#8A8A82]">{r.status}</td>
                        {/* The row keeps its hover tint as a reading aid across seven
                            columns, but the thing that actually opens is the signal —
                            the only cell here backed by an event. */}
                        <td className="px-4 py-2.5 text-[11px] text-[#8A8A82] max-w-[260px] truncate">
                          {r.best ? (
                            <button
                              type="button"
                              onClick={() => setSignal(r.best.event)}
                              title="Open the signal driving this verdict"
                              className="max-w-full truncate text-left hover:text-crimson-light underline decoration-dotted decoration-[#2E2E2C]"
                            >
                              {r.best.event.canonical_title} · {Math.round(r.best.km)} km
                            </button>
                          ) : "—"}
                        </td>
                        <td className="px-4 py-2.5 font-mono text-[10px]" style={{ color: r.unaccounted ? SEV.alert.c : "#6A6A64" }}>
                          {r.unaccounted ? "no record" : r.lastSeen ? new Date(r.lastSeen).toISOString().slice(0, 16).replace("T", " ") : "—"}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </Band>
        </motion.div>
      )}

      {/* ══ COUNTRIES ════════════════════════════════════════════════════════ */}
      {view === "Countries" && (
        <motion.div {...rise(0)}>
          <Band label="Country risk profile"
            note="A 0–5 score per domain, rolled to a band — the shape incumbents publish. The difference: every number here drills to the signal that produced it, and a quiet domain reads 0 because nothing was found, not because nobody looked. Overall is the WORST domain, never the mean.">
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-left min-w-[900px]">
                <thead>
                  <tr className="font-mono text-[9px] tracking-[0.14em] uppercase text-[#6A6A64]">
                    <th className="px-4 py-2.5 font-normal border-b border-[#1C1C1C]">Country</th>
                    <th className="px-4 py-2.5 font-normal border-b border-[#1C1C1C]">Overall</th>
                    {LAYER_KEYS.map((k) => <th key={k} className="px-2 py-2.5 font-normal border-b border-[#1C1C1C]">{LAYER_LABELS[k]}</th>)}
                    <th className="px-4 py-2.5 font-normal border-b border-[#1C1C1C]">Worst site</th>
                  </tr>
                </thead>
                <tbody>
                  {countries.filter((c) => !q || c.country.toLowerCase().includes(q)).map((c) => (
                    <tr key={c.country} className="border-b border-[#151515] hover:bg-[#0E0E0E]">
                      {/* Drills into the register filtered to this country, reusing the
                          existing country dimension rather than inventing a second
                          filtering concept. Replaces (not adds to) any country already
                          selected, which is what clicking a specific country implies. */}
                      <td className="px-4 py-3">
                        <button
                          type="button"
                          onClick={() => {
                            setFilters((f) => toggleValue(clearDimension(f, "country"), "country", c.country));
                            setView("Sites");
                          }}
                          title={`Show the ${c.sites} site${c.sites === 1 ? "" : "s"} in ${c.country}`}
                          className="text-left hover:text-crimson-light group"
                        >
                          <div className="text-[12px] group-hover:underline decoration-dotted">{c.country}</div>
                          <div className="font-mono text-[10px] text-[#5A5A55]">{c.sites} sites · {n(c.people)} people</div>
                        </button>
                      </td>
                      <td className="px-4 py-3">
                        <span className="font-display text-[1.3rem] leading-none" style={{ color: c.band.color }}>{c.overall.toFixed(1)}</span>
                        <div className="font-mono text-[9px] uppercase tracking-[0.1em] mt-1" style={{ color: c.band.color }}>{c.band.label}</div>
                      </td>
                      {LAYER_KEYS.map((k) => (
                        <td key={k} className="px-2 py-3">
                          <span className="font-mono text-[11px] tabular-nums" style={{ color: bandFor(c.domains[k]?.score || 0).color }}>
                            {(c.domains[k]?.score || 0).toFixed(1)}
                          </span>
                        </td>
                      ))}
                      <td className="px-4 py-3">
                        {c.worstSite && (
                          <button type="button" onClick={() => { setSelected(c.worstSite.office.id); setView("Sites"); }}
                            className="text-[11px] text-[#8A8A82] hover:text-crimson-light underline decoration-dotted">
                            {c.worstSite.office.name}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Band>
        </motion.div>
      )}

      {/* ══ CALENDAR ═════════════════════════════════════════════════════════ */}
      {view === "Calendar" && (
        <motion.div {...rise(0)}>
          <Band label="Forward calendar · 60 days"
            note="Public holidays, gatherings and traveller departures on one grid, with the people behind each date — so leadership plans ahead of the window instead of being alerted during it.">
            <CalendarGrid ahead={ahead} trips={SAMPLE.SAMPLE_TRIPS} today={SAMPLE.SAMPLE_TODAY} />
          </Band>
        </motion.div>
      )}

      <footer className="px-6 lg:px-10 py-6 border-t border-[#1C1C1C]">
        <p className="font-mono text-[10px] text-[#4A4845] leading-relaxed">
          Advisory only — physical response (evacuation, ground support) via partner.
          Sample board: {exp.sites} sites · {n(exp.people)} people · {SAMPLE.SAMPLE_TRIPS.length} itineraries.
          {" "}Operator board: <Link to="/deck" className="text-crimson-light hover:underline">signal deck →</Link>
        </p>
      </footer>

      {/* Rendered last and fixed-positioned: the deck stays mounted underneath, so
          filters, sort, page and site selection all survive opening a signal. */}
      {signal && (
        <SignalDrawer
          event={signal}
          contexts={contexts}
          onClose={() => setSignal(null)}
          onSelectSite={(id) => { setSelected(id); setView("Sites"); }}
        />
      )}
    </div>
  );
}

// ── All-layers strip ─────────────────────────────────────────────────────────
// Every domain across the whole estate — geopolitics, cyber, market, hazards,
// weather, holiday, festival and derived road traffic. Weather and hazards are as
// load-bearing here as unrest: severe weather is what actually closes a campus,
// and burying it is how a board is surprised by a flood.
function LayerStrip({ contexts, appetite, onPick }) {
  const rows = useMemo(() => {
    const acc = LAYER_KEYS.map((k) => ({
      key: k, label: LAYER_LABELS[k], score: 0, alert: 0, watch: 0,
      driver: null, evidence: null, scope: "site",
    }));
    const index = Object.fromEntries(acc.map((r) => [r.key, r]));
    for (const c of contexts) {
      const s = domainScores(c, { appetite });
      for (const k of LAYER_KEYS) {
        const row = index[k];
        const lvl = c.layers[k]?.level;
        if (lvl === "alert") row.alert += 1;
        else if (lvl === "watch") row.watch += 1;
        if (s[k].score > row.score) {
          row.score = s[k].score;
          row.driver = c.office;
          row.evidence = s[k].evidence;
          row.scope = s[k].scope || "site";
        }
      }
    }
    return acc;
  }, [contexts, appetite]);

  return (
    <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-px bg-[#1C1C1C] mt-3">
      {rows.map((r) => {
        const b = bandFor(r.score);
        return (
          <div key={r.key} className="bg-[#0A0A0A] p-4">
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-mono text-[10px] tracking-[0.14em] uppercase text-[#8A8A82]">{r.label}</span>
              <span className="font-display text-[1.5rem] leading-none tabular-nums" style={{ color: b.color }}>
                {r.score.toFixed(1)}
              </span>
            </div>
            <div className="h-1 bg-[#161616] mt-2 rounded-[1px] overflow-hidden">
              <div className="h-full rounded-[1px]" style={{ width: `${(r.score / 5) * 100}%`, background: b.color }} />
            </div>
            <div className="font-mono text-[10px] text-[#6A6A64] mt-2">
              {r.scope === "organisation"
                ? "organisation-wide"
                : `${r.alert} alert · ${r.watch} watch of ${contexts.length}`}
            </div>
            <div className="text-[11px] text-[#5A5A55] mt-1.5 leading-snug min-h-[2.4em]">
              {r.evidence
                ? r.evidence.title
                : r.score > 0 && r.driver
                  ? `Highest at ${r.driver.name}`
                  : "Nothing found across the estate"}
            </div>
            {r.driver && r.scope !== "organisation" && (
              <button type="button" onClick={() => onPick(r.driver.id)}
                className="font-mono text-[10px] text-[#6A6A64] hover:text-crimson-light underline decoration-dotted mt-1 no-print">
                {r.driver.name} →
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Calendar ─────────────────────────────────────────────────────────────────
// Real month grids built from the same forward() rows plus trip departures.
function CalendarGrid({ ahead, trips, today }) {
  const months = useMemo(() => {
    const byDay = new Map();
    const push = (iso, item) => {
      if (!iso) return;
      if (!byDay.has(iso)) byDay.set(iso, []);
      byDay.get(iso).push(item);
    };
    for (const f of ahead) push(f.date, { kind: f.kind, name: f.name, people: f.people, sites: f.sites.length });
    for (const t of trips) push(t.departISO, { kind: "trip", name: `${t.traveler} → ${t.to}`, people: 1, sites: 0 });

    const start = new Date(today.getFullYear(), today.getMonth(), 1);
    return [0, 1, 2].map((m) => {
      const first = new Date(start.getFullYear(), start.getMonth() + m, 1);
      const days = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate();
      const lead = (first.getDay() + 6) % 7;   // Monday-first
      const cells = [];
      for (let i = 0; i < lead; i++) cells.push(null);
      for (let d = 1; d <= days; d++) {
        const iso = `${first.getFullYear()}-${String(first.getMonth() + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
        cells.push({ d, iso, items: byDay.get(iso) || [] });
      }
      return { label: first.toLocaleDateString("en-GB", { month: "long", year: "numeric" }), cells };
    });
  }, [ahead, trips, today]);

  const KIND = { holiday: "#E0A93C", festival: "#FF5C43", trip: "#5FBF74" };
  const todayISO = today.toISOString().slice(0, 10);

  return (
    <div className="px-6 lg:px-10 pb-10 pt-3 grid lg:grid-cols-3 gap-6">
      {months.map((m) => (
        <div key={m.label}>
          <p className="font-mono text-[10px] tracking-[0.16em] uppercase text-[#8A8A82] mb-3">{m.label}</p>
          <div className="grid grid-cols-7 gap-px bg-[#141414]">
            {["M", "T", "W", "T", "F", "S", "S"].map((d, i) => (
              <div key={i} className="bg-[#0A0A0A] py-1 text-center font-mono text-[9px] text-[#4A4845]">{d}</div>
            ))}
            {m.cells.map((c, i) => (
              <div key={i} className="bg-[#0A0A0A] min-h-[52px] p-1"
                style={{ outline: c?.iso === todayISO ? "1px solid #FF5C43" : undefined }}>
                {c && (
                  <>
                    <div className="font-mono text-[9px] text-[#5A5A55]">{c.d}</div>
                    <div className="flex flex-wrap gap-0.5 mt-0.5">
                      {c.items.slice(0, 4).map((it, j) => (
                        <span key={j} title={`${it.name}${it.people > 1 ? ` · ${it.people.toLocaleString()} people` : ""}`}
                          className="w-1.5 h-1.5 rounded-full" style={{ background: KIND[it.kind] || "#6A6A64" }} />
                      ))}
                      {c.items.length > 4 && <span className="font-mono text-[8px] text-[#5A5A55]">+{c.items.length - 4}</span>}
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
      <div className="lg:col-span-3 flex flex-wrap gap-x-6 gap-y-2 pt-2 border-t border-[#1C1C1C]">
        {Object.entries(KIND).map(([k, c]) => (
          <span key={k} className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: c }} />
            <span className="font-mono text-[10px] tracking-[0.1em] uppercase text-[#6A6A64]">{k}</span>
          </span>
        ))}
        <span className="font-mono text-[10px] text-[#4A4845]">hover a marker for detail</span>
      </div>
    </div>
  );
}
