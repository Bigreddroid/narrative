// Tier definitions — single source of truth for access rules

export const TIERS = {
  free:         { rank: 0, label: "Free",         color: "#6A6A60" },
  pro:          { rank: 1, label: "Pro",           color: "#2D7DD2" },
  intelligence: { rank: 2, label: "Intelligence",  color: "#C80028" },
  enterprise:   { rank: 3, label: "Enterprise",    color: "#B07020" },
  // Stripe's single "Full Access" plan sets tier='paid'. The backend grants it
  // full (non-free) access, so it's enterprise-equivalent here. Without this,
  // TIERS['paid'] is undefined and canAccess falls back to free — locking
  // paying customers out of every gated feature in the UI.
  paid:         { rank: 3, label: "Full Access",   color: "#B07020" },
  admin:        { rank: 4, label: "Admin",         color: "#C80028" },
};

// Feature access map: minimum tier rank required
export const ACCESS = {
  // Free
  fullFeed:            0,
  liveNews:            0,  // free taster (2 channels); backend widens set by tier
  osint:               0,  // free taster of the OSINT tool catalog; backend widens by tier
  // Pro
  eventGraph:          1,
  worldRegions:        1,
  chainArcs:           1,
  articleSources:      1,
  biasIndicators:      1,
  predictions:         1,
  effects:             1,
  osintInvestigate:    1,  // entity-aware OSINT pivots (templated lookups)
  // Intelligence
  apiAccess:           2,
  realTimeAlerts:      2,
  export:              2,
  advancedBias:        2,
  historicalData:      2,
  // Enterprise
  teamSeats:           3,
  webhooks:            3,
  customAlerts:        3,
  sso:                 3,
  dedicatedSupport:    3,
  whiteLabel:          3,
  scheduledReports:    3,
};

export function canAccess(userTier, feature) {
  const tier = TIERS[userTier] || TIERS.free;
  return tier.rank >= (ACCESS[feature] ?? 99);
}

// Dev test accounts — email → user object
export const DEV_ACCOUNTS = {
  "free@narrative.dev": {
    id: "dev-free-001",
    name: "Free Tester",
    email: "free@narrative.dev",
    tier: "free",
  },
  "pro@narrative.dev": {
    id: "dev-pro-001",
    name: "Pro Tester",
    email: "pro@narrative.dev",
    tier: "pro",
  },
  "intel@narrative.dev": {
    id: "dev-intel-001",
    name: "Intelligence Tester",
    email: "intel@narrative.dev",
    tier: "intelligence",
  },
  "enterprise@narrative.dev": {
    id: "dev-enterprise-001",
    name: "Enterprise Tester",
    email: "enterprise@narrative.dev",
    tier: "enterprise",
  },
  "admin@narrative.dev": {
    id: "dev-admin-001",
    name: "Admin",
    email: "admin@narrative.dev",
    tier: "admin",
  },
};

