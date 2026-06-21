import * as d3 from "d3";

/**
 * D3 world map renderer — used as fallback when Mapbox token is absent.
 * Renders a mercator projection on an SVG canvas.
 */
export function createWorldMapRenderer(svgEl, width, height) {
  const projection = d3
    .geoMercator()
    .scale((width / 2 / Math.PI) * 0.85)
    .translate([width / 2, height / 1.6])
    .center([0, 20]);

  const path = d3.geoPath().projection(projection);

  const svg = d3.select(svgEl);
  svg.selectAll("*").remove();

  const g = svg.append("g").attr("class", "world-map");

  let zoom = d3
    .zoom()
    .scaleExtent([0.5, 8])
    .on("zoom", (event) => {
      g.attr("transform", event.transform);
    });

  svg.call(zoom);

  let featuresGroup = g.append("g").attr("class", "features");
  let nodesGroup = g.append("g").attr("class", "nodes");
  let edgesGroup = g.append("g").attr("class", "edges").lower();

  async function loadGeoJSON() {
    try {
      const world = await d3.json(
        "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json"
      );
      const { feature } = await import("topojson-client");
      const countries = feature(world, world.objects.countries);

      featuresGroup
        .selectAll("path")
        .data(countries.features)
        .join("path")
        .attr("d", path)
        .attr("fill", "#0F1520")
        .attr("stroke", "#1A2030")
        .attr("stroke-width", 0.5);
    } catch {
      // Fallback — blank dark background
      svg
        .insert("rect", ":first-child")
        .attr("width", width)
        .attr("height", height)
        .attr("fill", "#080B12");
    }
  }

  function renderNodes(nodes, { onHover, onClick } = {}) {
    const circles = nodesGroup
      .selectAll("circle.event-node")
      .data(nodes, (d) => d.id)
      .join(
        (enter) =>
          enter
            .append("circle")
            .attr("class", "event-node")
            .attr("r", 0)
            .call((e) =>
              e.transition().duration(600).attr("r", (d) => nodeRadius(d))
            ),
        (update) =>
          update.call((u) =>
            u.transition().duration(300).attr("r", (d) => nodeRadius(d))
          ),
        (exit) =>
          exit.call((x) => x.transition().duration(300).attr("r", 0).remove())
      );

    circles
      .attr("cx", (d) => {
        const [x] = projection([d.lng, d.lat]);
        return x;
      })
      .attr("cy", (d) => {
        const [, y] = projection([d.lng, d.lat]);
        return y;
      })
      .attr("fill", (d) => categoryColor(d.category))
      .attr("opacity", (d) => (d.status === "resolved" ? 0.35 : 0.9))
      .attr("cursor", "pointer")
      .on("mouseover", (event, d) => onHover?.(d, event))
      .on("mouseout", () => onHover?.(null))
      .on("click", (event, d) => {
        event.stopPropagation();
        onClick?.(d);
      });
  }

  function renderEdges(edges, nodes) {
    const nodeById = new Map(nodes.map((n) => [n.id, n]));

    edgesGroup
      .selectAll("line.event-edge")
      .data(edges, (d) => d.id)
      .join("line")
      .attr("class", "event-edge")
      .attr("x1", (d) => {
        const n = nodeById.get(d.source);
        return n ? projection([n.lng, n.lat])[0] : 0;
      })
      .attr("y1", (d) => {
        const n = nodeById.get(d.source);
        return n ? projection([n.lng, n.lat])[1] : 0;
      })
      .attr("x2", (d) => {
        const n = nodeById.get(d.target);
        return n ? projection([n.lng, n.lat])[0] : 0;
      })
      .attr("y2", (d) => {
        const n = nodeById.get(d.target);
        return n ? projection([n.lng, n.lat])[1] : 0;
      })
      .attr("stroke", "#21262D")
      .attr("stroke-width", (d) => 0.5 + (d.weight || 0.3) * 2)
      .attr("opacity", 0.25);
  }

  function zoomIn() {
    svg.transition().call(zoom.scaleBy, 1.5);
  }

  function zoomOut() {
    svg.transition().call(zoom.scaleBy, 0.67);
  }

  function resetZoom() {
    svg.transition().call(zoom.transform, d3.zoomIdentity);
  }

  loadGeoJSON();

  return { renderNodes, renderEdges, zoomIn, zoomOut, resetZoom };
}

function nodeRadius(node) {
  const min = 4;
  const max = 20;
  return min + ((node.importance || 0) / 100) * (max - min);
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
