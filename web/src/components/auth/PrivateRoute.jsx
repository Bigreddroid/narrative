import { useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { setStoredUser } from "../../hooks/useUser.js";

const DEV_BYPASS = import.meta.env.DEV;
const DEV_EMAIL = "enterprise@narrative.dev";  // full-tier dev account

function hasToken() {
  const t = localStorage.getItem("narrative_token");
  // an offline-demo token is invalid against the live backend — treat as none
  return !!t && t !== "offline-demo-token";
}

export default function PrivateRoute({ children }) {
  const location = useLocation();
  // In dev we bypass the /auth redirect — but without a token every API call
  // 401s and the UI silently falls back to mock data. So auto-acquire a dev
  // token before rendering, so the app shows LIVE backend data out of the box.
  const [ready, setReady] = useState(hasToken() || !DEV_BYPASS);

  useEffect(() => {
    if (!DEV_BYPASS || hasToken()) return;
    (async () => {
      try {
        const r = await fetch("/api/v1/auth/dev-login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: DEV_EMAIL, password: "dev" }),
        });
        const d = r.ok ? await r.json() : null;
        if (d?.access_token) {
          localStorage.setItem("narrative_token", d.access_token);
          // Also store the real user so tier + profile (Your Exposure) are correct.
          const ur = await fetch("/api/v1/users/me", { headers: { Authorization: `Bearer ${d.access_token}` } });
          if (ur.ok) setStoredUser(await ur.json());
        }
      } catch {                   // backend down → honest empty/error states downstream
        /* no-op */
      } finally {
        setReady(true);
      }
    })();
  }, []);

  if (!DEV_BYPASS && !hasToken()) {
    return <Navigate to="/auth" state={{ from: location }} replace />;
  }
  if (!ready) return null;        // brief wait while the dev token is acquired
  return children;
}
