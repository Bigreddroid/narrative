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
} from "react-native";
import { COLORS } from "../lib/colors.js";
import { api, clearToken } from "../lib/api.js";
import { useNavigation } from "@react-navigation/native";

const TIER_LABEL = { free: "Free", paid: "Full Access" };

function Field({ label, value, onChangeText }) {
  return (
    <View style={styles.field}>
      <Text style={styles.fieldLabel}>{label}</Text>
      {onChangeText ? (
        <TextInput
          value={value || ""}
          onChangeText={onChangeText}
          style={styles.fieldInput}
          placeholderTextColor={COLORS.textMuted}
          placeholder={`Enter ${label.toLowerCase()}`}
          autoCapitalize="none"
          autoCorrect={false}
        />
      ) : (
        <Text style={styles.fieldValue}>{value || "—"}</Text>
      )}
    </View>
  );
}

export default function ProfileScreen() {
  const navigation = useNavigation();
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
      <View style={styles.center}>
        <ActivityIndicator color={COLORS.accent} size="large" />
      </View>
    );
  }

  if (!user) {
    return (
      <View style={styles.center}>
        <Text style={{ color: COLORS.textMuted }}>Failed to load profile.</Text>
      </View>
    );
  }

  const isPaid = user.tier === "paid";

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ paddingBottom: 40 }}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Profile</Text>
      </View>

      {/* Tier badge */}
      <View style={styles.tierBox}>
        <View>
          <Text style={styles.tierLabel}>Subscription</Text>
          <Text style={[styles.tierValue, isPaid && { color: COLORS.accent }]}>
            {TIER_LABEL[user.tier] || user.tier}
          </Text>
        </View>
        {!isPaid && (
          <TouchableOpacity
            style={styles.upgradeBtn}
            onPress={() => Alert.alert("Upgrade", "Open the web app at app.thenarrative.io/settings to upgrade.")}
          >
            <Text style={styles.upgradeBtnText}>Upgrade</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Profile fields */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Consequence profile</Text>
        <Field label="Email" value={user.email} />
        <Field label="Country" value={user.country} onChangeText={(v) => setUser({ ...user, country: v })} />
        <Field label="City" value={user.city} onChangeText={(v) => setUser({ ...user, city: v })} />
        <Field label="Profession" value={user.profession} onChangeText={(v) => setUser({ ...user, profession: v })} />
      </View>

      <TouchableOpacity
        style={[styles.saveBtn, saved && styles.saveBtnDone]}
        onPress={handleSave}
        disabled={saving}
      >
        <Text style={styles.saveBtnText}>
          {saved ? "Saved!" : saving ? "Saving..." : "Save changes"}
        </Text>
      </TouchableOpacity>

      <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
        <Text style={styles.logoutText}>Log out</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bgBase },
  center: { flex: 1, backgroundColor: COLORS.bgBase, alignItems: "center", justifyContent: "center" },
  header: { paddingHorizontal: 20, paddingTop: 16, paddingBottom: 12 },
  headerTitle: { fontSize: 22, fontWeight: "700", color: COLORS.textPrimary },
  tierBox: {
    marginHorizontal: 16,
    marginBottom: 16,
    backgroundColor: COLORS.bgSurface,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: COLORS.border,
    padding: 16,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  tierLabel: { fontSize: 11, color: COLORS.textMuted, textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 3 },
  tierValue: { fontSize: 16, fontWeight: "700", color: COLORS.textPrimary },
  upgradeBtn: {
    backgroundColor: COLORS.accent,
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 7,
  },
  upgradeBtnText: { color: "#000", fontSize: 12, fontWeight: "700" },
  section: {
    marginHorizontal: 16,
    marginBottom: 12,
    backgroundColor: COLORS.bgSurface,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: COLORS.border,
    overflow: "hidden",
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: "700",
    color: COLORS.textMuted,
    textTransform: "uppercase",
    letterSpacing: 0.8,
    padding: 12,
    paddingBottom: 6,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  field: {
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  fieldLabel: { fontSize: 10, color: COLORS.textMuted, textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 4 },
  fieldValue: { fontSize: 14, color: COLORS.textSecondary },
  fieldInput: {
    fontSize: 14,
    color: COLORS.textPrimary,
    padding: 0,
  },
  saveBtn: {
    marginHorizontal: 16,
    marginBottom: 12,
    backgroundColor: COLORS.accent,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
  },
  saveBtnDone: { backgroundColor: "#27AE60" },
  saveBtnText: { color: "#000", fontSize: 14, fontWeight: "700" },
  logoutBtn: {
    marginHorizontal: 16,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  logoutText: { color: COLORS.textMuted, fontSize: 14, fontWeight: "600" },
});
