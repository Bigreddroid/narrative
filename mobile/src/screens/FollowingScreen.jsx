import { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  RefreshControl,
  ActivityIndicator,
} from "react-native";
import { useNavigation, useFocusEffect } from "@react-navigation/native";
import { COLORS, getCategoryColor, STATUS_COLORS } from "../lib/colors.js";
import { api } from "../lib/api.js";

function FollowRow({ follow, onPress, onUnfollow }) {
  const color = getCategoryColor(follow.event_category || "geopolitics");
  const statusColor = STATUS_COLORS[follow.event_status] || COLORS.textMuted;

  return (
    <TouchableOpacity style={styles.row} onPress={() => onPress(follow)} activeOpacity={0.75}>
      <View style={[styles.colorDot, { backgroundColor: color }]} />
      <View style={styles.rowContent}>
        <View style={styles.rowMeta}>
          <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
          <Text style={[styles.category, { color }]}>{(follow.event_category || "geopolitics").toUpperCase()}</Text>
        </View>
        <Text style={styles.title} numberOfLines={2}>{follow.event_title || "Untitled event"}</Text>
      </View>
      <TouchableOpacity onPress={() => onUnfollow(follow)} style={styles.unfollowBtn}>
        <Text style={styles.unfollowText}>✕</Text>
      </TouchableOpacity>
    </TouchableOpacity>
  );
}

export default function FollowingScreen() {
  const navigation = useNavigation();
  const [follows, setFollows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (fromPull = false) => {
    if (fromPull) setRefreshing(true);
    try {
      const data = await api.get("/follows");
      setFollows(Array.isArray(data) ? data : data.follows || []);
    } catch (err) {
      console.error("FollowingScreen load error:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Reload when screen comes into focus
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const handleUnfollow = async (follow) => {
    try {
      await api.delete(`/follows/${follow.event_id}`);
      setFollows((prev) => prev.filter((f) => f.event_id !== follow.event_id));
    } catch (err) {
      console.error("Unfollow error:", err);
    }
  };

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
        <Text style={styles.headerTitle}>Following</Text>
        <Text style={styles.headerSub}>
          {follows.length} event{follows.length !== 1 ? "s" : ""}
        </Text>
      </View>

      {follows.length === 0 ? (
        <View style={styles.emptyState}>
          <Text style={styles.emptyTitle}>Nothing followed yet</Text>
          <Text style={styles.emptyBody}>
            Star events on the World screen to track them here and receive alerts.
          </Text>
        </View>
      ) : (
        <FlatList
          data={follows}
          keyExtractor={(item) => item.event_id}
          renderItem={({ item }) => (
            <FollowRow
              follow={item}
              onPress={(f) => navigation.navigate("Event", { eventId: f.event_id })}
              onUnfollow={handleUnfollow}
            />
          )}
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
          ItemSeparatorComponent={() => <View style={{ height: 1, backgroundColor: COLORS.border }} />}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={() => load(true)} tintColor={COLORS.accent} />
          }
        />
      )}
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
  headerTitle: { fontSize: 22, fontWeight: "700", color: COLORS.textPrimary },
  headerSub: { fontSize: 12, color: COLORS.textMuted, marginTop: 2 },
  list: { paddingVertical: 8 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 14,
    gap: 12,
  },
  colorDot: { width: 10, height: 10, borderRadius: 5, flexShrink: 0 },
  rowContent: { flex: 1 },
  rowMeta: { flexDirection: "row", alignItems: "center", gap: 5, marginBottom: 3 },
  statusDot: { width: 6, height: 6, borderRadius: 3 },
  category: { fontSize: 9, fontWeight: "700", letterSpacing: 0.8 },
  title: { fontSize: 14, fontWeight: "500", color: COLORS.textPrimary, lineHeight: 20 },
  unfollowBtn: { padding: 8 },
  unfollowText: { color: COLORS.textMuted, fontSize: 14 },
  emptyState: { flex: 1, alignItems: "center", justifyContent: "center", padding: 32, gap: 10 },
  emptyTitle: { fontSize: 16, fontWeight: "600", color: COLORS.textPrimary, textAlign: "center" },
  emptyBody: { fontSize: 13, color: COLORS.textMuted, textAlign: "center", lineHeight: 19 },
});
