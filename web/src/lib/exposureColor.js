// Shared Exposure-Index colour scale (neutral → amber → crimson).
// One source of truth for ExposurePanel and the WorldMap exposure layer.
export function exposureColor(score) {
  if (score >= 70) return "#C80028";
  if (score >= 45) return "#D9663A";
  if (score >= 20) return "#C9A227";
  return "#6B8E6B";
}
