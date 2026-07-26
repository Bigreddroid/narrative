// ─────────────────────────────────────────────────────────────────────────────
// SignalDrawer — the answer to "I clicked it and nothing happened".
//
// Before this, the deck rendered about twelve kinds of signal row and not one of
// them opened the signal. Sources appeared in exactly one place on the whole page
// (the decision-queue cards) and even there as a bare integer — no outlet names, no
// links. For a product whose entire claim is "our sourcing is auditable", a board
// you cannot drill into is the claim unproven.
//
// It is a DRAWER, not a route, on purpose: the deck stays mounted underneath, so
// filters, sort, page and site selection all survive. Navigating to /event/:id
// unmounts the board and the reader loses the context they were reading. The link
// out is still offered for anyone who wants a shareable URL.
//
// HONESTY RULES, since this is the surface that proves the rest:
//   • Sources come from the API's own articles[] — never synthesised, never inferred
//     from the transport slug.
//   • An event we hold no document for says so plainly. It does not show "1 source"
//     and it does not show an empty list styled to look like a complete one.
//   • The Intelligence/Informative split is reported as EARNED (severity.js), so a
//     single-source item is visibly labelled as not having met the two-source bar
//     rather than quietly presented as assessed.
//   • Every link is the real article URL, opened with rel="noopener noreferrer".
// ─────────────────────────────────────────────────────────────────────────────
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api.js";
import {
  classify, ALERT_TYPES, MIN_SOURCES_FOR_INTELLIGENCE,
} from "../../lib/severity.js";

const fmtDate = (v) => {
  if (!v) return null;
  const t = Date.parse(v);
  return Number.isNaN(t) ? null
    : new Date(t).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
};

// NATO-Admiralty pill. Reliability letter + credibility digit, with the meaning in
// the tooltip — an unexplained "B2" is jargon, and this deck is read by executives.
function Grade({ grade, title }) {
  if (!grade) return null;
  const good = /^[AB][12]$/.test(grade);
  return (
    <span
      title={title || `NATO-Admiralty ${grade} — source reliability ${grade[0]}, information credibility ${grade[1]}`}
      className={[
        "font-mono text-[9px] tracking-[0.1em] px-1.5 py-0.5 rounded-[2px] border shrink-0",
        good ? "border-[#2F5D3A] text-[#7FA88C]" : "border-[#5A4A1E] text-[#E0A93C]",
      ].join(" ")}
    >
      {grade}
    </span>
  );
}

function Row({ label, children }) {
  return (
    <div className="flex gap-3 py-1.5 border-b border-[#141414] last:border-0">
      <span className="font-mono text-[9px] tracking-[0.18em] uppercase text-[#5A5A55] w-[92px] shrink-0 pt-0.5">
        {label}
      </span>
      <div className="min-w-0 flex-1 text-[12px] text-[#C8C4BC]">{children}</div>
    </div>
  );
}

export default function SignalDrawer({ event, contexts = [], onClose, onSelectSite }) {
  const [detail, setDetail] = useState({ state: "loading", articles: [], grade: null, error: null });
  const panelRef = useRef(null);
  const restoreTo = useRef(null);

  // Remember what had focus so it can be handed back on close. A drawer that
  // dumps focus at the top of the document makes the board unusable by keyboard.
  useEffect(() => {
    restoreTo.current = document.activeElement;
    const t = setTimeout(() => panelRef.current?.focus(), 20);
    return () => {
      clearTimeout(t);
      const el = restoreTo.current;
      if (el && typeof el.focus === "function" && document.contains(el)) el.focus();
    };
  }, []);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") { e.stopPropagation(); onClose?.(); } };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Sources live on the DETAIL endpoint — the list payload carries only counts.
  useEffect(() => {
    let alive = true;
    if (!event?.id) { setDetail({ state: "none", articles: [], grade: null, error: null }); return undefined; }
    setDetail({ state: "loading", articles: [], grade: null, error: null });
    api.get(`/events/${event.id}`, { timeoutMs: 15000 })
      .then((d) => {
        if (!alive) return;
        setDetail({
          state: "ready",
          articles: Array.isArray(d?.articles) ? d.articles : [],
          grade: d?.source_grade || null,
          error: null,
        });
      })
      .catch((err) => {
        if (!alive) return;
        // Failing to LOAD sources is not the same as having none. Say which.
        setDetail({ state: "error", articles: [], grade: null, error: err?.message || "could not load sources" });
      });
    return () => { alive = false; };
  }, [event?.id]);

  if (!event) return null;

  const c = classify(event, { contexts });
  const outlets = [...new Set(detail.articles.map((a) => a.source).filter(Boolean))];
  const outletCount = outlets.length;
  const isIntel = c.type.key === ALERT_TYPES.intelligence.key;

  // TWO DIFFERENT THINGS, deliberately not conflated — an early build of this drawer
  // showed "3 independent sources converged" in the grading panel directly above
  // "Single source", which is exactly the kind of contradiction that destroys trust in
  // a board whose whole pitch is auditable sourcing:
  //
  //   documentsOnFile — stored articles we can actually LINK to. Feed events (USGS,
  //                     GDACS, Mastodon relays) publish structured alerts, not articles,
  //                     so this is legitimately 0 for them.
  //   gateCount       — event.source_count, the number the two-source gate in
  //                     severity.js actually judged. Reporting anything else here would
  //                     mean the drawer disagreed with the decision it is explaining.
  //
  // The grading panel's convergence count is a third, separate signal (geo+time
  // clustering of related events) under its own heading. Keeping it visually separate was
  // not enough on its own: its rationale used to read "2 independent sources converged"
  // beside "1 outlet", so the two measures still collided in the reader's head even
  // though the numbers were correct. The backend now words that measure as "independent
  // feeds reported related activity nearby" (source_reliability._credibility, locked by a
  // test) — separate headings AND separate vocabulary.
  const documentsOnFile = detail.articles.length;
  const gateCount = Number(event?.source_count) || 0;
  const corroborated = gateCount >= MIN_SOURCES_FOR_INTELLIGENCE;

  return (
    <div className="fixed inset-0 z-50 flex justify-end no-print">
      <button
        type="button"
        aria-label="Close signal"
        onClick={onClose}
        className="absolute inset-0 bg-black/55 backdrop-blur-[1px] cursor-default"
      />
      <aside
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={event.canonical_title || "Signal"}
        className="relative h-full w-full max-w-[520px] bg-[#080808] border-l border-[#1F1F1F] overflow-y-auto outline-none shadow-[0_0_60px_rgba(0,0,0,0.6)]"
      >
        {/* header */}
        <div className="sticky top-0 bg-[#080808] border-b border-[#1C1C1C] px-5 py-4 z-10">
          <div className="flex items-start justify-between gap-3">
            <span className="font-mono text-[9px] tracking-[0.2em] uppercase text-[#5A5A55]">Signal</span>
            <button
              type="button" onClick={onClose}
              className="font-mono text-[10px] tracking-[0.12em] uppercase text-[#8A8A82] hover:text-[#F0EDE8]"
            >
              Close · Esc
            </button>
          </div>
          <h2 className="mt-2 text-[17px] leading-snug text-[#F0EDE8]">{event.canonical_title}</h2>
          <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
            <span
              className="font-mono text-[9px] tracking-[0.1em] uppercase px-2 py-0.5 rounded-[2px] text-[#050505]"
              style={{ background: c.band.color }}
            >
              {c.band.label} · {c.score.toFixed(1)}
            </span>
            <span className={[
              "font-mono text-[9px] tracking-[0.1em] uppercase px-2 py-0.5 rounded-[2px] border",
              isIntel ? "border-[#2F5D3A] text-[#7FA88C]" : "border-[#2A2A2A] text-[#8A8A82]",
            ].join(" ")}>
              {c.type.label}
            </span>
            {event.category && (
              <span className="font-mono text-[9px] tracking-[0.1em] uppercase px-2 py-0.5 rounded-[2px] border border-[#2A2A2A] text-[#8A8A82]">
                {event.category}
              </span>
            )}
            {c.validity.state !== "unknown" && (
              <span className={[
                "font-mono text-[9px] tracking-[0.1em] uppercase px-2 py-0.5 rounded-[2px] border",
                c.validity.state === "expired" ? "border-[#3A2020] text-[#7A5555]"
                  : c.validity.state === "expiring" ? "border-[#5A4A1E] text-[#E0A93C]"
                    : "border-[#2A2A2A] text-[#8A8A82]",
              ].join(" ")}>
                {c.validity.state === "expired" ? "Expired"
                  : c.validity.state === "expiring" ? `Expiring · ${c.validity.remainingHours}h`
                    : `Valid · ${c.validity.remainingHours}h`}
              </span>
            )}
          </div>
          {/* The band's operative meaning, not its threshold. */}
          <p className="mt-2.5 text-[11px] leading-relaxed text-[#8A8A82]">{c.consequence}</p>
        </div>

        <div className="px-5 py-4 space-y-5">
          {event.canonical_summary && (
            <p className="text-[12.5px] leading-relaxed text-[#C8C4BC]">{event.canonical_summary}</p>
          )}

          {/* ── SOURCES ── the whole point of this drawer ── */}
          <section>
            <div className="flex items-baseline justify-between gap-3 mb-2">
              <h3 className="font-mono text-[9px] tracking-[0.2em] uppercase text-[#5A5A55]">
                Source documents
              </h3>
              {detail.state === "ready" && (
                <span className="font-mono text-[9px] tracking-[0.1em] uppercase text-[#5A5A55] tabular-nums">
                  {documentsOnFile} on file · {outletCount} {outletCount === 1 ? "outlet" : "outlets"}
                </span>
              )}
            </div>

            {detail.state === "loading" && (
              <p className="text-[11px] text-[#5A5A55]">Loading sources…</p>
            )}

            {detail.state === "error" && (
              <p className="text-[11px] text-[#E0A93C]">
                Could not load sources — {detail.error}. This is a fetch failure, not an
                absence of sourcing.
              </p>
            )}

            {detail.state === "ready" && detail.articles.length === 0 && (
              <p className="text-[11px] leading-relaxed text-[#8A8A82]">
                No source document is stored for this signal. It came from the{" "}
                <span className="text-[#C8C4BC] font-mono">{event.source || "feed"}</span>{" "}
                feed, which publishes structured alerts rather than articles — so there is
                a grade but no link to follow. We do not invent one.
              </p>
            )}

            {detail.state === "ready" && detail.articles.length > 0 && (
              <ul className="space-y-1.5">
                {detail.articles.map((a, i) => (
                  <li key={`${a.url}-${i}`} className="border border-[#1C1C1C] rounded-[2px] p-2.5 hover:border-[#2E2E2C] transition-colors">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-mono text-[10px] tracking-[0.06em] uppercase text-[#C8C4BC] truncate">
                        {a.source || "Unknown outlet"}
                      </span>
                      {a.date && <span className="font-mono text-[9px] text-[#5A5A55] shrink-0">{a.date}</span>}
                    </div>
                    <a
                      href={a.url} target="_blank" rel="noopener noreferrer"
                      className="text-[12px] leading-snug text-[#8FB8D8] hover:text-[#B8D4EC] hover:underline break-words"
                    >
                      {a.title} ↗
                    </a>
                  </li>
                ))}
              </ul>
            )}

            {/* The gate, stated. A single-source item must never read as assessed. */}
            {detail.state === "ready" && (
              <p className={[
                "mt-2 text-[11px] leading-relaxed",
                corroborated ? "text-[#7FA88C]" : "text-[#8A8A82]",
              ].join(" ")}>
                {corroborated
                  ? `Corroborated — ${gateCount} independent sources carry this. Meets the two-source bar.`
                  : `${gateCount || "No"} corroborating source${gateCount === 1 ? "" : "s"} on the two-source gate, so this is carried as ${ALERT_TYPES.informative.label} rather than assessed Intelligence.${
                      documentsOnFile === 0 ? " Source grading below is computed separately, from convergence with related events." : ""}`}
              </p>
            )}
          </section>

          {/* ── Grading ── */}
          {detail.grade?.grade && (
            <section>
              <h3 className="font-mono text-[9px] tracking-[0.2em] uppercase text-[#5A5A55] mb-2">
                Source grading
              </h3>
              <div className="flex items-center gap-2 mb-1.5">
                <Grade grade={detail.grade.grade} />
                <span className="text-[11px] text-[#8A8A82]">
                  {detail.grade.reliability?.label} · {detail.grade.credibility?.label}
                </span>
              </div>
              {Array.isArray(detail.grade.rationale) && detail.grade.rationale.length > 0 && (
                <ul className="space-y-0.5">
                  {detail.grade.rationale.map((r, i) => (
                    <li key={i} className="text-[11px] text-[#5A5A55]">— {r}</li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {/* ── Assets affected ── signal→asset attribution at the item level ── */}
          <section>
            <h3 className="font-mono text-[9px] tracking-[0.2em] uppercase text-[#5A5A55] mb-2">
              Assets affected
            </h3>
            {!c.assets || c.assets.count === 0 ? (
              <p className="text-[11px] text-[#8A8A82]">
                {event.geo_centroid_lat == null
                  ? "Not geolocated — cannot be attributed to specific sites."
                  : "No site falls within this event's extent."}
              </p>
            ) : (
              <>
                <p className="text-[11px] text-[#C8C4BC] mb-1.5 tabular-nums">
                  <span className="text-[#F0EDE8]">{c.assets.count}</span> sites ·{" "}
                  <span className="text-[#F0EDE8]">{c.assets.people.toLocaleString()}</span> people
                </p>
                <ul className="space-y-0.5">
                  {c.assets.sites.slice(0, 8).map(({ office, km }) => (
                    <li key={office.id}>
                      <button
                        type="button"
                        onClick={() => { onSelectSite?.(office.id); onClose?.(); }}
                        className="w-full text-left flex items-baseline justify-between gap-3 py-0.5 hover:text-[#F0EDE8] text-[#8A8A82]"
                      >
                        <span className="text-[11.5px] truncate">{office.name || office.city}</span>
                        <span className="font-mono text-[10px] tabular-nums shrink-0">{km} km</span>
                      </button>
                    </li>
                  ))}
                  {c.assets.sites.length > 8 && (
                    <li className="text-[10px] text-[#5A5A55] pt-0.5">
                      +{c.assets.sites.length - 8} more
                    </li>
                  )}
                </ul>
              </>
            )}
          </section>

          {/* ── Record ── */}
          <section>
            <h3 className="font-mono text-[9px] tracking-[0.2em] uppercase text-[#5A5A55] mb-2">Record</h3>
            <Row label="Detected">{fmtDate(event.first_detected_at) || "—"}</Row>
            <Row label="Updated">{fmtDate(event.last_updated_at) || "—"}</Row>
            <Row label="Feed">{event.source || "—"}</Row>
            {event.int_discipline && <Row label="Discipline">{event.int_discipline}</Row>}
            {c.validity.to && (
              <Row label="Valid to">
                {fmtDate(c.validity.to.toISOString())} · {c.validity.days}-day window for {event.category}
              </Row>
            )}
          </section>

          <Link
            to={`/event/${event.id}`}
            className="inline-block font-mono text-[10px] tracking-[0.12em] uppercase text-[#8FB8D8] hover:underline"
          >
            Open full record ↗
          </Link>
        </div>
      </aside>
    </div>
  );
}
