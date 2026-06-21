import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api } from "../lib/api.js";

export default function HallucinationFlags() {
  const [flagged, setFlagged] = useState([]);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState({});

  useEffect(() => {
    // Fetch suppressed maps — these are the flagged outputs
    api.get("/events/?limit=100")
      .then((d) => {
        // Filter to those with suppressed maps
        setFlagged(
          (d.events || []).filter((e) => e.is_suppressed)
        );
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleAction = async (eventId, action) => {
    setActing((p) => ({ ...p, [eventId]: action }));
    try {
      if (action === "suppress") {
        await api.post("/admin/events/override", {
          event_id: eventId,
          suppress_map: true,
          suppression_reason: "Admin: confirmed hallucination",
        });
        setFlagged((prev) => prev.filter((f) => f.id !== eventId));
      } else if (action === "ok") {
        await api.post("/admin/events/override", {
          event_id: eventId,
          suppress_map: false,
        });
        setFlagged((prev) => prev.filter((f) => f.id !== eventId));
      }
    } finally {
      setActing((p) => ({ ...p, [eventId]: null }));
    }
  };

  if (loading) return <p className="text-text-muted text-sm">Loading...</p>;

  return (
    <div>
      <h1 className="text-xl font-bold mb-2">Hallucination Flags</h1>
      <p className="text-sm text-text-secondary mb-6">
        Consequence maps flagged for review. Suppress to hide from users or mark OK to restore.
      </p>

      {flagged.length === 0 && (
        <div className="text-center py-16 text-text-muted text-sm">
          No flagged outputs — pipeline is clean.
        </div>
      )}

      <div className="space-y-3">
        {flagged.map((event) => (
          <motion.div
            key={event.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-bg-elevated border border-border rounded-lg p-4"
            style={{ borderLeftColor: "#FF4B4B", borderLeftWidth: 3 }}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <p className="text-sm font-semibold text-text-primary mb-1">
                  {event.canonical_title}
                </p>
                <div className="flex items-center gap-2 text-2xs text-text-muted">
                  <span className="capitalize">{event.category}</span>
                  <span>·</span>
                  <span>Importance: {Math.round(event.global_importance_score)}</span>
                  <span>·</span>
                  <span>{event.first_detected_at ? new Date(event.first_detected_at).toLocaleDateString() : "—"}</span>
                </div>
              </div>

              <div className="flex items-center gap-2 flex-shrink-0">
                <button
                  onClick={() => handleAction(event.id, "ok")}
                  disabled={!!acting[event.id]}
                  className="text-xs px-3 py-1.5 rounded-lg border border-border text-type-verified hover:bg-bg-surface transition-colors disabled:opacity-50"
                >
                  Mark OK
                </button>
                <button
                  onClick={() => handleAction(event.id, "suppress")}
                  disabled={!!acting[event.id]}
                  className="text-xs px-3 py-1.5 rounded-lg border border-border text-severity-critical hover:bg-bg-surface transition-colors disabled:opacity-50"
                >
                  Suppress
                </button>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
