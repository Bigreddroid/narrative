import { useEffect, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
} from "react-native";
import { useRoute, useNavigation } from "@react-navigation/native";
import { COLORS, getCategoryColor, STATUS_COLORS, TYPE_COLORS } from "../lib/colors.js";
import { api } from "../lib/api.js";
import MobileGraph from "../components/MobileGraph.jsx";
import MobileChainNode from "../components/MobileChainNode.jsx";
import MobileImpactCard from "../components/MobileImpactCard.jsx";
import MobilePredictionMeter from "../components/MobilePredictionMeter.jsx";

export default function EventScreen() {
  const route = useRoute();
  const navigation = useNavigation();
  const { eventId } = route.params;

  const [event, setEvent] = useState(null);
  const [graph, setGraph] = useState(null);
  const [map, setMap] = useState(null);
  const [following, setFollowing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("chain"); // chain | impact | graph

  useEffect(() => {
    Promise.all([
      api.get(`/events/${eventId}`),
      api.get(`/graph/event/${eventId}`).catch(() => null),
    ]).then(([ev, gr]) => {
      setEvent(ev);
      setMap(ev.consequence_map);
      setGraph(gr);
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

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={COLORS.accent} size="large" />
      </View>
    );
  }

  if (!event) {
    return (
      <View style={styles.center}>
        <Text style={{ color: COLORS.textMuted }}>Event not found.</Text>
      </View>
    );
  }

  const color = getCategoryColor(event.category);
  const statusColor = STATUS_COLORS[event.status] || COLORS.textMuted;
  const chain = map?.consequence_chain || [];
  const directImpacts = map?.direct_impact || [];
  const predictions = map?.predictions || [];

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={[styles.header, { borderBottomColor: color }]}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={{ color: COLORS.textMuted, fontSize: 16 }}>←</Text>
        </TouchableOpacity>
        <View style={styles.headerContent}>
          <View style={styles.headerMeta}>
            <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
            <Text style={[styles.categoryLabel, { color }]}>{event.category?.toUpperCase()}</Text>
          </View>
          <Text style={styles.title} numberOfLines={3}>{event.title}</Text>
        </View>
        <TouchableOpacity onPress={handleFollow} style={styles.followBtn}>
          <Text style={[styles.followText, { color: following ? COLORS.accent : COLORS.textMuted }]}>
            {following ? "★" : "☆"}
          </Text>
        </TouchableOpacity>
      </View>

      {/* Tabs */}
      <View style={styles.tabs}>
        {["chain", "impact", "graph"].map((t) => (
          <TouchableOpacity key={t} onPress={() => setTab(t)} style={[styles.tab, tab === t && styles.tabActive]}>
            <Text style={[styles.tabText, tab === t && { color: COLORS.textPrimary }]}>
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView style={{ flex: 1 }} showsVerticalScrollIndicator={false}>
        {tab === "chain" && (
          <View style={styles.section}>
            {map?.is_paywalled ? (
              <View style={styles.paywallBox}>
                <Text style={styles.paywallTitle}>Full chain is paid-only</Text>
                <Text style={styles.paywallSub}>Upgrade in Settings to unlock the complete consequence chain.</Text>
              </View>
            ) : chain.length ? (
              chain.map((node, i) => <MobileChainNode key={i} node={node} depth={0} />)
            ) : (
              <Text style={styles.empty}>No chain data available.</Text>
            )}
          </View>
        )}

        {tab === "impact" && (
          <View style={styles.section}>
            {/* Predictions */}
            {predictions.length > 0 && (
              <View style={styles.predictionsRow}>
                {predictions.map((pred, i) => (
                  <MobilePredictionMeter key={i} confidence={pred.confidence} label={pred.label} />
                ))}
              </View>
            )}
            {/* Direct impacts */}
            {directImpacts.length ? (
              directImpacts.map((imp, i) => <MobileImpactCard key={i} impact={imp} />)
            ) : (
              <Text style={styles.empty}>No impact data available.</Text>
            )}
          </View>
        )}

        {tab === "graph" && (
          <View>
            <MobileGraph
              nodes={graph?.nodes || []}
              edges={graph?.edges || []}
              onNodePress={(node) => {
                if (node.id !== eventId) {
                  navigation.push("Event", { eventId: node.id });
                }
              }}
            />
            <Text style={styles.graphHint}>Tap a node to explore that event.</Text>
          </View>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bgBase },
  center: { flex: 1, backgroundColor: COLORS.bgBase, alignItems: "center", justifyContent: "center" },
  header: {
    flexDirection: "row",
    alignItems: "flex-start",
    padding: 16,
    borderBottomWidth: 2,
    gap: 12,
  },
  backBtn: { paddingTop: 2 },
  headerContent: { flex: 1 },
  headerMeta: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 4 },
  statusDot: { width: 7, height: 7, borderRadius: 4 },
  categoryLabel: { fontSize: 9, fontWeight: "700", letterSpacing: 0.8 },
  title: { fontSize: 16, fontWeight: "700", color: COLORS.textPrimary, lineHeight: 22 },
  followBtn: { paddingTop: 2 },
  followText: { fontSize: 22 },
  tabs: {
    flexDirection: "row",
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  tab: {
    flex: 1,
    paddingVertical: 10,
    alignItems: "center",
  },
  tabActive: {
    borderBottomWidth: 2,
    borderBottomColor: COLORS.accent,
  },
  tabText: {
    fontSize: 12,
    fontWeight: "600",
    color: COLORS.textMuted,
    letterSpacing: 0.3,
  },
  section: { padding: 12 },
  empty: { color: COLORS.textMuted, fontSize: 13, textAlign: "center", marginTop: 32 },
  paywallBox: {
    backgroundColor: COLORS.bgSurface,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: COLORS.border,
    padding: 20,
    alignItems: "center",
    gap: 8,
  },
  paywallTitle: {
    fontSize: 15,
    fontWeight: "600",
    color: COLORS.textPrimary,
  },
  paywallSub: {
    fontSize: 13,
    color: COLORS.textMuted,
    textAlign: "center",
    lineHeight: 18,
  },
  predictionsRow: {
    flexDirection: "row",
    justifyContent: "space-around",
    marginBottom: 16,
    paddingVertical: 8,
    backgroundColor: COLORS.bgSurface,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  graphHint: {
    textAlign: "center",
    color: COLORS.textMuted,
    fontSize: 11,
    paddingTop: 8,
    paddingBottom: 16,
  },
});
