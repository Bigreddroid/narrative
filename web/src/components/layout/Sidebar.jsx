import { NavLink } from "react-router-dom";

const NAV = [
  {
    to: "/world",
    label: "Intelligence",
    icon: (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5">
        <rect x="2" y="3" width="14" height="2" />
        <rect x="2" y="8" width="10" height="2" />
        <rect x="2" y="13" width="12" height="2" />
      </svg>
    ),
  },
  {
    to: "/geolocate",
    label: "Image Geolocation",
    icon: (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M9 16s5-4.5 5-8A5 5 0 0 0 4 8c0 3.5 5 8 5 8z" />
        <circle cx="9" cy="8" r="1.8" />
      </svg>
    ),
  },
  {
    to: "/following",
    label: "Following",
    icon: (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="9" cy="6" r="3" />
        <path d="M2 16c0-3.866 3.134-7 7-7s7 3.134 7 7" />
      </svg>
    ),
  },
  {
    to: "/settings",
    label: "Settings",
    icon: (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="9" cy="9" r="2.5" />
        <path d="M9 1v2M9 15v2M1 9h2M15 9h2M3.22 3.22l1.42 1.42M13.36 13.36l1.42 1.42M3.22 14.78l1.42-1.42M13.36 4.64l1.42-1.42" />
      </svg>
    ),
  },
];

export default function Sidebar() {
  return (
    <nav className="flex flex-col w-14 bg-bg-surface border-r border-border py-5 items-center gap-1 flex-shrink-0">
      {/* Logo */}
      <div className="mb-5 w-8 h-8 flex items-center justify-center" title="The Narrative">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
          <polygon
            points="12,2 21,7 21,17 12,22 3,17 3,7"
            stroke="#C80028"
            strokeWidth="1.5"
            fill="none"
          />
          <polygon
            points="12,7 17,10 17,14 12,17 7,14 7,10"
            stroke="#C80028"
            strokeWidth="1"
            fill="#C80028"
            fillOpacity="0.15"
          />
        </svg>
      </div>

      <div className="w-6 h-px bg-border mb-3" />

      {NAV.map(({ to, label, icon }) => (
        <NavLink key={to} to={to} title={label}>
          {({ isActive }) => (
            <div
              className="relative w-10 h-10 flex items-center justify-center transition-colors"
              style={{ color: isActive ? "#C80028" : "#4A4845" }}
            >
              {isActive && (
                <div
                  className="absolute left-0 top-2 bottom-2 w-px"
                  style={{ backgroundColor: "#C80028" }}
                />
              )}
              {icon}
            </div>
          )}
        </NavLink>
      ))}
    </nav>
  );
}
