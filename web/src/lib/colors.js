export const CATEGORY_COLORS = {
  geopolitics: "#C84020",
  economics:   "#B07820",
  economy:     "#B07820",
  climate:     "#308050",
  health:      "#2878A8",
  technology:  "#7848C8",
  security:    "#C84020",
  conflict:    "#C80028",
  social:      "#B07820",
  policy:      "#4878A8",
  disinfo:     "#C040A0",
};

export const STATUS_PULSE = {
  developing: "#B07820",
  escalating: "#C80028",
  stable:     "#333333",
  resolved:   "#252525",
};

export const TYPE_COLORS = {
  "VERIFIED FACT":      "#308050",
  "INFERRED MECHANISM": "#B07820",
  "SPECULATIVE EFFECT": "#C84020",
};

export const SEVERITY_COLORS = {
  critical: "#C80028",
  high:     "#C84020",
  medium:   "#B07820",
  low:      "#333333",
};

// Multi-INT discipline palette — 7 distinct hues that read cleanly on the dark
// deck/map. Keyed by the UPPERCASE discipline code from backend/taxonomy.py.
export const DISCIPLINE_COLORS = {
  HUMINT: "#C08A2E",  // amber — human reporting
  SIGINT: "#2E7CC0",  // blue — signals/emitters
  IMINT:  "#8A50C8",  // violet — imagery
  GEOINT: "#2E9E5B",  // green — geospatial
  MASINT: "#C8541F",  // rust — measurement/signature
  FININT: "#B8B020",  // gold — financial
  CYBINT: "#C80028",  // crimson — cyber
};

export function getCategoryColor(category) {
  return CATEGORY_COLORS[category?.toLowerCase()] || "#4A4845";
}

export function getDisciplineColor(discipline) {
  return DISCIPLINE_COLORS[(discipline || "").toUpperCase()] || "#4A4845";
}

export function getNodeSize(importanceScore) {
  const min = 8;
  const max = 28;
  return min + ((importanceScore || 0) / 100) * (max - min);
}
