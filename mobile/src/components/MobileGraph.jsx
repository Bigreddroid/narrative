import { useEffect, useRef, useState, useCallback } from "react";
import { View, StyleSheet, Dimensions, Text } from "react-native";
import {
  Canvas,
  Circle,
  Line,
  vec,
  Paint,
  Group,
  LinearGradient,
  RoundedRect,
  matchFont,
  Fill,
} from "@shopify/react-native-skia";
import {
  useSharedValue,
  useAnimatedReaction,
  withSpring,
  runOnJS,
} from "react-native-reanimated";
import { Gesture, GestureDetector } from "react-native-gesture-handler";
import { getCategoryColor, TYPE_COLORS, COLORS } from "../lib/colors.js";

const { width, height } = Dimensions.get("window");
const GRAPH_HEIGHT = height * 0.55;
const NODE_R = 18;
const SPRING = { stiffness: 300, damping: 30 };

function buildLayout(nodes, edges, centerX, centerY) {
  if (!nodes.length) return { positions: [] };

  // Simple radial layout: center node + ring
  const positions = nodes.map((node, i) => {
    if (i === 0) return { ...node, x: centerX, y: centerY * 0.45 };
    const angle = ((i - 1) / (nodes.length - 1)) * 2 * Math.PI;
    const r = Math.min(centerX, centerY) * 0.55;
    return {
      ...node,
      x: centerX + r * Math.cos(angle),
      y: centerY * 0.45 + r * Math.sin(angle),
    };
  });

  return { positions };
}

export default function MobileGraph({ nodes = [], edges = [], onNodePress }) {
  const cx = width / 2;
  const cy = GRAPH_HEIGHT / 2;
  const { positions } = buildLayout(nodes, edges, cx, cy);

  const [selected, setSelected] = useState(null);

  const tap = Gesture.Tap().onEnd((e) => {
    const { x, y } = e;
    const hit = positions.find(
      (n) => Math.hypot(n.x - x, n.y - (y)) < NODE_R + 8
    );
    if (hit) {
      runOnJS(setSelected)(hit.id);
      if (onNodePress) runOnJS(onNodePress)(hit);
    } else {
      runOnJS(setSelected)(null);
    }
  });

  if (!nodes.length) {
    return (
      <View style={[styles.container, styles.empty]}>
        <Text style={styles.emptyText}>No consequence graph available.</Text>
      </View>
    );
  }

  return (
    <GestureDetector gesture={tap}>
      <View style={styles.container}>
        <Canvas style={{ width, height: GRAPH_HEIGHT }}>
          <Fill color={COLORS.bgBase} />

          {/* Edges */}
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
                color={isHighlighted ? COLORS.accent : COLORS.border}
                strokeWidth={isHighlighted ? 2 : 1}
                style="stroke"
              />
            );
          })}

          {/* Nodes */}
          {positions.map((node) => {
            const color = getCategoryColor(node.category);
            const isSelected = selected === node.id;
            return (
              <Group key={node.id}>
                {/* Glow ring when selected */}
                {isSelected && (
                  <Circle cx={node.x} cy={node.y} r={NODE_R + 8} color={color + "30"} />
                )}
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
  container: {
    width,
    height: GRAPH_HEIGHT,
    backgroundColor: COLORS.bgBase,
  },
  empty: {
    alignItems: "center",
    justifyContent: "center",
  },
  emptyText: {
    color: COLORS.textMuted,
    fontSize: 14,
  },
});
