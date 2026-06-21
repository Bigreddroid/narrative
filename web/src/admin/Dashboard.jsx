import { useEffect, useState } from "react";
import { api } from "../lib/api.js";

function StatCard({ label, value, sub, color }) {
  return (
    <div className="bg-bg-elevated border border-border rounded-lg p-4">
      <p className="text-xs text-text-muted uppercase tracking-wider mb-1">{label}</p>
      <p className="text-2xl font-mono font-bold" style={{ color: color || "#F0F6FC" }}>
        {value}
      </p>
      {sub && <p className="text-xs text-text-muted mt-1">{sub}</p>}
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = () => {
    setLoading(true);
    api.get("/admin/dashboard")
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 10000);
    return () => clearInterval(t);
  }, []);

  if (loading && !data) {
    return <p className="text-text-muted text-sm">Loading dashboard...</p>;
  }

  const today = data?.today || {};
  const totals = data?.totals || {};

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold">Dashboard</h1>
        <button
          onClick={refresh}
          className="text-xs text-text-muted border border-border px-3 py-1.5 rounded-lg hover:text-text-primary transition-colors"
        >
          Refresh
        </button>
      </div>

      <h2 className="text-xs uppercase tracking-wider text-text-muted mb-3">Today</h2>
      <div className="grid grid-cols-4 gap-4 mb-8">
        <StatCard label="Articles Scraped" value={today.articles_scraped?.toLocaleString() ?? "—"} />
        <StatCard label="Events Mapped" value={today.events_mapped?.toLocaleString() ?? "—"} color="#27AE60" />
        <StatCard label="Claude Calls" value={today.claude_calls?.toLocaleString() ?? "—"} color="#9B51E0" />
        <StatCard
          label="Claude Cost"
          value={`$${today.claude_cost_usd?.toFixed(4) ?? "0.00"}`}
          color={today.claude_cost_usd > 15 ? "#FF4B4B" : "#F5A623"}
          sub="today"
        />
        <StatCard label="Alerts Sent" value={today.alerts_sent?.toLocaleString() ?? "—"} />
        <StatCard
          label="Errors"
          value={today.errors?.toLocaleString() ?? "—"}
          color={today.errors > 0 ? "#FF4B4B" : "#27AE60"}
        />
      </div>

      <h2 className="text-xs uppercase tracking-wider text-text-muted mb-3">Totals</h2>
      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Total Users" value={totals.users?.toLocaleString() ?? "—"} />
        <StatCard label="Mapped Events" value={totals.mapped_events?.toLocaleString() ?? "—"} color="#56CCF2" />
      </div>
    </div>
  );
}
