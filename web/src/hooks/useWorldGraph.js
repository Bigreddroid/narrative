import { useState, useEffect } from "react";
import { api } from "../lib/api.js";
import { MOCK_NODES, MOCK_EDGES } from "../lib/mockData.js";
import { DEMO_MODE } from "../lib/demoMode.js";

function normalizeNode(n) {
  return {
    ...n,
    current_status:   n.current_status ?? n.status,
    importance_score: n.importance_score ?? n.importance ?? 0,
  };
}

function normalizeEdge(e) {
  return {
    ...e,
    source_event_id: e.source_event_id ?? e.source,
    target_event_id: e.target_event_id ?? e.target,
  };
}

export function useWorldGraph() {
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Graph build runs server-side over the whole event graph — like /exposure
    // it can exceed the default 3.5s fail-fast on a busy backend; give it room.
    api.get("/graph/world", { timeoutMs: 20000 })
      .then((data) => {
        setNodes((data.nodes || []).map(normalizeNode));
        setEdges((data.edges || []).map(normalizeEdge));
      })
      .catch((err) => {
        if (DEMO_MODE) {
          setNodes(MOCK_NODES.map(normalizeNode));
          setEdges(MOCK_EDGES.map(normalizeEdge));
          return;
        }
        // Real-only: empty map + error instead of fabricated nodes.
        setNodes([]);
        setEdges([]);
        setError(err);
      })
      .finally(() => setLoading(false));
  }, []);

  return { nodes, edges, loading, error };
}
