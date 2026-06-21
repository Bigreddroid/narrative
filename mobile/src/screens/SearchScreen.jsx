import { useState, useCallback, useRef } from "react";
import {
  View,
  Text,
  TextInput,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import { useNavigation } from "@react-navigation/native";
import { COLORS, getCategoryColor, STATUS_COLORS } from "../lib/colors.js";
import { api } from "../lib/api.js";

const CATEGORIES = ["geopolitics", "economics", "climate", "technology", "health", "security", "social"];

function ResultCard({ event, onPress }) {
  const color = getCategoryColor(event.category);
  const statusColor = STATUS_COLORS[event.status] || COLORS.textMuted;

  return (
    <TouchableOpacity style={styles.card} onPress={() => onPress(event)} activeOpacity={0.75}>
      <View style={[styles.stripe, { backgroundColor: color }]} />
      <View style={styles.cardBody}>
        <View style={styles.meta}>
          <View style={[styles.dot, { backgroundColor: statusColor }]} />
          <Text style={[styles.cat, { color }]}>{event.category?.toUpperCase()}</Text>
          <Text style={styles.score}>{event.importance_score}</Text>
        </View>
        <Text style={styles.title} numberOfLines={2}>{event.title}</Text>
      </View>
    </TouchableOpacity>
  );
}

export default function SearchScreen() {
  const navigation = useNavigation();
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
      const data = await api.get(`/events?${params.toString()}`);
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
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Search</Text>
      </View>

      {/* Search input */}
      <View style={styles.inputWrapper}>
        <TextInput
          style={styles.input}
          value={query}
          onChangeText={handleChangeText}
          placeholder="Search events, sectors, regions..."
          placeholderTextColor={COLORS.textMuted}
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
              style={[styles.pill, active && { backgroundColor: color + "22", borderColor: color }]}
            >
              <Text style={[styles.pillText, active && { color }]}>{item}</Text>
            </TouchableOpacity>
          );
        }}
      />

      {/* Results */}
      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={COLORS.accent} />
        </View>
      ) : (
        <FlatList
          data={results}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => (
            <ResultCard event={item} onPress={(ev) => navigation.navigate("Event", { eventId: ev.id })} />
          )}
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
          ItemSeparatorComponent={() => <View style={{ height: 8 }} />}
          ListEmptyComponent={
            searched ? (
              <Text style={styles.empty}>No events found.</Text>
            ) : (
              <Text style={styles.empty}>Search for any world event or sector.</Text>
            )
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bgBase },
  center: { flex: 1, alignItems: "center", justifyContent: "center", paddingTop: 40 },
  header: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 8,
  },
  headerTitle: { fontSize: 22, fontWeight: "700", color: COLORS.textPrimary },
  inputWrapper: {
    marginHorizontal: 12,
    marginBottom: 10,
    backgroundColor: COLORS.bgSurface,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: COLORS.border,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
  },
  input: {
    flex: 1,
    color: COLORS.textPrimary,
    fontSize: 14,
    paddingVertical: 11,
  },
  pills: { flexGrow: 0, marginBottom: 10 },
  pill: {
    borderRadius: 16,
    borderWidth: 1,
    borderColor: COLORS.border,
    paddingHorizontal: 12,
    paddingVertical: 5,
    backgroundColor: COLORS.bgSurface,
  },
  pillText: {
    fontSize: 11,
    fontWeight: "600",
    color: COLORS.textMuted,
    textTransform: "capitalize",
  },
  list: { padding: 12 },
  card: {
    backgroundColor: COLORS.bgSurface,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: COLORS.border,
    flexDirection: "row",
    overflow: "hidden",
  },
  stripe: { width: 3 },
  cardBody: { flex: 1, padding: 11 },
  meta: { flexDirection: "row", alignItems: "center", marginBottom: 5, gap: 5 },
  dot: { width: 6, height: 6, borderRadius: 3 },
  cat: { fontSize: 9, fontWeight: "700", letterSpacing: 0.8, flex: 1 },
  score: { fontSize: 11, fontWeight: "600", color: COLORS.textMuted },
  title: { fontSize: 13, fontWeight: "600", color: COLORS.textPrimary, lineHeight: 19 },
  empty: { color: COLORS.textMuted, fontSize: 13, textAlign: "center", marginTop: 40 },
});
