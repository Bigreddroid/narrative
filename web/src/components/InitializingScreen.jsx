// ─── Initializing screen ──────────────────────────────────────────────────────
// Shown while the live feed is still coming up: either the first fetch is in
// flight, or the DB is genuinely empty because the scheduler is still scraping,
// embedding and ranking its first batch of real events (the first few minutes of a
// fresh boot). It replaces a bare spinner / flat "no events" with an honest,
// on-brand "the wire is warming up" state so a fresh install doesn't look broken.
//
// `dark` switches the palette for the dark Intelligence Deck vs. the light feed.

export default function InitializingScreen({
  dark = false,
  title = "Initializing",
  note = "Bringing the live wire up — scraping, embedding and ranking real events. This can take a few minutes on a fresh boot. New signals appear here on their own.",
}) {
  const fg      = dark ? "rgba(240,237,232,0.92)" : "#1a1a1a";
  const fgMuted = dark ? "rgba(240,237,232,0.45)" : "rgba(26,26,26,0.45)";
  const crimson = "#C80028";

  return (
    <div className="flex flex-col items-center justify-center w-full h-full min-h-[280px] px-6 text-center select-none">
      {/* Pulsing scanner ring */}
      <div className="relative w-12 h-12 mb-6">
        <div
          className="absolute inset-0 rounded-full border-2 animate-spin"
          style={{ borderColor: dark ? "rgba(240,237,232,0.12)" : "rgba(26,26,26,0.12)", borderTopColor: crimson }}
        />
        <div className="absolute inset-0 rounded-full animate-ping" style={{ backgroundColor: `${crimson}22` }} />
      </div>

      <div className="flex items-center gap-2 mb-2">
        <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: crimson }} />
        <span className="text-[11px] font-mono font-bold uppercase tracking-[0.35em]" style={{ color: fg }}>
          {title}
        </span>
      </div>

      <p className="max-w-sm text-[12px] leading-relaxed" style={{ color: fgMuted }}>
        {note}
      </p>

      {/* Scanning bars — motion so it never reads as a frozen screen */}
      <div className="flex items-end gap-1 mt-6 h-4" aria-hidden="true">
        {[0, 1, 2, 3, 4].map((i) => (
          <span
            key={i}
            className="w-1 rounded-sm animate-pulse"
            style={{
              height: `${6 + ((i * 7) % 16)}px`,
              backgroundColor: crimson,
              opacity: 0.55,
              animationDelay: `${i * 140}ms`,
              animationDuration: "1.1s",
            }}
          />
        ))}
      </div>
    </div>
  );
}
