import { useState } from "react";
import { motion } from "framer-motion";
import { api } from "../lib/api.js";

const WORKERS = [
  "scrape_worker", "embed_worker", "cluster_worker", "importance_worker",
  "mapping_worker", "graph_worker", "evolution_worker", "feed_worker",
  "alert_worker", "outcome_worker", "archive_worker",
];

export default function WorkerControls() {
  const [triggering, setTriggering] = useState({});
  const [results, setResults] = useState({});

  const trigger = async (worker) => {
    setTriggering((p) => ({ ...p, [worker]: true }));
    try {
      const result = await api.post("/admin/workers/trigger", { worker_name: worker });
      setResults((p) => ({ ...p, [worker]: result }));
    } catch (err) {
      setResults((p) => ({ ...p, [worker]: { error: err.message } }));
    } finally {
      setTriggering((p) => ({ ...p, [worker]: false }));
    }
  };

  return (
    <div>
      <h1 className="text-xl font-bold mb-2">Worker Controls</h1>
      <p className="text-sm text-text-secondary mb-6">Manually trigger any worker. All actions are logged.</p>

      <div className="grid grid-cols-2 gap-3">
        {WORKERS.map((worker) => {
          const result = results[worker];
          return (
            <div key={worker} className="bg-bg-elevated border border-border rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono text-xs text-text-primary">{worker}</span>
                <motion.button
                  onClick={() => trigger(worker)}
                  disabled={triggering[worker]}
                  className="text-xs px-3 py-1.5 rounded-lg font-medium disabled:opacity-50 transition-colors"
                  style={{ backgroundColor: "#161B22", color: "#F0F6FC", border: "1px solid #21262D" }}
                  whileTap={{ scale: 0.96 }}
                >
                  {triggering[worker] ? "Running..." : "Trigger"}
                </motion.button>
              </div>

              {result && (
                <div className="text-2xs font-mono">
                  {result.error ? (
                    <span className="text-severity-critical">{result.error}</span>
                  ) : (
                    <span className="text-type-verified">Enqueued: {result.job_id?.slice(0, 8)}</span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
