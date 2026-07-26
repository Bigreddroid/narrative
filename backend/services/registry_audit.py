"""registry_audit — integrity checks over a customer's site register.

A faithful server-side mirror of ``web/src/lib/registryAudit.js``, whose header
already anticipated this: it was written pure and dependency-free specifically so
the same checks could run during an import job. The browser copy audits what is on
screen; this copy audits what is being written to the database, which is the moment
that actually matters — a defective row accepted here contaminates every per-site
number the platform later produces, including the ones that reach a board.

Why a port and not a shared implementation: there is no JS runtime in the API
container and no Python runtime in the browser bundle, and the repo has no
transpile step between them. The two copies are kept honest by running the SAME
scenarios against both — ``registry_audit_test.py`` mirrors the 28 assertions in
``registryAudit.test.mjs`` case for case, so a drift in either direction fails a
suite rather than silently producing two different verdicts on one register.

The identifier this audits is the CUSTOMER's own (``external_id`` in the database,
``id`` in the fixture and in the CSV they hand us). That is deliberate: duplicate
and conflicting identifiers are exactly the defects worth reporting, and they only
exist in their numbering, never in our surrogate UUIDs. So callers pass rows keyed
the way the customer wrote them, and the findings name rows the customer recognises.

Observed in a production incumbent console: the same site identifier present twice
under two different countries, and another row with no country at all.
"""

import math

SEVERITY = {"critical": 3, "warning": 2, "info": 1}

CHECK_LABELS = {
    "duplicate_id": "Duplicate site identifier",
    "conflicting_country": "Same identifier, different countries",
    "duplicate_location": "Two sites at the same name and city",
    "missing_country": "No country on the record",
    "unmapped_country": "Country has no calendar mapping",
    "missing_coordinates": "No usable coordinates",
    "invalid_coordinates": "Coordinates outside valid range",
    "null_island": "Coordinates at 0°,0°",
    "missing_headcount": "No headcount — cannot be counted in exposure",
    "country_outlier": "Coordinates far from every other site in its country",
}

CHECK_SEVERITY = {
    "duplicate_id": "critical",
    "conflicting_country": "critical",
    "invalid_coordinates": "critical",
    "null_island": "critical",
    "missing_coordinates": "critical",
    "missing_country": "warning",
    "duplicate_location": "warning",
    "country_outlier": "warning",
    "unmapped_country": "info",
    "missing_headcount": "warning",
}


def _is_num(v) -> bool:
    """Mirror of the JS ``isNum``: a real, finite number.

    ``bool`` is excluded explicitly — it is a subclass of ``int`` in Python, so a
    stray ``True`` from a CSV parser would otherwise pass as a latitude of 1.
    """
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    return math.isfinite(v)


def _norm(s) -> str:
    return str(s if s is not None else "").strip().lower()


def _km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance, inlined to match the JS copy's arithmetic exactly."""
    R, r = 6371.0, math.pi / 180.0
    d_lat = (lat2 - lat1) * r
    d_lng = (lng2 - lng1) * r
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(lat1 * r) * math.cos(lat2 * r) * math.sin(d_lng / 2) ** 2
    )
    return 2 * R * math.asin(min(1.0, math.sqrt(a)))


def audit_register(sites=None, country_codes=None, outlier_km: float = 3000) -> dict:
    """Audit a site register.

    :param sites: the customer's rows, as dicts keyed ``id, name, city, country,
                  lat, lng, headcount`` (``id`` being the customer's own identifier).
    :param country_codes: country → ISO map. An unmapped country silently loses its
                  public-holiday layer, so it is worth surfacing rather than swallowing.
    :param outlier_km: distance beyond which a site is flagged as sitting far from
                  its country's other sites.
    """
    sites = list(sites or [])
    country_codes = country_codes or {}
    findings: list[dict] = []

    def add(check: str, site, detail: str) -> None:
        sev = CHECK_SEVERITY[check]
        findings.append({
            "check": check,
            "label": CHECK_LABELS[check],
            "severity": sev,
            "rank": SEVERITY[sev],
            "site_id": (site or {}).get("id"),
            "site_name": (site or {}).get("name"),
            "detail": detail,
        })

    # ── duplicates ───────────────────────────────────────────────────────────
    by_id: dict[str, list] = {}
    by_name_city: dict[str, list] = {}
    for s in sites:
        if s.get("id") is not None:
            by_id.setdefault(_norm(s.get("id")), []).append(s)
        nk = f"{_norm(s.get('name'))}|{_norm(s.get('city'))}"
        if nk != "|":
            by_name_city.setdefault(nk, []).append(s)

    for group in by_id.values():
        if len(group) < 2:
            continue
        countries, seen = [], set()
        for g in group:
            c = _norm(g.get("country"))
            if c and c not in seen:
                seen.add(c)
                countries.append(c)
        # The precise failure observed in the wild: one identifier, two countries.
        if len(countries) > 1:
            named = ", ".join(g.get("country") or "—" for g in group)
            add("conflicting_country", group[0],
                f"{len(group)} rows share this identifier across "
                f"{len(countries)} countries: {named}")
        else:
            add("duplicate_id", group[0], f"{len(group)} rows share this identifier")

    for group in by_name_city.values():
        if len(group) < 2:
            continue
        if len({_norm(g.get("id")) for g in group}) < 2:
            continue  # already caught above
        ids = ", ".join(str(g.get("id")) for g in group)
        add("duplicate_location", group[0],
            f"{len(group)} distinct records with the same name and city: {ids}")

    # ── per-row field checks ─────────────────────────────────────────────────
    for s in sites:
        if not _norm(s.get("country")):
            add("missing_country", s,
                "Country is empty — this row cannot be grouped or given a calendar")
        elif not country_codes.get(s.get("country")):
            add("unmapped_country", s,
                f'"{s.get("country")}" has no ISO mapping — public-holiday layer '
                f"will be blank for this site")

        lat, lng = s.get("lat"), s.get("lng")
        if not _is_num(lat) or not _is_num(lng):
            add("missing_coordinates", s,
                "Latitude/longitude missing — the site cannot be mapped or scored "
                "against nearby signals")
        elif abs(lat) > 90 or abs(lng) > 180:
            add("invalid_coordinates", s,
                f"lat {lat}, lng {lng} is outside the valid range")
        elif lat == 0 and lng == 0:
            add("null_island", s,
                "Coordinates are exactly 0°,0° — almost always an import default, "
                "not a location")

        hc = s.get("headcount")
        if not _is_num(hc) or hc <= 0:
            add("missing_headcount", s,
                "No headcount — this site contributes nothing to people-exposure figures")

    # ── geographic coherence ─────────────────────────────────────────────────
    # A site whose coordinates sit far from every other site in the same country is
    # usually a wrong-country row, which is how a register ends up claiming a
    # Johannesburg address in India.
    by_country: dict[str, list] = {}
    for s in sites:
        if not _norm(s.get("country")) or not _is_num(s.get("lat")) or not _is_num(s.get("lng")):
            continue
        by_country.setdefault(_norm(s.get("country")), []).append(s)

    for group in by_country.values():
        if len(group) < 3:
            continue  # too few peers to judge
        for s in group:
            nearest = math.inf
            for o in group:
                if o is s:
                    continue
                nearest = min(nearest, _km(s["lat"], s["lng"], o["lat"], o["lng"]))
            if nearest > outlier_km:
                add("country_outlier", s,
                    f"Nearest site in {s.get('country')} is {round(nearest)} km away "
                    f"— check the country on this row")

    findings.sort(key=lambda f: (-f["rank"], f["check"]))
    by_check: dict[str, int] = {}
    for f in findings:
        by_check[f["check"]] = by_check.get(f["check"], 0) + 1
    affected = {f["site_id"] for f in findings if f["site_id"] is not None}

    return {
        "findings": findings,
        "by_check": by_check,
        "checked": len(sites),
        "affected_sites": len(affected),
        "critical": sum(1 for f in findings if f["severity"] == "critical"),
        "warnings": sum(1 for f in findings if f["severity"] == "warning"),
        "clean": len(findings) == 0,
    }
