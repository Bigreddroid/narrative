export const COLORS = {
  bgBase: "#0D1117",
  bgSurface: "#161B22",
  bgElevated: "#1C2128",
  textPrimary: "#F0F6FC",
  textSecondary: "#C9D1D9",
  textMuted: "#8B949E",
  border: "#30363D",
  accent: "#F5A623",
};

export const CATEGORY_COLORS = {
  geopolitics: "#E74C3C",
  economics: "#3498DB",
  climate: "#27AE60",
  technology: "#9B59B6",
  health: "#1ABC9C",
  social: "#F39C12",
  security: "#E67E22",
  default: "#8B949E",
};

export function getCategoryColor(category) {
  return CATEGORY_COLORS[category?.toLowerCase()] || CATEGORY_COLORS.default;
}

export const TYPE_COLORS = {
  "VERIFIED FACT": "#27AE60",
  "INFERRED MECHANISM": "#F5A623",
  "SPECULATIVE EFFECT": "#8B5CF6",
};

export const STATUS_COLORS = {
  developing: "#F5A623",
  escalating: "#E74C3C",
  stable: "#27AE60",
  resolved: "#8B949E",
};
