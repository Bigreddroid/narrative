import { useState, useEffect } from "react";
import { api } from "../lib/api.js";

const MOCK_EVENTS = [
  {
    id: "1", category: "conflict", current_status: "escalating",
    canonical_title: "Red Sea Shipping Corridor Under Sustained Attack",
    canonical_summary: "Houthi missile and drone strikes on commercial vessels have reduced Red Sea cargo transit by 40%, forcing rerouting around the Cape of Good Hope and adding 10-14 days to Asia-Europe shipping times.",
    importance_score: 91, geography: ["Yemen", "Red Sea", "Gulf of Aden"],
    source_bias: { left: 22, center: 60, right: 18 },
  },
  {
    id: "2", category: "economics", current_status: "developing",
    canonical_title: "Fed Signals Rates Higher for Longer as Inflation Stalls at 3.4%",
    canonical_summary: "The Federal Reserve held rates at 5.25-5.5% and revised down its 2024 cut expectations from three to one. Mortgage rates remain above 7%, suppressing housing starts and consumer credit appetite.",
    importance_score: 84, geography: ["United States"],
    source_bias: { left: 38, center: 40, right: 22 },
  },
  {
    id: "3", category: "geopolitics", current_status: "escalating",
    canonical_title: "Taiwan Strait Military Exercises Intensify Ahead of Leadership Transition",
    canonical_summary: "PLA Eastern Theater Command conducted live-fire drills encircling Taiwan. Semiconductor supply chains at risk — TSMC accounts for 92% of advanced chips below 5nm globally.",
    importance_score: 89, geography: ["Taiwan", "China", "South China Sea"],
    source_bias: { left: 28, center: 50, right: 22 },
  },
  {
    id: "4", category: "climate", current_status: "developing",
    canonical_title: "Amazon Basin Records Worst Drought in 45 Years",
    canonical_summary: "River levels 60% below seasonal average. Brazilian soy harvest projected down 38%. Global commodity prices for feed grains rising — downstream pressure on meat, dairy, and processed food sectors worldwide.",
    importance_score: 76, geography: ["Brazil", "Amazon Basin", "South America"],
    source_bias: { left: 55, center: 32, right: 13 },
  },
  {
    id: "5", category: "technology", current_status: "developing",
    canonical_title: "EU AI Act Enforcement Begins — Compliance Wave Hits Tech Sector",
    canonical_summary: "Major AI systems classified as high-risk must comply with transparency and audit requirements by August. US tech firms face fines up to €35M or 7% of global turnover for non-compliance.",
    importance_score: 72, geography: ["European Union", "Global"],
    source_bias: { left: 42, center: 44, right: 14 },
  },
  {
    id: "6", category: "health", current_status: "stable",
    canonical_title: "WHO Declares Mpox Variant PHEIC — Travel Advisories Issued",
    canonical_summary: "A new clade of mpox with higher transmissibility prompted a Public Health Emergency of International Concern. 14 countries issued travel advisories; vaccine supply constrained to high-income nations.",
    importance_score: 68, geography: ["DRC", "Central Africa", "Global"],
    source_bias: { left: 18, center: 64, right: 18 },
  },
  {
    id: "7", category: "policy", current_status: "developing",
    canonical_title: "US Tariff Package on Chinese EVs and Solar Panels Takes Effect",
    canonical_summary: "100% tariffs on Chinese EVs and 50% on solar panels reshape clean energy supply chains. Domestic US production costs for solar installations projected to rise 18-24% over 18 months.",
    importance_score: 79, geography: ["United States", "China"],
    source_bias: { left: 20, center: 34, right: 46 },
  },
  {
    id: "8", category: "security", current_status: "escalating",
    canonical_title: "Critical Infrastructure Cyberattacks Surge Across NATO Members",
    canonical_summary: "Coordinated intrusions targeting power grids and water systems in Poland, Germany, and the Baltics attributed to state-sponsored groups. NATO Article 5 cyber threshold debate intensifies.",
    importance_score: 83, geography: ["NATO", "Eastern Europe", "Baltic States"],
    source_bias: { left: 25, center: 52, right: 23 },
  },
  {
    id: "9", category: "economics", current_status: "stable",
    canonical_title: "OPEC+ Extends Production Cuts Through Q3, Brent Holds Above $85",
    canonical_summary: "Saudi Arabia and Russia extended voluntary cuts of 1.65M barrels/day. Fuel costs remain elevated globally — aviation and logistics sectors absorbing margin compression.",
    importance_score: 71, geography: ["Saudi Arabia", "Russia", "Global"],
    source_bias: { left: 14, center: 46, right: 40 },
  },
  {
    id: "10", category: "geopolitics", current_status: "developing",
    canonical_title: "Pakistan-India Border Tensions Spike After Kashmir Incident",
    canonical_summary: "Cross-border exchange of fire following a militant attack in Jammu. Both sides recalled ambassadors. Pakistani nuclear doctrine ambiguity raises regional escalation risk assessment to elevated.",
    importance_score: 77, geography: ["Pakistan", "India", "Kashmir"],
    source_bias: { left: 30, center: 44, right: 26 },
  },
];

function normalizeEvent(e) {
  return {
    ...e,
    importance_score: e.importance_score ?? e.global_importance_score ?? 0,
    geography:        e.geography ?? e.geographic_relevance ?? [],
  };
}

export function useEventFeed({ category = null, status = null, limit = 50 } = {}) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const q = new URLSearchParams();
    if (category) q.set("category", category);
    if (status)   q.set("status", status);
    q.set("limit", limit);

    setLoading(true);
    // Use the real /feed endpoint (like mobile) which joins consequence maps for impact/prediction
    api.get(`/feed?${q}`)
      .then((data) => {
        const raw = data.feed || [];
        setEvents(raw.map(normalizeEvent));
      })
      .catch((err) => {
        console.warn("Real feed failed, no mock fallback (seed the DB and run lean scheduler)", err);
        setEvents([]);
        setError(err);
      })
      .finally(() => setLoading(false));
  }, [category, status, limit]);

  return { events, loading, error };
}
