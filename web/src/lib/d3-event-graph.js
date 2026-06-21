import * as d3 from "d3";

/**
 * D3 force-directed event graph.
 * Used inside EventGraph when expanding the consequence connection web.
 * Spring physics: stiffness 300, damping 30 (via d3 force).
 */
export function createEventGraphSimulation(containerEl, width, height) {
  const svg = d3
    .select(containerEl)
    .append("svg")
    .attr("width", width)
    .attr("height", height);

  const defs = svg.append("defs");
  defs
    .append("marker")
    .attr("id", "arrow")
    .attr("viewBox", "0 -3 6 6")
    .attr("refX", 16)
    .attr("refY", 0)
    .attr("markerWidth", 6)
    .attr("markerHeight", 6)
    .attr("orient", "auto")
    .append("path")
    .attr("d", "M 0,-3 L 6,0 L 0,3")
    .attr("fill", "#21262D");

  const g = svg.append("g");

  svg.call(
    d3
      .zoom()
      .scaleExtent([0.3, 3])
      .on("zoom", (e) => g.attr("transform", e.transform))
  );

  const simulation = d3
    .forceSimulation()
    .force(
      "link",
      d3
        .forceLink()
        .id((d) => d.id)
        .distance(120)
        .strength(0.6)
    )
    .force("charge", d3.forceManyBody().strength(-400))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collision", d3.forceCollide().radius(30))
    .alphaDecay(0.03);

  let linkSel = g.append("g").attr("class", "links").selectAll("line");
  let nodeSel = g.append("g").attr("class", "nodes").selectAll("g");

  function update(nodes, links, { onNodeClick } = {}) {
    linkSel = linkSel
      .data(links, (d) => `${d.source.id || d.source}-${d.target.id || d.target}`)
      .join("line")
      .attr("stroke", "#21262D")
      .attr("stroke-width", (d) => 0.5 + (d.weight || 0.3) * 2)
      .attr("marker-end", "url(#arrow)")
      .attr("opacity", 0.4);

    const nodeEnter = nodeSel
      .data(nodes, (d) => d.id)
      .join(
        (enter) => {
          const ng = enter.append("g").attr("class", "node").call(drag(simulation));

          ng.append("circle")
            .attr("r", (d) => nodeRadius(d))
            .attr("fill", (d) => categoryColor(d.category))
            .attr("opacity", 0.9)
            .attr("cursor", "pointer")
            .on("click", (event, d) => onNodeClick?.(d));

          ng.append("text")
            .attr("dy", (d) => nodeRadius(d) + 12)
            .attr("text-anchor", "middle")
            .attr("fill", "#8B949E")
            .attr("font-size", 10)
            .text((d) => truncate(d.title || d.canonical_title || "", 24));

          return ng;
        },
        (update) => update,
        (exit) => exit.remove()
      );

    nodeSel = nodeEnter;

    simulation.nodes(nodes).on("tick", ticked);
    simulation.force("link").links(links);
    simulation.alpha(0.5).restart();
  }

  function ticked() {
    linkSel
      .attr("x1", (d) => d.source.x)
      .attr("y1", (d) => d.source.y)
      .attr("x2", (d) => d.target.x)
      .attr("y2", (d) => d.target.y);

    nodeSel.attr("transform", (d) => `translate(${d.x},${d.y})`);
  }

  function destroy() {
    simulation.stop();
    svg.remove();
  }

  return { update, destroy, simulation };
}

function drag(simulation) {
  return d3
    .drag()
    .on("start", (event, d) => {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    })
    .on("drag", (event, d) => {
      d.fx = event.x;
      d.fy = event.y;
    })
    .on("end", (event, d) => {
      if (!event.active) simulation.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    });
}

function nodeRadius(node) {
  if (node.is_root) return 24;
  return 8 + ((node.importance || 0) / 100) * 16;
}

function truncate(str, len) {
  return str.length > len ? str.slice(0, len) + "…" : str;
}

const CATEGORY_COLORS = {
  geopolitics: "#FF4B4B",
  economy: "#F5A623",
  climate: "#27AE60",
  health: "#2D9CDB",
  technology: "#9B51E0",
  conflict: "#EB5757",
  policy: "#56CCF2",
};

function categoryColor(cat) {
  return CATEGORY_COLORS[cat] || "#8B949E";
}
