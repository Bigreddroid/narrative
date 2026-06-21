import { useEffect, useState } from "react";
import { api } from "../lib/api.js";

export default function UserStats() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    api.get("/admin/users/stats").then(setStats).catch(console.error);
  }, []);

  if (!stats) return <p className="text-text-muted text-sm">Loading...</p>;

  return (
    <div>
      <h1 className="text-xl font-bold mb-6">User Stats</h1>

      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="bg-bg-elevated border border-border rounded-lg p-4">
          <p className="text-xs text-text-muted uppercase tracking-wider mb-1">Total Users</p>
          <p className="text-2xl font-mono font-bold text-text-primary">{stats.total.toLocaleString()}</p>
        </div>
        {Object.entries(stats.by_tier).map(([tier, count]) => (
          <div key={tier} className="bg-bg-elevated border border-border rounded-lg p-4">
            <p className="text-xs text-text-muted uppercase tracking-wider mb-1">{tier}</p>
            <p className="text-2xl font-mono font-bold text-text-primary">{count.toLocaleString()}</p>
          </div>
        ))}
      </div>

      <h2 className="text-xs uppercase tracking-wider text-text-muted mb-3">Growth</h2>
      <div className="grid grid-cols-3 gap-4">
        {Object.entries(stats.new_users).map(([period, count]) => (
          <div key={period} className="bg-bg-elevated border border-border rounded-lg p-4">
            <p className="text-xs text-text-muted uppercase tracking-wider mb-1">New — {period}</p>
            <p className="text-xl font-mono font-bold text-accent-climate">{count}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
