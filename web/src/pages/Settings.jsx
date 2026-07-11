import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../lib/api.js";
import { DEMO_MODE } from "../lib/demoMode.js";
import { getStoredUser, setStoredUser } from "../hooks/useUser.js";

const MOCK_USER = {
  email: "user@example.com",
  city: "",
  country: "",
  profession: "",
  tier: "free",
};

// R2 lens vocab — kept in sync with Onboarding so Settings can re-edit the lens.
const PURPOSES = ["Protect supply chain", "Protect people", "Protect capital", "Protect sites"];
const REGIONS = [
  "Strait of Hormuz", "Suez Canal", "Bab-el-Mandeb", "Panama Canal",
  "South China Sea", "Rotterdam", "Singapore", "Persian Gulf",
  "Black Sea", "Taiwan Strait", "Red Sea", "Gulf of Mexico",
];

// Friendly labels for the admin AI-engine selector. Values map to the backend
// llm_provider choices; "self-trained" is a roadmap option, rendered disabled.
const LLM_OPTIONS = [
  { val: "ollama",    label: "Local (Ollama)", hint: "Free, on-device. The default." },
  { val: "anthropic", label: "Anthropic API",  hint: "Paid, hard-capped." },
  { val: "off",       label: "Off",            hint: "No LLM — grounded templated answers only." },
];

const OSINT_OPTIONS = [
  { val: "gdelt",  label: "GDELT",  hint: "Keyless global news. The default." },
  { val: "reddit", label: "Reddit", hint: "Opt-in; needs app OAuth creds." },
];

export default function Settings() {
  const navigate = useNavigate();
  const [user,          setUser]          = useState(null);
  const [saving,        setSaving]        = useState(false);
  const [saved,         setSaved]         = useState(false);
  const [spendingText,  setSpendingText]  = useState("");
  const [assetInput,    setAssetInput]    = useState("");
  const [searchParams]                    = useSearchParams();

  const upgraded  = searchParams.get("upgraded")  === "1";
  const cancelled = searchParams.get("cancelled") === "1";
  const [billing, setBilling] = useState(null);  // "loading" | error string | null

  // Admin-only runtime config (AI engine + OSINT source). null until loaded / non-admin.
  const [config,  setConfig]  = useState(null);
  const [cfgBusy, setCfgBusy] = useState(null);  // key currently saving
  const [cfgErr,  setCfgErr]  = useState(null);
  const isAdmin = user?.tier === "admin";

  const handleUpgrade = async () => {
    setBilling("loading");
    try {
      const { checkout_url } = await api.post("/stripe/checkout", {});
      if (checkout_url) { window.location.href = checkout_url; return; }
      setBilling("Couldn't start checkout — try again.");
    } catch (err) {
      setBilling(err.status === 503 ? "Payments aren't enabled yet." : (err.message || "Couldn't start checkout."));
    }
  };

  const handlePortal = async () => {
    setBilling("loading");
    try {
      const { portal_url } = await api.post("/stripe/portal", {});
      if (portal_url) { window.location.href = portal_url; return; }
      setBilling("Couldn't open billing — try again.");
    } catch (err) {
      setBilling(err.message || "Couldn't open billing.");
    }
  };

  useEffect(() => {
    api.get("/users/me")
      .then((u) => {
        setUser(u);
        setSpendingText((u.spending_categories || []).join(", "));
      })
      .catch(() => { if (DEMO_MODE) setUser(MOCK_USER); });
  }, []);

  // Load runtime config once we know the user is an admin.
  useEffect(() => {
    if (user?.tier !== "admin") return;
    api.get("/admin/config").then(setConfig).catch(() => setConfig(null));
  }, [user?.tier]);

  const handleSave = async () => {
    if (!user) return;
    setSaving(true);
    const patch = {
      city:       user.city,
      country:    user.country,
      profession: user.profession,
      spending_categories: spendingText.split(",").map(s => s.trim()).filter(Boolean),
      purpose:        user.purpose || [],
      regions:        user.regions || [],
      watched_assets: user.watched_assets || [],
      notification_preferences: user.notification_preferences || {},
    };
    try {
      await api.patch("/users/me", patch);
    } catch {
      // Non-fatal: still apply locally so the lens updates this session.
    } finally {
      // Merge the edited lens into the stored user so every screen re-scopes
      // immediately (same-tab user event), matching Onboarding's behaviour.
      const current = getStoredUser();
      if (current) setStoredUser({ ...current, ...patch });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      setSaving(false);
    }
  };

  // Toggle a value in one of the user's array-valued lens fields.
  const toggleArr = (key, v) =>
    setUser((u) => {
      const list = u[key] || [];
      return { ...u, [key]: list.includes(v) ? list.filter((x) => x !== v) : [...list, v] };
    });

  const addAsset = () => {
    const v = assetInput.trim();
    if (v) toggleArrAdd("watched_assets", v);
    setAssetInput("");
  };
  const toggleArrAdd = (key, v) =>
    setUser((u) => {
      const list = u[key] || [];
      return list.includes(v) ? u : { ...u, [key]: [...list, v] };
    });

  const saveConfig = async (key, value) => {
    setCfgBusy(key);
    setCfgErr(null);
    try {
      const res = await api.patch("/admin/config", { key, value });
      setConfig(c => ({ ...c, ...res }));
    } catch (err) {
      setCfgErr(err.message || "Couldn't save.");
    } finally {
      setCfgBusy(null);
    }
  };

  const setPref = (key, value) =>
    setUser({ ...user, notification_preferences: { ...(user.notification_preferences || {}), [key]: value } });

  return (
    <div className="min-h-screen bg-paper pb-20 md:pb-0">
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
              </div>
            </div>

            {/* Customization section */}
            <div className="border-b border-ink/10 pb-8 mb-8">
              <h2 className="font-display text-3xl text-ink mb-1">Customization</h2>
              <p className="text-sm text-ink/40 mb-6 font-mono uppercase tracking-wider text-[10px]">
                Tune what the intelligence layer watches for you
              </p>

              <div className="space-y-5">
                <div>
                  <label className="text-[10px] font-mono uppercase tracking-widest text-ink/40 block mb-1.5">
                    Exposure Categories
                  </label>
                  <input
                    value={spendingText}
                    onChange={e => setSpendingText(e.target.value)}
                    placeholder="e.g. energy, shipping, semiconductors"
                    className="w-full bg-transparent border-b border-ink/15 py-2 text-sm text-ink placeholder:text-ink/20 focus:outline-none focus:border-ink/40 transition-colors"
                  />
                  <p className="text-[11px] text-ink/35 mt-1.5">
                    Comma-separated. Personalises your exposure readout.
                  </p>
                </div>

                {/* Routes & chokepoints — the geographic half of the lens */}
                <div>
                  <label className="text-[10px] font-mono uppercase tracking-widest text-ink/40 block mb-2">
                    Routes &amp; Chokepoints
                  </label>
                  <div className="flex flex-wrap gap-1.5">
                    {REGIONS.map((r) => {
                      const on = (user.regions || []).includes(r);
                      return (
                        <button
                          key={r}
                          type="button"
                          onClick={() => toggleArr("regions", r)}
                          className="px-2.5 py-1 text-[11px] border transition-colors"
                          style={{
                            borderColor: on ? "#C80028" : "rgba(26,26,26,0.15)",
                            backgroundColor: on ? "#C8002810" : "transparent",
                            color: on ? "#C80028" : "rgba(26,26,26,0.55)",
                          }}
                        >
                          {r}
                        </button>
                      );
                    })}
                  </div>
                  <p className="text-[11px] text-ink/35 mt-1.5">
                    The app scopes the feed, map heat &amp; exposure to these.
                  </p>
                </div>

                {/* Purpose — WHY you watch, orders which consequences surface first */}
                <div>
                  <label className="text-[10px] font-mono uppercase tracking-widest text-ink/40 block mb-2">
                    What you're protecting
                  </label>
                  <div className="flex flex-wrap gap-1.5">
                    {PURPOSES.map((p) => {
                      const on = (user.purpose || []).includes(p);
                      return (
                        <button
                          key={p}
                          type="button"
                          onClick={() => toggleArr("purpose", p)}
                          className="px-2.5 py-1 text-[11px] border transition-colors"
                          style={{
                            borderColor: on ? "#C80028" : "rgba(26,26,26,0.15)",
                            backgroundColor: on ? "#C8002810" : "transparent",
                            color: on ? "#C80028" : "rgba(26,26,26,0.55)",
                          }}
                        >
                          {p}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Watched assets — named suppliers / ports / firms */}
                <div>
                  <label className="text-[10px] font-mono uppercase tracking-widest text-ink/40 block mb-2">
                    Watched Assets
                  </label>
                  <div className="flex gap-2">
                    <input
                      value={assetInput}
                      onChange={(e) => setAssetInput(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addAsset(); } }}
                      placeholder="Add a supplier, port or company…"
                      className="flex-1 bg-transparent border-b border-ink/15 py-2 text-sm text-ink placeholder:text-ink/20 focus:outline-none focus:border-ink/40 transition-colors"
                    />
                    <button
                      type="button"
                      onClick={addAsset}
                      className="px-3 text-[11px] font-mono uppercase tracking-widest border border-ink/15 text-ink/55 hover:border-crimson/40 hover:text-crimson transition-colors"
                    >
                      Add
                    </button>
                  </div>
                  {(user.watched_assets || []).length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2.5">
                      {(user.watched_assets || []).map((a) => (
                        <button
                          key={a}
                          type="button"
                          onClick={() => toggleArr("watched_assets", a)}
                          title="Remove"
                          className="px-2 py-1 text-[11px] border"
                          style={{ borderColor: "#C80028", backgroundColor: "#C8002810", color: "#C80028" }}
                        >
                          {a} ✕
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {[
                  { key: "event_alerts", label: "Event alerts", hint: "Notify me when a followed event escalates" },
                  { key: "email_digest", label: "Email digest", hint: "Periodic summary of high-impact consequences" },
                ].map(({ key, label, hint }) => {
                  const on = !!(user.notification_preferences || {})[key];
                  return (
                    <div key={key} className="flex items-center justify-between py-1">
                      <div className="pr-4">
                        <p className="text-sm text-ink">{label}</p>
                        <p className="text-[11px] text-ink/35">{hint}</p>
                      </div>
                      <button
                        onClick={() => setPref(key, !on)}
                        aria-pressed={on}
                        className="relative w-10 h-5 rounded-full transition-colors shrink-0"
                        style={{ backgroundColor: on ? "#C80028" : "rgba(26,26,26,0.15)" }}
                      >
                        <span
                          className="absolute top-0.5 w-4 h-4 rounded-full bg-paper transition-all"
                          style={{ left: on ? "22px" : "2px" }}
                        />
                      </button>
                    </div>
                  );
                })}

                <motion.button
                  onClick={handleSave}
                  disabled={saving}
                  whileTap={{ scale: 0.98 }}
                  className="mt-2 px-6 py-2.5 text-[10px] font-mono font-bold uppercase tracking-widest transition-all disabled:opacity-50"
                  style={{ backgroundColor: saved ? "#27AE60" : "#1A1A1A", color: "#F5F1EB" }}
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

              {/* Upgrade / billing */}
              <div className="mt-5">
                {user.tier === "free" ? (
                  <motion.button
                    onClick={handleUpgrade}
                    disabled={billing === "loading"}
                    whileTap={{ scale: 0.98 }}
                    className="px-6 py-2.5 text-[10px] font-mono font-bold uppercase tracking-widest text-paper transition-all disabled:opacity-50"
                    style={{ backgroundColor: "#C80028" }}
                  >
                    {billing === "loading" ? "Starting checkout…" : "Upgrade — Full Access →"}
                  </motion.button>
                ) : (
                  <motion.button
                    onClick={handlePortal}
                    disabled={billing === "loading"}
                    whileTap={{ scale: 0.98 }}
                    className="px-6 py-2.5 text-[10px] font-mono font-bold uppercase tracking-widest transition-all disabled:opacity-50"
                    style={{ backgroundColor: "#1A1A1A", color: "#F5F1EB" }}
                  >
                    {billing === "loading" ? "Opening…" : "Manage Billing"}
                  </motion.button>
                )}
                {billing && billing !== "loading" && (
                  <p className="text-[12px] text-ink/50 mt-2">{billing}</p>
                )}
              </div>
            </div>

            {/* ── Operator config (admin only) ── */}
            {isAdmin && config && (
              <>
                {/* AI Engine */}
                <div className="border-b border-ink/10 pb-8 mb-8">
                  <div className="flex items-center gap-2 mb-1">
                    <h2 className="font-display text-3xl text-ink">AI Engine</h2>
                    <span className="text-[9px] font-mono uppercase tracking-widest text-crimson border border-crimson/30 px-2 py-0.5">
                      Operator
                    </span>
                  </div>
                  <p className="text-sm text-ink/40 mb-6 font-mono uppercase tracking-wider text-[10px]">
                    Which model powers analysis · active: {config.active_llm_provider}
                  </p>

                  <div className="space-y-2">
                    {LLM_OPTIONS.map(({ val, label, hint }) => {
                      const selected = config.config?.llm_provider?.value === val;
                      const disabled  = val === "anthropic" && !config.paid_apis_enabled;
                      return (
                        <button
                          key={val}
                          onClick={() => !disabled && !selected && saveConfig("llm_provider", val)}
                          disabled={disabled || cfgBusy === "llm_provider"}
                          className="w-full flex items-center justify-between text-left px-4 py-3 border transition-colors disabled:opacity-40"
                          style={{
                            borderColor: selected ? "#C80028" : "rgba(26,26,26,0.15)",
                            backgroundColor: selected ? "#C8002810" : "transparent",
                          }}
                        >
                          <div>
                            <p className="text-sm text-ink">{label}</p>
                            <p className="text-[11px] text-ink/35">
                              {disabled ? "Enable paid APIs (PAID_APIS_ENABLED) to use this." : hint}
                            </p>
                          </div>
                          {selected && <span className="text-crimson text-[10px] font-mono uppercase tracking-widest">Active</span>}
                        </button>
                      );
                    })}
                    <div
                      className="w-full flex items-center justify-between px-4 py-3 border opacity-40"
                      style={{ borderColor: "rgba(26,26,26,0.15)" }}
                    >
                      <div>
                        <p className="text-sm text-ink">Self-trained model</p>
                        <p className="text-[11px] text-ink/35">Our own fine-tuned engine.</p>
                      </div>
                      <span className="text-[9px] font-mono uppercase tracking-widest text-ink/40 border border-ink/20 px-2 py-0.5">
                        Roadmap
                      </span>
                    </div>
                  </div>
                </div>

                {/* OSINT Sources */}
                <div className="border-b border-ink/10 pb-8 mb-8">
                  <div className="flex items-center gap-2 mb-1">
                    <h2 className="font-display text-3xl text-ink">OSINT Sources</h2>
                    <span className="text-[9px] font-mono uppercase tracking-widest text-crimson border border-crimson/30 px-2 py-0.5">
                      Operator
                    </span>
                  </div>
                  <p className="text-sm text-ink/40 mb-6 font-mono uppercase tracking-wider text-[10px]">
                    Where open-source signals are pulled from
                  </p>

                  <div className="space-y-2">
                    {OSINT_OPTIONS.map(({ val, label, hint }) => {
                      const selected = config.config?.osint_source?.value === val;
                      return (
                        <button
                          key={val}
                          onClick={() => !selected && saveConfig("osint_source", val)}
                          disabled={cfgBusy === "osint_source"}
                          className="w-full flex items-center justify-between text-left px-4 py-3 border transition-colors disabled:opacity-40"
                          style={{
                            borderColor: selected ? "#C80028" : "rgba(26,26,26,0.15)",
                            backgroundColor: selected ? "#C8002810" : "transparent",
                          }}
                        >
                          <div>
                            <p className="text-sm text-ink">{label}</p>
                            <p className="text-[11px] text-ink/35">{hint}</p>
                          </div>
                          {selected && <span className="text-crimson text-[10px] font-mono uppercase tracking-widest">Active</span>}
                        </button>
                      );
                    })}

                    {/* RSS portfolio toggle */}
                    {(() => {
                      const on = !!config.config?.osint_rss_enabled?.value;
                      return (
                        <div className="flex items-center justify-between py-3 mt-1">
                          <div className="pr-4">
                            <p className="text-sm text-ink">RSS / Atom collector</p>
                            <p className="text-[11px] text-ink/35">Keyless multi-source portfolio (additive).</p>
                          </div>
                          <button
                            onClick={() => saveConfig("osint_rss_enabled", !on)}
                            disabled={cfgBusy === "osint_rss_enabled"}
                            aria-pressed={on}
                            className="relative w-10 h-5 rounded-full transition-colors shrink-0 disabled:opacity-50"
                            style={{ backgroundColor: on ? "#C80028" : "rgba(26,26,26,0.15)" }}
                          >
                            <span
                              className="absolute top-0.5 w-4 h-4 rounded-full bg-paper transition-all"
                              style={{ left: on ? "22px" : "2px" }}
                            />
                          </button>
                        </div>
                      );
                    })()}
                  </div>

                  {cfgErr && <p className="text-[12px] text-crimson mt-3">{cfgErr}</p>}
                  <p className="text-[11px] text-ink/35 mt-3">
                    Changes apply to on-demand analysis immediately; batch ingest picks them up next cycle.
                  </p>
                </div>
              </>
            )}

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
