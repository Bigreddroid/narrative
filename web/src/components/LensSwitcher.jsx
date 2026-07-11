import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { api } from "../lib/api.js";
import { getStoredUser, setStoredUser } from "../hooks/useUser.js";
import { useProfile } from "../hooks/useProfile.js";

// ─── Lens switcher (R2 demo) ──────────────────────────────────────────────────
// One click swaps the whole app to a different operator's point of view. Each
// preset is a full lens (sectors + named routes/chokepoints + purpose); applying
// it writes the stored user, which — via the same-tab user event — instantly
// re-scopes Exposure, the Feed "For You" ranking, the World heat layer and the
// Analyst readout on the *same* live events. Proof that the lens is real.

export const LENS_PRESETS = [
  {
    id: "eu-logistics",
    label: "EU Logistics",
    blurb: "Rotterdam · Suez — shipping desk",
    patch: {
      spending_categories: ["Shipping & Logistics", "Energy", "Manufacturing"],
      regions: ["Rotterdam", "Suez Canal", "Red Sea"],
      purpose: ["Protect supply chain"],
      country: "Germany",
    },
  },
  {
    id: "gulf-energy",
    label: "Gulf Energy",
    blurb: "Hormuz · Persian Gulf — energy desk",
    patch: {
      spending_categories: ["Energy", "Finance"],
      regions: ["Strait of Hormuz", "Persian Gulf", "Bab-el-Mandeb"],
      purpose: ["Protect capital"],
      country: "United States",
    },
  },
  {
    id: "asia-tech",
    label: "Asia Tech",
    blurb: "Taiwan · South China Sea — chips",
    patch: {
      spending_categories: ["Technology", "Manufacturing"],
      regions: ["Taiwan Strait", "South China Sea", "Singapore"],
      purpose: ["Protect supply chain"],
      country: "Japan",
    },
  },
];

// Which preset (if any) the current stored regions match — drives the active tick.
function matchPreset(profileRegions) {
  const set = new Set((profileRegions || []).map((r) => r.toLowerCase()));
  return LENS_PRESETS.find((p) =>
    p.patch.regions.some((r) => set.has(r.toLowerCase())))?.id || null;
}

export default function LensSwitcher({ dark = false }) {
  const profile = useProfile();
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const btnRef = useRef(null);

  const activeId = matchPreset(profile.regions);
  const activeLabel = LENS_PRESETS.find((p) => p.id === activeId)?.label
    || (profile.active ? profile.label : "No lens");

  const apply = (preset) => {
    const current = getStoredUser() || {};
    const next = { ...current, ...preset.patch, watched_assets: current.watched_assets || [] };
    setStoredUser(next);                         // instant same-tab re-scope
    api.patch("/users/me", preset.patch).catch(() => {});  // persist best-effort
    setOpen(false);
  };

  const toggle = () => {
    const r = btnRef.current?.getBoundingClientRect();
    if (r) setPos({ top: r.bottom + 6, left: Math.max(8, r.right - 220) });
    setOpen((o) => !o);
  };

  // Close on Escape for keyboard users.
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const fg = dark ? "rgba(240,237,232,0.65)" : "inherit";

  return (
    <>
      <button
        ref={btnRef}
        onClick={toggle}
        className="flex items-center gap-1.5 hover:text-crimson transition-colors cursor-pointer"
        style={{ color: fg }}
        title="Switch your lens — re-scopes the whole app"
      >
        <svg width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round">
          <path d="M7 1.5L12.5 7 7 12.5 1.5 7z" />
        </svg>
        <span className="normal-case">Lens: <span className="font-semibold">{activeLabel}</span></span>
        <span style={{ fontSize: 8, opacity: 0.6 }}>▼</span>
      </button>

      {open && createPortal(
        <>
          <div className="fixed inset-0 z-[90]" onClick={() => setOpen(false)} />
          <div
            className="fixed z-[100] w-[240px] border shadow-2xl bg-paper"
            style={{ top: pos.top, left: pos.left, borderColor: "rgba(26,26,26,0.15)" }}
          >
            <div className="px-3 py-2 border-b border-ink/10 text-[9px] font-mono uppercase tracking-widest text-ink/40">
              Point of view
            </div>
            {LENS_PRESETS.map((p) => {
              const active = p.id === activeId;
              return (
                <button
                  key={p.id}
                  onClick={() => apply(p)}
                  className="w-full text-left px-3 py-2.5 border-b border-ink/8 transition-colors hover:bg-crimson/[0.05]"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-[13px] font-semibold text-ink">{p.label}</span>
                    {active && <span className="text-crimson text-[9px] font-mono uppercase tracking-widest ml-auto">Active</span>}
                  </div>
                  <p className="text-[11px] text-ink/45 mt-0.5">{p.blurb}</p>
                </button>
              );
            })}
            <button
              onClick={() => { setOpen(false); window.location.assign("/settings"); }}
              className="w-full text-left px-3 py-2.5 text-[11px] text-ink/50 hover:text-crimson transition-colors"
            >
              Customise in Settings →
            </button>
          </div>
        </>,
        document.body,
      )}
    </>
  );
}
