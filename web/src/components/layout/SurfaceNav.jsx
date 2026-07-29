// ─────────────────────────────────────────────────────────────────────────────
// SurfaceNav — the back-and-across bar for surfaces outside the main app shell.
//
// The shell surfaces (/world, /analyst, /following, /settings, /int) get their
// navigation from FeedHeader. Everything else — the customer decks, the operator
// board, the public scoreboard — had none, so each was a cul-de-sac: reachable by
// link and leavable only by editing the address bar. A reader sent "look at the
// exec deck" could not get back to where they came from, and the two Wipro
// altitudes could not see each other at all.
//
// Back is history-aware on purpose. These surfaces write their own state to the
// query string with replace:true, so history holds the page the reader ARRIVED
// from; popping it returns them there rather than to a hardcoded parent they may
// never have visited. With nothing to pop (a link opened cold in a new tab) it
// falls through to `fallback`, which each surface sets to its real parent.
// ─────────────────────────────────────────────────────────────────────────────
import { Link, useLocation } from "react-router-dom";
import { useTheme } from "../../hooks/useTheme.js";
import { useGoBack } from "../../hooks/useGoBack.js";

function SunIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor"
      strokeWidth="1.4" strokeLinecap="round" aria-hidden="true">
      <circle cx="7" cy="7" r="2.5" />
      <path d="M7 1v1.5M7 11.5V13M1 7h1.5M11.5 7H13M2.93 2.93l1.06 1.06M10.01 10.01l1.06 1.06M11.07 2.93l-1.06 1.06M3.99 10.01l-1.06 1.06" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 13 13" fill="none" stroke="currentColor"
      strokeWidth="1.4" strokeLinecap="round" aria-hidden="true">
      <path d="M11 8.5A5.5 5.5 0 1 1 4.5 2a4 4 0 0 0 6.5 6.5z" />
    </svg>
  );
}

/**
 * @param links     [{ to, label }] — sibling surfaces, rendered after Back.
 * @param fallback  where Back goes when there is no history to pop.
 * @param showTheme render the day/night switch (surfaces that are theme-aware).
 * @param tone      "var"  — inherits the exec deck's --xd-* ramp.
 *                  "ink"  — inherits the app's paper/ink tokens.
 *                  "dark" — fixed dark, for the permanently-dark operator board.
 */
export default function SurfaceNav({
  links = [], fallback = "/world", showTheme = true, tone = "ink", className = "",
}) {
  const { pathname } = useLocation();
  const { isDark, toggle } = useTheme();
  const goBack = useGoBack(fallback);

  // Every entry is a COMPLETE literal class string, including the hover: variants.
  // Tailwind's JIT scans source text for class names, so a composed `hover:${x}`
  // would emit a class at runtime that was never generated at build time — the
  // hover state would silently do nothing.
  const T = {
    var: {
      bar:  "border-[var(--xd-8)] bg-[var(--xd-1)]",
      mid:  "text-[var(--xd-20)] hover:text-[var(--xd-23)]",
      dim:  "text-[var(--xd-19)] hover:text-[var(--xd-23)]",
      rule: "bg-[var(--xd-11)]",
      edge: "border-[var(--xd-11)] hover:border-[var(--xd-15)]",
    },
    ink: {
      bar:  "border-ink/10 bg-paper",
      mid:  "text-ink/55 hover:text-crimson",
      dim:  "text-ink/40 hover:text-crimson",
      rule: "bg-ink/15",
      edge: "border-ink/15 hover:border-crimson/40",
    },
    dark: {
      bar:  "border-[rgba(240,237,232,0.08)] bg-[#0B0E13]",
      mid:  "text-[rgba(232,228,220,0.6)] hover:text-[#E8E4DC]",
      dim:  "text-[rgba(232,228,220,0.4)] hover:text-[#E8E4DC]",
      rule: "bg-[rgba(232,228,220,0.15)]",
      edge: "border-[rgba(232,228,220,0.15)] hover:border-[rgba(232,228,220,0.35)]",
    },
  }[tone];

  return (
    <nav className={`no-print border-b ${T.bar} px-6 lg:px-10 py-2 flex flex-wrap items-center
                     gap-x-5 gap-y-2 ${className}`}>
      <button type="button" onClick={goBack}
        className={`flex items-center gap-1.5 font-mono text-[10px] tracking-[0.14em] uppercase
                    ${T.mid} transition-colors`}>
        <svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor"
          strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M7.5 2L3.5 6l4 4" />
        </svg>
        Back
      </button>

      {links.length > 0 && <span className={`w-px h-3 ${T.rule}`} aria-hidden="true" />}

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        {links.map((l) => (
          <Link key={l.to} to={l.to}
            aria-current={pathname === l.to ? "page" : undefined}
            className={`font-mono text-[10px] tracking-[0.14em] uppercase ${T.dim} transition-colors`}>
            {l.label}
          </Link>
        ))}
      </div>

      {showTheme && (
        <button type="button" onClick={toggle} aria-pressed={!isDark}
          title={isDark ? "Switch to day mode" : "Switch to night mode"}
          className={`ml-auto flex items-center gap-1.5 font-mono text-[10px] tracking-[0.14em]
                      uppercase ${T.dim} border ${T.edge} px-2.5 py-1
                      rounded-[2px] transition-colors`}>
          {isDark ? <SunIcon /> : <MoonIcon />}
          {isDark ? "Day" : "Night"}
        </button>
      )}
    </nav>
  );
}
