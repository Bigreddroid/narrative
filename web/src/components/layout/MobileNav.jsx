import { useNavigate, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { useFollowing } from "../../hooks/useFollowing.js";

const TABS = [
  {
    id: "threats",
    path: "/threats",
    label: "Threats",
    icon: (active) => (
      <svg width="20" height="20" viewBox="0 0 20 20" fill={active ? "currentColor" : "none"} stroke="currentColor" strokeWidth={active ? 2 : 1.5} strokeLinecap="round" strokeLinejoin="round">
        <path d="M10 2.5l6 2.2v4.6c0 4-2.7 6.6-6 8.2-3.3-1.6-6-4.2-6-8.2V4.7l6-2.2z" />
      </svg>
    ),
  },
  {
    id: "feed",
    path: "/world",
    label: "Feed",
    icon: (active) => (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={active ? 2 : 1.5} strokeLinecap="round">
        <rect x="3" y="3" width="6" height="6" rx="1" />
        <rect x="11" y="3" width="6" height="6" rx="1" />
        <rect x="3" y="11" width="6" height="6" rx="1" />
        <rect x="11" y="11" width="6" height="6" rx="1" />
      </svg>
    ),
  },
  {
    id: "world",
    path: "/world?tab=world",
    label: "World",
    icon: (active) => (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={active ? 2 : 1.5} strokeLinecap="round">
        <circle cx="10" cy="10" r="7" />
        <path d="M3 10h14M10 3c-2 2-3 4.5-3 7s1 5 3 7M10 3c2 2 3 4.5 3 7s-1 5-3 7" />
      </svg>
    ),
  },
  {
    id: "exposure",
    path: "/world?tab=exposure",
    label: "Exposure",
    icon: (active) => (
      <svg width="20" height="20" viewBox="0 0 20 20" fill={active ? "currentColor" : "none"} stroke="currentColor" strokeWidth={active ? 2 : 1.5} strokeLinecap="round" strokeLinejoin="round">
        <path d="M10 2.5c2.8 3.4 4.5 5.7 4.5 8.5a4.5 4.5 0 1 1-9 0C5.5 8.2 7.2 5.9 10 2.5z" />
      </svg>
    ),
  },
  {
    id: "analyst",
    path: "/analyst",
    label: "Analyst",
    icon: (active) => (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={active ? 2 : 1.5} strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 5.5A1.5 1.5 0 0 1 4.5 4h11A1.5 1.5 0 0 1 17 5.5v6A1.5 1.5 0 0 1 15.5 13H8l-4 3v-3H4.5A1.5 1.5 0 0 1 3 11.5z" />
      </svg>
    ),
  },
  {
    id: "locate",
    path: "/geolocate",
    label: "Locate",
    icon: (active) => (
      <svg width="20" height="20" viewBox="0 0 20 20" fill={active ? "currentColor" : "none"} stroke="currentColor" strokeWidth={active ? 2 : 1.5} strokeLinecap="round" strokeLinejoin="round">
        <path d="M10 18s6-5.2 6-9.5A6 6 0 0 0 4 8.5C4 12.8 10 18 10 18z" />
        <circle cx="10" cy="8.5" r="2" fill="none" />
      </svg>
    ),
  },
  {
    id: "tracked",
    path: "/following",
    label: "Tracked",
    icon: (active) => (
      <svg width="20" height="20" viewBox="0 0 20 20" fill={active ? "currentColor" : "none"} stroke="currentColor" strokeWidth={active ? 2 : 1.5} strokeLinecap="round">
        <path d="M10 2.5C7.5 2.5 5 4.5 5 7.5c0 4 5 10 5 10s5-6 5-10c0-3-2.5-5-5-5z" />
      </svg>
    ),
  },
  {
    id: "profile",
    path: "/settings",
    label: "Profile",
    icon: (active) => (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={active ? 2 : 1.5} strokeLinecap="round">
        <circle cx="10" cy="7" r="3" />
        <path d="M4 17c0-3.3 2.7-6 6-6s6 2.7 6 6" />
      </svg>
    ),
  },
];

export default function MobileNav() {
  const navigate = useNavigate();
  const location = useLocation();
  const { followed } = useFollowing();

  const activeId =
    location.pathname === "/analyst" ? "analyst"
    : location.pathname === "/geolocate" ? "locate"
    : location.pathname === "/threats" ? "threats"
    : location.pathname === "/following" ? "tracked"
    : location.pathname === "/settings" ? "profile"
    : location.search.includes("tab=exposure") ? "exposure"
    : location.search.includes("tab=world") ? "world"
    : "feed";

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 md:hidden"
      style={{
        backgroundColor: "#111111",
        borderTop: "1px solid rgba(240,237,232,0.08)",
        paddingBottom: "env(safe-area-inset-bottom)",
      }}
    >
      <div className="flex items-stretch">
        {TABS.map(tab => {
          const active = activeId === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => navigate(tab.path)}
              aria-label={tab.label}
              aria-current={active ? "page" : undefined}
              className="flex-1 flex flex-col items-center justify-center py-3 gap-1 relative transition-colors"
              style={{ color: active ? "#C80028" : "rgba(240,237,232,0.35)" }}
            >
              {tab.id === "tracked" && followed.length > 0 && (
                <span
                  className="absolute top-2 right-[calc(50%-12px)] w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-bold"
                  style={{ backgroundColor: "#C80028", color: "#F0EDE8" }}
                >
                  {followed.length > 9 ? "9+" : followed.length}
                </span>
              )}
              {tab.icon(active)}
              <span className="text-[9px] font-semibold uppercase tracking-wider">{tab.label}</span>
              {active && (
                <motion.div
                  layoutId="mobile-nav-dot"
                  className="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-0.5 bg-crimson"
                />
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
