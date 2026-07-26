// ─────────────────────────────────────────────────────────────────────────────
// auditAdapter — reconcile the SERVER's register audit with what the board expects.
//
// The audit exists twice on purpose: `registryAudit.js` runs in the browser over
// whatever is on screen, and `backend/services/registry_audit.py` runs during an
// import over what is being written to the database. The two agree on the checks
// (their suites mirror each other case for case) but not on two surface details,
// and both would fail silently rather than loudly:
//
//   1. The server speaks snake_case (`by_check`, `affected_sites`, `site_id`).
//      A missing `affectedSites` renders as an empty cell, not an error.
//
//   2. 🔴 The server names a row by the CUSTOMER's identifier — "AFR08" — because
//      that is what makes a finding actionable to the person who owns the register.
//      The board selects sites by OUR internal id. Handing the raw value to
//      `setSelected` would make every finding on the integrity panel a dead click:
//      the row highlights, nothing opens, and nothing says why.
//
// So this maps the customer's identifier back to the internal id, and leaves
// `siteId` null when it cannot — a finding that cannot be resolved to a row on the
// board is rendered as plain text rather than a button that does nothing.
//
// Pure + unit-tested (auditAdapter.test.mjs). No network, no React.
// ─────────────────────────────────────────────────────────────────────────────

/**
 * @param audit  the payload from GET /sites or POST /sites/import
 * @param sites  the register as the board holds it (internal `id` + `external_id`)
 * @returns the audit in the shape registryAudit.js produces
 */
export function adaptAudit(audit, sites = []) {
  if (!audit) return null;
  // Already the browser shape (the sample board's own audit) — leave it alone.
  if (audit.byCheck !== undefined) return audit;

  // A duplicate identifier maps to whichever row we saw first. That is acceptable:
  // the finding for a duplicate is ABOUT the collision, so landing on either of the
  // two rows shows the user the thing they need to look at.
  const byExternal = new Map();
  for (const s of sites) {
    const ext = s?.external_id;
    if (ext != null && String(ext) !== "" && !byExternal.has(String(ext))) {
      byExternal.set(String(ext), s.id);
    }
  }

  const findings = (audit.findings || []).map((f) => ({
    ...f,
    // What the customer calls this row — kept, because it is what they will search
    // their own spreadsheet for.
    siteRef: f.site_id ?? null,
    siteName: f.site_name ?? null,
    siteId: f.site_id != null ? (byExternal.get(String(f.site_id)) ?? null) : null,
  }));

  return {
    findings,
    byCheck: audit.by_check ?? {},
    checked: audit.checked ?? 0,
    // Counted from the RESOLVED findings would be wrong — a row we cannot map is
    // still an affected row. The server's count is the truthful one.
    affectedSites: audit.affected_sites ?? 0,
    critical: audit.critical ?? 0,
    warnings: audit.warnings ?? 0,
    clean: audit.clean === true,
  };
}
