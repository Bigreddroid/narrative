import { useState, useEffect } from "react";
import { api } from "../lib/api.js";
import { getCategoryColor } from "../lib/colors.js";

// "How this affects you" — the consequence payoff strip under the globe. Binds to
// GET /exposure/me (the user's profile-scoped exposure) and turns each exposure
// driver into a so-what/action card. This is the differentiator: not "a hotspot in
// the Gulf" but "N% of YOUR exposure comes from this — here's what to do."
//
// The action line is a deterministic, honest template scoped by the driver's
// category ($0, no LLM). Phase 5's reasoner can later replace it with grounded
// multi-step reasoning; the card shape stays the same.

const CRIMSON = "#C80028";
const FG = "#F0EDE8";

const ACTIONS = {
  conflict:  "Review contingency routing and counterparty risk in the affected corridor.",
  military:  "Review contingency routing and counterparty risk in the affected corridor.",
  climate:   "Check asset resilience, insurance cover, and alternate supply for the region.",
  disaster:  "Check asset resilience, insurance cover, and alternate supply for the region.",
  cyber:     "Verify patching and incident response for exposed systems and vendors.",
  economy:   "Hedge or pre-book exposed positions before the move is priced in.",
  markets:   "Hedge or pre-book exposed positions before the move is priced in.",
  energy:    "Lock in supply and pricing; identify alternate sources for exposed sites.",
  health:    "Review continuity plans for staffing and supply in the affected area.",
};
function actionFor(category) {
  return ACTIONS[(category || "").toLowerCase()]
    || "Monitor closely and prepare a mitigation for the affected operations.";
}

function DriverCard({ d }) {
  const color = getCategoryColor(d.category);
  const pct = Math.round(d.pct || 0);
  return (
    <div
      className="flex-shrink-0 w-72 border p-3 space-y-2"
      style={{ borderColor: "rgba(232,228,220,0.14)", backgroundColor: "rgba(20,20,20,0.7)" }}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[9px] font-bold uppercase tracking-widest" style={{ color }}>
          {d.category || "signal"}
        </span>
        {pct > 0 && (
          <span className="text-[10px] font-mono tabular-nums" style={{ color: CRIMSON }}>
            {pct}% of your exposure
          </span>
        )}
      </div>
      <p className="text-[13px] font-semibold leading-snug" style={{ color: FG }}>
        {d.title || "Unnamed driver"}
      </p>
      <p className="text-[11px] leading-snug" style={{ color: "rgba(240,237,232,0.6)" }}>
        {actionFor(d.category)}
      </p>
    </div>
  );
}

export default function HowThisAffectsYou({ profileActive, profileLabel, onSetLens }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    if (!profileActive) return;
    let alive = true;
    setData(null);
    setErr(false);
    api.get("/exposure/me")
      .then((r) => { if (alive) setData(r); })
      .catch(() => { if (alive) setErr(true); });
    return () => { alive = false; };
  }, [profileActive]);

  const shell = "px-4 py-3";
  const shellStyle = { borderTop: "1px solid rgba(232,228,220,0.1)", backgroundColor: "rgba(15,15,15,0.9)" };

  // No lens set yet — nudge to Settings (mirrors the feed's "For You" gate).
  if (!profileActive) {
    return (
      <div className={`${shell} flex items-center gap-3`} style={shellStyle}>
        <span className="text-[10px] font-mono uppercase tracking-widest" style={{ color: "rgba(240,237,232,0.5)" }}>
          How this affects you
        </span>
        <button onClick={onSetLens} className="text-[11px] font-semibold" style={{ color: CRIMSON }}>
          Set your lens →
        </button>
        <span className="text-[11px]" style={{ color: "rgba(240,237,232,0.35)" }}>
          to see your personalised consequences on these events.
        </span>
      </div>
    );
  }

  const drivers = data?.exposure?.drivers || [];
  const score = Math.round(data?.exposure?.score || 0);

  if (err || (data && drivers.length === 0)) {
    return (
      <div className={shell} style={shellStyle}>
        <span className="text-[10px] font-mono uppercase tracking-widest" style={{ color: "rgba(240,237,232,0.4)" }}>
          {err ? "Couldn't load your exposure." : "No current events hit your profile — you're clear for now."}
        </span>
      </div>
    );
  }

  return (
    <div className={`${shell} space-y-2`} style={shellStyle}>
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-mono font-bold uppercase tracking-[0.3em] text-crimson">
          How this affects you
        </span>
        {profileLabel && (
          <span className="text-[10px] font-mono" style={{ color: "rgba(240,237,232,0.4)" }}>
            · {profileLabel}
          </span>
        )}
        {data && (
          <span className="ml-auto text-[10px] font-mono tabular-nums" style={{ color: "rgba(240,237,232,0.45)" }}>
            exposure index {score}
          </span>
        )}
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {!data ? (
          <span className="text-[11px]" style={{ color: "rgba(240,237,232,0.35)" }}>
            Loading your consequences…
          </span>
        ) : (
          drivers.map((d, i) => <DriverCard key={d.id || i} d={d} />)
        )}
      </div>
    </div>
  );
}
