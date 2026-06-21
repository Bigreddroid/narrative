import { NavLink, Outlet } from "react-router-dom";
import { motion } from "framer-motion";

const ADMIN_NAV = [
  { to: "/admin", label: "Dashboard", end: true },
  { to: "/admin/pipeline", label: "Pipeline" },
  { to: "/admin/workers", label: "Workers" },
  { to: "/admin/costs", label: "Costs" },
  { to: "/admin/sources", label: "Sources" },
  { to: "/admin/events", label: "Events" },
  { to: "/admin/users", label: "Users" },
  { to: "/admin/hallucinations", label: "Flags" },
];

export default function AdminLayout() {
  return (
    <div className="flex h-screen bg-bg-base text-text-primary">
      {/* Admin sidebar */}
      <nav className="w-48 bg-bg-surface border-r border-border flex-shrink-0 flex flex-col py-6 px-3">
        <div className="mb-6 px-3">
          <p className="text-xs font-semibold uppercase tracking-widest text-text-muted">Admin</p>
          <p className="text-sm font-bold text-text-primary mt-1">The Narrative</p>
        </div>

        <div className="space-y-1">
          {ADMIN_NAV.map(({ to, label, end }) => (
            <NavLink key={to} to={to} end={end}>
              {({ isActive }) => (
                <motion.div
                  className="px-3 py-2 rounded-lg text-sm font-medium transition-colors"
                  style={{
                    color: isActive ? "#F0F6FC" : "#8B949E",
                    backgroundColor: isActive ? "#161B22" : "transparent",
                  }}
                  whileHover={{ backgroundColor: "#161B22", color: "#F0F6FC" }}
                >
                  {label}
                </motion.div>
              )}
            </NavLink>
          ))}
        </div>
      </nav>

      {/* Content */}
      <main className="flex-1 overflow-y-auto p-8">
        <Outlet />
      </main>
    </div>
  );
}
