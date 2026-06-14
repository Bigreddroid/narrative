import { useEffect, useState } from "react";
import { api } from "../lib/api.js";

const STATUS_COLOR = {
  running: "#27AE60",
  idle: "#8B949E",
  error: "#FF4B4B",
  paused: "#F5A623",
};

export default function PipelineMonitor() {
  const [metrics, setMetrics] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/admin/pipeline/metrics")
      .then((d) => setMetrics(d.metrics || []))
      .catch(console.error)
      .finally(() => setLoading(false));

    const t = setInterval(() => {
      api.get("/admin/pipeline/metrics")
        .then((d) => setMetrics(d.metrics || []))
        .catch(console.error);
    }, 10000);
    return () => clearInterval(t);
  }, []);

  if (loading) return <p className="text-text-muted text-sm">Loading...</p>;

  return (
    <div>
      <h1 className="text-xl font-bold mb-6">Pipeline Monitor</h1>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-text-muted text-xs uppercase tracking-wider border-b border-border">
              {["Worker", "Run At", "Scraped", "Embedded", "Mapped", "Claude $", "Errors", "Duration"].map(
                (h) => <th key={h} className="py-2 pr-4">{h}</th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {metrics.slice(0, 100).map((m, i) => (
              <tr key={i} className="text-text-secondary hover:text-text-primary transition-colors">
                <td className="py-2 pr-4 font-mono text-xs text-text-primary">{m.worker_name}</td>
                <td className="py-2 pr-4 font-mono text-xs">
                  {new Date(m.run_at).toLocaleTimeString()}
                </td>
                <td className="py-2 pr-4 font-mono text-xs">{m.articles_scraped || 0}</td>
                <td className="py-2 pr-4 font-mono text-xs">{m.articles_embedded || 0}</td>
                <td className="py-2 pr-4 font-mono text-xs">{m.events_mapped || 0}</td>
                <td className="py-2 pr-4 font-mono text-xs text-type-speculative">
                  ${(m.claude_cost_usd || 0).toFixed(4)}
                </td>
                <td className="py-2 pr-4 font-mono text-xs" style={{ color: m.errors > 0 ? "#FF4B4B" : "#4F4F4F" }}>
                  {m.errors || 0}
                </td>
                <td className="py-2 font-mono text-xs">{m.duration_seconds?.toFixed(1)}s</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
