// ─────────────────────────────────────────────────────────────────────────────
//  Advice — official government travel advice for the countries you operate in.
//
//  Every word on this page was written by a named government and is shown with its
//  publication date and a link to the original. We author nothing here, and there is
//  no endpoint that would let us: the incumbent's ~143 advice sheets come from a
//  research desk we do not have, and inventing guidance would be the same fabrication
//  this project refuses everywhere else.
//
//  🔴 The two authorities are shown SIDE BY SIDE, never merged. The US State
//  Department uses Level 1-4; the UK FCDO uses alert statuses like "avoid all travel
//  to parts". Different governments, different instruments, different publics.
//  Blending them into one number would invent a precision neither claims — and a
//  reader acting on that number would believe two governments agreed when they had
//  never been asked the same question. Where they disagree, that disagreement IS the
//  information.
//
//  Countries with no sheet are listed as uncovered rather than omitted. "We hold no
//  advisory for Malta" and "Malta is not on this page" look identical to a reader,
//  and only one of them is honest about a gap in the library.
// ─────────────────────────────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api.js";

const AUTHORITY_SHORT = {
  gov_us_state_dept: "US State Dept",
  gov_uk_fcdo: "UK FCDO",
};

// Colour comes from the ISSUER's own severity words, not from a score of ours.
// Unrecognised wording is left neutral rather than guessed at.
function tone(a) {
  const s = `${a.level_code || ""} ${a.level_label || ""}`.toLowerCase();
  if (s.includes("l4") || s.includes("do not travel") || s.includes("all travel")) return "#FF5C43";
  if (s.includes("l3") || s.includes("reconsider") || s.includes("essential")) return "#E0A93C";
  if (s.includes("l2") || s.includes("increased caution") || s.includes("parts")) return "#E0C93C";
  if (s.includes("l1") || s.includes("normal precaution") || s.includes("no specific")) return "#5FBF74";
  return "#8A8A82";
}

const fmt = (iso) => (iso ? new Date(iso).toISOString().slice(0, 10) : "—");

export default function Advice() {
  const [state, setState] = useState({ loading: true, countries: [], error: null,
                                       covered: 0, uncovered: 0 });
  const [open, setOpen] = useState(null);

  useEffect(() => {
    let alive = true;
    api.get("/advisories/for-register", { timeoutMs: 15000 })
      .then((d) => alive && setState({
        loading: false, countries: d?.countries ?? [], error: null,
        covered: d?.covered ?? 0, uncovered: d?.uncovered ?? 0,
      }))
      .catch((e) => alive && setState({
        loading: false, countries: [], covered: 0, uncovered: 0,
        error: e?.status === 403
          ? "This page reads the countries in your site register — available once your account belongs to an organization."
          : (e?.message || "Could not load the advice library"),
      }));
    return () => { alive = false; };
  }, []);

  return (
    <div className="min-h-screen bg-[#050505] text-[#F0EDE8] px-6 lg:px-10 py-10">
      <p className="font-mono text-[10px] tracking-[0.28em] uppercase text-[#6A6A64]">
        Duty of care · official sources only
      </p>
      <h1 className="font-display leading-[0.9] tracking-tight mt-2"
        style={{ fontSize: "clamp(2rem, 4.5vw, 3.2rem)" }}>
        TRAVEL <span className="text-crimson-light">ADVICE</span>
      </h1>
      <p className="text-[13px] text-[#8A8A82] mt-4 max-w-[62ch] leading-relaxed">
        Published by the governments named below, shown with their own wording, their
        own date and a link to the original. We write none of it. Where two governments
        say different things about the same country, both are shown — the disagreement
        is the information.
      </p>

      {state.loading && (
        <p className="font-mono text-[11px] tracking-[0.2em] uppercase text-[#6A6A64] mt-10">
          Reading the advice library…
        </p>
      )}

      {state.error && (
        <p className="text-[12px] text-[#FF7A63] mt-8 max-w-[62ch]">{state.error}</p>
      )}

      {!state.loading && !state.error && state.countries.length === 0 && (
        <p className="text-[13px] text-[#8A8A82] mt-8 max-w-[62ch]">
          No countries in your register yet, so there is nothing to look up. Import a
          site register and this page fills itself from official sources.
        </p>
      )}

      {!state.loading && state.countries.length > 0 && (
        <>
          <p className="font-mono text-[11px] text-[#6A6A64] mt-8 tabular-nums">
            {state.covered} of {state.countries.length} countries covered
            {state.uncovered > 0 && (
              // Said plainly. A missing sheet is a gap in the library, not a clean bill.
              <span className="text-[#E0A93C]"> · {state.uncovered} with no official sheet held</span>
            )}
          </p>

          <div className="mt-6 space-y-3">
            {state.countries.map((c) => (
              <div key={c.country} className="border border-[#1C1C1C] bg-[#0A0A0A]">
                <div className="px-4 py-3 flex flex-wrap items-baseline gap-x-4 gap-y-1">
                  <span className="text-[14px]">{c.country}</span>
                  <span className="font-mono text-[10px] text-[#4A4845]">{c.country_iso || "—"}</span>
                  {!c.covered && (
                    <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-[#E0A93C]">
                      No official sheet held
                    </span>
                  )}
                </div>

                {c.advisories.map((a) => (
                  <div key={a.id} className="px-4 py-3 border-t border-[#141414]">
                    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                      <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-[#8A8A82]">
                        {AUTHORITY_SHORT[a.authority] || a.authority}
                      </span>
                      <span className="text-[12px]" style={{ color: tone(a) }}>
                        {a.level_label}
                      </span>
                      <span className="font-mono text-[10px] text-[#4A4845] tabular-nums">
                        published {fmt(a.published_at)}
                      </span>
                      {/* The same Admiralty grade every other source on the platform
                          carries — official government sources are not exempt from it. */}
                      <span className="font-mono text-[10px] text-[#4A4845]">
                        Admiralty {a.grade}
                      </span>
                    </div>
                    {a.summary && (
                      <p className="text-[12px] text-[#8A8A82] mt-1.5 leading-relaxed">{a.summary}</p>
                    )}
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
                      {a.url && (
                        <a href={a.url} target="_blank" rel="noreferrer"
                          className="font-mono text-[10px] uppercase tracking-[0.14em] text-crimson-light hover:underline">
                          Read the original →
                        </a>
                      )}
                      <button type="button" onClick={() => setOpen(open === a.id ? null : a.id)}
                        className="font-mono text-[10px] uppercase tracking-[0.14em] text-[#6A6A64] hover:text-[#F0EDE8]">
                        {open === a.id ? "Hide sections" : "Full sheet"}
                      </button>
                    </div>
                    {open === a.id && <Sections id={a.id} />}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </>
      )}

      <p className="font-mono text-[10px] text-[#4A4845] mt-10 leading-relaxed">
        Advisory text © the issuing government. Advisory only — physical response via partner.
        {" "}<Link to="/wipro/exec" className="text-crimson-light hover:underline">Executive deck →</Link>
      </p>
    </div>
  );
}

// Fetched only when opened: a full sheet is several thousand words per country, and
// pulling every one on page load would make the list slow to serve no purpose.
function Sections({ id }) {
  const [d, setD] = useState({ loading: true, sections: {}, error: null });
  useEffect(() => {
    let alive = true;
    api.get(`/advisories/${id}`, { timeoutMs: 15000 })
      .then((r) => alive && setD({ loading: false, sections: r?.sections || {}, error: null }))
      .catch((e) => alive && setD({ loading: false, sections: {}, error: e?.message || "Unavailable" }));
    return () => { alive = false; };
  }, [id]);

  if (d.loading) return <p className="text-[11px] text-[#4A4845] mt-3">Loading the full sheet…</p>;
  if (d.error) return <p className="text-[11px] text-[#FF7A63] mt-3">{d.error}</p>;

  const keys = Object.keys(d.sections);
  if (!keys.length) {
    return (
      <p className="text-[11px] text-[#4A4845] mt-3">
        This authority publishes no sectioned sheet for this country — the summary above
        is everything it gave us.
      </p>
    );
  }
  return (
    <div className="mt-3 space-y-3 border-l border-[#1C1C1C] pl-4">
      {keys.map((k) => (
        <div key={k}>
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-[#6A6A64]">
            {k.replace(/-/g, " ")}
          </p>
          <p className="text-[12px] text-[#8A8A82] mt-1 leading-relaxed">{d.sections[k]}</p>
        </div>
      ))}
    </div>
  );
}
