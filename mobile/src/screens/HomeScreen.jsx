import { useState, useCallback, useEffect } from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  Dimensions,
  RefreshControl,
  Image,
  useColorScheme,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useNavigation } from "@react-navigation/native";
import { getThemeColors, getCategoryColor } from "../lib/colors.js";
import { api } from "../lib/api.js";
import { getCached, setCached } from "../lib/cache.js";

const { width } = Dimensions.get("window");
const GUTTER = 16;
const CARD_W = width - GUTTER * 2; // full-width prominent cards to match reference photo treatment
const HERO_H = Math.round(CARD_W * 0.58); // taller photo hero like reference

const CAT_EMOJI = {
  geopolitics: "⚔️", economics: "📈", climate: "🌍",
  health: "🏥", technology: "💻", security: "🛡️", social: "🗣️",
};

function BiasToggle({ bias }) {
  // Styled as iOS-like pill switch (top-right of hero in reference)
  const isRight = bias == null || bias >= 0;
  const trackColor = isRight ? "#C80028" : "#3B82F6"; // right lean crimson, left blue (like reference)
  return (
    <View style={[styles.toggleTrack, { backgroundColor: trackColor }]}>
      <View style={[
        styles.toggleKnob,
        { alignSelf: isRight ? "flex-end" : "flex-start" },
      ]} />
    </View>
  );
}

function StoryCard({ event, onPress, colors, isDark }) {
  const catColor = getCategoryColor(event.category);

  return (
    <TouchableOpacity
      style={[styles.card, { backgroundColor: colors.bgSurface, borderColor: colors.border }]}
      onPress={() => onPress(event)}
      activeOpacity={0.85}
    >
      {/* Hero photo — prominent, full top of card (match reference) */}
      <View style={[styles.hero, { backgroundColor: catColor + "22" }]}>
        {event.thumbnail_url ? (
          <Image
            source={{ uri: event.thumbnail_url }}
            style={StyleSheet.absoluteFill}
            resizeMode="cover"
          />
        ) : (
          <View style={[StyleSheet.absoluteFill, styles.emojiCenter]}>
            <Text style={styles.heroEmoji}>{CAT_EMOJI[event.category] || "📰"}</Text>
          </View>
        )}

        {/* Overlays only when we have a real photo (prevents broken look on emoji fallback) */}
        {event.thumbnail_url && (
          <>
            {/* Bias/lean switch — top-right on image (reference style) */}
            <View style={styles.toggleOverlayTopRight}>
              <BiasToggle bias={event.bias_score} />
            </View>

            {/* % pill on image (reference red pill with dot) */}
            {event.bias_pct != null && (
              <View style={styles.biasPctOnImage}>
                <Text style={styles.biasPctOnImageTxt}>● {event.bias_pct}%</Text>
              </View>
            )}
          </>
        )}
      </View>

      {/* Card body — clean, reference-like */}
      <View style={styles.body}>
        <Text style={[styles.title, { color: colors.textPrimary }]} numberOfLines={2}>
          {event.title}
        </Text>

        {event.source_name ? (
          <Text style={[styles.meta, { color: colors.textMuted }]} numberOfLines={1}>
            {event.source_name}
          </Text>
        ) : null}

        {event.summary ? (
          <Text style={[styles.summary, { color: colors.textSecondary }]} numberOfLines={2}>
            {event.summary}
          </Text>
        ) : null}
      </View>
    </TouchableOpacity>
  );
}

export default function HomeScreen() {
  const nav = useNavigation();
  const scheme = useColorScheme();
  const C = getThemeColors(scheme === "dark");
  const isDark = scheme === "dark";
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [userName, setUserName] = useState("");

  useEffect(() => {
    AsyncStorage.getItem("narrative_user")
      .then((raw) => {
        if (!raw) return;
        const u = JSON.parse(raw);
        const name = u?.name || u?.first_name || u?.email?.split("@")[0] || "";
        setUserName(name.split(" ")[0]);
      })
      .catch(() => {});
  }, []);

  const load = useCallback(async (fromPull = false) => {
    if (fromPull) setRefreshing(true);
    const key = "home_feed";
    if (!fromPull) {
      const cached = await getCached(key);
      if (cached) { setEvents(cached); setLoading(false); return; }
    }
    try {
      const res = await api.get("/feed");
      const biasDir = (score) => {
        if (score == null) return null;
        return score < -0.25 ? "Left" : score > 0.25 ? "Right" : "Neutral";
      };
      const items = (res.feed || []).slice(0, 20).map((e) => ({
        id: e.id,
        title: e.canonical_title || e.title || "Untitled",
        category: e.category,
        summary: e.canonical_summary || e.summary || "",
        source_name: e.source_name || null,
        thumbnail_url: e.thumbnail_url || null,
        bias_score: e.source_bias ?? null,
        bias_pct: e.source_bias != null ? Math.round(Math.abs(e.source_bias) * 100) : null,
        bias_label: e.source_bias != null
          ? `${biasDir(e.source_bias)} ${Math.round(Math.abs(e.source_bias) * 100)}%`
          : null,
      }));
      setEvents(items);
      setCached(key, items);
    } catch (err) {
      console.error("HomeScreen:", err.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onPress = useCallback((ev) => nav.navigate("Event", { eventId: ev.id }), [nav]);

  return (
    <View style={[styles.screen, { backgroundColor: C.bgBase }]}>
      <FlatList
        data={events}
        numColumns={1}
        keyExtractor={(e) => String(e.id)}
        renderItem={({ item }) => (
          <StoryCard event={item} onPress={onPress} colors={C} isDark={isDark} />
        )}
        ListHeaderComponent={
          <View style={[styles.header, { borderBottomColor: C.border }]}>
            {/* Greeting row — match reference: small muted time, large bold name (crimson first letter), location pill right */}
            <View style={styles.greetRow}>
              <View style={{ flex: 1 }}>
                <Text style={[styles.greetSub, { color: C.textMuted }]}>
                  {new Date().getHours() < 12 ? "Good morning" : new Date().getHours() < 17 ? "Good afternoon" : "Good evening"}
                </Text>
                <Text style={[styles.greetName, { color: C.textPrimary }]}>
                  {userName ? (
                    <>
                      <Text style={{ color: C.accent }}>{userName[0]}</Text>
                      {userName.slice(1)}
                    </>
                  ) : (
                    <>
                      <Text style={{ color: C.accent }}>V</Text>aruna
                    </>
                  )}
                </Text>
              </View>
              {/* Location pill */}
              <TouchableOpacity
                style={[styles.locationPill, { backgroundColor: C.bgSurface, borderColor: C.border }]}
              >
                <Text style={[styles.locationDot, { color: C.accent }]}>●</Text>
                <Text style={[styles.locationTxt, { color: C.textPrimary }]}> Delhi</Text>
              </TouchableOpacity>
            </View>

            {/* "Top Stories For You" — reference style, clean header */}
            <View style={styles.sectionRow}>
              <Text style={[styles.sectionLabel, { color: C.textPrimary }]}>
                Top Stories For You
              </Text>
            </View>
          </View>
        }
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        ItemSeparatorComponent={() => <View style={{ height: GUTTER }} />}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => load(true)} tintColor={C.accent} />
        }
        ListFooterComponent={<View style={{ height: 32 }} />}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  listContent: { paddingBottom: 20, paddingHorizontal: GUTTER },

  // Header
  header: { paddingBottom: 4 },
  greetRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 0,
    paddingTop: 20,
    paddingBottom: 4,
  },
  greetSub: { fontSize: 13, marginBottom: 2, letterSpacing: 0.2 },
  greetName: { fontSize: 32, fontWeight: "800", letterSpacing: -0.8, lineHeight: 38 },

  locationPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 6,
    marginLeft: 10,
  },
  locationDot: { fontSize: 11 },
  locationTxt: { fontSize: 12, fontWeight: "600" },

  sectionRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 0,
    paddingTop: 16,
    paddingBottom: 10,
  },
  sectionLabel: { fontSize: 18, fontWeight: "700", letterSpacing: -0.2 },

  // Full-width photo card (reference style: prominent hero + clean body)
  card: {
    borderRadius: 14,
    borderWidth: 1,
    overflow: "hidden",
    marginBottom: 12,
  },
  hero: {
    width: "100%",
    height: HERO_H,
    overflow: "hidden",
    position: "relative",
  },
  emojiCenter: { alignItems: "center", justifyContent: "center" },
  heroEmoji: { fontSize: 42 },

  // Bias/lean switch top-right on the photo (reference exact position + iOS pill look)
  toggleOverlayTopRight: {
    position: "absolute",
    top: 10,
    right: 10,
  },
  toggleTrack: {
    width: 42,
    height: 24,
    borderRadius: 12,
    padding: 2,
    justifyContent: "center",
  },
  toggleKnob: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: "#fff",
    shadowColor: "#000",
    shadowOpacity: 0.18,
    shadowRadius: 2,
    shadowOffset: { width: 0, height: 1 },
  },

  // Red % pill badge on image (reference "● 10%" style)
  biasPctOnImage: {
    position: "absolute",
    bottom: 10,
    right: 10,
    backgroundColor: "#C80028",
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  biasPctOnImageTxt: {
    color: "#fff",
    fontSize: 11,
    fontWeight: "700",
  },

  // Body (reference clean spacing)
  body: { padding: 12, paddingTop: 10, gap: 4 },
  title: { fontSize: 15, fontWeight: "700", lineHeight: 20 },
  meta: { fontSize: 11, lineHeight: 15, marginTop: 1 },
  summary: { fontSize: 12, lineHeight: 17, marginTop: 2 },

  // Legacy (kept for now, not used in primary cards)
  affectsBtn: {
    borderRadius: 8,
    paddingVertical: 8,
    paddingHorizontal: 8,
    alignItems: "center",
    marginTop: 6,
  },
  affectsTxt: { color: "#fff", fontSize: 10, fontWeight: "700", letterSpacing: 0.2 },
});
