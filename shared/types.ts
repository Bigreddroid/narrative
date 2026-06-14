export type EventCategory =
  | "geopolitics"
  | "economy"
  | "climate"
  | "health"
  | "technology"
  | "conflict"
  | "policy";

export type EventStatus = "developing" | "stable" | "resolved" | "escalating";

export type EvidenceType =
  | "VERIFIED FACT"
  | "INFERRED MECHANISM"
  | "SPECULATIVE EFFECT";

export type Severity = "low" | "medium" | "high" | "critical";

export type Confidence = "low" | "medium" | "high";

export interface ChainNode {
  step: number;
  node: string;
  description: string;
  type: EvidenceType;
  evidence: string;
  source: string;
  actors: string[];
}

export interface Impact {
  description: string;
  timeline: string;
  severity: Severity;
  type: EvidenceType;
  evidence: string;
  affected_groups: string[];
}

export interface ConsequenceMap {
  version: number;
  consensus_summary: string;
  disputed_points: string[];
  consequence_chain: ChainNode[];
  direct_impact: Impact;
  indirect_impact: Impact | null;
  prediction_score: number;
  prediction_reasoning: string;
  confidence: Confidence;
  sources_analyzed: string[];
  created_at: string;
}

export interface NarrativeEvent {
  id: string;
  canonical_title: string;
  canonical_summary: string | null;
  category: EventCategory;
  global_importance_score: number;
  current_status: EventStatus;
  affected_sectors: string[];
  affected_professions: string[];
  geographic_relevance: string[];
  geo_centroid_lat: number | null;
  geo_centroid_lng: number | null;
  follow_keywords: string[];
  first_detected_at: string;
  last_updated_at: string | null;
  consequence_map: ConsequenceMap | null;
}

export interface WorldGraphNode {
  id: string;
  title: string;
  category: EventCategory;
  status: EventStatus;
  importance: number;
  lat: number;
  lng: number;
  affected_sectors: string[];
  geographic_relevance: string[];
}

export interface WorldGraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  weight: number;
  shared_sectors: string[];
  shared_geography: string[];
  shared_context: string;
}

export interface User {
  id: string;
  email: string;
  city: string | null;
  country: string | null;
  profession: string | null;
  spending_categories: string[];
  tier: "free" | "paid" | "admin";
  created_at: string;
}
