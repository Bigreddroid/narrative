import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api } from "../lib/api.js";

export default function SourceManager() {
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState({});

  useEffect(() => {
    api.get("/admin/sources")
      .then((d) => setSources(d.sources || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const toggleSource = async (id, current) => {
    setToggling((p) => ({ ...p, [id]: true }));
    try {
      await api.patch("/admin/sources/toggle", { source_id: id, is_active: !current });
      setSources((prev) =>
        prev.map((s) => (s.id === id ? { ...s, is_active: !current } : s))
      );
    } finally {
      setToggling((p) => ({ ...p, [id]: false }));
    }
  };

  if (loading) return <p className="text-text-muted text-sm">Loading sources...</p>;

  return (
    <div>
      <h1 className="text-xl font-bold mb-6">Source Manager</h1>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-text-muted text-xs uppercase tracking-wider border-b border-border">
              {["Name", "Category", "Bias", "Method", "Last Scraped", "Errors", "Active"].map(
                (h) => <th key={h} className="py-2 pr-4">{h}</th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {sources.map((s) => (
              <tr key={s.id} className="text-text-secondary hover:text-text-primary transition-colors">
                <td className="py-2 pr-4 font-medium text-text-primary">{s.name}</td>
                <td className="py-2 pr-4 text-xs capitalize">{s.category}</td>
                <td className="py-2 pr-4 text-xs">{s.bias_rating}</td>
                <td className="py-2 pr-4 font-mono text-xs">{s.scrape_method}</td>
                <td className="py-2 pr-4 font-mono text-xs">
                  {s.last_scraped_at
                    ? new Date(s.last_scraped_at).toLocaleTimeString()
                    : "Never"}
                </td>
                <td className="py-2 pr-4 font-mono text-xs" style={{ color: s.scrape_error_count > 0 ? "#FF4B4B" : "#4F4F4F" }}>
                  {s.scrape_error_count}
                </td>
                <td className="py-2">
                  <motion.button
                    onClick={() => toggleSource(s.id, s.is_active)}
                    disabled={toggling[s.id]}
                    className="w-10 h-5 rounded-full relative transition-colors"
                    style={{ backgroundColor: s.is_active ? "#27AE60" : "#21262D" }}
                    whileTap={{ scale: 0.9 }}
                  >
                    <motion.div
                      className="absolute top-0.5 w-4 h-4 bg-white rounded-full shadow"
                      animate={{ left: s.is_active ? "calc(100% - 18px)" : 2 }}
                      transition={{ type: "spring", stiffness: 500, damping: 30 }}
                    />
                  </motion.button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
