export const MAP_COLORS = {
  light: {
    bg:       "#C8D8E4",
    ocean:    "#C8D8E4",
    country0: "#D8E2E8",
    country1: "#CDDAE3",
    country2: "#D2DDE7",
    border:   "#9AAFBC",
    graticule:"#B8CDD8",
    countryStroke: "none",
  },
  dark: {
    bg:       "#0E1520",
    ocean:    "#0E1520",
    country0: "#1C2535",
    country1: "#18202E",
    country2: "#1A2231",
    border:   "#2C3A50",
    graticule:"#151E2C",
    countryStroke: "none",
  },
};

export function getMapColors(_isDark) {
  return MAP_COLORS.dark;
}
