import { useEffect, useState } from "react";
import { api } from "../lib/api.js";

export default function EventReview() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/events/?limit=100")
      .then((d) => setEvents(d.events || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-text-muted text-sm">Loading events...</p>;

  return (
    <div>
      <h1 className="text-xl font-bold mb-6">Event Review</h1>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-text-muted text-xs uppercase tracking-wider border-b border-border">
              {["Title", "Category", "Importance", "Status", "Detected"].map(
                (h) => <th key={h} className="py-2 pr-4">{h}</th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {events.map((e) => (
              <tr key={e.id} className="text-text-secondary hover:text-text-primary transition-colors">
                <td className="py-2 pr-4 max-w-xs">
                  <p className="text-text-primary font-medium truncate">{e.canonical_title}</p>
                  <p className="text-xs text-text-muted truncate">{e.geographic_relevance?.join(", ")}</p>
                </td>
                <td className="py-2 pr-4 text-xs capitalize">{e.category}</td>
                <td className="py-2 pr-4 font-mono text-xs">{Math.round(e.global_importance_score)}</td>
                <td className="py-2 pr-4 text-xs capitalize">{e.current_status}</td>
                <td className="py-2 font-mono text-xs">
                  {e.first_detected_at ? new Date(e.first_detected_at).toLocaleDateString() : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
