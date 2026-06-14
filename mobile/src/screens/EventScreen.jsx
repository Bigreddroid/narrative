import { useEffect, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  Image,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
  useColorScheme,
  Dimensions,
} from "react-native";
import { useRoute, useNavigation } from "@react-navigation/native";
import { getThemeColors, getCategoryColor, STATUS_COLORS } from "../lib/colors.js";
import { api } from "../lib/api.js";
import MobileChainNode from "../components/MobileChainNode.jsx";
import MobileImpactCard from "../components/MobileImpactCard.jsx";
import MobilePredictionMeter from "../components/MobilePredictionMeter.jsx";
import MobileGraph from "../components/MobileGraph.jsx";

const { width } = Dimensions.get("window");

const CATEGORY_EMOJI = {
  geopolitics: "🌍",
  economics:   "📈",
  climate:     "🌿",
  health:      "🏥",
  technology:  "💻",
  security:    "🛡️",
  social:      "🗣️",
  default:     "📰",
};

function biasInfo(score) {
  if (score == null) return { label: "Center", pct: 87 };
  const abs = Math.abs(score);
  const label = score < -0.3 ? "Left Lean" : score > 0.3 ? "Right Lean" : "Center";
  const pct = Math.round((1 - Math.min(abs, 1)) * 100);
  return { label, pct };
}

export default function EventScreen() {
  const route = useRoute();
  const navigation = useNavigation();
  const { eventId } = route.params;

  const [event, setEvent] = useState(null);
  const [graph, setGraph] = useState(null);
  const [following, setFollowing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [showGraph, setShowGraph] = useState(false);

  useEffect(() => {
    Promise.all([
      api.get(`/feed`).then((res) => {
        const found = (res.feed || []).find(
          (e) => e.id === eventId || String(e.id) === String(eventId)
        );
        return found || { id: eventId, title: "Event", category: "unknown", current_status: "developing" };
      }),
      api.get(`/graph/event/${eventId}`).catch(() => ({ root: null, connected_events: [], connections: [] })),
    ]).then(([ev, gr]) => {
      const normalizedEv = {
        ...ev,
        title: ev.canonical_title || ev.title,
        status: ev.current_status || ev.status,
        consequence_map: ev.consequence_map || null,
      };
      const normalizedGraph = gr ? {
        nodes: gr.nodes || (gr.connected_events || []).map((e) => ({
          id: e.id,
          category: e.category,
          title: e.title || e.canonical_title,
        })),
        edges: gr.edges || (gr.connections || []).map((c) => ({
          source_event_id: c.source || c.source_event_id || c.event_a_id,
          target_event_id: c.target || c.target_event_id || c.event_b_id,
        })),
      } : { nodes: [], edges: [] };
      setEvent(normalizedEv);
      setGraph(normalizedGraph);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [eventId]);

  const handleFollow = async () => {
    try {
      if (following) {
        await api.delete(`/follows/${eventId}`);
        setFollowing(false);
      } else {
        await api.post("/follows", { event_id: eventId });
        setFollowing(true);
      }
    } catch (err) {
      Alert.alert("Error", err.message);
    }
  };

  const scheme = useColorScheme();
  const isDark = scheme === "dark";
  const C = getThemeColors(isDark);

  if (loading) {
    return (
      <View style={[styles.center, { backgroundColor: C.bgBase }]}>
        <ActivityIndicator color={C.accent} size="large" />
      </View>
    );
  }

  if (!event) {
    return (
      <View style={[styles.center, { backgroundColor: C.bgBase }]}>
        <Text style={{ color: C.textMuted }}>Event not found.</Text>
      </View>
    );
  }

  const catColor = getCategoryColor(event.category);
  const map = event.consequence_map;
  const chain = map?.consequence_chain || [];
  const directImpacts = map?.direct_impact || [];
  const predictions = map?.predictions || [];
  const emoji = CATEGORY_EMOJI[event.category] || CATEGORY_EMOJI.default;
  const { label: biasLabel, pct: biasPct } = biasInfo(event.source_bias ?? event.bias_score);
  const readTime = Math.max(2, Math.ceil((event.summary?.length || 200) / 400));

  return (
    <View style={[styles.container, { backgroundColor: C.bgBase }]}>
      <ScrollView
        style={{ flex: 1 }}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={{ paddingBottom: 90 }}
      >
        {/* ── Hero Image ── */}
        <View style={styles.heroWrapper}>
          {event.thumbnail_url ? (
            <Image
              source={{ uri: event.thumbnail_url }}
              style={styles.heroImage}
              resizeMode="cover"
            />
          ) : (
            <View style={[styles.heroPlaceholder, { backgroundColor: catColor + "28" }]}>
              <Text style={styles.heroEmoji}>{emoji}</Text>
            </View>
          )}

          {/* < Premium News pill */}
          <TouchableOpacity
            style={[styles.premiumPill, { backgroundColor: C.accent }]}
            onPress={() => navigation.goBack()}
            activeOpacity={0.85}
          >
            <Text style={styles.premiumPillText}>‹  Premium News</Text>
          </TouchableOpacity>

          {/* Follow star */}
          <TouchableOpacity
            style={styles.followBtn}
            onPress={handleFollow}
          >
            <Text style={[styles.followText, { color: following ? C.accent : "#fff" }]}>
              {following ? "★" : "☆"}
            </Text>
          </TouchableOpacity>

          {/* Priority / importance badge */}
          {event.global_importance_score != null && (
            <View style={[styles.priorityBadge, { borderColor: isDark ? "#fff" : "#fff" }]}>
              <Text style={styles.priorityNum}>
                {Math.round(event.global_importance_score * 9) + 1}
              </Text>
            </View>
          )}
        </View>

        {/* ── Content ── */}
        <View style={styles.content}>
          {/* Status chip */}
          <View style={[styles.categoryChip, { backgroundColor: catColor + "22" }]}>
            <View style={[styles.statusDot, { backgroundColor: STATUS_COLORS[event.status] || C.textMuted }]} />
            <Text style={[styles.categoryLabel, { color: catColor }]}>
              {event.category?.toUpperCase()}
            </Text>
          </View>

          {/* Title */}
          <Text style={[styles.title, { color: C.textPrimary }]}>{event.title}</Text>

          {/* Bias line */}
          <Text style={[styles.biasLine, { color: isDark ? C.textMuted : C.accent }]}>
            {biasLabel} · {biasPct}% {biasLabel}
          </Text>

          {/* Summary */}
          {event.summary ? (
            <Text style={[styles.summary, { color: C.textSecondary }]}>{event.summary}</Text>
          ) : null}

          {/* ── How this affects you ── */}
          <View style={[styles.affectsBox, { backgroundColor: C.accent + "18", borderColor: C.accent }]}>
            <Text style={[styles.affectsTitle, { color: C.accent }]}>How this affects you</Text>
            <Text style={[styles.affectsBody, { color: C.textSecondary }]}>
              {event.personal_impact
                || directImpacts[0]?.description
                || `This ${event.category || "global"} event may directly impact policies, markets, and daily life in affected regions.`}
            </Text>
          </View>

          {/* ── Predictions ── */}
          {predictions.length > 0 && (
            <View style={[styles.predictionsRow, { backgroundColor: C.bgSurface, borderColor: C.border }]}>
              {predictions.map((pred, i) => (
                <MobilePredictionMeter key={i} confidence={pred.confidence} label={pred.label} colors={C} />
              ))}
            </View>
          )}

          {/* ── Consequence chain ── */}
          {map?.is_paywalled ? (
            <View style={[styles.paywallBox, { backgroundColor: C.bgSurface, borderColor: C.accent }]}>
              <Text style={[styles.paywallTitle, { color: C.textPrimary }]}>Full chain is paid-only</Text>
              <Text style={[styles.paywallSub, { color: C.textMuted }]}>
                Upgrade to unlock the complete consequence chain.
              </Text>
            </View>
          ) : chain.length > 0 ? (
            <>
              <Text style={[styles.sectionLabel, { color: C.textMuted }]}>CONSEQUENCE CHAIN</Text>
              {chain.map((node, i) => <MobileChainNode key={i} node={node} depth={0} colors={C} />)}
            </>
          ) : directImpacts.length > 0 ? (
            <>
              <Text style={[styles.sectionLabel, { color: C.textMuted }]}>DIRECT IMPACTS</Text>
              {directImpacts.map((imp, i) => <MobileImpactCard key={i} impact={imp} colors={C} />)}
            </>
          ) : null}

          {/* ── Connection Graph (collapsed by default) ── */}
          {graph && graph.nodes.length > 0 && (
            <View style={{ marginTop: 8 }}>
              <TouchableOpacity
                style={[styles.graphToggle, { borderColor: C.border }]}
                onPress={() => setShowGraph((v) => !v)}
              >
                <Text style={[styles.graphToggleText, { color: C.textMuted }]}>
                  {showGraph ? "Hide" : "Show"} connected events ({graph.nodes.length})
                </Text>
              </TouchableOpacity>
              {showGraph && (
                <>
                  <MobileGraph
                    nodes={graph.nodes}
                    edges={graph.edges}
                    colors={C}
                    onNodePress={(node) => {
                      if (node.id !== eventId) navigation.push("Event", { eventId: node.id });
                    }}
                  />
                  <Text style={[styles.graphHint, { color: C.textMuted }]}>Tap a node to explore that event.</Text>
                </>
              )}
            </View>
          )}
        </View>
      </ScrollView>

      {/* ── Bottom Action Bar (reference style) */}
      <View style={[styles.actionBar, { backgroundColor: C.bgSurface, borderTopColor: C.border }]}>
        <TouchableOpacity 
          style={[styles.actionPrimary, { backgroundColor: C.accent }]}
          onPress={() => setShowGraph(true)}
        >
          <Text style={styles.actionPrimaryText}>Full Analysis</Text>
        </TouchableOpacity>
        <TouchableOpacity 
          style={[styles.actionSecondary, { borderColor: C.border }]}
          onPress={() => Alert.alert("Saved", "Event saved to your list (demo)")}
        >
          <Text style={[styles.actionSecondaryText, { color: C.textSecondary }]}>Save</Text>
        </TouchableOpacity>
        <TouchableOpacity 
          style={[styles.actionSecondary, { borderColor: C.border }]}
          onPress={() => Alert.alert("Share", "Share link copied (demo)")}
        >
          <Text style={[styles.actionSecondaryText, { color: C.textSecondary }]}>Share</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const HERO_H = 220;

const styles = StyleSheet.create({
  container: { flex: 1 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },

  // Hero (strong photo like reference cards)
  heroWrapper: {
    marginHorizontal: 14,
    marginTop: 12,
    borderRadius: 16,
    overflow: "hidden",
    height: HERO_H,
  },
  heroImage: {
    width: "100%",
    height: HERO_H,
  },
  heroPlaceholder: {
    width: "100%",
    height: HERO_H,
    alignItems: "center",
    justifyContent: "center",
  },
  heroEmoji: { fontSize: 56 },

  // Premium News pill overlay
  premiumPill: {
    position: "absolute",
    top: 14,
    left: 14,
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 7,
  },
  premiumPillText: {
    color: "#fff",
    fontSize: 14,
    fontWeight: "700",
    letterSpacing: 0.2,
  },

  // Follow star
  followBtn: {
    position: "absolute",
    top: 14,
    right: 14,
  },
  followText: { fontSize: 22 },

  // Priority circle
  priorityBadge: {
    position: "absolute",
    bottom: 14,
    left: 14,
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 2,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(0,0,0,0.45)",
  },
  priorityNum: { color: "#fff", fontSize: 14, fontWeight: "700" },

  // Content block
  content: { paddingHorizontal: 16, paddingTop: 20 },

  categoryChip: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 3,
    gap: 5,
    marginBottom: 10,
  },
  statusDot: { width: 6, height: 6, borderRadius: 3 },
  categoryLabel: { fontSize: 9, fontWeight: "700", letterSpacing: 0.9 },

  title: {
    fontSize: 26,
    fontWeight: "800",
    lineHeight: 34,
    marginBottom: 8,
  },
  biasLine: {
    fontSize: 14,
    fontWeight: "500",
    marginBottom: 12,
  },
  summary: {
    fontSize: 15,
    lineHeight: 23,
    marginBottom: 20,
  },

  // How this affects you (reference visual treatment)
  affectsBox: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    marginBottom: 16,
    backgroundColor: "rgba(200,0,40,0.06)",
  },
  affectsTitle: {
    fontSize: 14,
    fontWeight: "700",
    marginBottom: 6,
    color: "#C80028",
  },
  affectsBody: {
    fontSize: 13,
    lineHeight: 19,
  },

  // Predictions
  predictionsRow: {
    flexDirection: "row",
    justifyContent: "space-around",
    marginBottom: 20,
    paddingVertical: 10,
    borderRadius: 12,
    borderWidth: 1,
  },

  // Paywall
  paywallBox: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 20,
    alignItems: "center",
    gap: 8,
    marginBottom: 16,
  },
  paywallTitle: { fontSize: 15, fontWeight: "600" },
  paywallSub: { fontSize: 13, textAlign: "center", lineHeight: 18 },

  sectionLabel: {
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 1,
    marginBottom: 10,
  },

  // Graph toggle
  graphToggle: {
    borderWidth: 1,
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 16,
    alignItems: "center",
    marginBottom: 8,
  },
  graphToggleText: { fontSize: 13, fontWeight: "500" },
  graphHint: { textAlign: "center", fontSize: 11, paddingVertical: 8 },

  // Bottom action bar (reference pill buttons, prominent crimson primary)
  actionBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderTopWidth: 1,
    gap: 8,
  },
  actionPrimary: {
    borderRadius: 999,
    paddingVertical: 10,
    paddingHorizontal: 18,
    flex: 1,
    alignItems: "center",
  },
  actionPrimaryText: { color: "#fff", fontSize: 13, fontWeight: "700" },
  actionSecondary: {
    borderRadius: 999,
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderWidth: 1,
    alignItems: "center",
  },
  actionSecondaryText: { fontSize: 12, fontWeight: "600" },
});
