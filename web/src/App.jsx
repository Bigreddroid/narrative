import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import Landing from "./pages/Landing.jsx";
import Onboarding from "./pages/Onboarding.jsx";
import WorldView from "./pages/WorldView.jsx";
import EventDetail from "./pages/EventDetail.jsx";
import Following from "./pages/Following.jsx";
import Settings from "./pages/Settings.jsx";
import Auth from "./pages/Auth.jsx";
import PrivateRoute from "./components/auth/PrivateRoute.jsx";
import MobileNav from "./components/layout/MobileNav.jsx";
import AdminLayout from "./admin/AdminLayout.jsx";
import Dashboard from "./admin/Dashboard.jsx";
import PipelineMonitor from "./admin/PipelineMonitor.jsx";
import WorkerControls from "./admin/WorkerControls.jsx";
import CostDashboard from "./admin/CostDashboard.jsx";
import SourceManager from "./admin/SourceManager.jsx";
import EventReview from "./admin/EventReview.jsx";
import UserStats from "./admin/UserStats.jsx";
import HallucinationFlags from "./admin/HallucinationFlags.jsx";
import { useUser } from "./hooks/useUser.js";

const DEV_BYPASS = import.meta.env.DEV;

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
      <Routes>
        {/* Public */}
        <Route path="/"     element={<Landing />} />
        <Route path="/auth" element={<Auth />} />

        {/* Protected */}
        <Route path="/onboarding"      element={<PrivateRoute><Onboarding /></PrivateRoute>} />
        <Route path="/world"           element={<PrivateRoute><WorldView /></PrivateRoute>} />
        <Route path="/event/:eventId"  element={<PrivateRoute><EventDetail /></PrivateRoute>} />
        <Route path="/following"       element={<PrivateRoute><Following /></PrivateRoute>} />
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
    </AppShell>
  );
}
