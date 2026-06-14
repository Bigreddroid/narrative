import { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  RefreshControl,
  ActivityIndicator,
  useColorScheme,
} from "react-native";
import { useNavigation, useFocusEffect } from "@react-navigation/native";
import { getThemeColors, getCategoryColor, STATUS_COLORS } from "../lib/colors.js";
import { api } from "../lib/api.js";

function FollowRow({ follow, onPress, onUnfollow, colors }) {
  const cat = follow.event_category || follow.category || "geopolitics";
  const title = follow.event_title || follow.title || "Untitled event";
  const status = follow.event_status || follow.status || "developing";
  const catColor = getCategoryColor(cat);
  const statusColor = STATUS_COLORS[status] || colors.textMuted;

  return (
    <TouchableOpacity style={[styles.row, { borderBottomColor: colors.border }]} onPress={() => onPress(follow)} activeOpacity={0.75}>
      <View style={[styles.colorDot, { backgroundColor: catColor }]} />
      <View style={styles.rowContent}>
        <View style={styles.rowMeta}>
          <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
          <Text style={[styles.category, { color: catColor }]}>{cat.toUpperCase()}</Text>
        </View>
        <Text style={[styles.title, { color: colors.textPrimary }]} numberOfLines={2}>{title}</Text>
      </View>
      <TouchableOpacity onPress={() => onUnfollow(follow)} style={styles.unfollowBtn}>
        <Text style={[styles.unfollowText, { color: colors.accent }]}>✕</Text>
      </TouchableOpacity>
    </TouchableOpacity>
  );
}

export default function FollowingScreen() {
  const navigation = useNavigation();
  const scheme = useColorScheme();
  const C = getThemeColors(scheme === "dark");
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
      <View style={[styles.center, { backgroundColor: C.bgBase }]}>
        <ActivityIndicator color={C.accent} size="large" />
      </View>
    );
  }

  return (
    <View style={[styles.container, { backgroundColor: C.bgBase }]}>
      <View style={[styles.header, { borderBottomColor: C.accent }]}>
        <Text style={[styles.headerTitle, { color: C.textPrimary }]}>Following</Text>
        <Text style={[styles.headerSub, { color: C.textMuted }]}>
          {follows.length} event{follows.length !== 1 ? "s" : ""}
        </Text>
      </View>

      {follows.length === 0 ? (
        <View style={styles.emptyState}>
          <Text style={[styles.emptyTitle, { color: C.textPrimary }]}>Nothing followed yet</Text>
          <Text style={[styles.emptyBody, { color: C.textMuted }]}>
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
              colors={C}
            />
          )}
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
          ItemSeparatorComponent={() => <View style={{ height: 1, backgroundColor: C.border }} />}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={() => load(true)} tintColor={C.accent} />
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  header: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 12,
    borderBottomWidth: 1,
  },
  headerTitle: { fontSize: 22, fontWeight: "700" },
  headerSub: { fontSize: 12, marginTop: 2 },
  list: { paddingVertical: 8 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 14,
    gap: 12,
    borderBottomWidth: 1,
  },
  colorDot: { width: 10, height: 10, borderRadius: 5, flexShrink: 0 },
  rowContent: { flex: 1 },
  rowMeta: { flexDirection: "row", alignItems: "center", gap: 5, marginBottom: 3 },
  statusDot: { width: 6, height: 6, borderRadius: 3 },
  category: { fontSize: 9, fontWeight: "700", letterSpacing: 0.8 },
  title: { fontSize: 14, fontWeight: "500", lineHeight: 20 },
  unfollowBtn: { padding: 8 },
  unfollowText: { fontSize: 14 },
  emptyState: { flex: 1, alignItems: "center", justifyContent: "center", padding: 32, gap: 10 },
  emptyTitle: { fontSize: 16, fontWeight: "600", textAlign: "center" },
  emptyBody: { fontSize: 13, textAlign: "center", lineHeight: 19 },
});
