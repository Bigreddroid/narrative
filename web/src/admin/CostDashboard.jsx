import { useEffect, useState } from "react";
import { api } from "../lib/api.js";

function CostBar({ label, value, max, color }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="mb-3">
      <div className="flex justify-between text-xs mb-1">
        <span className="text-text-secondary">{label}</span>
        <span className="font-mono" style={{ color }}>${value.toFixed(4)}</span>
      </div>
      <div className="h-1.5 bg-bg-elevated rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

export default function CostDashboard() {
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/admin/costs").then(setData).catch(console.error);
  }, []);

  if (!data) return <p className="text-text-muted text-sm">Loading costs...</p>;

  const daily = data.daily_breakdown || [];

  return (
    <div>
      <h1 className="text-xl font-bold mb-6">Cost Dashboard</h1>

      <div className="grid grid-cols-3 gap-4 mb-8">
        {[
          { label: "Today", value: data.today_usd, color: "#F5A623" },
          { label: "This Week", value: data.week_usd, color: "#F5A623" },
          { label: "This Month", value: data.month_usd, color: "#F5A623" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-bg-elevated border border-border rounded-lg p-4">
            <p className="text-xs text-text-muted uppercase tracking-wider mb-1">{label}</p>
            <p className="text-2xl font-mono font-bold" style={{ color }}>
              ${value?.toFixed(2) ?? "0.00"}
            </p>
          </div>
        ))}
      </div>

      <div className="bg-bg-elevated border border-border rounded-lg p-4 mb-6">
        <p className="text-xs text-text-muted uppercase tracking-wider mb-3">Projected Monthly</p>
        <p className="text-lg font-mono font-bold text-text-primary">${data.projected_monthly_usd?.toFixed(2) ?? "0.00"}</p>
      </div>

      <h2 className="text-xs uppercase tracking-wider text-text-muted mb-3">30-Day Breakdown</h2>
      <div className="bg-bg-elevated border border-border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-text-muted text-xs uppercase tracking-wider border-b border-border">
              {["Day", "Claude Calls", "Tokens", "Cost", "Events"].map(
                (h) => <th key={h} className="py-2 px-4">{h}</th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {daily.map((row) => (
              <tr key={row.day} className="text-text-secondary hover:text-text-primary transition-colors">
                <td className="py-2 px-4 font-mono text-xs">{row.day}</td>
                <td className="py-2 px-4 font-mono text-xs">{row.claude_calls}</td>
                <td className="py-2 px-4 font-mono text-xs">{row.claude_tokens?.toLocaleString()}</td>
                <td className="py-2 px-4 font-mono text-xs text-accent-economy">${row.cost_usd?.toFixed(4)}</td>
                <td className="py-2 px-4 font-mono text-xs">{row.events_mapped}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
