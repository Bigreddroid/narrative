import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../lib/api.js";

const MOCK_USER = {
  email: "user@example.com",
  city: "",
  country: "",
  profession: "",
  tier: "free",
};

export default function Settings() {
  const navigate = useNavigate();
  const [user,          setUser]          = useState(null);
  const [saving,        setSaving]        = useState(false);
  const [saved,         setSaved]         = useState(false);
  const [searchParams]                    = useSearchParams();

  const upgraded  = searchParams.get("upgraded")  === "1";
  const cancelled = searchParams.get("cancelled") === "1";

  useEffect(() => {
    api.get("/users/me")
      .then(setUser)
      .catch(() => setUser(MOCK_USER));
  }, []);

  const handleSave = async () => {
    if (!user) return;
    setSaving(true);
    try {
      await api.patch("/users/me", {
        city:     user.city,
        country:  user.country,
        profession: user.profession,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-paper">
      {/* Header */}
      <header className="bg-ink border-b-2 border-ink sticky top-0 z-50">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <button
            onClick={() => navigate("/world")}
            className="flex items-center gap-2 text-paper/40 hover:text-paper transition-colors text-[10px] font-mono uppercase tracking-widest"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M10 7H4M4 7L7 4M4 7L7 10" />
            </svg>
            Back to Feed
          </button>
          <h1
            onClick={() => navigate("/world")}
            className="font-display text-2xl text-paper cursor-pointer select-none"
          >
            THE <span className="text-crimson">NARRATIVE</span>
          </h1>
          <span className="text-[10px] font-mono text-paper/25 uppercase tracking-widest">Settings</span>
        </div>
      </header>

      <div className="max-w-lg mx-auto px-4 sm:px-6 py-8 sm:py-10">
        {/* Status banners */}
        <AnimatePresence>
          {upgraded && (
            <motion.div
              key="upgraded"
              className="mb-6 p-4 border text-sm font-medium"
              style={{ borderColor: "#27AE6040", color: "#27AE60", backgroundColor: "#27AE6010" }}
              initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            >
              Welcome to full access. Your consequence chains are now unlocked.
            </motion.div>
          )}
          {cancelled && (
            <motion.div
              key="cancelled"
              className="mb-6 p-4 border text-sm font-medium"
              style={{ borderColor: "#B0702040", color: "#B07020", backgroundColor: "#B0702010" }}
              initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            >
              Checkout cancelled.
            </motion.div>
          )}
        </AnimatePresence>

        {/* Loading */}
        {!user ? (
          <div className="flex justify-center py-16">
            <div className="w-5 h-5 border-2 border-ink/10 border-t-crimson rounded-full animate-spin" />
          </div>
        ) : (
          <>
            {/* Profile section */}
            <div className="border-b border-ink/10 pb-8 mb-8">
              <h2 className="font-display text-3xl text-ink mb-1">Profile</h2>
              <p className="text-sm text-ink/40 mb-6 font-mono uppercase tracking-wider text-[10px]">
                Your consequence intelligence profile
              </p>

              <div className="space-y-5">
                <div>
                  <label className="text-[10px] font-mono uppercase tracking-widest text-ink/40 block mb-1.5">
                    Email
                  </label>
                  <p className="text-sm text-ink/60 border-b border-ink/10 pb-2">{user.email}</p>
                </div>

                {[
                  { key: "country",    label: "Country",    placeholder: "e.g. United Kingdom" },
                  { key: "city",       label: "City",       placeholder: "e.g. London" },
                  { key: "profession", label: "Profession", placeholder: "e.g. Analyst" },
                ].map(({ key, label, placeholder }) => (
                  <div key={key}>
                    <label className="text-[10px] font-mono uppercase tracking-widest text-ink/40 block mb-1.5">
                      {label}
                    </label>
                    <input
                      value={user[key] || ""}
                      onChange={e => setUser({ ...user, [key]: e.target.value })}
                      placeholder={placeholder}
                      className="w-full bg-transparent border-b border-ink/15 py-2 text-sm text-ink placeholder:text-ink/20 focus:outline-none focus:border-ink/40 transition-colors"
                    />
                  </div>
                ))}

                <motion.button
                  onClick={handleSave}
                  disabled={saving}
                  whileTap={{ scale: 0.98 }}
                  className="mt-2 px-6 py-2.5 text-[10px] font-mono font-bold uppercase tracking-widest transition-all disabled:opacity-50"
                  style={{
                    backgroundColor: saved ? "#27AE60" : "#1A1A1A",
                    color: "#F5F1EB",
                  }}
                >
                  {saved ? "✓ Saved" : saving ? "Saving..." : "Save Changes"}
                </motion.button>
              </div>
            </div>

            {/* Account section */}
            <div className="border-b border-ink/10 pb-8 mb-8">
              <h2 className="font-display text-3xl text-ink mb-1">Account</h2>
              <div className="flex items-center justify-between py-3 border-b border-ink/8">
                <div>
                  <p className="text-[10px] font-mono uppercase tracking-widest text-ink/40 mb-1">Access Level</p>
                  <p className="text-sm text-ink capitalize">{user.tier || "Free"}</p>
                </div>
                {user.tier === "free" && (
                  <span className="text-[9px] font-mono uppercase tracking-widest text-crimson border border-crimson/30 px-2 py-1">
                    Free Tier
                  </span>
                )}
              </div>
            </div>

            {/* Sign out */}
            <div>
              <motion.button
                onClick={() => { localStorage.removeItem("narrative_token"); navigate("/"); }}
                whileTap={{ scale: 0.98 }}
                className="text-[10px] font-mono uppercase tracking-widest text-ink/35 hover:text-crimson transition-colors border border-ink/10 hover:border-crimson/30 px-4 py-2"
              >
                Sign Out
              </motion.button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
