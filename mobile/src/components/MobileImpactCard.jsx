import { View, Text, StyleSheet } from "react-native";
import { light as defaultColors } from "../lib/colors.js";

const SECTOR_ICONS = {
  housing: "🏠",
  food: "🌾",
  energy: "⚡",
  employment: "💼",
  healthcare: "🏥",
  transport: "🚂",
  finance: "📈",
  education: "🎓",
  default: "◆",
};

export default function MobileImpactCard({ impact, colors = defaultColors }) {
  if (!impact) return null;
  const { sector, severity, description, population_affected, evidence } = impact;
  const icon = SECTOR_ICONS[sector?.toLowerCase()] || SECTOR_ICONS.default;

  const severityColor =
    severity === "high" ? "#E74C3C" :
    severity === "medium" ? "#F5A623" : "#27AE60";

  return (
    <View style={[styles.card, { backgroundColor: colors.bgSurface, borderColor: colors.border, borderLeftColor: severityColor }]}>
      <View style={styles.header}>
        <Text style={styles.icon}>{icon}</Text>
        <View style={styles.headerText}>
          <Text style={[styles.sector, { color: colors.textPrimary }]}>{sector}</Text>
          {population_affected && (
            <Text style={[styles.population, { color: colors.textMuted }]}>{population_affected} affected</Text>
          )}
        </View>
        <View style={[styles.severityBadge, { backgroundColor: severityColor + "22" }]}>
          <Text style={[styles.severityText, { color: severityColor }]}>{severity?.toUpperCase()}</Text>
        </View>
      </View>

      <Text style={[styles.description, { color: colors.textSecondary }]}>{description}</Text>

      {evidence && (
        <Text style={[styles.evidence, { color: colors.textMuted }]}>"{evidence}"</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 10,
    padding: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderLeftWidth: 3,
  },
  header: { flexDirection: "row", alignItems: "center", marginBottom: 8, gap: 8 },
  icon: { fontSize: 18, width: 28, textAlign: "center" },
  headerText: { flex: 1 },
  sector: { fontSize: 13, fontWeight: "600", textTransform: "capitalize" },
  population: { fontSize: 11, marginTop: 1 },
  severityBadge: { borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2 },
  severityText: { fontSize: 9, fontWeight: "700", letterSpacing: 0.8 },
  description: { fontSize: 13, lineHeight: 19 },
  evidence: { fontSize: 11, fontStyle: "italic", marginTop: 6, lineHeight: 16 },
});
