import { useMemo } from "react";
import { View, StyleSheet, TouchableOpacity } from "react-native";
import {
  Canvas,
  Fill,
  Path,
  Circle,
  Group,
  BlurMask,
  Skia,
} from "@shopify/react-native-skia";
import { light as defaultColors } from "../lib/colors.js";

const MAP_H = 220;

// Simplified continent outlines as [lat, lng] pairs (equirectangular)
const CONTINENT_COORDS = [
  // North America
  [
    [71, -141], [83, -80], [73, -65], [47, -53], [44, -66],
    [25, -80],  [25, -97], [15, -87], [8,  -77], [10, -75],
    [23, -90],  [32,-117], [48,-124], [60,-137], [71,-141],
  ],
  // South America
  [
    [10, -75], [12, -71], [10, -61], [5,  -52], [-5,  -35],
    [-15,-38], [-25,-48], [-35,-58], [-55,-67], [-54, -68],
    [-53,-70], [-41,-72], [-30,-71], [-18,-70], [0,   -75],
    [5,  -77], [10, -75],
  ],
  // Europe
  [
    [71, 28], [58, 25], [48, 20], [45, 13], [44,  8],
    [43, -3], [37, -9], [36, -6], [35, 11], [36, 36],
    [42, 40], [47, 40], [60, 26], [71, 28],
  ],
  // Africa
  [
    [37,  -6], [35, 11], [30, 32], [23, 37], [12, 44],
    [0,   42], [-10,40], [-25,35], [-34,19], [-35,24],
    [-28, 17], [-17,12], [-5, 10], [5,   2], [6,  -3],
    [8,   -9], [15,-17], [24,-16], [30,-10], [37, -6],
  ],
  // Asia (Middle East → Siberia → SE Asia → India)
  [
    [36, 36], [42, 40], [47, 52], [65, 55], [72,  70],
    [72,120], [65,175], [53,141], [35,129], [23, 121],
    [13,100], [1, 104], [5,  80], [8,  78], [23,  68],
    [36, 36],
  ],
  // Australia
  [
    [-17,122], [-13,136], [-14,141], [-20,147], [-28,153],
    [-37,148], [-39,146], [-38,140], [-38,130], [-31,115],
    [-25,113], [-22,114], [-17,122],
  ],
  // Greenland
  [
    [83,-30], [76,-18], [72,-22], [68,-27], [60,-44],
    [62,-52], [65,-52], [68,-53], [76,-68], [83,-41],
    [83,-30],
  ],
];

function project(lat, lng, W, H) {
  return {
    x: ((lng + 180) / 360) * W,
    y: ((90 - lat) / 180) * H,
  };
}

export default function MiniWorldMap({ events = [], colors = defaultColors, width = 375, onDotPress }) {
  const W = width;
  const H = MAP_H;
  const isDark = colors.bgBase === "#0D1117";

  // Dark: near-black navy ocean, dark slate land, CYAN (#00D4FF) glowing dots — per ChatGPT Image
  // Light: paper ocean + crimson-filled continents + crimson dots — per image(14)
  const oceanColor  = isDark ? "#080E1A" : "#F0EDE8";
  const landFill    = isDark ? "#182238" : "#8B0018";
  const landStroke  = isDark ? "#243350" : "#6B0010";
  const strokeW     = isDark ? 0.8       : 0.8;
  const dotColor    = isDark ? "#00D4FF" : "#C80028";

  const continentPaths = useMemo(() => {
    return CONTINENT_COORDS.map((coords) => {
      const pts = coords.map(([lat, lng]) => project(lat, lng, W, H));
      const path = Skia.Path.Make();
      path.addPoly(pts, true);
      return path;
    });
  }, [W, H]);

  const dots = useMemo(() => {
    return events
      .filter((e) => e.lat != null && e.lng != null)
      .map((e) => ({ ...project(e.lat, e.lng, W, H), id: e.id, event: e }));
  }, [events, W, H]);

  return (
    <View style={[styles.container, { width: W, height: H }]}>
      <Canvas style={{ width: W, height: H }}>
        <Fill color={oceanColor} />

        {continentPaths.map((path, i) => (
          <Group key={i}>
            <Path path={path} color={landFill} style="fill" />
            <Path path={path} color={landStroke} style="stroke" strokeWidth={strokeW} />
          </Group>
        ))}

        {dots.map((dot) => (
          <Group key={dot.id}>
            {/* Outer diffuse halo */}
            <Circle cx={dot.x} cy={dot.y} r={18} color={dotColor + "18"}>
              <BlurMask blur={14} style="normal" />
            </Circle>
            {/* Mid glow ring */}
            <Circle cx={dot.x} cy={dot.y} r={8} color={dotColor + "50"}>
              <BlurMask blur={5} style="normal" />
            </Circle>
            {/* Core dot */}
            <Circle cx={dot.x} cy={dot.y} r={4} color={dotColor} />
            {/* Bright centre highlight */}
            <Circle cx={dot.x} cy={dot.y} r={1.5} color="#FFFFFF" />
          </Group>
        ))}
      </Canvas>

      {/* Transparent touch overlays — one per dot, 48×48 hit target */}
      {onDotPress && dots.map((dot) => (
        <TouchableOpacity
          key={`touch-${dot.id}`}
          style={[styles.dotHit, { left: dot.x - 24, top: dot.y - 24 }]}
          onPress={() => onDotPress(dot.event)}
          activeOpacity={0.6}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { overflow: "hidden" },
  dotHit: {
    position: "absolute",
    width: 48,
    height: 48,
    borderRadius: 24,
  },
});
