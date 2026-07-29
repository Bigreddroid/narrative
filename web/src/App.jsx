import { lazy, Suspense } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import Landing from "./pages/Landing.jsx";
import Auth from "./pages/Auth.jsx";
import PrivateRoute from "./components/auth/PrivateRoute.jsx";
import MobileNav from "./components/layout/MobileNav.jsx";
import { useUser } from "./hooks/useUser.js";
import { FEATURES } from "./lib/features.js";
import wiproConfig from "./data/customers/wipro.json";

// Lazy-load everything behind the public entry (Landing/Auth). This moves the
// heavy map/d3 deps (WorldView, EventDetail) and the rarely-used admin console
// into separate chunks fetched on demand instead of the initial bundle.
const Onboarding = lazy(() => import("./pages/Onboarding.jsx"));
const WorldView = lazy(() => import("./pages/WorldView.jsx"));
const EventDetail = lazy(() => import("./pages/EventDetail.jsx"));
const Following = lazy(() => import("./pages/Following.jsx"));
const Settings = lazy(() => import("./pages/Settings.jsx"));
const Analyst = lazy(() => import("./pages/Analyst.jsx"));
const GeoLocate = lazy(() => import("./pages/GeoLocate.jsx"));
const IntFusion = lazy(() => import("./pages/IntFusion.jsx"));
// Public calibration scoreboard — citable, no login (Phase 0 benchmark surface).
const Benchmark = lazy(() => import("./pages/Benchmark.jsx"));
// Customer deck — config-driven dashboard over the live backend; direct URL only
// (/wipro), intentionally not in the nav. Next tenant = another config + route.
const CustomerDeck = lazy(() => import("./pages/CustomerDeck.jsx"));
const ExecDeck = lazy(() => import("./pages/ExecDeck.jsx"));
const Advice = lazy(() => import("./pages/Advice.jsx"));
const SignalBoard = lazy(() => import("./pages/SignalBoard.jsx"));
const AdminLayout = lazy(() => import("./admin/AdminLayout.jsx"));
const PipelineMonitor = lazy(() => import("./admin/PipelineMonitor.jsx"));
const CostDashboard = lazy(() => import("./admin/CostDashboard.jsx"));

const DEV_BYPASS = import.meta.env.DEV;

// The OSINT Framework folded into the Analyst tab. Keep /osint (and its
// ?value=&kind= deep-links from event chips) working by forwarding to /analyst.
function OsintRedirect() {
  const { search } = useLocation();
  return <Navigate to={`/analyst${search}`} replace />;
}

function RouteFallback() {
  return (
    <div className="flex items-center justify-center h-screen w-full bg-paper">
      <div className="w-5 h-5 border-2 border-ink/15 border-t-crimson rounded-full animate-spin" />
    </div>
  );
}

function AdminRoute({ children }) {
  const { user } = useUser();
  if (!DEV_BYPASS && user?.tier !== "admin") {
    return <Navigate to="/world" replace />;
  }
  return <PrivateRoute>{children}</PrivateRoute>;
}

function AppShell({ children }) {
  const location = useLocation();
  const { user } = useUser();
  const isAdmin = location.pathname.startsWith("/admin");
  // /wipro/exec carries its own navigation (back, cross-surface links, day/night).
  // Stacking the app's bottom bar under it gave the deck two competing navs on the
  // same screen — one of them highlighting a tab the reader wasn't on.
  const noNav = ["/", "/auth", "/onboarding", "/wipro/exec"].includes(location.pathname);
  const showNav = user && !noNav && !isAdmin;
  return (
    <>
      {children}
      {showNav && <MobileNav />}
    </>
  );
}

export default function App() {
  return (
    <AppShell>
      <Suspense fallback={<RouteFallback />}>
      <Routes>
        {/* Public */}
        <Route path="/"     element={<Landing />} />
        <Route path="/auth" element={<Auth />} />
        <Route path="/benchmark" element={<Benchmark />} />

        {/* Protected */}
        <Route path="/onboarding"      element={<PrivateRoute><Onboarding /></PrivateRoute>} />
        <Route path="/world"           element={<PrivateRoute><WorldView /></PrivateRoute>} />
        <Route path="/event/:eventId"  element={<PrivateRoute><EventDetail /></PrivateRoute>} />
        <Route path="/following"       element={<PrivateRoute><Following /></PrivateRoute>} />
        <Route path="/analyst"         element={<PrivateRoute><Analyst /></PrivateRoute>} />
        {/* Photo geolocation is hidden from the v1 (GSOC/duty-of-care) buyer — see
            docs/SURFACE-AUDIT.md. Kept behind a flag (FEATURES.geolocate), not deleted;
            when off, the route redirects to /world so old links don't dead-end. */}
        <Route path="/geolocate"       element={FEATURES.geolocate ? <PrivateRoute><GeoLocate /></PrivateRoute> : <Navigate to="/world" replace />} />
        <Route path="/int"             element={<PrivateRoute><IntFusion /></PrivateRoute>} />
        <Route path="/wipro"           element={<PrivateRoute><CustomerDeck config={wiproConfig} /></PrivateRoute>} />
        {/* Executive altitude over the same engine: exposure-first, no feed. The
            analyst board at /wipro is deliberately untouched — two personas, two
            altitudes. Runs on a sample dataset until the real site list lands. */}
        <Route path="/wipro/exec"      element={<PrivateRoute><ExecDeck /></PrivateRoute>} />
        <Route path="/advice"          element={<PrivateRoute><Advice /></PrivateRoute>} />
        {/* The TweetDeck-style operator board, full viewport. Lived in a 600px box
            at the bottom of /wipro; it earns its own room. Needs the backend. */}
        <Route path="/deck"            element={<PrivateRoute><SignalBoard /></PrivateRoute>} />
        <Route path="/osint"           element={<OsintRedirect />} />
        <Route path="/settings"        element={<PrivateRoute><Settings /></PrivateRoute>} />

        {/* Admin */}
        <Route path="/admin" element={<AdminRoute><AdminLayout /></AdminRoute>}>
          <Route index                  element={<PipelineMonitor />} />
          <Route path="pipeline"        element={<PipelineMonitor />} />
          <Route path="costs"           element={<CostDashboard />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </Suspense>
    </AppShell>
  );
}
