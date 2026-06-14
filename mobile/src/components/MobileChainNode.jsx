import { useState } from "react";
import { View, Text, TouchableOpacity, StyleSheet, LayoutAnimation } from "react-native";
import { TYPE_COLORS, light as defaultColors } from "../lib/colors.js";

export default function MobileChainNode({ node, depth = 0, colors = defaultColors }) {
  const [expanded, setExpanded] = useState(depth === 0);
  const typeColor = TYPE_COLORS[node.type] || colors.textMuted;

  const toggle = () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setExpanded((v) => !v);
  };

  return (
    <View style={[styles.wrapper, { marginLeft: depth * 16 }]}>
      <TouchableOpacity
        onPress={node.children?.length ? toggle : undefined}
        activeOpacity={node.children?.length ? 0.7 : 1}
        style={[styles.card, { backgroundColor: colors.bgSurface, borderColor: colors.border, borderLeftColor: typeColor }]}
      >
        <View style={[styles.typePill, { backgroundColor: typeColor + "22" }]}>
          <Text style={[styles.typeText, { color: typeColor }]}>{node.type}</Text>
        </View>

        <Text style={[styles.content, { color: colors.textSecondary }]}>{node.content}</Text>

        {node.evidence && (
          <Text style={[styles.evidence, { color: colors.textMuted }]}>"{node.evidence}"</Text>
        )}

        {node.children?.length > 0 && (
          <Text style={[styles.expand, { color: typeColor }]}>
            {expanded ? "▲ collapse" : `▼ ${node.children.length} consequence${node.children.length > 1 ? "s" : ""}`}
          </Text>
        )}
      </TouchableOpacity>

      {expanded && node.children?.map((child, i) => (
        <MobileChainNode key={i} node={child} depth={depth + 1} colors={colors} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { marginBottom: 8 },
  card: {
    borderRadius: 10,
    padding: 12,
    borderWidth: 1,
    borderLeftWidth: 3,
  },
  typePill: {
    alignSelf: "flex-start",
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
    marginBottom: 6,
  },
  typeText: { fontSize: 9, fontWeight: "700", letterSpacing: 0.8, textTransform: "uppercase" },
  content: { fontSize: 13, lineHeight: 19 },
  evidence: { fontSize: 11, fontStyle: "italic", marginTop: 6, lineHeight: 16 },
  expand: { fontSize: 11, fontWeight: "600", marginTop: 8, letterSpacing: 0.3 },
});
