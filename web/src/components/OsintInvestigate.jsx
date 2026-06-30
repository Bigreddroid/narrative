import { useState, useEffect } from "react";
import { api } from "../lib/api.js";

// Shared OSINT investigate surface: live enrichment facts (Tier 1) on top, then
// every catalog tool for the entity, each rendered by its capability —
//   live   → fetched facts (shown as cards above) + the source link
//   pivot  → one-click; opens the tool's native search (or a site-scoped search)
//            with the value pre-filled
//   launch → opens the tool and copies the value to the clipboard
// Used by the OSINT page and inline on an event's entity chips.

const KIND_LABELS = {
  username: "Username", domain: "Domain / URL", ip: "IP / MAC", email: "Email",
  name: "Person / Org", location: "Location", phone: "Phone", image: "Image",
  crypto: "Crypto Address", hash: "File Hash", cve: "CVE", vehicle: "Vessel / Aircraft",
  media: "Media / Image URL",
};

const CAP_BADGE = {
  live: { label: "live", color: "#2E8B57", title: "Live data fetched in-app" },
  pivot: { label: "1-click", color: "#1E5FA8", title: "Opens with the value pre-filled" },
  launch: { label: "launch", color: "#B07020", title: "Opens the tool; value copied to clipboard" },
};

function FactCards({ facts }) {
  if (!facts?.length) return null;
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-3">
      {facts.map((f, i) => (
        <div key={i} className="border border-emerald-700/30 bg-emerald-700/[0.04] px-2.5 py-1.5">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[8px] font-mono uppercase tracking-wider text-ink/40">{f.label}</span>
            <span className="text-[8px] font-mono text-emerald-700/80">{f.source}</span>
          </div>
          {f.url ? (
            <a href={f.url} target="_blank" rel="noopener noreferrer"
               className="text-[12px] text-ink hover:text-crimson break-words">{f.value}</a>
          ) : (
            <span className="text-[12px] text-ink break-words">{f.value}</span>
          )}
        </div>
      ))}
    </div>
  );
}

function ToolPill({ t }) {
  const [copied, setCopied] = useState(false);
  const cap = CAP_BADGE[t.capability] || CAP_BADGE.launch;
  const isLaunch = t.capability === "launch" || (!t.templated && t.note);

  const onLaunch = (e) => {
    // Best-effort: copy the value so the user can paste into the tool's own box.
    if (t._value && navigator?.clipboard?.writeText) {
      e.stopPropagation();
      navigator.clipboard.writeText(t._value).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1200);
      }).catch(() => {});
    }
  };

  return (
    <a href={t.url} target="_blank" rel="noopener noreferrer"
       onClick={isLaunch ? onLaunch : undefined}
       title={`${cap.title}${t.note ? " — " + t.note : ""}${t.registration ? " (registration required)" : ""}`}
       className="inline-flex items-center gap-1.5 text-[12px] border border-ink/15 px-2.5 py-1.5 hover:border-crimson hover:text-crimson transition-colors text-ink/75">
      <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: cap.color }} />
      <span>{copied ? "copied ✓" : t.name}</span>
      {!t.native && t.templated && <span className="text-[8px] text-ink/35" title="site-scoped search">site</span>}
      {t.registration && <span className="text-[8px] text-amber-700/70" title="registration required">reg</span>}
      {isLaunch && !copied && <span className="text-[9px] text-ink/35">↗</span>}
    </a>
  );
}

export default function OsintInvestigate({ value, kind, compact = false }) {
  const [tools, setTools] = useState([]);
  const [facts, setFacts] = useState([]);
  const [resolvedKind, setResolvedKind] = useState(kind);
  const [caps, setCaps] = useState(null);
  const [enrichable, setEnrichable] = useState(false);
  const [loading, setLoading] = useState(true);
  const [enriching, setEnriching] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setFacts([]);
    const qs = new URLSearchParams({ value, ...(kind ? { kind } : {}) }).toString();
    api.get(`/osint/investigate?${qs}`)
      .then((d) => {
        if (!alive) return;
        const rk = d?.kind || kind;
        setResolvedKind(rk);
        setCaps(d?.capabilities || null);
        setEnrichable(!!d?.enrichable);
        setTools((d?.tools || []).map((t) => ({ ...t, _value: value })));
        // Auto-fetch live facts when the kind supports it.
        if (d?.enrichable) {
          setEnriching(true);
          api.get(`/osint/enrich?${qs}`)
            .then((e) => { if (alive) setFacts(e?.facts || []); })
            .catch(() => { if (alive) setFacts([]); })
            .finally(() => { if (alive) setEnriching(false); });
        }
      })
      .catch(() => { if (alive) { setTools([]); setCaps(null); } })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [value, kind]);

  return (
    <div className={compact ? "" : "mb-8 border border-crimson/30 bg-crimson/[0.03] p-4"}>
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <span className="text-[9px] font-mono uppercase tracking-[0.3em] text-crimson">Investigate</span>
        <span className="text-sm font-semibold text-ink break-all">{value}</span>
        {resolvedKind && (
          <span className="text-[9px] font-mono uppercase tracking-wider border border-ink/15 px-1.5 py-px text-ink/45">
            {KIND_LABELS[resolvedKind] || resolvedKind}
          </span>
        )}
        {caps && (
          <span className="text-[9px] font-mono text-ink/35 ml-auto">
            {caps.live ? `${caps.live} live · ` : ""}{caps.pivot || 0} 1-click{caps.launch ? ` · ${caps.launch} launch` : ""}
          </span>
        )}
      </div>

      {loading ? (
        <p className="text-[11px] font-mono text-ink/30 py-3">Resolving lookups…</p>
      ) : (
        <>
          {enrichable && (enriching || facts.length > 0) && (
            <div className="mb-3">
              <p className="text-[9px] font-mono uppercase tracking-[0.2em] text-emerald-700/70 mb-1.5">
                Live facts {enriching && <span className="text-ink/30">· fetching…</span>}
              </p>
              {facts.length > 0
                ? <FactCards facts={facts} />
                : !enriching && <p className="text-[11px] font-mono text-ink/30 mb-2">No live facts returned.</p>}
            </div>
          )}

          {tools.length === 0 ? (
            <p className="text-[11px] font-mono text-ink/30 py-2">No lookups for this entity kind.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {tools.map((t, i) => <ToolPill key={`${t.name}-${i}`} t={t} />)}
            </div>
          )}
        </>
      )}
    </div>
  );
}
