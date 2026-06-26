import { useState, useEffect, useMemo } from "react";
import HlsPlayer from "./HlsPlayer.jsx";
import { useLiveStreams } from "../../hooks/useLiveStreams.js";
import { useTheme } from "../../hooks/useTheme.js";

// Live-news tab: a main player + a channel grid selector. Channels come from
// the tier-aware backend manifest (official broadcaster feeds; optional iptv-org
// expansion). Real streams only — no simulated content.
export default function LiveNewsTab() {
  const { channels, loading, error } = useLiveStreams();
  const { isDark } = useTheme();
  const [activeId, setActiveId] = useState(null);

  useEffect(() => {
    if (!activeId && channels.length > 0) setActiveId(channels[0].id);
  }, [channels, activeId]);

  const active = useMemo(
    () => channels.find((c) => c.id === activeId) || null,
    [channels, activeId]
  );

  const bg = isDark ? "#0E1520" : "#111111";
  const FG = "#F0EDE8";
  const FG40 = "rgba(240,237,232,0.4)";
  const BD = "rgba(240,237,232,0.1)";

  return (
    <div className="flex-1 flex flex-col overflow-hidden" style={{ backgroundColor: bg }}>
      {/* Player */}
      <div className="flex-shrink-0 relative w-full bg-black" style={{ aspectRatio: "16 / 9", maxHeight: "62vh" }}>
        {loading ? (
          <div className="flex items-center justify-center w-full h-full">
            <div className="w-6 h-6 border-2 rounded-full animate-spin"
              style={{ borderColor: "rgba(240,237,232,0.15)", borderTopColor: "#C80028" }} />
          </div>
        ) : (
          <HlsPlayer channel={active} />
        )}
      </div>

      {/* Now-playing bar */}
      <div className="flex items-center gap-2 px-4 md:px-6 py-2.5" style={{ borderBottom: `1px solid ${BD}` }}>
        <span className="w-1.5 h-1.5 rounded-full bg-crimson animate-pulse" />
        <span className="text-[10px] font-bold uppercase tracking-[0.3em] text-crimson">Live</span>
        {active && <span className="text-[12px] font-semibold" style={{ color: FG }}>{active.name}</span>}
        {error && (
          <span className="ml-auto text-[10px] uppercase tracking-wider" style={{ color: FG40 }}>
            Offline — showing official channels
          </span>
        )}
      </div>

      {/* Channel grid */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 pb-20 md:pb-6">
        <p className="text-[9px] font-mono font-bold uppercase tracking-[0.4em] mb-3" style={{ color: FG40 }}>
          Channels
        </p>
        {channels.length === 0 && !loading ? (
          <p className="text-[11px] uppercase tracking-wider" style={{ color: FG40 }}>
            No channels available.
          </p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
            {channels.map((c) => {
              const isActive = c.id === activeId;
              return (
                <button
                  key={c.id}
                  onClick={() => setActiveId(c.id)}
                  className="flex items-center gap-2 px-3 py-2.5 text-left transition-colors border rounded-sm"
                  style={{
                    color: isActive ? FG : "rgba(240,237,232,0.55)",
                    borderColor: isActive ? "rgba(200,0,40,0.6)" : BD,
                    backgroundColor: isActive ? "rgba(200,0,40,0.12)" : "transparent",
                  }}
                >
                  {c.logo ? (
                    <img src={c.logo} alt="" className="w-6 h-6 object-contain flex-shrink-0"
                      onError={(e) => { e.currentTarget.style.display = "none"; }} />
                  ) : (
                    <span className="w-6 h-6 flex-shrink-0 flex items-center justify-center text-[9px] font-bold rounded-sm"
                      style={{ backgroundColor: "rgba(240,237,232,0.08)" }}>
                      {(c.name || "?").slice(0, 2).toUpperCase()}
                    </span>
                  )}
                  <span className="min-w-0">
                    <span className="block text-[11px] font-semibold truncate">{c.name}</span>
                    <span className="block text-[9px] uppercase tracking-wider" style={{ color: FG40 }}>
                      {c.region || c.lang || ""}{c.official === false ? " · community" : ""}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
