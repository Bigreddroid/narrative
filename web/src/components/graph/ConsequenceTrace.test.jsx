import { describe, it, expect } from "vitest";
import { buildTraceTree } from "./ConsequenceTrace.jsx";

// Shape mirrors GET /graph/event/{id}/trace:
//   root: A → B (grounded, score 90) → C (grounded, score 70)
//               → D (co_occurrence, score 40)
const trace = {
  root: { id: "A", title: "U.S. strikes Iran", category: "conflict" },
  nodes: [
    { id: "B", title: "Iran → Bahrain retaliation", category: "conflict", depth: 1, score: 90, kind: "semantic", grounded: true },
    { id: "D", title: "Ceasefire strain", category: "geopolitics", depth: 1, score: 40, kind: "co_occurrence", grounded: false },
    { id: "C", title: "Oil surges", category: "economics", depth: 2, score: 70, kind: "semantic", grounded: true },
  ],
  hops: [
    { from: "A", to: "B", kind: "semantic", grounded: true, mechanism: "sectors: defense, energy" },
    { from: "A", to: "D", kind: "co_occurrence", grounded: false, mechanism: "related" },
    { from: "B", to: "C", kind: "semantic", grounded: true, mechanism: "sectors: energy" },
  ],
  limited: false,
};

describe("buildTraceTree", () => {
  it("nests each hop under its parent (from → to)", () => {
    const tree = buildTraceTree(trace);
    expect(tree.id).toBe("A");
    expect(tree.children.map((c) => c.id).sort()).toEqual(["B", "D"]);
    const b = tree.children.find((c) => c.id === "B");
    expect(b.children.map((c) => c.id)).toEqual(["C"]); // C hangs off B, not the root
    const d = tree.children.find((c) => c.id === "D");
    expect(d.children).toEqual([]);
  });

  it("orders siblings grounded-first, then by score", () => {
    const tree = buildTraceTree(trace);
    // B (grounded, 90) must precede D (co-occurrence, 40)
    expect(tree.children.map((c) => c.id)).toEqual(["B", "D"]);
  });

  it("carries the incoming hop (mechanism/kind) onto each node", () => {
    const tree = buildTraceTree(trace);
    const b = tree.children.find((c) => c.id === "B");
    expect(b.hop.mechanism).toBe("sectors: defense, energy");
    expect(b.hop.kind).toBe("semantic");
  });

  it("returns null when there is no root", () => {
    expect(buildTraceTree(null)).toBeNull();
    expect(buildTraceTree({ nodes: [], hops: [] })).toBeNull();
  });

  it("yields an empty child list for an isolated (limited) root", () => {
    const tree = buildTraceTree({ root: { id: "X", title: "Lone event" }, nodes: [], hops: [], limited: true });
    expect(tree.children).toEqual([]);
  });

  it("does not revisit a node reached by a stray back-edge (cycle guard)", () => {
    const cyclic = {
      root: { id: "A", title: "root" },
      nodes: [{ id: "B", title: "b", score: 50, grounded: true, kind: "semantic" }],
      hops: [
        { from: "A", to: "B", kind: "semantic", grounded: true },
        { from: "B", to: "A", kind: "semantic", grounded: true }, // would loop back to root
      ],
    };
    const tree = buildTraceTree(cyclic);
    expect(tree.children.map((c) => c.id)).toEqual(["B"]);
    expect(tree.children[0].children).toEqual([]); // root not re-attached under B
  });
});
