// Source-level political lean scores
// Based on AllSides + Media Bias Fact Check research
// { left, center, right } — must sum to 100
export const SOURCE_BIAS = {
  // Centre / wire services
  "Reuters":           { left: 12, center: 76, right: 12 },
  "AP":                { left: 14, center: 72, right: 14 },
  "AFP":               { left: 15, center: 70, right: 15 },

  // Centre-left
  "Bloomberg":         { left: 32, center: 52, right: 16 },
  "Financial Times":   { left: 28, center: 54, right: 18 },
  "BBC":               { left: 30, center: 52, right: 18 },
  "Guardian":          { left: 62, center: 28, right: 10 },
  "New York Times":    { left: 55, center: 34, right: 11 },
  "Washington Post":   { left: 52, center: 36, right: 12 },
  "NPR":               { left: 48, center: 42, right: 10 },
  "The Economist":     { left: 30, center: 55, right: 15 },
  "Al Jazeera":        { left: 40, center: 42, right: 18 },

  // Centre-right
  "WSJ":               { left: 16, center: 44, right: 40 },
  "Politico":          { left: 32, center: 48, right: 20 },
  "Axios":             { left: 26, center: 54, right: 20 },
  "Times of India":    { left: 18, center: 52, right: 30 },
  "NDTV":              { left: 30, center: 48, right: 22 },

  // Right / right-leaning
  "Fox News":          { left:  6, center: 14, right: 80 },
  "Daily Mail":        { left:  8, center: 22, right: 70 },
  "NY Post":           { left:  8, center: 18, right: 74 },
  "Breitbart":         { left:  4, center:  8, right: 88 },
  "Daily Wire":        { left:  5, center: 10, right: 85 },
};

// Calculate aggregate bias for an array of articles
// Each article: { source, bias_score? }
// Returns { left, center, right } percentages
export function calcEventBias(articles = []) {
  if (!articles.length) return null;

  let totalLeft = 0, totalCenter = 0, totalRight = 0, count = 0;

  articles.forEach(a => {
    // Use pre-computed article bias if available, else fall back to source lookup
    const score = a.bias_score || SOURCE_BIAS[a.source];
    if (!score) return;
    totalLeft   += score.left;
    totalCenter += score.center;
    totalRight  += score.right;
    count++;
  });

  if (!count) return null;

  return {
    left:   Math.round(totalLeft   / count),
    center: Math.round(totalCenter / count),
    right:  Math.round(totalRight  / count),
  };
}

// Dominant lean label + colour
export function biasLabel(bias) {
  if (!bias) return null;
  if (bias.left > bias.right + 15)   return { label: "Left-leaning",   color: "#2D7DD2" };
  if (bias.right > bias.left + 15)   return { label: "Right-leaning",  color: "#DC7020" };
  if (bias.center >= 50)             return { label: "Centre",          color: "#6B6B5A" };
  if (bias.left > bias.right)        return { label: "Centre-left",     color: "#4A8FC0" };
  if (bias.right > bias.left)        return { label: "Centre-right",    color: "#C07040" };
  return                                    { label: "Balanced",         color: "#6B6B5A" };
}

export const BIAS_COLORS = {
  left:   "#2D7DD2",
  center: "#6B6B5A",
  right:  "#DC7020",
};
