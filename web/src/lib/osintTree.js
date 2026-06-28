// Group a flat OSINT tool list into a category → subcategory → tools tree for the
// browsable hierarchy view (mirrors the osintframework.com structure). Insertion
// order is preserved, so categories/subfolders appear in the snapshot's own order.
//
// A tool with an empty `subcategory` sits directly under its category; it lands in
// a leading "" subgroup the UI renders without a sub-header.
export function buildTree(tools) {
  const cats = new Map(); // category -> Map(subName -> tool[])
  for (const t of tools || []) {
    const cat = t.category || "Other";
    const sub = t.subcategory || "";
    if (!cats.has(cat)) cats.set(cat, new Map());
    const subs = cats.get(cat);
    if (!subs.has(sub)) subs.set(sub, []);
    subs.get(sub).push(t);
  }
  return [...cats.entries()].map(([category, subs]) => {
    const subList = [...subs.entries()].map(([name, items]) => ({ name, tools: items }));
    const count = subList.reduce((n, s) => n + s.tools.length, 0);
    return { category, count, subs: subList };
  });
}
