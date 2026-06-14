import { getThemeColors } from "./colors.js";

export function getMapColors(isDark = false) {
  const t = getThemeColors(isDark);

  if (isDark) {
    return {
      bg:        "#060809",           // near-pure black — globe floats on void
      ocean:     "#0B1424",           // deep midnight — clearly darker than land
      country0:  "#243040",           // slate-charcoal — readable land mass
      country1:  "#1E2A3A",           // slightly darker slate
      country2:  "#213444",           // medium slate
      border:    "#344E68",           // visible but subtle border
      graticule: "#10192A",           // nearly invisible grid lines
      countryStroke: "none",
      dot:       t.vizAccent,         // cyan #00D4FF
      arc:       t.vizAccent,
    };
  }

  // Light — classic editorial globe: warm tan land, deep-sea blue ocean
  return {
    bg:        "#F5F1EB",            // cream paper
    ocean:     "#6E9AB8",            // classic atlas blue
    country0:  "#C8B090",            // warm tan parchment
    country1:  "#C2AA8A",            // slightly darker tan
    country2:  "#C5AC8C",            // medium tan
    border:    "#8A6E54",            // warm brown border
    graticule: "#5C8DA8",            // subtle blue grid
    countryStroke: "none",
    dot:       t.accent,             // crimson
    arc:       t.accent,
  };
}
