import { useEffect, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  TextInput,
  StyleSheet,
  ActivityIndicator,
  Alert,
  useColorScheme,
} from "react-native";
import { getThemeColors } from "../lib/colors.js";
import { api, clearToken } from "../lib/api.js";
import { useNavigation } from "@react-navigation/native";

const TIER_LABEL = { free: "Free", paid: "Full Access" };

function Field({ label, value, onChangeText, colors }) {
  return (
    <View style={[styles.field, { borderBottomColor: colors.border }]}>
      <Text style={[styles.fieldLabel, { color: colors.textMuted }]}>{label}</Text>
      {onChangeText ? (
        <TextInput
          value={value || ""}
          onChangeText={onChangeText}
          style={[styles.fieldInput, { color: colors.textPrimary }]}
          placeholderTextColor={colors.textMuted}
          placeholder={`Enter ${label.toLowerCase()}`}
          autoCapitalize="none"
          autoCorrect={false}
        />
      ) : (
        <Text style={[styles.fieldValue, { color: colors.textSecondary }]}>{value || "—"}</Text>
      )}
    </View>
  );
}

export default function ProfileScreen() {
  const navigation = useNavigation();
  const scheme = useColorScheme();
  const C = getThemeColors(scheme === "dark");
  const [user, setUser] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/users/me").then(setUser).catch(console.error).finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    if (!user) return;
    setSaving(true);
    try {
      await api.patch("/users/me", {
        city: user.city,
        country: user.country,
        profession: user.profession,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      Alert.alert("Error", err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = async () => {
    Alert.alert("Log out", "Are you sure?", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Log out",
        style: "destructive",
        onPress: async () => {
          await clearToken();
          navigation.reset({ index: 0, routes: [{ name: "Auth" }] });
        },
      },
    ]);
  };

  if (loading) {
    return (
      <View style={[styles.center, { backgroundColor: C.bgBase }]}>
        <ActivityIndicator color={C.accent} size="large" />
      </View>
    );
  }

  if (!user) {
    return (
      <View style={[styles.center, { backgroundColor: C.bgBase }]}>
        <Text style={{ color: C.textMuted }}>Failed to load profile.</Text>
      </View>
    );
  }

  const isPaid = user.tier === "paid";

  return (
    <ScrollView style={[styles.container, { backgroundColor: C.bgBase }]} contentContainerStyle={{ paddingBottom: 40 }}>
      <View style={styles.header}>
        <Text style={[styles.headerTitle, { color: C.textPrimary }]}>Profile</Text>
      </View>

      {/* Tier badge */}
      <View style={[styles.tierBox, { backgroundColor: C.bgSurface, borderColor: C.border }]}>
        <View>
          <Text style={[styles.tierLabel, { color: C.textMuted }]}>Subscription</Text>
          <Text style={[styles.tierValue, { color: isPaid ? C.accent : C.textPrimary }]}>
            {TIER_LABEL[user.tier] || user.tier}
          </Text>
        </View>
        {!isPaid && (
          <TouchableOpacity
            style={[styles.upgradeBtn, { backgroundColor: C.accent }]}
            onPress={() => Alert.alert("Upgrade", "Open the web app at app.thenarrative.io/settings to upgrade.")}
          >
            <Text style={styles.upgradeBtnText}>Upgrade</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Profile fields */}
      <View style={[styles.section, { backgroundColor: C.bgSurface, borderColor: C.border }]}>
        <Text style={[styles.sectionTitle, { color: C.textMuted, borderBottomColor: C.border }]}>Consequence profile</Text>
        <Field label="Email" value={user.email} colors={C} />
        <Field label="Country" value={user.country} onChangeText={(v) => setUser({ ...user, country: v })} colors={C} />
        <Field label="City" value={user.city} onChangeText={(v) => setUser({ ...user, city: v })} colors={C} />
        <Field label="Profession" value={user.profession} onChangeText={(v) => setUser({ ...user, profession: v })} colors={C} />
      </View>

      <TouchableOpacity
        style={[styles.saveBtn, { backgroundColor: saved ? "#27AE60" : C.accent }]}
        onPress={handleSave}
        disabled={saving}
      >
        <Text style={styles.saveBtnText}>
          {saved ? "Saved!" : saving ? "Saving..." : "Save changes"}
        </Text>
      </TouchableOpacity>

      <TouchableOpacity style={[styles.logoutBtn, { borderColor: C.border }]} onPress={handleLogout}>
        <Text style={[styles.logoutText, { color: C.textMuted }]}>Log out</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  header: { paddingHorizontal: 20, paddingTop: 16, paddingBottom: 12 },
  headerTitle: { fontSize: 22, fontWeight: "700" },
  tierBox: {
    marginHorizontal: 16,
    marginBottom: 16,
    borderRadius: 12,
    borderWidth: 1,
    padding: 16,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  tierLabel: { fontSize: 11, textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 3 },
  tierValue: { fontSize: 16, fontWeight: "700" },
  upgradeBtn: {
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 7,
  },
  upgradeBtnText: { color: "#FFF", fontSize: 12, fontWeight: "700" },
  section: {
    marginHorizontal: 16,
    marginBottom: 12,
    borderRadius: 12,
    borderWidth: 1,
    overflow: "hidden",
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.8,
    padding: 12,
    paddingBottom: 6,
    borderBottomWidth: 1,
  },
  field: {
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderBottomWidth: 1,
  },
  fieldLabel: { fontSize: 10, textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 4 },
  fieldValue: { fontSize: 14 },
  fieldInput: {
    fontSize: 14,
    padding: 0,
  },
  saveBtn: {
    marginHorizontal: 16,
    marginBottom: 12,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
  },
  saveBtnText: { color: "#FFF", fontSize: 14, fontWeight: "700" },
  logoutBtn: {
    marginHorizontal: 16,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    borderWidth: 1,
  },
  logoutText: { fontSize: 14, fontWeight: "600" },
});
