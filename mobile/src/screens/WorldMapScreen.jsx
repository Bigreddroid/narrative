import { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  RefreshControl,
  Dimensions,
  ActivityIndicator,
} from "react-native";
import { useNavigation } from "@react-navigation/native";
import { COLORS, getCategoryColor, STATUS_COLORS } from "../lib/colors.js";
import { api } from "../lib/api.js";
import { getCached, setCached } from "../lib/cache.js";

const { width } = Dimensions.get("window");

function EventCard({ event, onPress }) {
  const color = getCategoryColor(event.category);
  const statusColor = STATUS_COLORS[event.status] || COLORS.textMuted;

  return (
    <TouchableOpacity style={styles.card} onPress={() => onPress(event)} activeOpacity={0.75}>
      {/* Category stripe */}
      <View style={[styles.stripe, { backgroundColor: color }]} />
      <View style={styles.cardBody}>
        <View style={styles.cardTop}>
          <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
          <Text style={[styles.category, { color }]}>{event.category?.toUpperCase()}</Text>
          <Text style={styles.score}>{event.importance_score}</Text>
        </View>
        <Text style={styles.title} numberOfLines={2}>{event.title}</Text>
        {event.geography?.length > 0 && (
          <Text style={styles.geo}>{event.geography.slice(0, 3).join(" · ")}</Text>
        )}
      </View>
    </TouchableOpacity>
  );
}

export default function WorldMapScreen() {
  const navigation = useNavigation();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (fromPull = false) => {
    if (fromPull) setRefreshing(true);

    const cacheKey = "world_events";
    if (!fromPull) {
      const cached = await getCached(cacheKey);
      if (cached) {
        setEvents(cached);
        setLoading(false);
        return;
      }
    }

    try {
      const data = await api.get("/events?limit=40&status=developing,escalating");
      const list = Array.isArray(data) ? data : data.events || [];
      setEvents(list);
      setCached(cacheKey, list);
    } catch (err) {
      console.error("WorldMapScreen load error:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={COLORS.accent} size="large" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>World Events</Text>
        <Text style={styles.headerSub}>{events.length} active consequences</Text>
      </View>

      <FlatList
        data={events}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <EventCard event={item} onPress={(ev) => navigation.navigate("Event", { eventId: ev.id })} />
        )}
        contentContainerStyle={styles.list}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => load(true)}
            tintColor={COLORS.accent}
          />
        }
        ItemSeparatorComponent={() => <View style={{ height: 8 }} />}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bgBase },
  center: { flex: 1, backgroundColor: COLORS.bgBase, alignItems: "center", justifyContent: "center" },
  header: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: "700",
    color: COLORS.textPrimary,
  },
  headerSub: {
    fontSize: 12,
    color: COLORS.textMuted,
    marginTop: 2,
  },
  list: { padding: 12 },
  card: {
    backgroundColor: COLORS.bgSurface,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: COLORS.border,
    flexDirection: "row",
    overflow: "hidden",
  },
  stripe: { width: 4 },
  cardBody: { flex: 1, padding: 12 },
  cardTop: { flexDirection: "row", alignItems: "center", marginBottom: 6, gap: 6 },
  statusDot: { width: 7, height: 7, borderRadius: 4 },
  category: { fontSize: 9, fontWeight: "700", letterSpacing: 0.8, flex: 1 },
  score: { fontSize: 11, fontWeight: "600", color: COLORS.textMuted },
  title: { fontSize: 14, fontWeight: "600", color: COLORS.textPrimary, lineHeight: 20 },
  geo: { fontSize: 11, color: COLORS.textMuted, marginTop: 4 },
});
