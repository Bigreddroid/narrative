import { useState, useCallback, useRef } from "react";
import {
  View,
  Text,
  TextInput,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  useColorScheme,
} from "react-native";
import { useNavigation } from "@react-navigation/native";
import { getThemeColors, getCategoryColor, STATUS_COLORS } from "../lib/colors.js";
import { api } from "../lib/api.js";

const CATEGORIES = ["geopolitics", "economics", "climate", "technology", "health", "security", "social"];

function ResultCard({ event, onPress, colors }) {
  const cat = event.category || "geopolitics";
  const title = event.canonical_title || event.title || "Untitled";
  const score = event.global_importance_score ?? event.importance_score ?? 0;
  const status = event.current_status || event.status || "developing";
  const catColor = getCategoryColor(cat);
  const statusColor = STATUS_COLORS[status] || colors.textMuted;

  return (
    <TouchableOpacity style={[styles.card, { backgroundColor: colors.bgSurface, borderColor: colors.border }]} onPress={() => onPress(event)} activeOpacity={0.75}>
      <View style={[styles.stripe, { backgroundColor: catColor }]} />
      <View style={styles.cardBody}>
        <View style={styles.meta}>
          <View style={[styles.dot, { backgroundColor: statusColor }]} />
          <Text style={[styles.cat, { color: catColor }]}>{cat.toUpperCase()}</Text>
          <Text style={[styles.score, { color: colors.textMuted }]}>{score}</Text>
        </View>
        <Text style={[styles.title, { color: colors.textPrimary }]} numberOfLines={2}>{title}</Text>
      </View>
    </TouchableOpacity>
  );
}

export default function SearchScreen() {
  const navigation = useNavigation();
  const scheme = useColorScheme();
  const C = getThemeColors(scheme === "dark");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState(null);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const debounceRef = useRef(null);

  const search = useCallback(async (q, cat) => {
    setLoading(true);
    setSearched(true);
    try {
      const params = new URLSearchParams();
      if (q.trim()) params.set("q", q.trim());
      if (cat) params.set("category", cat);
      params.set("limit", "30");
      const data = await api.get(`/search?${params.toString()}`).catch(() =>
        api.get(`/feed`).then(r => ({ events: r.feed || [] }))
      );
      setResults(Array.isArray(data) ? data : data.events || []);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleChangeText = (text) => {
    setQuery(text);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      if (text.length >= 2 || category) search(text, category);
    }, 400);
  };

  const handleCategory = (cat) => {
    const next = cat === category ? null : cat;
    setCategory(next);
    search(query, next);
  };

  return (
    <View style={[styles.container, { backgroundColor: C.bgBase }]}>
      <View style={[styles.header, { borderBottomColor: C.border }]}>
        <Text style={[styles.headerTitle, { color: C.textPrimary }]}>Search</Text>
      </View>

      {/* Search input */}
      <View style={[styles.inputWrapper, { backgroundColor: C.bgSurface, borderColor: C.border }]}>
        <TextInput
          style={[styles.input, { color: C.textPrimary }]}
          value={query}
          onChangeText={handleChangeText}
          placeholder="Search events, sectors, regions..."
          placeholderTextColor={C.textMuted}
          returnKeyType="search"
          onSubmitEditing={() => search(query, category)}
          autoCorrect={false}
          autoCapitalize="none"
        />
      </View>

      {/* Category filter pills */}
      <FlatList
        horizontal
        data={CATEGORIES}
        keyExtractor={(c) => c}
        showsHorizontalScrollIndicator={false}
        style={styles.pills}
        contentContainerStyle={{ gap: 6, paddingHorizontal: 12 }}
        renderItem={({ item }) => {
          const active = item === category;
          const color = getCategoryColor(item);
          return (
            <TouchableOpacity
              onPress={() => handleCategory(item)}
              style={[styles.pill, { borderColor: active ? color : C.border }, active && { backgroundColor: color + "22" }]}
            >
              <Text style={[styles.pillText, { color: active ? color : C.textMuted }]}>{item}</Text>
            </TouchableOpacity>
          );
        }}
      />

      {/* Results */}
      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={C.accent} />
        </View>
      ) : (
        <FlatList
          data={results}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => (
            <ResultCard event={item} onPress={(ev) => navigation.navigate("Event", { eventId: ev.id })} colors={C} />
          )}
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
          ItemSeparatorComponent={() => <View style={{ height: 8 }} />}
          ListEmptyComponent={
            searched ? (
              <Text style={[styles.empty, { color: C.textMuted }]}>No events found.</Text>
            ) : (
              <Text style={[styles.empty, { color: C.textMuted }]}>Search for any world event or sector.</Text>
            )
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", paddingTop: 40 },
  header: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 8,
    borderBottomWidth: 1,
  },
  headerTitle: { fontSize: 22, fontWeight: "700" },
  inputWrapper: {
    marginHorizontal: 12,
    marginBottom: 10,
    borderRadius: 10,
    borderWidth: 1,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
  },
  input: {
    flex: 1,
    fontSize: 14,
    paddingVertical: 11,
  },
  pills: { flexGrow: 0, marginBottom: 10 },
  pill: {
    borderRadius: 16,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 5,
  },
  pillText: {
    fontSize: 11,
    fontWeight: "600",
    textTransform: "capitalize",
  },
  list: { padding: 12 },
  card: {
    borderRadius: 10,
    borderWidth: 1,
    flexDirection: "row",
    overflow: "hidden",
  },
  stripe: { width: 3 },
  cardBody: { flex: 1, padding: 11 },
  meta: { flexDirection: "row", alignItems: "center", marginBottom: 5, gap: 5 },
  dot: { width: 6, height: 6, borderRadius: 3 },
  cat: { fontSize: 9, fontWeight: "700", letterSpacing: 0.8, flex: 1 },
  score: { fontSize: 11, fontWeight: "600" },
  title: { fontSize: 13, fontWeight: "600", lineHeight: 19 },
  empty: { fontSize: 13, textAlign: "center", marginTop: 40 },
});
