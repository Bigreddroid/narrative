// ─────────────────────────────────────────────────────────────────────────────
// registryAudit — integrity checks over a customer's site register.
//
// Why this exists: the site register is the join key for every per-site number a
// security platform produces. If a row is duplicated, or carries the wrong or a
// missing country, every downstream figure inherits the error — including the ones
// that reach a board. Observed in a production incumbent console: the same site
// identifier present twice under two different countries, and another row with no
// country at all.
//
// So this runs before any alerting and hands back what is broken. It is the one
// piece of value we can deliver on day one, against data the customer already has,
// with nothing to take on trust — every finding names the rows it came from.
//
// Pure + unit-tested (registryAudit.test.mjs). No network, no React.
// ─────────────────────────────────────────────────────────────────────────────

export const SEVERITY = { critical: 3, warning: 2, info: 1 };

export const CHECK_LABELS = {
  duplicate_id: "Duplicate site identifier",
  conflicting_country: "Same identifier, different countries",
  duplicate_location: "Two sites at the same name and city",
  missing_country: "No country on the record",
  unmapped_country: "Country has no calendar mapping",
  missing_coordinates: "No usable coordinates",
  invalid_coordinates: "Coordinates outside valid range",
  null_island: "Coordinates at 0°,0°",
  missing_headcount: "No headcount — cannot be counted in exposure",
  country_outlier: "Coordinates far from every other site in its country",
};

const CHECK_SEVERITY = {
  duplicate_id: "critical",
  conflicting_country: "critical",
  invalid_coordinates: "critical",
  null_island: "critical",
  missing_coordinates: "critical",
  missing_country: "warning",
  duplicate_location: "warning",
  country_outlier: "warning",
  unmapped_country: "info",
  missing_headcount: "warning",
};

const isNum = (v) => typeof v === "number" && Number.isFinite(v);
const norm = (s) => String(s ?? "").trim().toLowerCase();

// Great-circle distance, inlined so this lib stays dependency-free and usable
// server-side during an import/onboarding job.
function km(lat1, lng1, lat2, lng2) {
  const R = 6371, r = Math.PI / 180;
  const dLat = (lat2 - lat1) * r, dLng = (lng2 - lng1) * r;
  const a = Math.sin(dLat / 2) ** 2
    + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
}

/**
 * Audit a site register.
 * @param sites  the customer's site list
 * @param opts.countryCodes  country → ISO map (an unmapped country silently loses
 *                           its public-holiday layer, so it is worth surfacing)
 * @param opts.outlierKm     distance beyond which a site is flagged as sitting far
 *                           from its country's other sites
 */
export function auditRegister(sites = [], opts = {}) {
  const { countryCodes = {}, outlierKm = 3000 } = opts;
  const findings = [];
  const add = (check, site, detail) => findings.push({
    check, label: CHECK_LABELS[check], severity: CHECK_SEVERITY[check],
    rank: SEVERITY[CHECK_SEVERITY[check]],
    siteId: site?.id ?? null, siteName: site?.name ?? null, detail,
  });

  // ── duplicates ─────────────────────────────────────────────────────────────
  const byId = new Map(), byNameCity = new Map();
  for (const s of sites) {
    if (s?.id != null) {
      const k = norm(s.id);
      if (!byId.has(k)) byId.set(k, []);
      byId.get(k).push(s);
    }
    const nk = `${norm(s?.name)}|${norm(s?.city)}`;
    if (nk !== "|") {
      if (!byNameCity.has(nk)) byNameCity.set(nk, []);
      byNameCity.get(nk).push(s);
    }
  }
  for (const [, group] of byId) {
    if (group.length < 2) continue;
    const countries = [...new Set(group.map((g) => norm(g.country)).filter(Boolean))];
    // The precise failure observed in the wild: one identifier, two countries.
    if (countries.length > 1) {
      add("conflicting_country", group[0],
        `${group.length} rows share this identifier across ${countries.length} countries: ${group.map((g) => g.country || "—").join(", ")}`);
    } else {
      add("duplicate_id", group[0], `${group.length} rows share this identifier`);
    }
  }
  for (const [, group] of byNameCity) {
    if (group.length < 2) continue;
    if (new Set(group.map((g) => norm(g.id))).size < 2) continue;  // already caught above
    add("duplicate_location", group[0],
      `${group.length} distinct records with the same name and city: ${group.map((g) => g.id).join(", ")}`);
  }

  // ── per-row field checks ───────────────────────────────────────────────────
  for (const s of sites) {
    if (!norm(s?.country)) add("missing_country", s, "Country is empty — this row cannot be grouped or given a calendar");
    else if (!countryCodes[s.country]) {
      add("unmapped_country", s, `"${s.country}" has no ISO mapping — public-holiday layer will be blank for this site`);
    }

    const lat = s?.lat, lng = s?.lng;
    if (!isNum(lat) || !isNum(lng)) add("missing_coordinates", s, "Latitude/longitude missing — the site cannot be mapped or scored against nearby signals");
    else if (Math.abs(lat) > 90 || Math.abs(lng) > 180) add("invalid_coordinates", s, `lat ${lat}, lng ${lng} is outside the valid range`);
    else if (lat === 0 && lng === 0) add("null_island", s, "Coordinates are exactly 0°,0° — almost always an import default, not a location");

    if (!isNum(s?.headcount) || s.headcount <= 0) {
      add("missing_headcount", s, "No headcount — this site contributes nothing to people-exposure figures");
    }
  }

  // ── geographic coherence ───────────────────────────────────────────────────
  // A site whose coordinates sit far from every other site in the same country is
  // usually a wrong-country row, which is how a register ends up claiming a
  // Johannesburg address in India.
  const byCountry = new Map();
  for (const s of sites) {
    if (!norm(s?.country) || !isNum(s?.lat) || !isNum(s?.lng)) continue;
    const k = norm(s.country);
    if (!byCountry.has(k)) byCountry.set(k, []);
    byCountry.get(k).push(s);
  }
  for (const [, group] of byCountry) {
    if (group.length < 3) continue;      // too few peers to judge
    for (const s of group) {
      let nearest = Infinity;
      for (const o of group) {
        if (o === s) continue;
        nearest = Math.min(nearest, km(s.lat, s.lng, o.lat, o.lng));
      }
      if (nearest > outlierKm) {
        add("country_outlier", s, `Nearest site in ${s.country} is ${Math.round(nearest)} km away — check the country on this row`);
      }
    }
  }

  findings.sort((a, b) => b.rank - a.rank || a.check.localeCompare(b.check));
  const byCheck = {};
  for (const f of findings) byCheck[f.check] = (byCheck[f.check] || 0) + 1;
  const affected = new Set(findings.map((f) => f.siteId).filter((x) => x != null));

  return {
    findings, byCheck,
    checked: sites.length,
    affectedSites: affected.size,
    critical: findings.filter((f) => f.severity === "critical").length,
    warnings: findings.filter((f) => f.severity === "warning").length,
    clean: findings.length === 0,
  };
}
