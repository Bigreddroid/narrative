import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../lib/api.js";

const PROFESSIONS = [
  "Finance & Banking", "Healthcare", "Technology", "Education",
  "Agriculture", "Energy", "Manufacturing", "Government",
  "Logistics & Transport", "Retail", "Media", "Law",
];

const SECTORS = [
  "Energy", "Food", "Transport", "Housing",
  "Finance", "Healthcare", "Technology", "Agriculture",
];

const COUNTRIES = [
  "United States", "United Kingdom", "India", "China",
  "Germany", "France", "Brazil", "Australia",
  "Canada", "Japan", "Nigeria", "South Africa",
];

function StepIndicator({ step, total }) {
  return (
    <div className="flex items-center gap-2 justify-center mb-12">
      {Array.from({ length: total }).map((_, i) => (
        <motion.div
          key={i}
          animate={{
            width: i === step ? 20 : 4,
            backgroundColor: i === step ? "#2A6EBB" : i < step ? "#1E3450" : "#152338",
          }}
          style={{ height: 2 }}
          transition={{ type: "spring", stiffness: 400, damping: 30 }}
        />
      ))}
      <span className="text-2xs font-mono text-text-muted ml-1">
        {step + 1}/{total}
      </span>
    </div>
  );
}

const stepVariants = {
  enter:  { opacity: 0, x: 24  },
  center: { opacity: 1, x: 0   },
  exit:   { opacity: 0, x: -24 },
};

export default function Onboarding() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [country, setCountry] = useState("");
  const [city, setCity] = useState("");
  const [profession, setProfession] = useState("");
  const [sectors, setSectors] = useState([]);
  const [saving, setSaving] = useState(false);

  const toggleSector = (s) =>
    setSectors((prev) => prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]);

  const handleFinish = async () => {
    setSaving(true);
    try {
      await api.patch("/users/me", { country, city, profession, spending_categories: sectors });
    } catch {}
    navigate("/osint");
  };

  const stepContent = [
    <motion.div
      key="step0"
      variants={stepVariants}
      initial="enter" animate="center" exit="exit"
      transition={{ duration: 0.25 }}
      className="text-center"
    >
      <h2 className="text-2xl font-bold text-text-primary mb-2">Where do we map consequences for?</h2>
      <p className="text-sm text-text-secondary mb-8">Your location shapes which events hit closest to home.</p>

      <div className="max-w-xs mx-auto space-y-3">
        <select
          value={country}
          onChange={(e) => setCountry(e.target.value)}
          className="w-full px-3 py-2.5 text-sm rounded-none appearance-none cursor-pointer"
        >
          <option value="">Select country…</option>
          {COUNTRIES.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>

        <input
          type="text"
          placeholder="City (optional)"
          value={city}
          onChange={(e) => setCity(e.target.value)}
          className="w-full px-3 py-2.5 text-sm rounded-none"
        />
      </div>

      <button
        onClick={() => country && setStep(1)}
        disabled={!country}
        className="mt-8 px-8 py-2.5 text-sm font-medium text-text-primary disabled:opacity-30 transition-colors"
        style={{ backgroundColor: "#2A6EBB" }}
      >
        Continue
      </button>
    </motion.div>,

    <motion.div
      key="step1"
      variants={stepVariants}
      initial="enter" animate="center" exit="exit"
      transition={{ duration: 0.25 }}
      className="text-center"
    >
      <h2 className="text-2xl font-bold text-text-primary mb-2">Your profession shapes your exposure.</h2>
      <p className="text-sm text-text-secondary mb-8">Select what you do.</p>

      <div className="grid grid-cols-3 gap-2 max-w-md mx-auto mb-8">
        {PROFESSIONS.map((p) => (
          <button
            key={p}
            onClick={() => setProfession(p)}
            className="p-2.5 text-xs text-left border transition-colors"
            style={{
              backgroundColor: profession === p ? "#0C1C33" : "#081526",
              borderColor:     profession === p ? "#2A6EBB" : "#152338",
              color:           profession === p ? "#C2D6EE" : "#4E6E8E",
            }}
          >
            {p}
          </button>
        ))}
      </div>

      <button
        onClick={() => profession && setStep(2)}
        disabled={!profession}
        className="px-8 py-2.5 text-sm font-medium text-text-primary disabled:opacity-30 transition-colors"
        style={{ backgroundColor: "#2A6EBB" }}
      >
        Continue
      </button>
    </motion.div>,

    <motion.div
      key="step2"
      variants={stepVariants}
      initial="enter" animate="center" exit="exit"
      transition={{ duration: 0.25 }}
      className="text-center"
    >
      <h2 className="text-2xl font-bold text-text-primary mb-2">Which sectors affect you most?</h2>
      <p className="text-sm text-text-secondary mb-8">Select all that apply.</p>

      <div className="flex flex-wrap gap-2 justify-center max-w-md mx-auto mb-8">
        {SECTORS.map((s) => {
          const on = sectors.includes(s);
          return (
            <button
              key={s}
              onClick={() => toggleSector(s)}
              className="px-4 py-2 text-sm border transition-colors"
              style={{
                backgroundColor: on ? "#0C1C33" : "#081526",
                borderColor:     on ? "#2A6EBB" : "#152338",
                color:           on ? "#C2D6EE" : "#4E6E8E",
              }}
            >
              {s}
            </button>
          );
        })}
      </div>

      <button
        onClick={handleFinish}
        disabled={sectors.length === 0 || saving}
        className="px-8 py-2.5 text-sm font-medium text-text-primary disabled:opacity-30 transition-colors"
        style={{ backgroundColor: "#2A6EBB" }}
      >
        {saving ? "Setting up…" : "Open my consequence map"}
      </button>
    </motion.div>,
  ];

  return (
    <div className="min-h-screen bg-bg-base flex flex-col items-center justify-center px-6">
      <div className="w-full max-w-xl">
        <StepIndicator step={step} total={3} />
        <AnimatePresence mode="wait">{stepContent[step]}</AnimatePresence>
      </div>
    </div>
  );
}
