import { useEffect, useState, useCallback, useRef } from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  RefreshControl,
  Dimensions,
  ActivityIndicator,
  useColorScheme,
  Image,
  Animated,
  Modal,
  ScrollView,
  Platform,
} from "react-native";
import { useNavigation } from "@react-navigation/native";
import { getThemeColors, getCategoryColor, STATUS_COLORS } from "../lib/colors.js";
import { api } from "../lib/api.js";
import { getCached, setCached } from "../lib/cache.js";
import MiniWorldMap from "../components/MiniWorldMap.jsx";

const { width, height } = Dimensions.get("window");
const CARD_W = (width - 36) / 2; // 2-col grid padding

function MediaBiasBadge({ score, colors }) {
  if (score == null) return null;
  const label = score > 0.3 ? "Right Lean" : score < -0.3 ? "Left Lean" : "Center";
  const dotColor = score > 0.3 ? "#F59E0B" : score < -0.3 ? "#3B82F6" : "#6B7280"; // orange / blue / grey
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
      <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: dotColor }} />
      <Text style={[styles.biasLabel, { color: colors.textMuted }]}>{label}</Text>
    </View>
  );
}

function EventCard({ event, onPress, colors }) {
  const catColor = getCategoryColor(event.category);

  return (
    <TouchableOpacity 
      style={[styles.card, { backgroundColor: colors.bgSurface, borderColor: colors.border, width: CARD_W }]} 
      onPress={() => onPress(event)} 
      activeOpacity={0.8}
    >
      {/* Hero with photo when available (reference style) */}
      <View style={[styles.cardHero, { backgroundColor: catColor + "22" }]}>
        {event.thumbnail_url ? (
          <Image
            source={{ uri: event.thumbnail_url }}
            style={StyleSheet.absoluteFill}
            resizeMode="cover"
          />
        ) : (
          <Text style={{ fontSize: 26 }}>{event.category === "geopolitics" ? "🌍" : event.category === "economics" ? "📈" : "📰"}</Text>
        )}

        {/* Small % pill on hero like reference */}
        {event.bias_pct != null && (
          <View style={styles.biasPctOnHero}>
            <Text style={styles.biasPctOnHeroTxt}>● {event.bias_pct}%</Text>
          </View>
        )}
      </View>

      <View style={styles.cardBody}>
        <Text style={[styles.title, { color: colors.textPrimary }]} numberOfLines={2}>{event.title}</Text>

        <TouchableOpacity 
          style={[styles.affectBtn, { backgroundColor: "#C80028" }]}
          onPress={() => onPress(event)}
        >
          <Text style={styles.affectBtnText}>How this affects you</Text>
        </TouchableOpacity>
      </View>
    </TouchableOpacity>
  );
}

export default function WorldMapScreen() {
  const navigation = useNavigation();
  const scheme = useColorScheme();
  const C = getThemeColors(scheme === "dark");
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [biasFilter, setBiasFilter] = useState(null); // null | 'left' | 'center' | 'right' for toggle

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
      const resp = await api.get("/feed");
      const raw = resp.feed || [];
      let list = raw.map((e) => {
        const bs = e.source_bias ?? null;
        return {
          id: e.id,
          title: e.canonical_title || e.title || "Untitled",
          category: e.category,
          status: e.current_status || e.status || "developing",
          importance_score: e.global_importance_score ?? e.importance_score ?? 0,
          geography: e.geography || [],
          prediction_score: e.prediction_score,
          lat: e.geo_centroid_lat ?? null,
          lng: e.geo_centroid_lng ?? null,
          bias_score: bs,
          bias_pct: bs != null ? Math.round(Math.abs(bs) * 100) : null,
          thumbnail_url: e.thumbnail_url || null,
        };
      });

      if (biasFilter) {
        list = list.filter(e => {
          if (!e.bias_score) return biasFilter === "center";
          if (biasFilter === "left") return e.bias_score < -0.3;
          if (biasFilter === "right") return e.bias_score > 0.3;
          return Math.abs(e.bias_score) <= 0.3;
        });
      }

      setEvents(list);
      setCached(cacheKey, list);
    } catch (err) {
      console.error("WorldMapScreen load error (real backend):", err);
      if (events.length === 0) setEvents([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [biasFilter]);

  // Region panel state
  const [regionPanel, setRegionPanel] = useState(null); // { region, count, events }
  const panelAnim = useRef(new Animated.Value(0)).current;

  const openRegionPanel = useCallback((event) => {
    // Determine region from geography or lat/lng
    const geo = event.geography || [];
    let region = "Global";
    if (geo.some(g => /india|delhi|mumbai|bengaluru|south asia/i.test(g))) region = "India";
    else if (geo.some(g => /china|japan|korea|tokyo|beijing|asia|singapore|vietnam/i.test(g))) region = "Asia";
    else if (geo.some(g => /europe|uk|france|germany|paris|london|berlin|moscow|russia/i.test(g))) region = "Europe";
    else if (geo.some(g => /america|usa|canada|mexico|brazil|argentina|new york/i.test(g))) region = "Americas";
    else if (geo.some(g => /africa|kenya|nigeria|cairo|egypt|south africa/i.test(g))) region = "Africa";
    else if (event.lat != null) {
      if (event.lat > 5 && event.lat < 40 && event.lng > 60 && event.lng < 145) region = "Asia";
      else if (event.lat > 20 && event.lat < 75 && event.lng > -25 && event.lng < 50) region = "Europe";
      else if (event.lng < -30 && event.lng > -165) region = "Americas";
      else if (event.lat < 40 && event.lat > -40 && event.lng > -20 && event.lng < 55) region = "Africa";
      else if (event.lat > 5 && event.lat < 40 && event.lng > 65 && event.lng < 90) region = "India";
    }

    const regionEvents = events.filter(e => {
      const g2 = e.geography || [];
      if (region === "India") return g2.some(g => /india|delhi|mumbai|south asia/i.test(g)) || (e.lat > 5 && e.lat < 40 && e.lng > 65 && e.lng < 90);
      if (region === "Asia") return g2.some(g => /asia|japan|china|korea|singapore/i.test(g)) || (e.lat > 5 && e.lat < 55 && e.lng > 60 && e.lng < 145);
      if (region === "Europe") return g2.some(g => /europe|uk|france|germany|russia|moscow/i.test(g)) || (e.lat > 36 && e.lat < 75 && e.lng > -25 && e.lng < 60);
      if (region === "Americas") return g2.some(g => /america|usa|canada|brazil/i.test(g)) || (e.lng < -30);
      if (region === "Africa") return g2.some(g => /africa|nigeria|kenya|egypt/i.test(g)) || (e.lat > -40 && e.lat < 37 && e.lng > -20 && e.lng < 55);
      return true;
    }).slice(0, 12);

    setRegionPanel({ region, count: regionEvents.length || 1, events: regionEvents.length ? regionEvents : [event] });
    Animated.spring(panelAnim, { toValue: 1, useNativeDriver: true, damping: 20, stiffness: 180 }).start();
  }, [events, panelAnim]);

  const closeRegionPanel = useCallback(() => {
    Animated.timing(panelAnim, { toValue: 0, duration: 200, useNativeDriver: true }).start(() => setRegionPanel(null));
  }, [panelAnim]);

  useEffect(() => { load(); }, [load]);

  const toggleBias = (which) => {
    setBiasFilter(biasFilter === which ? null : which);
  };

  if (loading) {
    return (
      <View style={[styles.center, { backgroundColor: C.bgBase }]}>
        <ActivityIndicator color={C.accent} size="large" />
      </View>
    );
  }

  const isDark = scheme === "dark";
  const PANEL_H = Math.round(height * 0.45);

  return (
    <View style={[styles.container, { backgroundColor: C.bgBase }]}>
      {/* Greeting header — reference style */}
      <View style={styles.greetingHeader}>
        <Text style={[styles.greetingMuted, { color: C.textMuted }]}>Good morning</Text>
        <Text style={[styles.greetingName, { color: C.textPrimary }]}>
          { /* dynamic first letter crimson to support any name */ }
          <Text style={{ color: C.accent }}>V</Text>aruna
        </Text>
        <View style={[styles.locationPill, { backgroundColor: C.bgSurface, borderColor: C.border }]}>
          <Text style={[styles.locationText, { color: C.textPrimary }]}>● Delhi</Text>
        </View>
      </View>

      <FlatList
        data={events}
        keyExtractor={(item) => item.id}
        numColumns={2}
        columnWrapperStyle={{ gap: 12, paddingHorizontal: 12 }}
        renderItem={({ item }) => (
          <EventCard event={item} onPress={(ev) => navigation.navigate("Event", { eventId: ev.id })} colors={C} />
        )}
        ListHeaderComponent={
          <>
            <MiniWorldMap events={events} colors={C} width={width} onDotPress={openRegionPanel} />
            {/* Bias toggle row (blue left / grey center / orange right) — bottom-right of "hero" */}
            <View style={styles.biasToggleRow}>
              {[
                { key: "left", label: "Left", color: "#3B82F6" },
                { key: "center", label: "Center", color: "#6B7280" },
                { key: "right", label: "Right", color: "#F59E0B" },
              ].map(b => (
                <TouchableOpacity
                  key={b.key}
                  onPress={() => toggleBias(b.key)}
                  style={[
                    styles.biasToggle,
                    { 
                      backgroundColor: biasFilter === b.key ? b.color : C.bgSurface,
                      borderColor: C.border 
                    }
                  ]}
                >
                  <Text style={{ 
                    color: biasFilter === b.key ? "#fff" : C.textMuted, 
                    fontSize: 11, 
                    fontWeight: "600" 
                  }}>
                    {b.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <View style={[styles.header, { borderBottomColor: C.border }]}>
              <Text style={[styles.headerTitle, { color: C.textPrimary }]}>Top Stories For You</Text>
              <Text style={[styles.headerSub, { color: C.textMuted }]}>
                {biasFilter ? `${events.length} matching` : `${events.length} active events`}
              </Text>
            </View>
          </>
        }
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => load(true)}
            tintColor={C.accent}
          />
        }
        ItemSeparatorComponent={() => <View style={{ height: 12 }} />}
      />

      {/* ── Region Panel (bottom sheet) ── */}
      {regionPanel && (
        <Modal transparent animationType="none" onRequestClose={closeRegionPanel}>
          {/* Backdrop */}
          <TouchableOpacity
            style={styles.backdrop}
            activeOpacity={1}
            onPress={closeRegionPanel}
          />
          {/* Panel */}
          <Animated.View
            style={[
              styles.regionPanel,
              {
                height: PANEL_H,
                backgroundColor: isDark ? "#0F1520" : "#FFFFFF",
                borderTopColor: isDark ? "rgba(0,212,255,0.2)" : "rgba(200,0,40,0.15)",
                transform: [{
                  translateY: panelAnim.interpolate({
                    inputRange: [0, 1],
                    outputRange: [PANEL_H, 0],
                  }),
                }],
              },
            ]}
          >
            {/* Handle bar */}
            <View style={[styles.panelHandle, { backgroundColor: isDark ? "rgba(255,255,255,0.2)" : "rgba(0,0,0,0.15)" }]} />

            {/* Header */}
            <View style={styles.panelHeader}>
              <View>
                <Text style={[styles.panelRegion, { color: isDark ? "#00D4FF" : "#C80028" }]}>
                  {regionPanel.region}
                </Text>
                <Text style={[styles.panelCount, { color: isDark ? "#E8E4DC" : "#1A1A1A" }]}>
                  {regionPanel.count} New Update{regionPanel.count !== 1 ? "s" : ""}
                </Text>
              </View>
              <TouchableOpacity onPress={closeRegionPanel} style={styles.panelClose}>
                <Text style={{ color: isDark ? "rgba(232,228,220,0.5)" : "rgba(26,26,26,0.4)", fontSize: 20 }}>✕</Text>
              </TouchableOpacity>
            </View>

            {/* Event cards — horizontal scroll */}
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.panelScroll}
            >
              {regionPanel.events.map((ev) => {
                const catColor = getCategoryColor(ev.category);
                return (
                  <TouchableOpacity
                    key={ev.id}
                    style={[styles.panelCard, {
                      backgroundColor: isDark ? "#1A1F2E" : "#F5F5F5",
                      borderColor: isDark ? "rgba(232,228,220,0.1)" : "rgba(26,26,26,0.1)",
                    }]}
                    onPress={() => { closeRegionPanel(); navigation.navigate("Event", { eventId: ev.id }); }}
                    activeOpacity={0.8}
                  >
                    <Text style={[styles.panelCardCat, { color: catColor }]}>
                      {ev.category?.toUpperCase()}
                    </Text>
                    <Text style={[styles.panelCardTitle, { color: isDark ? "#E8E4DC" : "#1A1A1A" }]} numberOfLines={3}>
                      {ev.title}
                    </Text>
                    <Text style={[styles.panelCardStatus, {
                      color: ev.status === "escalating" ? "#C80028" : isDark ? "rgba(232,228,220,0.4)" : "rgba(26,26,26,0.4)"
                    }]}>
                      {ev.status?.toUpperCase()}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
          </Animated.View>
        </Modal>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  greetingHeader: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
    gap: 8,
  },
  greetingMuted: { fontSize: 13 },
  greetingName: { fontSize: 28, fontWeight: "800", letterSpacing: -0.6, marginLeft: 4 },
  locationPill: {
    marginLeft: "auto",
    borderRadius: 999,
    paddingHorizontal: 11,
    paddingVertical: 6,
    borderWidth: 1,
  },
  locationText: { fontSize: 12, fontWeight: "600" },

  biasToggleRow: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 6,
    paddingHorizontal: 16,
    marginBottom: 8,
  },
  biasToggle: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    borderWidth: 1,
  },

  header: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 10,
    marginBottom: 4,
    borderBottomWidth: 1,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: "700",
  },
  headerSub: {
    fontSize: 12,
    marginTop: 2,
  },
  listContent: { paddingBottom: 20, paddingHorizontal: 12 },

  card: {
    borderRadius: 12,
    borderWidth: 1,
    overflow: "hidden",
    marginBottom: 12,
    width: CARD_W,
  },
  cardHero: {
    height: 90,
    alignItems: "center",
    justifyContent: "center",
  },
  cardBody: { flex: 1, padding: 10 },
  cardTop: { flexDirection: "row", alignItems: "center", marginBottom: 4, gap: 6 },
  category: { fontSize: 9, fontWeight: "700", letterSpacing: 0.8, flex: 1 },
  title: { fontSize: 13, fontWeight: "600", lineHeight: 17, marginBottom: 6 },
  geo: { fontSize: 10, marginTop: 2 },

  biasBadge: {
    borderRadius: 10,
    borderWidth: 1,
    paddingHorizontal: 6,
    paddingVertical: 1,
    marginLeft: "auto",
  },
  biasLabel: { fontSize: 8, fontWeight: "700", letterSpacing: 0.4 },

  affectBtn: {
    marginTop: 8,
    borderRadius: 8,
    paddingVertical: 6,
    alignItems: "center",
  },
  affectBtnText: {
    color: "#fff",
    fontSize: 11,
    fontWeight: "700",
  },

  // % pill on card hero (reference)
  biasPctOnHero: {
    position: "absolute",
    bottom: 8,
    right: 8,
    backgroundColor: "#C80028",
    borderRadius: 999,
    paddingHorizontal: 7,
    paddingVertical: 2,
  },
  biasPctOnHeroTxt: {
    color: "#fff",
    fontSize: 10,
    fontWeight: "700",
  },

  // Region panel (bottom sheet)
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.45)",
  },
  regionPanel: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    borderTopLeftRadius: 22,
    borderTopRightRadius: 22,
    borderTopWidth: 1.5,
    paddingTop: 10,
    overflow: "hidden",
  },
  panelHandle: {
    width: 40,
    height: 4,
    borderRadius: 2,
    alignSelf: "center",
    marginBottom: 14,
  },
  panelHeader: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 20,
    marginBottom: 16,
  },
  panelRegion: {
    fontSize: 13,
    fontWeight: "700",
    letterSpacing: 0.5,
    textTransform: "uppercase",
    marginBottom: 2,
  },
  panelCount: {
    fontSize: 22,
    fontWeight: "800",
    letterSpacing: -0.4,
  },
  panelClose: {
    marginLeft: "auto",
    padding: 8,
  },
  panelScroll: {
    paddingHorizontal: 16,
    paddingBottom: 20,
    gap: 12,
  },
  panelCard: {
    width: 180,
    borderRadius: 14,
    borderWidth: 1,
    padding: 14,
    gap: 6,
  },
  panelCardCat: {
    fontSize: 9,
    fontWeight: "700",
    letterSpacing: 0.9,
  },
  panelCardTitle: {
    fontSize: 13,
    fontWeight: "600",
    lineHeight: 18,
  },
  panelCardStatus: {
    fontSize: 9,
    fontWeight: "600",
    letterSpacing: 0.5,
    marginTop: 2,
  },
});
