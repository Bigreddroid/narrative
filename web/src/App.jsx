import { lazy, Suspense } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import Landing from "./pages/Landing.jsx";
import Auth from "./pages/Auth.jsx";
import PrivateRoute from "./components/auth/PrivateRoute.jsx";
import MobileNav from "./components/layout/MobileNav.jsx";
import { useUser } from "./hooks/useUser.js";

// Lazy-load everything behind the public entry (Landing/Auth). This moves the
// heavy map/d3 deps (WorldView, EventDetail) and the rarely-used admin console
// into separate chunks fetched on demand instead of the initial bundle.
const Onboarding = lazy(() => import("./pages/Onboarding.jsx"));
const WorldView = lazy(() => import("./pages/WorldView.jsx"));
const EventDetail = lazy(() => import("./pages/EventDetail.jsx"));
const Following = lazy(() => import("./pages/Following.jsx"));
const Settings = lazy(() => import("./pages/Settings.jsx"));
const Analyst = lazy(() => import("./pages/Analyst.jsx"));
const Osint = lazy(() => import("./pages/Osint.jsx"));
const DisinfoThreat = lazy(() => import("./pages/DisinfoThreat.jsx"));
const AdminLayout = lazy(() => import("./admin/AdminLayout.jsx"));
const Dashboard = lazy(() => import("./admin/Dashboard.jsx"));
const PipelineMonitor = lazy(() => import("./admin/PipelineMonitor.jsx"));
const WorkerControls = lazy(() => import("./admin/WorkerControls.jsx"));
const CostDashboard = lazy(() => import("./admin/CostDashboard.jsx"));
const SourceManager = lazy(() => import("./admin/SourceManager.jsx"));
const EventReview = lazy(() => import("./admin/EventReview.jsx"));
const UserStats = lazy(() => import("./admin/UserStats.jsx"));
const HallucinationFlags = lazy(() => import("./admin/HallucinationFlags.jsx"));

const DEV_BYPASS = import.meta.env.DEV;

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
  const noNav = ["/", "/auth", "/onboarding"].includes(location.pathname);
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

        {/* Protected */}
        <Route path="/onboarding"      element={<PrivateRoute><Onboarding /></PrivateRoute>} />
        <Route path="/world"           element={<PrivateRoute><WorldView /></PrivateRoute>} />
        <Route path="/event/:eventId"  element={<PrivateRoute><EventDetail /></PrivateRoute>} />
        <Route path="/following"       element={<PrivateRoute><Following /></PrivateRoute>} />
        <Route path="/analyst"         element={<PrivateRoute><Analyst /></PrivateRoute>} />
        <Route path="/osint"           element={<PrivateRoute><Osint /></PrivateRoute>} />
        <Route path="/threats"         element={<PrivateRoute><DisinfoThreat /></PrivateRoute>} />
        <Route path="/settings"        element={<PrivateRoute><Settings /></PrivateRoute>} />

        {/* Admin */}
        <Route path="/admin" element={<AdminRoute><AdminLayout /></AdminRoute>}>
          <Route index                  element={<Dashboard />} />
          <Route path="pipeline"        element={<PipelineMonitor />} />
          <Route path="workers"         element={<WorkerControls />} />
          <Route path="costs"           element={<CostDashboard />} />
          <Route path="sources"         element={<SourceManager />} />
          <Route path="events"          element={<EventReview />} />
          <Route path="users"           element={<UserStats />} />
          <Route path="hallucinations"  element={<HallucinationFlags />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </Suspense>
    </AppShell>
  );
}
