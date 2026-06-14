// Dual theme tokens — kept in sync with mobile/src/lib/colors.js and the CSS vars in index.css
// Light = paper editorial (customer)
// Dark  = terminal (enterprise primary for desktop views)

export const light = {
  bgBase: "#F5F1EB",
  bgSurface: "#FFFFFF",
  textPrimary: "#1A1A1A",
  textSecondary: "#333333",
  textMuted: "#666666",
  border: "#E5E5E5",
  accent: "#C80028",
  vizAccent: "#C80028", // on light we use crimson for map elements
};

export const dark = {
  bgBase: "#0D1117",
  bgSurface: "#161B22",
  textPrimary: "#E8E8E8",
  textSecondary: "#C8C8C8",
  textMuted: "#8B949E",
  border: "#30363D",
  accent: "#C80028",
  vizAccent: "#00D4FF", // cyan for globe/hotspots on dark (matches mocks)
};

export const CATEGORY_COLORS = {
  geopolitics: "#C84020",
  economics:   "#B07820",
  climate:     "#308050",
  health:      "#2878A8",
  technology:  "#7848C8",
  security:    "#C84020",
  conflict:    "#C80028",
  social:      "#B07820",
  policy:      "#4878A8",
  default:     "#8B949E",
};

export const STATUS_PULSE = {
  developing: "#B07820",
  escalating: "#C80028",
  stable:     "#8B949E",
  resolved:   "#666666",
};

export const TYPE_COLORS = {
  "VERIFIED FACT":      "#308050",
  "INFERRED MECHANISM": "#B07820",
  "SPECULATIVE EFFECT": "#C84020",
};

export const SEVERITY_COLORS = {
  high:   "#C84020",
  medium: "#B07820",
  low:    "#308050",
};

export function getCategoryColor(category) {
  return CATEGORY_COLORS[category?.toLowerCase()] || CATEGORY_COLORS.default;
}

export function getThemeColors(isDark) {
  return isDark ? dark : light;
}

export function getNodeSize(importanceScore) {
  const min = 8;
  const max = 28;
  return min + ((importanceScore || 0) / 100) * (max - min);
}
