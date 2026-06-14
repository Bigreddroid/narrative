import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { useTheme } from "../../hooks/useTheme.js";
import { useUser } from "../../hooks/useUser.js";
import { setStoredUser } from "../../hooks/useUser.js";
import { clearToken } from "../../lib/api.js";
import { TIERS } from "../../lib/tiers.js";

const CATEGORIES = ["All", "Geopolitics", "Conflict", "Economics", "Climate", "Technology", "Health", "Policy", "Security"];

function SunIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round">
      <circle cx="7" cy="7" r="2.5" />
      <line x1="7" y1="1" x2="7" y2="2.5" />
      <line x1="7" y1="11.5" x2="7" y2="13" />
      <line x1="1" y1="7" x2="2.5" y2="7" />
      <line x1="11.5" y1="7" x2="13" y2="7" />
      <line x1="2.93" y1="2.93" x2="3.99" y2="3.99" />
      <line x1="10.01" y1="10.01" x2="11.07" y2="11.07" />
      <line x1="11.07" y1="2.93" x2="10.01" y2="3.99" />
      <line x1="3.99" y1="10.01" x2="2.93" y2="11.07" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round">
      <path d="M11 8.5A5.5 5.5 0 1 1 4.5 2a4 4 0 0 0 6.5 6.5z" />
    </svg>
  );
}

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

export default function FeedHeader({ activeCategory, onCategoryChange, activeTab, onTabChange, searchValue, onSearchChange }) {
  const [searchOpen, setSearchOpen] = useState(false);
  const navigate = useNavigate();
  const { isDark, toggle } = useTheme();
  const { user, tier }     = useUser();
  const tierMeta           = TIERS[tier] || TIERS.free;
  const firstName          = user?.name?.split(" ")[0] || "there";

  const handleSignOut = () => {
    clearToken();
    setStoredUser(null);
    navigate("/auth");
  };

  const handleSearchToggle = () => {
    if (searchOpen) onSearchChange("");
    setSearchOpen(s => !s);
  };

  return (
    <header className="bg-paper sticky top-0 z-50 border-b border-ink/10">

      {/* ── Desktop utility bar — hidden on mobile ── */}
      <div className="hidden md:flex max-w-[1400px] mx-auto px-6 justify-between items-center py-1.5 border-b border-ink/8 text-[11px] text-ink/45 tracking-wide">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-crimson animate-pulse" />
          <span>Intelligence Live</span>
        </div>
        <div className="flex items-center gap-5">
          <AnimatePresence>
            {searchOpen && (
              <motion.input
                initial={{ width: 0, opacity: 0 }}
                animate={{ width: 180, opacity: 1 }}
                exit={{ width: 0, opacity: 0 }}
                type="text"
                value={searchValue}
                onChange={e => onSearchChange(e.target.value)}
                placeholder="Search signals..."
                autoFocus
                className="bg-transparent border-b border-ink/20 px-1 py-0.5 text-[11px] text-ink outline-none placeholder:text-ink/25 normal-case"
              />
            )}
          </AnimatePresence>
          <button onClick={handleSearchToggle} className="hover:text-crimson transition-colors cursor-pointer">
            {searchOpen ? "✕ Close" : "⌕ Search"}
          </button>
          <button onClick={toggle} className="hover:text-crimson transition-colors cursor-pointer" title={isDark ? "Switch to day mode" : "Switch to night mode"}>
            {isDark ? <SunIcon /> : <MoonIcon />}
          </button>
          <button onClick={() => navigate("/settings")} className="hover:text-crimson transition-colors cursor-pointer">
            Settings
          </button>
          {user ? (
            <div className="flex items-center gap-2">
              <span className="text-[9px] font-bold uppercase tracking-widest border px-2 py-0.5"
                style={{ color: tierMeta.color, borderColor: tierMeta.color + "40" }}>
                {tierMeta.label}
              </span>
              <button onClick={handleSignOut} className="hover:text-crimson transition-colors cursor-pointer">
                Sign Out
              </button>
            </div>
          ) : (
            <button onClick={() => navigate("/auth")}
              className="hover:text-crimson transition-colors cursor-pointer border border-ink/15 px-2.5 py-0.5 hover:border-crimson/40 rounded-sm">
              Sign In
            </button>
          )}
        </div>
      </div>

      {/* ── Mobile top bar — greeting + search ── */}
      <div className="flex md:hidden items-center justify-between px-4 py-3 bg-paper">
        <div>
          <p className="text-[10px] text-ink/40 uppercase tracking-widest">{greeting()}</p>
          <p className="text-[16px] font-bold text-ink leading-tight">{firstName}</p>
        </div>
        <div className="flex items-center gap-3">
          <AnimatePresence>
            {searchOpen && (
              <motion.input
                initial={{ width: 0, opacity: 0 }}
                animate={{ width: 140, opacity: 1 }}
                exit={{ width: 0, opacity: 0 }}
                type="text"
                value={searchValue}
                onChange={e => onSearchChange(e.target.value)}
                placeholder="Search…"
                autoFocus
                className="bg-transparent border-b border-ink/20 px-1 py-0.5 text-[13px] text-ink outline-none placeholder:text-ink/25"
              />
            )}
          </AnimatePresence>
          <button onClick={handleSearchToggle} className="w-9 h-9 flex items-center justify-center rounded-full border border-ink/10 text-ink/40">
            {searchOpen
              ? <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M1 1l10 10M11 1L1 11"/></svg>
              : <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.4"><circle cx="6" cy="6" r="4"/><path d="M10 10l2.5 2.5"/></svg>
            }
          </button>
          <button onClick={toggle} className="w-9 h-9 flex items-center justify-center rounded-full border border-ink/10 text-ink/40">
            {isDark ? <SunIcon /> : <MoonIcon />}
          </button>
        </div>
      </div>

      {/* ── Masthead — always dark ── */}
      <div style={{ backgroundColor: "#111111" }}>
        <div className="max-w-[1400px] mx-auto px-4 md:px-6 py-2 md:py-2.5 flex items-center justify-between">
          <div>
            <h1
              onClick={() => navigate("/")}
              className="font-display text-[1.8rem] md:text-[2.8rem] tracking-tighter leading-none cursor-pointer select-none"
              style={{ color: "#F0EDE8" }}
            >
              THE <span style={{ color: "#C80028" }}>NARRATIVE</span>
            </h1>
            <p className="text-[7px] md:text-[8px] tracking-[0.35em] uppercase mt-0.5 hidden md:block" style={{ color: "rgba(240,237,232,0.3)" }}>
              Consequences, not headlines.
            </p>
          </div>
          <span className="flex items-center gap-1.5 text-[9px] uppercase tracking-wider" style={{ color: "rgba(240,237,232,0.3)" }}>
            <span className="w-1.5 h-1.5 rounded-full bg-crimson animate-pulse" />
            <span className="hidden md:inline">Live</span>
          </span>
        </div>

        {/* ── Tab switcher — desktop only, mobile uses bottom nav ── */}
        <div className="hidden md:flex max-w-[1400px] mx-auto px-6" style={{ borderTop: "1px solid rgba(240,237,232,0.08)" }}>
          {[
            { id: "feed",      label: "Intelligence Feed" },
            { id: "world",     label: "World View"        },
            { id: "following", label: "Tracked"           },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className="px-5 py-2 text-[11px] font-semibold uppercase tracking-widest transition-colors relative"
              style={{ color: activeTab === tab.id ? "#F0EDE8" : "rgba(240,237,232,0.3)" }}
            >
              {tab.label}
              {activeTab === tab.id && (
                <motion.div layoutId="main-tab-line" className="absolute bottom-0 left-0 right-0 h-0.5 bg-crimson" />
              )}
            </button>
          ))}
        </div>
      </div>

      {/* ── Category nav ── */}
      {activeTab === "feed" && (
        <nav className="max-w-[1400px] mx-auto px-4 md:px-6 overflow-x-auto border-b border-ink/8">
          <ul className="flex gap-4 md:gap-6 py-2 text-[11px] md:text-[12px] font-semibold uppercase tracking-wider text-ink/40 whitespace-nowrap">
            {CATEGORIES.map(cat => {
              const active = activeCategory === (cat === "All" ? null : cat.toLowerCase());
              return (
                <li
                  key={cat}
                  onClick={() => onCategoryChange(cat === "All" ? null : cat.toLowerCase())}
                  className={`cursor-pointer py-1 transition-colors border-b-2 ${
                    active ? "border-crimson text-crimson" : "border-transparent hover:text-crimson"
                  }`}
                >
                  {cat}
                </li>
              );
            })}
          </ul>
        </nav>
      )}
    </header>
  );
}
