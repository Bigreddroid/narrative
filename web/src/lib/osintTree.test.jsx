import { describe, it, expect } from "vitest";
import { buildTree } from "./osintTree.js";

const tools = [
  { id: "a", category: "Username", subcategory: "Search Engines" },
  { id: "b", category: "Username", subcategory: "Search Engines" },
  { id: "c", category: "Username", subcategory: "" },
  { id: "d", category: "Domain Name", subcategory: "DNS" },
];

describe("buildTree", () => {
  it("groups by category then subcategory", () => {
    const tree = buildTree(tools);
    expect(tree.map((c) => c.category)).toEqual(["Username", "Domain Name"]);
    const username = tree[0];
    expect(username.count).toBe(3);
    expect(username.subs.map((s) => s.name)).toEqual(["Search Engines", ""]);
    expect(username.subs[0].tools).toHaveLength(2);
    expect(username.subs[1].tools).toHaveLength(1);
  });

  it("preserves insertion order of categories and subfolders", () => {
    const tree = buildTree(tools);
    expect(tree[1].category).toBe("Domain Name");
    expect(tree[1].subs[0].name).toBe("DNS");
  });

  it("handles empty / missing input", () => {
    expect(buildTree([])).toEqual([]);
    expect(buildTree(undefined)).toEqual([]);
  });

  it("falls back to Other for a tool with no category", () => {
    const tree = buildTree([{ id: "x" }]);
    expect(tree[0].category).toBe("Other");
    expect(tree[0].subs[0].name).toBe("");
  });
});
