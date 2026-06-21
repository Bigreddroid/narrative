import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useState, useEffect } from "react";
import { useUser } from "../hooks/useUser.js";

const ROTATING_WORDS = ["Conflict", "Economics", "Geopolitics", "Climate", "Security", "Policy"];

const CHAIN_EXAMPLES = [
  [
    { label: "Red Sea Crisis",    color: "#C80028" },
    { label: "Shipping Rerouted", color: "#B07020" },
    { label: "Supply Delays",     color: "#B07020" },
    { label: "Your Energy Bill",  color: "#2D7DD2" },
  ],
  [
    { label: "Taiwan Tensions",   color: "#C80028" },
    { label: "PLA Exercises",     color: "#C84020" },
    { label: "Chip Shortage",     color: "#7848C8" },
    { label: "Your Electronics",  color: "#2D7DD2" },
  ],
  [
    { label: "Amazon Drought",    color: "#308050" },
    { label: "Soy Harvest −40%",  color: "#308050" },
    { label: "Food Price Surge",  color: "#B07020" },
    { label: "Your Grocery Bill", color: "#2D7DD2" },
  ],
];

const TIERS_PREVIEW = [
  {
    name: "Free",
    price: "$0",
    period: "",
    features: [
      "Top 10 events per day",
      "Feed summaries only",
      "Global world map",
      "No consequence chains",
      "No predictions or effects",
    ],
    limit: "Get the gist",
    cta: "Start Free",
  },
  {
    name: "Pro",
    price: "$12",
    period: "/mo",
    features: [
      "Unlimited intelligence feed",
      "Full consequence chain explorer",
      "All 6 world regions",
      "Predictions & chain effects",
      "Article source & bias breakdown",
    ],
    limit: "For curious individuals",
    cta: "Get Pro",
  },
  {
    name: "Intelligence",
    price: "$29",
    period: "/mo",
    features: [
      "Everything in Pro",
      "Real-time push alerts",
      "Full REST API access",
      "Export to PDF / CSV",
      "90-day historical archive",
    ],
    highlight: true,
    limit: "For analysts & researchers",
    cta: "Get Intelligence",
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    features: [
      "Everything in Intelligence",
      "20+ team seats with roles",
      "Webhooks & custom integrations",
      "Scheduled reports & briefings",
      "SSO / SAML + dedicated support",
    ],
    limit: "For organisations & newsrooms",
    cta: "Contact Us",
  },
];

function RotatingWord() {
  const [idx, setIdx] = useState(0);
  const [show, setShow] = useState(true);
  useEffect(() => {
    const t = setInterval(() => {
      setShow(false);
      setTimeout(() => { setIdx(i => (i + 1) % ROTATING_WORDS.length); setShow(true); }, 180);
    }, 2000);
    return () => clearInterval(t);
  }, []);
  return (
    <motion.span animate={{ opacity: show ? 1 : 0 }} transition={{ duration: 0.18 }}
      className="text-crimson">{ROTATING_WORDS[idx]}</motion.span>
  );
}

function ChainDemo() {
  const [ci, setCi] = useState(0);
  const [step, setStep] = useState(0);
  const [visible, setVisible] = useState(true);
  const chain = CHAIN_EXAMPLES[ci];

  useEffect(() => {
    setStep(0);
    let s = 0;
    const t = setInterval(() => {
      s += 1;
      if (s > chain.length) {
        clearInterval(t);
        setTimeout(() => {
          setVisible(false);
          setTimeout(() => { setCi(i => (i + 1) % CHAIN_EXAMPLES.length); setStep(0); setVisible(true); }, 350);
        }, 2000);
        return;
      }
      setStep(s);
    }, 500);
    return () => clearInterval(t);
  }, [ci]);

  return (
    <motion.div animate={{ opacity: visible ? 1 : 0 }} transition={{ duration: 0.3 }}
      className="flex items-center justify-center gap-0 py-2">
      {chain.map((node, i) => (
        <div key={i} className="flex items-center">
          <div className="flex flex-col items-center gap-1.5 px-1">
            <motion.div
              animate={i < step ? { scale: 1, opacity: 1 } : { scale: 0.4, opacity: 0 }}
              transition={{ duration: 0.22 }}
              className="w-2.5 h-2.5 rounded-full"
              style={{ backgroundColor: node.color, boxShadow: i < step ? `0 0 8px ${node.color}80` : "none" }}
            />
            <motion.span
              animate={{ opacity: i < step ? 1 : 0 }}
              transition={{ duration: 0.18, delay: 0.06 }}
              className="text-[10px] text-ink/50 whitespace-nowrap font-medium"
            >
              {node.label}
            </motion.span>
          </div>
          {i < chain.length - 1 && (
            <motion.div
              animate={i < step - 1 ? { scaleX: 1, opacity: 0.3 } : { scaleX: 0, opacity: 0 }}
              transition={{ duration: 0.18 }}
              className="w-8 h-px origin-left mb-4"
              style={{ backgroundColor: "#1A1A1A" }}
            />
          )}
        </div>
      ))}
    </motion.div>
  );
}

export default function Landing() {
  const navigate    = useNavigate();
  const { user }    = useUser();
  const isLoggedIn  = !!user;

  return (
    <div className="min-h-screen bg-paper text-ink font-sans selection:bg-crimson selection:text-paper">

      {/* ── Nav ── */}
      <nav className="border-b border-ink/8 px-8 md:px-14 py-4 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <polygon points="11,1 20,6 20,16 11,21 2,16 2,6" stroke="#C80028" strokeWidth="1.5" fill="none" />
            <polygon points="11,5 16,8 16,14 11,17 6,14 6,8" stroke="#C80028" strokeWidth="1" fill="#C80028" fillOpacity="0.12" />
          </svg>
          <span className="font-display text-xl tracking-wide text-ink">THE NARRATIVE</span>
        </div>
        <div className="flex items-center gap-6">
          <button
            onClick={() => document.getElementById("pricing")?.scrollIntoView({ behavior: "smooth" })}
            className="text-[11px] font-semibold uppercase tracking-widest text-ink/40 hover:text-crimson transition-colors hidden sm:block"
          >
            Pricing
          </button>
          <button
            onClick={() => navigate(isLoggedIn ? "/world" : "/auth")}
            className="text-[11px] font-bold uppercase tracking-widest border border-ink/20 px-5 py-2 hover:border-crimson hover:text-crimson transition-colors"
          >
            {isLoggedIn ? "Open App →" : "Sign In"}
          </button>
        </div>
      </nav>

      {/* ── Hero ── */}
      <main className="max-w-4xl mx-auto px-8 md:px-14 pt-20 pb-16 text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        >
          <div className="inline-flex items-center gap-2 border border-ink/12 px-4 py-1.5 mb-10 text-[10px] font-semibold uppercase tracking-widest text-ink/40">
            <span className="w-1.5 h-1.5 rounded-full bg-crimson animate-pulse" />
            Live intelligence · 100+ sources monitored
          </div>

          <h1 className="font-display text-[2.6rem] sm:text-[4rem] md:text-[5.5rem] lg:text-[7rem] leading-none tracking-tighter text-ink mb-6">
            THE WORLD IN<br />
            <RotatingWord />{" "}
            <span className="text-ink/20">—</span><br />
            <span className="text-ink">CONSEQUENCE MAPPED.</span>
          </h1>

          <p className="text-[15px] text-ink/50 max-w-xl mx-auto leading-relaxed mb-10 font-normal">
            Every global event traced through cause and mechanism to its real-world consequence.
            Consequences, not headlines.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <button
              onClick={() => navigate(isLoggedIn ? "/world" : "/auth")}
              className="px-8 py-3.5 bg-ink text-paper text-[12px] font-bold uppercase tracking-widest hover:bg-crimson transition-colors"
            >
              Start Free →
            </button>
            <button
              onClick={() => document.getElementById("how")?.scrollIntoView({ behavior: "smooth" })}
              className="px-8 py-3.5 border border-ink/20 text-[12px] font-bold uppercase tracking-widest text-ink/50 hover:text-crimson hover:border-crimson transition-colors"
            >
              See How It Works
            </button>
          </div>
        </motion.div>
      </main>

      {/* ── Consequence chain demo ── */}
      <section id="how" className="border-t border-b border-ink/8 py-14 px-8">
        <div className="max-w-3xl mx-auto text-center">
          <p className="text-[9px] font-bold uppercase tracking-[0.45em] text-ink/30 mb-4">
            Example consequence chain
          </p>
          <ChainDemo />
          <p className="text-[11px] text-ink/35 mt-6 tracking-wide">
            One event. Four consequence steps. Your life at the end of the chain.
          </p>
        </div>
      </section>

      {/* ── What you get ── */}
      <section className="max-w-4xl mx-auto px-8 md:px-14 py-20">
        <p className="text-[9px] font-bold uppercase tracking-[0.45em] text-ink/30 mb-12 text-center">
          What The Narrative does
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[
            {
              title: "Intelligence Feed",
              desc: "Events ranked by AI consequence score. Not viral. Not clickbait. The things that actually matter, first.",
              accent: "#C80028",
            },
            {
              title: "Consequence Chains",
              desc: "Every event unfolded: Verified facts → Inferred mechanisms → Speculative effects. See the full causal path.",
              accent: "#B07020",
            },
            {
              title: "World View",
              desc: "Live geopolitical atlas. Click any event node to see how it connects to others across borders.",
              accent: "#2D7DD2",
            },
          ].map(item => (
            <div key={item.title} className="border border-ink/10 p-7 group hover:border-ink/25 transition-colors">
              <div className="w-8 h-0.5 mb-6" style={{ backgroundColor: item.accent }} />
              <h3 className="font-display text-2xl text-ink mb-3 leading-tight">{item.title}</h3>
              <p className="text-[13px] text-ink/45 leading-relaxed">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Pricing ── */}
      <section id="pricing" className="border-t border-ink/8 py-20 px-8 md:px-14">
        <div className="max-w-4xl mx-auto">
          <p className="text-[9px] font-bold uppercase tracking-[0.45em] text-ink/30 mb-2 text-center">
            Pricing
          </p>
          <p className="text-center text-[13px] text-ink/40 mb-12">Start free. Upgrade when you need more.</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {TIERS_PREVIEW.map(t => (
              <div
                key={t.name}
                className="border p-6 relative flex flex-col"
                style={{
                  borderColor: t.highlight ? "#C80028" : "rgba(26,26,26,0.10)",
                  backgroundColor: t.highlight ? "rgba(200,0,40,0.03)" : "transparent",
                }}
              >
                {t.highlight && <div className="absolute -top-px left-0 right-0 h-0.5 bg-crimson" />}
                {t.highlight && (
                  <div className="absolute -top-3 left-4 bg-crimson px-2 py-px">
                    <span className="text-[8px] font-bold uppercase tracking-widest text-paper">Most Popular</span>
                  </div>
                )}

                <div className="mb-4">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-ink/35 mb-2">{t.name}</p>
                  <div className="flex items-baseline gap-0.5">
                    <span className="font-display text-3xl text-ink">{t.price}</span>
                    {t.period && <span className="text-[11px] text-ink/35">{t.period}</span>}
                  </div>
                  <p className="text-[10px] text-ink/30 mt-1">{t.limit}</p>
                </div>

                <ul className="space-y-2 mb-6 flex-1">
                  {t.features.map(f => (
                    <li key={f} className="flex items-start gap-2 text-[12px] text-ink/55">
                      <span className="w-1 h-1 rounded-full bg-crimson flex-shrink-0 mt-1.5" />
                      {f}
                    </li>
                  ))}
                </ul>

                <button
                  onClick={() => {
                    if (t.name === "Enterprise") { window.location.href = "mailto:hello@narrative.com"; }
                    else navigate("/auth");
                  }}
                  className="pricing-cta w-full py-2.5 text-[11px] font-bold uppercase tracking-widest border"
                  style={t.highlight
                    ? { backgroundColor: "#C80028", color: "#F0EDE8", borderColor: "#C80028" }
                    : { borderColor: "rgba(26,26,26,0.15)", color: "rgba(26,26,26,0.6)" }
                  }
                  data-highlight={t.highlight ? "true" : undefined}
                >
                  {t.cta}
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-ink/8 py-10 px-8 md:px-14 flex flex-col md:flex-row justify-between items-center gap-4">
        <div className="flex items-center gap-2">
          <svg width="16" height="16" viewBox="0 0 22 22" fill="none">
            <polygon points="11,1 20,6 20,16 11,21 2,16 2,6" stroke="#C80028" strokeWidth="1.5" fill="none" />
          </svg>
          <span className="text-[9px] font-bold uppercase tracking-[0.35em] text-ink/30">
            The Narrative Intelligence
          </span>
        </div>
        <p className="text-[9px] font-mono text-ink/25 uppercase tracking-widest">
          © 2026 · Consequences, not headlines.
        </p>
      </footer>
    </div>
  );
}
