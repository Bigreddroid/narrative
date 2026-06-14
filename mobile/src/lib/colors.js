export const light = {
  bgBase: "#F5F1EB", // paper editorial (light mode from mocks)
  bgSurface: "#FFFFFF",
  bgElevated: "#F5F1EB",
  textPrimary: "#1A1A1A", // ink
  textSecondary: "#333333",
  textMuted: "#666666",
  border: "#E5E5E5",
  accent: "#C80028", // crimson brand (consistent across modes)
  accentLight: "#E85A5A",
  vizAccent: "#C80028", // map/globe in light: use brand crimson
  tabBar: "#FFFFFF",
  tabActive: "#C80028",
  tabInactive: "#666666",
};

export const dark = {
  bgBase: "#0D1117", // terminal dark (primary from most mocks)
  bgSurface: "#161B22",
  bgElevated: "#21262D",
  textPrimary: "#E8E8E8",
  textSecondary: "#C8C8C8",
  textMuted: "#8B949E",
  border: "#30363D",
  accent: "#C80028", // crimson brand (pops on dark)
  accentLight: "#E85A5A",
  vizAccent: "#00D4FF", // cyan/teal for globe hotspots & connections (matches multiple mocks)
  tabBar: "#161B22",
  tabActive: "#C80028",
  tabInactive: "#8B949E",
};

// Back-compat default (light editorial). Screens should migrate to getThemeColors.
export const COLORS = light;

export function getThemeColors(isDark) {
  return isDark ? dark : light;
}

// Web / desktop terminal support (for views matching the DESKTOP/TABLET mocks in Mockups/).
// Use the same tokens for any web implementation (CSS vars, Tailwind, styled-components, etc.).
// No full webapp/website — just the design tokens for consistency with mobile + desktop terminal mocks.
export const tokens = { light, dark };

export function getCssCustomProperties(isDark = false) {
  const t = isDark ? dark : light;
  return `
    --bg-base: ${t.bgBase};
    --bg-surface: ${t.bgSurface};
    --text-primary: ${t.textPrimary};
    --text-muted: ${t.textMuted};
    --border: ${t.border};
    --accent: ${t.accent};
    --viz-accent: ${t.vizAccent};
  `;
}

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
