import { useMemo } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { useExposure } from "../hooks/useExposure.js";
import { useUser } from "../hooks/useUser.js";
import { profileExposure } from "../lib/exposureProfile.js";
import { exposureColor } from "../lib/exposureColor.js";
import { getCategoryColor } from "../lib/colors.js";

const DEFAULT_PROFILE = { sectors: ["Technology", "Energy", "Shipping & Logistics"], regions: ["United States"] };

// ─── Exposure Index, visualised ─────────────────────────────────────────────
// 0–100 risk per sector/region, decomposed into the source events driving it.
// Trends are drawn ONLY from real accumulated history (model entity.history) —
// no synthetic series. A row with <2 real points simply shows no trend.

const FG    = "#F0EDE8";
const FG80  = "rgba(240,237,232,0.80)";
const FG50  = "rgba(240,237,232,0.50)";
const FG40  = "rgba(240,237,232,0.40)";
const FG30  = "rgba(240,237,232,0.30)";
const FG20  = "rgba(240,237,232,0.20)";
const BD    = "rgba(240,237,232,0.08)";
const EASE  = "#3FA77A";

// Tiny inline trajectory sparkline. Renders only when given ≥2 REAL points.
function Sparkline({ values, color, width = 52, height = 14 }) {
  if (!Array.isArray(values) || values.length < 2) return null;
  const max = Math.max(...values, 1), min = Math.min(...values, 0);
  const range = Math.max(1, max - min);
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * width},${height - ((v - min) / range) * height}`).join(" ");
  return (
    <svg width={width} height={height} className="block">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.2" strokeLinejoin="round" opacity="0.8" />
    </svg>
  );
}

const TREND_GLYPH = { rising: "↑", falling: "↓", stable: "→" };
const TREND_COLOR = { rising: "#C80028", falling: "#3FA77A", stable: "rgba(240,237,232,0.4)" };

// Plain-language risk bands, matched to exposureColor() thresholds.
const RISK_BANDS = [
  { label: "Low", at: 10 },
  { label: "Elevated", at: 30 },
  { label: "High", at: 55 },
  { label: "Severe", at: 85 },
];

function Legend() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
      {RISK_BANDS.map((b) => (
        <span key={b.label} className="flex items-center gap-1.5 text-[9px] font-mono uppercase tracking-wider" style={{ color: FG40 }}>
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: exposureColor(b.at) }} />
          {b.label}
        </span>
      ))}
    </div>
  );
}

function RiskGauge({ score }) {
  return (
    <div className="flex items-end gap-3">
      <span className="font-display leading-none tabular-nums" style={{ fontSize: "4rem", color: exposureColor(score) }}>
        {score}
      </span>
      <div className="pb-2">
        <p className="text-[10px] font-mono uppercase tracking-[0.3em]" style={{ color: FG40 }}>Overall</p>
        <p className="text-[10px] font-mono uppercase tracking-[0.3em]" style={{ color: FG40 }}>Risk</p>
      </div>
    </div>
  );
}

function ExposureRow({ entity, onDriver, corrob }) {
  // Real history only — no synthetic series. Trend = real first→last delta.
  const series = Array.isArray(entity.history) && entity.history.length >= 2 ? entity.history : null;
  const delta = series ? series[series.length - 1] - series[0] : 0;
  const trend = delta > 2 ? "rising" : delta < -2 ? "falling" : "stable";
  return (
    <div className="px-5 py-3.5" style={{ borderBottom: `1px solid ${BD}` }}>
      <div className="flex items-baseline justify-between gap-3 mb-1.5">
        <span className="text-[13px] font-semibold capitalize truncate" style={{ color: FG80 }}>{entity.name}</span>
        <div className="flex items-center gap-2 flex-shrink-0">
          {series && <Sparkline values={series} color={exposureColor(entity.score)} />}
          {series && (
            <span className="text-[11px] font-mono" style={{ color: TREND_COLOR[trend] }} title={`Trend over recent snapshots: ${trend}`}>
              {TREND_GLYPH[trend]}
            </span>
          )}
          <span className="text-[13px] font-mono tabular-nums w-7 text-right" style={{ color: exposureColor(entity.score) }}>
            {entity.score}
          </span>
        </div>
      </div>

      {/* Score bar */}
      <div className="h-1 rounded-full overflow-hidden mb-2" style={{ backgroundColor: FG20 }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${entity.score}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className="h-full rounded-full"
          style={{ backgroundColor: exposureColor(entity.score) }}
        />
      </div>

      {/* Drivers */}
      {entity.drivers.length > 0 && (
        <span className="text-[9px] font-mono uppercase tracking-wider mr-2" style={{ color: FG30 }}>Driven by</span>
      )}
      <div className="inline-flex flex-wrap gap-x-3 gap-y-1 align-middle">
        {entity.drivers.map((d) => {
          const c = corrob?.[d.id];
          return (
            <button
              key={d.id}
              onClick={() => onDriver(d.id)}
              className="flex items-center gap-1 text-[10px] font-mono transition-colors hover:opacity-100"
              style={{ color: FG40, opacity: 0.85 }}
              title={d.title}
            >
              <span className="w-1 h-1 rounded-full flex-shrink-0" style={{ backgroundColor: getCategoryColor(d.category) }} />
              <span className="truncate max-w-[150px]" style={{ color: FG50 }}>{d.title}</span>
              <span className="tabular-nums" style={{ color: FG30 }}>{d.pct}%</span>
              {c?.count > 0 && (
                <span
                  className="tabular-nums"
                  style={{ color: EASE }}
                  title={`Cross-feed corroborated by ${c.count} independent feed${c.count > 1 ? "s" : ""}: ${c.sources.join(", ")}`}
                >
                  ✓{c.count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Mitigators (events reducing this exposure) */}
      {entity.mitigators?.length > 0 && (
        <div className="flex items-center gap-1.5 mt-1.5 text-[10px] font-mono" style={{ color: EASE }}>
          <span className="uppercase tracking-wider text-[9px]">Reduced by</span>
          <span className="truncate max-w-[180px]" style={{ opacity: 0.8 }}>{entity.mitigators[0].title}</span>
        </div>
      )}
    </div>
  );
}

function Column({ title, entities, onDriver, corrob }) {
  return (
    <div className="flex-1 min-w-0">
      <div className="px-5 py-3" style={{ borderBottom: `1px solid ${BD}` }}>
        <p className="text-[9px] font-mono font-bold uppercase tracking-[0.4em]" style={{ color: FG40 }}>{title}</p>
      </div>
      {entities.length === 0 ? (
        <p className="px-5 py-6 text-[10px] font-mono uppercase tracking-wider" style={{ color: FG20 }}>No exposure detected</p>
      ) : (
        entities.map((e) => <ExposureRow key={e.key} entity={e} onDriver={onDriver} corrob={corrob} />)
      )}
    </div>
  );
}

export default function ExposurePanel() {
  const { model, loading, live, error } = useExposure();
  const { user } = useUser();
  const navigate = useNavigate();

  const sectors = useMemo(() => (model?.sectors || []).slice(0, 8), [model]);
  const regions = useMemo(() => (model?.regions || []).slice(0, 8), [model]);
  const corrob = model?.corroboration || {};
  const corrobCount = Object.keys(corrob).length;
  const onDriver = (id) => navigate(`/event/${id}`);

  const profile = useMemo(() => {
    const s = user?.spending_categories?.length ? user.spending_categories : DEFAULT_PROFILE.sectors;
    const r = [user?.country, user?.city].filter(Boolean);
    return { sectors: s, regions: r.length ? r : DEFAULT_PROFILE.regions };
  }, [user]);
  const personal = useMemo(() => (model ? profileExposure(profile, model) : { score: 0, drivers: [] }), [model, profile]);

  return (
    <div className="flex-1 min-h-0 overflow-y-auto" style={{ backgroundColor: "#0E0E0E", color: FG }}>
      <div className="max-w-[1100px] mx-auto">

        {/* Header */}
        <div className="px-5 md:px-8 py-6 flex items-end justify-between gap-6" style={{ borderBottom: `1px solid ${BD}` }}>
          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "#C80028", boxShadow: "0 0 6px #C80028" }} />
              <span className="text-[9px] font-mono font-bold uppercase tracking-[0.4em] text-crimson">
                Consequence Propagation Engine
              </span>
            </div>
            {loading ? (
              <div className="h-16 w-32 rounded animate-pulse" style={{ backgroundColor: FG20 }} />
            ) : (
              <RiskGauge score={model?.pressure ?? 0} />
            )}
          </div>

          <div className="text-right pb-1">
            <div className="flex items-center gap-1.5 justify-end mb-1">
              <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: live ? EASE : "#C9A227" }} />
              <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: live ? EASE : "#C9A227" }}>
                {live ? "Live data" : "Demo data"}
              </span>
            </div>
            {model?.meta && (
              <p className="text-[9px] font-mono uppercase tracking-wider" style={{ color: FG30 }}>
                CPE v{model.meta.version} · {model.meta.events} events · {model.meta.links} links
                {corrobCount > 0 && <span style={{ color: EASE }}> · {corrobCount} corroborated</span>}
              </p>
            )}
          </div>
        </div>

        {/* Honest error state — never silently fabricated data */}
        {error && !loading && (
          <div className="px-5 md:px-8 py-3 text-[11px] font-mono" style={{ color: "#C9A227", borderBottom: `1px solid ${BD}` }}>
            Couldn't load live exposure data — check your connection and refresh.
          </div>
        )}

        {/* What this is + risk legend */}
        <div className="px-5 md:px-8 py-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between" style={{ borderBottom: `1px solid ${BD}` }}>
          <p className="text-[11px] leading-relaxed max-w-[560px]" style={{ color: FG50 }}>
            How exposed each industry and region is to what's happening in the world right now — scored 0 (calm) to 100 (severe). Tap any event to see why.
          </p>
          <Legend />
        </div>

        {/* Your Exposure */}
        {model && (
          <div className="px-5 md:px-8 py-5 flex items-center gap-5" style={{ borderBottom: `1px solid ${BD}` }}>
            <div className="flex items-end gap-3 flex-shrink-0">
              <span className="font-display leading-none tabular-nums" style={{ fontSize: "2.6rem", color: exposureColor(personal.score) }}>
                {personal.score}
              </span>
              <div className="pb-1.5">
                <p className="text-[9px] font-mono uppercase tracking-[0.3em]" style={{ color: FG40 }}>Your</p>
                <p className="text-[9px] font-mono uppercase tracking-[0.3em]" style={{ color: FG40 }}>Exposure</p>
              </div>
            </div>
            <div className="min-w-0">
              <p className="text-[10px] leading-snug mb-1.5" style={{ color: FG50 }}>
                Your risk from the things you track. Higher = more of your profile is affected.
              </p>
              <p className="text-[10px] font-mono uppercase tracking-wider mb-1.5 truncate" style={{ color: FG30 }}>
                Profile · {[...profile.sectors, ...profile.regions].slice(0, 4).join(" · ")}
              </p>
              <div className="flex flex-wrap gap-x-3 gap-y-1">
                {personal.drivers.length ? personal.drivers.map((d) => (
                  <button key={d.id} onClick={() => onDriver(d.id)} className="flex items-center gap-1 text-[10px] font-mono" style={{ color: FG50 }} title={d.title}>
                    <span className="w-1 h-1 rounded-full flex-shrink-0" style={{ backgroundColor: getCategoryColor(d.category) }} />
                    <span className="truncate max-w-[180px]">{d.title}</span>
                  </button>
                )) : (
                  <span className="text-[10px] font-mono" style={{ color: FG20 }}>No exposure on your profile</span>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Two columns */}
        <div className="flex flex-col md:flex-row" style={{ borderBottom: `1px solid ${BD}` }}>
          <div className="md:border-r" style={{ borderColor: BD }}>
            <Column title="Most Exposed Sectors" entities={sectors} onDriver={onDriver} corrob={corrob} />
          </div>
          <Column title="Most Exposed Regions" entities={regions} onDriver={onDriver} corrob={corrob} />
        </div>

        {/* Footnote — plain language */}
        <div className="px-5 md:px-8 py-5 space-y-1.5">
          <p className="text-[10px] leading-relaxed max-w-[640px]" style={{ color: FG30 }}>
            Each score adds up how hard the current events hit that area — weighted by how serious each event is and how
            well-confirmed it is across sources. The events under each row are what's driving (or easing) it; tap one for the full chain.
          </p>
          <p className="text-[9px] font-mono uppercase tracking-wider" style={{ color: FG20 }}>
            <span style={{ color: EASE }}>✓</span> = confirmed by multiple independent feeds · trend line shows real change once history builds up
          </p>
        </div>
      </div>
    </div>
  );
}
