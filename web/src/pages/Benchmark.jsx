import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";
import { useUser } from "../hooks/useUser.js";

// The public, citable calibration scoreboard. Data comes from the public
// GET /api/v1/benchmark/score (no auth). The whole point is external
// defensibility, so the honesty layers and citations are shown verbatim.
//
// Brier is a proper score: LOWER is better, 0.25 = a coin flip. We render the
// comparison bars against that 0.25 "no-skill" ceiling so shorter = better.
const BRIER_CEILING = 0.25;
const pct = (brier) => `${Math.min(100, (brier / BRIER_CEILING) * 100).toFixed(0)}%`;

function Bar({ label, brier, brierLow, brierHigh, bss, note, accent, dashed }) {
  const range = brierLow != null && brierHigh != null;
  return (
    <div className="mb-5">
      <div className="flex items-baseline justify-between mb-1.5">
        <span className="text-[12px] font-semibold text-ink/70">{label}</span>
        <span className="text-[11px] font-mono text-ink/45">
          {range ? `Brier ${brierLow}-${brierHigh}` : brier != null ? `Brier ${brier}` : "accruing"}
          {bss != null && <span className="text-ink/35"> · BSS {bss}</span>}
        </span>
      </div>
      <div className="h-2.5 w-full bg-ink/5 relative overflow-hidden">
        {dashed ? (
          <div className="absolute inset-0 border border-dashed border-ink/25"
               style={{ backgroundImage: "repeating-linear-gradient(45deg,transparent,transparent 5px,rgba(26,26,26,0.06) 5px,rgba(26,26,26,0.06) 10px)" }} />
        ) : range ? (
          <div className="absolute top-0 bottom-0"
               style={{ left: pct(brierLow), width: `calc(${pct(brierHigh)} - ${pct(brierLow)})`, backgroundColor: accent, opacity: 0.55 }} />
        ) : (
          <div className="absolute top-0 bottom-0 left-0" style={{ width: pct(brier), backgroundColor: accent }} />
        )}
      </div>
      {note && <p className="text-[10.5px] text-ink/40 mt-1.5 leading-snug">{note}</p>}
    </div>
  );
}

const ACCENT = { baseline: "#8A8A8A", reference: "#B07020", crowd: "#2D7DD2", engine: "#C80028" };

function LayerCard({ layer }) {
  const proven = layer.status === "proven";
  return (
    <div className="border border-ink/10 p-5">
      <div className="flex items-center gap-2 mb-2">
        <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: proven ? "#2E8B57" : "#B07020" }} />
        <span className="text-[9px] font-bold uppercase tracking-widest"
              style={{ color: proven ? "#2E8B57" : "#B07020" }}>
          {proven ? "Proven" : "Accruing"}
        </span>
      </div>
      <h3 className="font-display text-lg text-ink mb-1.5 leading-tight">{layer.title}</h3>
      <p className="text-[12px] text-ink/50 leading-relaxed">{layer.claim}</p>
    </div>
  );
}

export default function Benchmark() {
  const navigate = useNavigate();
  const { user } = useUser();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [ledger, setLedger] = useState(null);   // the hash-anchored forward ledger
  const [skill, setSkill] = useState(null);      // gated engine BSS (or "withheld")

  useEffect(() => {
    // Public trust page — must not blank on cold-start latency; override the 3.5s default.
    api.get("/benchmark/score", { timeoutMs: 10000 })
      .then(setData)
      .catch((e) => setErr(e.message || "Failed to load benchmark"));
  }, []);

  // Per-prediction ledger detail: only fetched for signed-in viewers. Endpoints
  // are public + precomputed, so these are cheap and degrade to empty on error.
  useEffect(() => {
    if (!user) return;
    api.get("/benchmark/ledger?limit=25", { timeoutMs: 10000 }).then(setLedger).catch(() => setLedger({ entries: [] }));
    api.get("/benchmark/engine-skill", { timeoutMs: 10000 }).then(setSkill).catch(() => setSkill(null));
  }, [user]);

  if (err) {
    return (
      <div className="min-h-screen bg-paper text-ink flex items-center justify-center px-8">
        <p className="text-[13px] text-ink/50">Benchmark unavailable — {err}</p>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="min-h-screen bg-paper flex items-center justify-center">
        <div className="w-5 h-5 border-2 border-ink/15 border-t-crimson rounded-full animate-spin" />
      </div>
    );
  }

  const syn = data.synthetic;
  const auto = data.autocast;
  const accrual = data.engine_accrual;
  const meterPct = accrual.graded_outcomes != null
    ? Math.min(100, (accrual.graded_outcomes / accrual.required) * 100) : 0;

  return (
    <div className="min-h-screen bg-paper text-ink font-sans selection:bg-crimson selection:text-paper">
      {/* Nav */}
      <nav className="border-b border-ink/8 px-8 md:px-14 py-4 flex justify-between items-center">
        <button onClick={() => navigate("/")} className="flex items-center gap-3">
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <polygon points="11,1 20,6 20,16 11,21 2,16 2,6" stroke="#C80028" strokeWidth="1.5" fill="none" />
            <polygon points="11,5 16,8 16,14 11,17 6,14 6,8" stroke="#C80028" strokeWidth="1" fill="#C80028" fillOpacity="0.12" />
          </svg>
          <span className="font-display text-xl tracking-wide text-ink">THE NARRATIVE</span>
        </button>
        <button
          onClick={() => navigate(user ? "/world" : "/auth")}
          className="text-[11px] font-bold uppercase tracking-widest border border-ink/20 px-5 py-2 hover:border-crimson hover:text-crimson transition-colors"
        >
          {user ? "Open App →" : "Sign In"}
        </button>
      </nav>

      <main className="max-w-4xl mx-auto px-8 md:px-14 py-14">
        {/* Header */}
        <p className="text-[9px] font-bold uppercase tracking-[0.45em] text-ink/30 mb-4">
          Calibration Benchmark · public & reproducible
        </p>
        <h1 className="font-display text-[2.2rem] md:text-[3.2rem] leading-none tracking-tight text-ink mb-5">
          How trustworthy are our forecasts?
        </h1>
        <p className="text-[14px] text-ink/55 leading-relaxed max-w-2xl mb-3">
          We measure ourselves with the metrics the forecast-verification field already accepts —
          proper scoring rules (Brier, log-loss), the Brier Skill Score, and the Murphy decomposition —
          and we separate what is <span className="text-ink font-semibold">proven today</span> from what is
          still <span className="text-ink font-semibold">accruing</span>. No premature accuracy claims.
        </p>
        <div className="border-l-2 border-crimson pl-4 py-1 my-6">
          <p className="text-[13px] text-ink/70 leading-relaxed font-medium">{data.headline}</p>
        </div>

        {/* Three honesty layers */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 my-10">
          {data.layers.map((l) => <LayerCard key={l.id} layer={l} />)}
        </div>

        {/* Comparison bars */}
        <section className="my-12">
          <p className="text-[9px] font-bold uppercase tracking-[0.4em] text-ink/30 mb-1">
            Where forecasters land
          </p>
          <p className="text-[11px] text-ink/40 mb-6">Brier score — shorter bar is better · 0.25 = a coin flip</p>
          {data.reference_bars.map((b) => (
            <Bar key={b.label} label={b.label} brier={b.brier} brierLow={b.brier_low}
                 brierHigh={b.brier_high} bss={b.bss} note={b.note} accent={ACCENT[b.kind]} />
          ))}
          {/* Our engine — withheld until the gate is met, never a premature number */}
          <Bar
            label="Our engine"
            note={accrual.gate_met
              ? "Engine Brier Skill Score is now available below."
              : `Withheld until n≥${accrual.required} graded outcomes — currently ${accrual.graded_outcomes ?? "?"}. No premature number.`}
            accent={ACCENT.engine}
            dashed={!accrual.gate_met}
          />
        </section>

        {/* Engine accrual meter */}
        <section className="my-12 border border-ink/10 p-6">
          <div className="flex items-baseline justify-between mb-3">
            <h3 className="font-display text-xl text-ink">Engine skill — accruing</h3>
            <span className="text-[12px] font-mono text-ink/50">
              {accrual.graded_outcomes ?? "?"} / {accrual.required}
            </span>
          </div>
          <div className="h-3 w-full bg-ink/5 overflow-hidden">
            <div className="h-full bg-crimson transition-all" style={{ width: `${meterPct}%` }} />
          </div>
          <p className="text-[11.5px] text-ink/45 mt-3 leading-relaxed">{accrual.note}</p>
        </section>

        {/* Proven: synthetic controls */}
        <section className="my-12">
          <p className="text-[9px] font-bold uppercase tracking-[0.4em] text-ink/30 mb-4">
            Proven today · scoring-pipeline controls
          </p>
          <div className="flex items-center gap-3 mb-4">
            <span className="font-display text-4xl text-ink">{syn.passed}/{syn.total}</span>
            <span className="text-[11px] font-bold uppercase tracking-widest text-[#2E8B57]">controls pass</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-[12px]">
            <div className="border border-ink/8 p-4">
              <p className="text-ink/40 text-[10px] uppercase tracking-widest mb-1">Overconfidence detected</p>
              <p className="font-mono text-ink/70">ECE {syn.over_ece.toFixed(3)} → {syn.over_ece_recal.toFixed(3)}</p>
            </div>
            <div className="border border-ink/8 p-4">
              <p className="text-ink/40 text-[10px] uppercase tracking-widest mb-1">Isotonic recovery</p>
              <p className="font-mono text-ink/70">Brier {syn.over_brier.toFixed(3)} → {syn.over_brier_recal.toFixed(3)}</p>
            </div>
          </div>
        </section>

        {/* External crowd baseline */}
        <section className="my-12">
          <p className="text-[9px] font-bold uppercase tracking-[0.4em] text-ink/30 mb-4">
            External real data · {auto.source === "real" ? "Autocast dataset" : "selftest fixture (Autocast unreachable)"}
          </p>
          <p className="text-[12px] text-ink/50 leading-relaxed mb-4 max-w-2xl">
            The same math on real forecasts. This is <span className="font-semibold text-ink">crowd</span> calibration
            (Metaculus / Good Judgment / CSET) — an independent sanity check on our scoring code,
            <span className="font-semibold text-ink"> not</span> our engine's own skill.
          </p>
          <div className="flex flex-wrap gap-6 text-[12px] font-mono text-ink/70">
            <span>n = {auto.n}</span>
            <span>Brier {auto.model_brier?.toFixed(4)}</span>
            <span>BSS {auto.bss?.toFixed(3)}</span>
            <span className="text-ink/40">vs base-rate {auto.base_brier?.toFixed(3)}</span>
          </div>
        </section>

        {/* Gated detail */}
        <section className="my-12">
          {user ? (
            <div className="border border-ink/10 p-6">
              <p className="text-[9px] font-bold uppercase tracking-[0.4em] text-ink/30 mb-4">
                Full metric detail · signed in
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-[12px] font-mono text-ink/70">
                <Metric k="cal ECE" v={syn.cal_ece} />
                <Metric k="over ECE" v={syn.over_ece} />
                <Metric k="over ECE (recal)" v={syn.over_ece_recal} />
                <Metric k="over Brier" v={syn.over_brier} />
                <Metric k="over Brier (recal)" v={syn.over_brier_recal} />
                <Metric k="crowd log-loss" v={auto.log_loss} />
                <Metric k="crowd ECE" v={auto.ece} />
                <Metric k="crowd coin Brier" v={auto.coin_brier} />
              </div>
              <LedgerPanel ledger={ledger} skill={skill} />
            </div>
          ) : (
            <div className="border border-dashed border-ink/20 p-6 text-center">
              <p className="text-[12px] text-ink/50 mb-3">
                Sign in for the full metric breakdown and the per-prediction ledger.
              </p>
              <button onClick={() => navigate("/auth")}
                      className="text-[11px] font-bold uppercase tracking-widest border border-ink/20 px-5 py-2 hover:border-crimson hover:text-crimson transition-colors">
                Sign In →
              </button>
            </div>
          )}
        </section>

        {/* Citations */}
        <section className="my-12 border-t border-ink/8 pt-8">
          <p className="text-[9px] font-bold uppercase tracking-[0.4em] text-ink/30 mb-4">Methodology</p>
          <ul className="space-y-2">
            {data.citations.map((c) => (
              <li key={c} className="text-[11px] text-ink/45 leading-relaxed pl-4 border-l border-ink/10">{c}</li>
            ))}
          </ul>
        </section>
      </main>

      <footer className="border-t border-ink/8 py-8 px-8 md:px-14 text-center">
        <p className="text-[9px] font-mono text-ink/25 uppercase tracking-widest">
          Reproduce: python scripts/benchmark_score.py
        </p>
      </footer>
    </div>
  );
}

function Metric({ k, v }) {
  return (
    <div>
      <p className="text-ink/40 text-[10px] uppercase tracking-widest mb-0.5">{k}</p>
      <p>{v == null ? "—" : Number(v).toFixed(4)}</p>
    </div>
  );
}

// The per-prediction forward ledger: forecasts hashed + committed BEFORE their
// outcome was known (verifiable against the daily manifest root in git). Engine
// skill (BSS) stays gated at n>=20 — we render "withheld" below the gate, never
// a premature number.
function LedgerPanel({ ledger, skill }) {
  const entries = ledger?.entries ?? [];
  return (
    <div className="mt-6 border-t border-ink/8 pt-5">
      <div className="flex items-baseline justify-between mb-3">
        <p className="text-[9px] font-bold uppercase tracking-[0.4em] text-ink/30">
          Forward prediction ledger · hash-anchored
        </p>
        {skill && (
          <span className="text-[11px] font-mono text-ink/55">
            {skill.status === "ready"
              ? `engine BSS ${skill.brier_skill_score} (n=${skill.resolved_n})`
              : `engine skill withheld · ${skill.resolved_n ?? 0}/${skill.required}`}
          </span>
        )}
      </div>
      <p className="text-[10.5px] text-ink/40 leading-snug mb-4">
        Each forecast below was hashed (sha256 of question · score · created_at) and rolled into a daily
        manifest root committed to git — published before its outcome was known, so a resolved score
        cannot be back-dated. Verify: <span className="font-mono">GET /benchmark/ledger/manifest/&#123;date&#125;</span>.
      </p>
      {entries.length === 0 ? (
        <p className="text-[11px] text-ink/40">
          No forecasts published yet — the ledger fills as confident forecasts accrue
          (<span className="font-mono">scripts/publish_ledger.py</span>).
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[11px] text-left border-collapse">
            <thead>
              <tr className="text-ink/40 uppercase text-[9px] tracking-widest">
                <th className="py-1.5 pr-3 font-semibold">Forecast</th>
                <th className="py-1.5 pr-3 font-semibold">Score</th>
                <th className="py-1.5 pr-3 font-semibold">Hash</th>
                <th className="py-1.5 pr-3 font-semibold">Status</th>
              </tr>
            </thead>
            <tbody className="font-mono text-ink/70">
              {entries.map((e) => (
                <tr key={e.content_hash} className="border-t border-ink/8 align-top">
                  <td className="py-1.5 pr-3 max-w-[240px] truncate font-sans">{e.question_text}</td>
                  <td className="py-1.5 pr-3">{e.prediction_score}</td>
                  <td className="py-1.5 pr-3 text-ink/45" title={e.content_hash}>{e.content_hash.slice(0, 12)}…</td>
                  <td className="py-1.5 pr-3">
                    {e.resolved
                      ? <span className="text-ink/70">Brier {e.brier_score?.toFixed(3)} · {e.outcome}</span>
                      : <span className="text-ink/35">pending</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
