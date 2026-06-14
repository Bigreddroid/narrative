import { View, Text, StyleSheet } from "react-native";
import { Canvas, Path, Skia } from "@shopify/react-native-skia";
import { light as defaultColors } from "../lib/colors.js";

const SIZE = 90;
const STROKE = 8;
const R = (SIZE - STROKE) / 2;
const CX = SIZE / 2;
const CY = SIZE / 2;

function makeArcPath(cx, cy, r, startAngle, endAngle) {
  const path = Skia.Path.Make();
  const start = (startAngle - 90) * (Math.PI / 180);
  const x1 = cx + r * Math.cos(start);
  const y1 = cy + r * Math.sin(start);
  path.moveTo(x1, y1);
  path.addArc(
    { x: cx - r, y: cy - r, width: r * 2, height: r * 2 },
    startAngle - 90,
    endAngle - startAngle
  );
  return path;
}

export default function MobilePredictionMeter({ confidence = 0, label = "", colors = defaultColors }) {
  const pct = Math.min(100, Math.max(0, confidence));
  const arcEnd = pct * 3.6;

  const fillColor =
    pct >= 70 ? "#E74C3C" :
    pct >= 40 ? "#F5A623" : "#27AE60";

  const trackPath = makeArcPath(CX, CY, R, 0, 360);
  const fillPath = makeArcPath(CX, CY, R, 0, arcEnd);

  return (
    <View style={styles.wrapper}>
      <Canvas style={{ width: SIZE, height: SIZE }}>
        <Path path={trackPath} color={colors.border} style="stroke" strokeWidth={STROKE} />
        {pct > 0 && (
          <Path path={fillPath} color={fillColor} style="stroke" strokeWidth={STROKE} strokeCap="round" />
        )}
      </Canvas>
      <View style={styles.label}>
        <Text style={[styles.pct, { color: fillColor }]}>{pct}%</Text>
        <Text style={[styles.sub, { color: colors.textMuted }]}>{label || "confidence"}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { alignItems: "center" },
  label: {
    position: "absolute",
    top: 0, left: 0, right: 0, bottom: 0,
    alignItems: "center",
    justifyContent: "center",
  },
  pct: { fontSize: 18, fontWeight: "700" },
  sub: { fontSize: 9, letterSpacing: 0.5, marginTop: 2 },
});
