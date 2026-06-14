import { useState, useEffect } from "react";
import { api } from "../lib/api.js";

const MOCK_NODES = [
  { id: "1", category: "conflict",    current_status: "escalating", importance_score: 91, title: "Red Sea Shipping Attacks",            lat: 14.5,  lng: 42.8  },
  { id: "2", category: "economics",   current_status: "developing", importance_score: 84, title: "Fed Rates Higher for Longer",          lat: 38.9,  lng: -77.0 },
  { id: "3", category: "geopolitics", current_status: "escalating", importance_score: 89, title: "Taiwan Strait Exercises",              lat: 23.7,  lng: 120.9 },
  { id: "4", category: "climate",     current_status: "developing", importance_score: 76, title: "Amazon Drought — Worst in 45 Years",   lat: -3.5,  lng: -60.0 },
  { id: "5", category: "technology",  current_status: "developing", importance_score: 72, title: "EU AI Act Enforcement",                lat: 50.8,  lng: 4.4   },
  { id: "6", category: "health",      current_status: "stable",     importance_score: 68, title: "Mpox Variant PHEIC",                   lat: -4.3,  lng: 15.3  },
  { id: "7", category: "policy",      current_status: "developing", importance_score: 79, title: "US-China EV Tariffs",                  lat: 37.8,  lng: -96.0 },
  { id: "8", category: "security",    current_status: "escalating", importance_score: 83, title: "NATO Infrastructure Cyberattacks",     lat: 52.2,  lng: 21.0  },
  { id: "9", category: "economics",   current_status: "stable",     importance_score: 71, title: "OPEC+ Extends Production Cuts",        lat: 24.7,  lng: 46.7  },
  { id: "10", category: "geopolitics",current_status: "developing", importance_score: 77, title: "Pakistan-India Border Tensions",       lat: 33.7,  lng: 73.0  },
  { id: "11", category: "conflict",   current_status: "escalating", importance_score: 88, title: "Russia-Ukraine Front Line Shifts",     lat: 49.0,  lng: 32.0  },
  { id: "12", category: "economics",  current_status: "developing", importance_score: 74, title: "China Property Sector Debt Crisis",    lat: 31.2,  lng: 121.5 },
  { id: "13", category: "climate",    current_status: "escalating", importance_score: 80, title: "Horn of Africa Flash Floods",          lat: 9.0,   lng: 42.0  },
  { id: "14", category: "security",   current_status: "developing", importance_score: 66, title: "Myanmar Civil Conflict Expansion",     lat: 19.7,  lng: 96.1  },
  { id: "15", category: "policy",     current_status: "stable",     importance_score: 63, title: "Mexico Judicial Reform Crisis",        lat: 19.4,  lng: -99.1 },
];

const MOCK_EDGES = [
  { source_event_id: "1",  target_event_id: "2",  weight: 0.7 },
  { source_event_id: "1",  target_event_id: "9",  weight: 0.6 },
  { source_event_id: "3",  target_event_id: "12", weight: 0.8 },
  { source_event_id: "3",  target_event_id: "7",  weight: 0.65 },
  { source_event_id: "8",  target_event_id: "11", weight: 0.75 },
  { source_event_id: "4",  target_event_id: "13", weight: 0.5 },
  { source_event_id: "2",  target_event_id: "7",  weight: 0.6 },
];

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
    api.get("/graph/world")
      .then((data) => {
        setNodes((data.nodes || []).map(normalizeNode));
        setEdges((data.edges || []).map(normalizeEdge));
      })
      .catch((err) => {
        console.warn("World graph fetch failed, using empty (run backend/seed.py + lean scheduler)", err);
        setNodes([]);
        setEdges([]);
        setError(err);
      })
      .finally(() => setLoading(false));
  }, []);

  return { nodes, edges, loading, error };
}
