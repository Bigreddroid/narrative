import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { setToken } from "../lib/api.js";
import { DEV_ACCOUNTS } from "../lib/tiers.js";
import { setStoredUser } from "../hooks/useUser.js";

export default function Auth() {
  const navigate = useNavigate();
  const location = useLocation();
  const from     = location.state?.from?.pathname || "/analyst";

  const [mode,     setMode]     = useState("signin"); // "signin" | "signup"
  const [name,     setName]     = useState("");
  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);

  const switchMode = (m) => { setMode(m); setError(null); };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim()) { setError("Email is required."); return; }
    if (mode === "signup" && !name.trim()) { setError("Name is required."); return; }
    setLoading(true);
    setError(null);

    const cleanEmail = email.trim().toLowerCase();

    // Offline demo fallback — log in without the backend.
    // Lets the Enterprise demo (and other tiers) run from mock data alone.
    const loginOffline = () => {
      const devAccount = DEV_ACCOUNTS[cleanEmail];
      const profile = devAccount || { email: cleanEmail, tier: "free" };
      const displayName = (mode === "signup" && name.trim()) || profile.name || cleanEmail.split("@")[0] || "User";
      setToken("offline-demo-token");
      setStoredUser({ ...profile, email: cleanEmail, name: displayName });
      navigate(mode === "signup" ? "/onboarding" : from, { replace: true });
    };

    try {
      // Dev test accounts (enterprise@narrative.dev …) use the passwordless
      // dev-login locally; everyone else uses real signup/login.
      const isDevAccount = import.meta.env.DEV && DEV_ACCOUNTS[cleanEmail];
      const url = isDevAccount
        ? "/api/v1/auth/dev-login"
        : mode === "signup" ? "/api/v1/auth/signup" : "/api/v1/auth/login";

      let res;
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 3500);
      try {
        res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: cleanEmail, password: password || "" }),
          signal: ctrl.signal,
        });
      } catch {
        // Backend unreachable / timed out — fall into the offline demo session.
        loginOffline();
        return;
      } finally {
        clearTimeout(timer);
      }

      const text = await res.text().catch(() => "");
      let authData = {};
      try { authData = JSON.parse(text); } catch {}
      if (!res.ok) {
        if (res.status >= 500 && res.status <= 504) { loginOffline(); return; }
        throw new Error(authData.detail || "Authentication failed.");
      }
      if (!authData.access_token) throw new Error("Server did not return a token.");

      setToken(authData.access_token);

      // Fetch full user profile
      let profile = { email: email.trim().toLowerCase(), tier: "free" };
      try {
        const meRes = await fetch("/api/v1/users/me", {
          headers: { Authorization: `Bearer ${authData.access_token}` },
        });
        if (meRes.ok) profile = await meRes.json();
      } catch {}

      // DEV_ACCOUNTS tier override for test emails
      const devAccount = DEV_ACCOUNTS[email.trim().toLowerCase()];
      if (devAccount) profile = { ...profile, tier: devAccount.tier };

      // Backend has no name field — use sign-up input or email prefix
      const displayName = (mode === "signup" && name.trim()) || profile.name || profile.email?.split("@")[0] || "User";
      setStoredUser({ ...profile, name: displayName });

      navigate(mode === "signup" || authData.is_new_user ? "/onboarding" : from, { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex overflow-hidden" style={{ backgroundColor: "#0D0D0D" }}>

      {/* ── Left panel — always dark ── */}
      <div className="hidden lg:flex flex-col justify-between w-2/5 px-12 py-12 relative overflow-hidden"
        style={{ borderRight: "1px solid rgba(240,237,232,0.07)", backgroundColor: "#0A0A0A" }}>

        <div className="absolute inset-0 pointer-events-none"
          style={{ backgroundImage: "radial-gradient(circle, #252525 1px, transparent 1px)", backgroundSize: "28px 28px", opacity: 0.6 }} />
        <div className="absolute -bottom-20 -left-20 w-96 h-96 rounded-full pointer-events-none"
          style={{ background: "radial-gradient(circle, #C8002818 0%, transparent 70%)", filter: "blur(50px)" }} />

        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-16 cursor-pointer" onClick={() => navigate("/")}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <polygon points="12,2 21,7 21,17 12,22 3,17 3,7" stroke="#C80028" strokeWidth="1.5" fill="none" />
              <polygon points="12,6 17,9 17,15 12,18 7,15 7,9" stroke="#C80028" strokeWidth="1" fill="#C80028" fillOpacity="0.12" />
            </svg>
            <span className="text-[10px] font-bold uppercase tracking-[0.35em]" style={{ color: "rgba(240,237,232,0.35)" }}>
              The Narrative
            </span>
          </div>

          <h2 className="font-display text-5xl leading-none uppercase mb-4" style={{ color: "#F0EDE8" }}>
            World<br />Consequence<br />Intelligence.
          </h2>
          <p className="text-[13px] leading-relaxed mb-10 max-w-xs" style={{ color: "rgba(240,237,232,0.4)" }}>
            Map the causal chain from any global event to its effect on you — your costs, your sector, your city.
          </p>

          {["Consequences, not headlines", "Importance-ranked by AI analysis", "Traced to citizen-level impact"].map(item => (
            <div key={item} className="flex items-center gap-3 mb-3">
              <div className="w-1 h-1 bg-crimson flex-shrink-0" />
              <span className="text-[11px]" style={{ color: "rgba(240,237,232,0.4)" }}>{item}</span>
            </div>
          ))}
        </div>

        <p className="relative z-10 text-[9px] uppercase tracking-[0.3em]" style={{ color: "rgba(240,237,232,0.2)" }}>
          Consequences, not headlines.
        </p>
      </div>

      {/* ── Right panel — form ── */}
      <div className="flex-1 flex flex-col items-center justify-center px-8 py-12 bg-paper">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="w-full max-w-sm"
        >
          {/* Mobile logo */}
          <div className="flex items-center gap-2 mb-10 lg:hidden cursor-pointer" onClick={() => navigate("/")}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <polygon points="12,2 21,7 21,17 12,22 3,17 3,7" stroke="#C80028" strokeWidth="1.5" fill="none" />
            </svg>
            <span className="text-[10px] font-bold uppercase tracking-[0.3em] text-ink/40">The Narrative</span>
          </div>

          {/* Mode toggle */}
          <div className="flex mb-8" style={{ backgroundColor: "#1A1A1A" }}>
            {["signin", "signup"].map(m => (
              <button
                key={m}
                onClick={() => switchMode(m)}
                className="flex-1 py-2 text-[11px] font-bold uppercase tracking-widest transition-colors"
                style={mode === m
                  ? { backgroundColor: "#C80028", color: "#F0EDE8" }
                  : { backgroundColor: "transparent", color: "rgba(240,237,232,0.45)" }
                }
              >
                {m === "signin" ? "Sign In" : "Sign Up"}
              </button>
            ))}
          </div>

          <AnimatePresence mode="wait">
            <motion.form
              key={mode}
              onSubmit={handleSubmit}
              initial={{ opacity: 0, x: mode === "signup" ? 10 : -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: mode === "signup" ? -10 : 10 }}
              transition={{ duration: 0.18 }}
              className="space-y-4"
            >
              {mode === "signup" && (
                <div>
                  <label className="block text-[9px] font-bold uppercase tracking-[0.2em] text-ink/40 mb-2">Name</label>
                  <input
                    type="text"
                    placeholder="Your name"
                    value={name}
                    onChange={e => setName(e.target.value)}
                    required
                    autoFocus
                    className="w-full py-3 px-3 text-[13px] rounded-none"
                  />
                </div>
              )}

              <div>
                <label className="block text-[9px] font-bold uppercase tracking-[0.2em] text-ink/40 mb-2">Email</label>
                <input
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                  autoFocus={mode === "signin"}
                  className="w-full py-3 px-3 text-[13px] rounded-none"
                />
              </div>

              <div>
                <label className="block text-[9px] font-bold uppercase tracking-[0.2em] text-ink/40 mb-2">Password</label>
                <input
                  type="password"
                  placeholder={mode === "signup" ? "Choose a password" : "Your password"}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  className="w-full py-3 px-3 text-[13px] rounded-none"
                />
              </div>

              {error && (
                <p className="text-[12px] py-2 px-3 border border-ink/10 text-ink/60"
                  style={{ borderLeftColor: "#C80028", borderLeftWidth: 2 }}>
                  {error}
                </p>
              )}

              <motion.button
                type="submit"
                disabled={loading}
                className="w-full py-3.5 text-[11px] font-bold uppercase tracking-[0.25em] text-paper disabled:opacity-40 mt-2"
                style={{ backgroundColor: "#C80028" }}
                whileHover={{ backgroundColor: "#E52040" }}
                whileTap={{ scale: 0.99 }}
                transition={{ duration: 0.12 }}
              >
                {loading ? "Please wait…" : mode === "signin" ? "Sign In →" : "Create Account →"}
              </motion.button>

              {mode === "signin" && (
                <p className="text-[11px] text-ink/30 text-center pt-1">
                  No account?{" "}
                  <button type="button" onClick={() => switchMode("signup")} className="text-crimson hover:underline font-medium">
                    Sign up free
                  </button>
                </p>
              )}
            </motion.form>
          </AnimatePresence>

          <button
            onClick={() => navigate("/")}
            className="w-full mt-8 text-[10px] uppercase tracking-widest text-ink/25 hover:text-crimson transition-colors text-left"
          >
            ← Back to home
          </button>
        </motion.div>
      </div>
    </div>
  );
}
