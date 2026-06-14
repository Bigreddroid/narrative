import { Navigate, useLocation } from "react-router-dom";

const DEV_BYPASS = import.meta.env.DEV;

function hasToken() {
  return !!localStorage.getItem("narrative_token");
}

export default function PrivateRoute({ children }) {
  const location = useLocation();
  if (!DEV_BYPASS && !hasToken()) {
    return <Navigate to="/auth" state={{ from: location }} replace />;
  }
  return children;
}
