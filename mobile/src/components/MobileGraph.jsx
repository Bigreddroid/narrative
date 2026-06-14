import { useState } from "react";
import { View, StyleSheet, Dimensions, Text } from "react-native";
import {
  Canvas,
  Circle,
  Line,
  vec,
  Group,
  Fill,
} from "@shopify/react-native-skia";
import { runOnJS } from "react-native-reanimated";
import { Gesture, GestureDetector } from "react-native-gesture-handler";
import { getCategoryColor, light as defaultColors } from "../lib/colors.js";

const { width, height } = Dimensions.get("window");
const GRAPH_HEIGHT = height * 0.55;
const NODE_R = 18;

function buildLayout(nodes, edges, centerX, centerY) {
  if (!nodes.length) return { positions: [] };
  const positions = nodes.map((node, i) => {
    if (i === 0) return { ...node, x: centerX, y: centerY * 0.45 };
    const angle = ((i - 1) / (nodes.length - 1)) * 2 * Math.PI;
    const r = Math.min(centerX, centerY) * 0.55;
    return { ...node, x: centerX + r * Math.cos(angle), y: centerY * 0.45 + r * Math.sin(angle) };
  });
  return { positions };
}

export default function MobileGraph({ nodes = [], edges = [], onNodePress, colors = defaultColors }) {
  const cx = width / 2;
  const cy = GRAPH_HEIGHT / 2;
  const { positions } = buildLayout(nodes, edges, cx, cy);
  const [selected, setSelected] = useState(null);

  const tap = Gesture.Tap().onEnd((e) => {
    const { x, y } = e;
    const hit = positions.find((n) => Math.hypot(n.x - x, n.y - y) < NODE_R + 8);
    if (hit) {
      runOnJS(setSelected)(hit.id);
      if (onNodePress) runOnJS(onNodePress)(hit);
    } else {
      runOnJS(setSelected)(null);
    }
  });

  if (!nodes.length) {
    return (
      <View style={[styles.container, styles.empty, { backgroundColor: colors.bgBase }]}>
        <Text style={[styles.emptyText, { color: colors.textMuted }]}>No consequence graph available.</Text>
      </View>
    );
  }

  return (
    <GestureDetector gesture={tap}>
      <View style={[styles.container, { backgroundColor: colors.bgBase }]}>
        <Canvas style={{ width, height: GRAPH_HEIGHT }}>
          <Fill color={colors.bgBase} />

          {edges.map((edge, i) => {
            const src = positions.find((n) => n.id === edge.source_event_id);
            const tgt = positions.find((n) => n.id === edge.target_event_id);
            if (!src || !tgt) return null;
            const isHighlighted = selected === src.id || selected === tgt.id;
            return (
              <Line
                key={i}
                p1={vec(src.x, src.y)}
                p2={vec(tgt.x, tgt.y)}
                color={isHighlighted ? colors.vizAccent : colors.border}
                strokeWidth={isHighlighted ? 2 : 1}
                style="stroke"
              />
            );
          })}

          {positions.map((node) => {
            const color = getCategoryColor(node.category);
            const isSelected = selected === node.id;
            return (
              <Group key={node.id}>
                {isSelected && <Circle cx={node.x} cy={node.y} r={NODE_R + 8} color={color + "30"} />}
                <Circle cx={node.x} cy={node.y} r={NODE_R} color={color + "CC"} />
                <Circle
                  cx={node.x}
                  cy={node.y}
                  r={NODE_R}
                  color="transparent"
                  style="stroke"
                  strokeWidth={isSelected ? 2.5 : 1}
                />
              </Group>
            );
          })}
        </Canvas>
      </View>
    </GestureDetector>
  );
}

const styles = StyleSheet.create({
  container: { width, height: GRAPH_HEIGHT },
  empty: { alignItems: "center", justifyContent: "center" },
  emptyText: { fontSize: 14 },
});
