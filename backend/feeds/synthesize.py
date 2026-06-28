"""
Deterministic consequence synthesis for free-feed signals — NOT the LLM, NOT mock.

Turns a normalized Signal (a real hazard/market/launch/conflict datum) into the
direct/indirect impacts + consequence chain the CPE consumes, via explicit rules.
Rule-based + explainable: the same defensible-IP property as the rest of the engine.
"""

# category → (direct-impact sectors, indirect-impact sectors)
SECTOR_MAP = {
    "disaster":  (["Infrastructure", "Shipping & Logistics"], ["Energy", "Insurance"]),
    "wildfire":  (["Energy", "Agriculture"],                  ["Air Quality", "Insurance"]),
    "storm":     (["Shipping & Logistics", "Aviation"],       ["Energy", "Agriculture"]),
    "flood":     (["Infrastructure", "Agriculture"],          ["Shipping & Logistics", "Insurance"]),
    "drought":   (["Agriculture"],                            ["Commodities", "Energy"]),
    "volcano":   (["Aviation", "Infrastructure"],             ["Agriculture", "Energy"]),
    "conflict":  (["Defense", "Energy"],                      ["Shipping & Logistics", "Commodities"]),
    "unrest":    (["Infrastructure", "Banking"],              ["Tourism", "Energy"]),
    "cyber":     (["Technology", "Banking"],                  ["Infrastructure"]),
    "sanction":  (["Banking"],                                ["Commodities", "Shipping & Logistics"]),
    "space":     (["Aerospace", "Technology"],                ["Telecommunications"]),
    "market":    (["Commodities", "Energy"],                  ["Shipping & Logistics"]),
    "disinfo":   (["Information Integrity", "Public Trust"],  ["Elections", "Financial Markets"]),
}
DEFAULT_SECTORS = (["Infrastructure"], ["Energy"])

# How likely a category is to keep escalating (drives the prediction score).
PRED_VOLATILITY = {
    "conflict": 0.92, "unrest": 0.85, "market": 0.82, "sanction": 0.75,
    "cyber": 0.70, "disaster": 0.60, "storm": 0.60, "flood": 0.55,
    "wildfire": 0.62, "drought": 0.45, "volcano": 0.50, "space": 0.35,
    "disinfo": 0.68,
}
# Concrete escalation phrasing per category (used in the prediction sentence).
ESCALATION = {
    "conflict": "military escalation and supply-route disruption",
    "unrest": "civil unrest and governance strain",
    "market": "market-volatility spillover",
    "sanction": "trade and banking friction",
    "cyber": "follow-on intrusions and outages",
    "disaster": "humanitarian and infrastructure strain",
    "storm": "transport and power disruption",
    "flood": "displacement and infrastructure damage",
    "wildfire": "air-quality and evacuation impacts",
    "drought": "crop and water stress",
    "volcano": "aviation and evacuation impacts",
    "space": "launch-cadence and orbital effects",
    "disinfo": "narrative manipulation and erosion of public trust",
}
DEFAULT_ESCALATION = "knock-on disruption"


def severity_from(importance: float) -> str:
    if importance >= 80:
        return "critical"
    if importance >= 60:
        return "high"
    if importance >= 40:
        return "medium"
    return "low"


def _timeframe(sev: str) -> str:
    return {"critical": "days", "high": "1–2 weeks",
            "medium": "several weeks"}.get(sev, "a month")


def predict_from(cat: str, importance: float, severity: str, geo: list[str], sectors: list[str]) -> tuple[int, str]:
    """Deterministic (score, reasoning) — concrete likelihood of continued escalation."""
    vol = PRED_VOLATILITY.get(cat, 0.50)
    score = round(min(95, max(20, importance * vol + 8)))
    where = ", ".join(geo[:2]) if geo and geo[0] != "the affected area" else "the affected area"
    reasoning = (
        f"~{score}% likelihood of continued {ESCALATION.get(cat, DEFAULT_ESCALATION)} "
        f"affecting {', '.join(sectors)} within {_timeframe(severity)}, given the situation in {where}."
    )
    return score, reasoning


def synthesize(signal: dict) -> dict:
    """Signal → EventConsequenceMap-shaped dict (direct/indirect impacts + chain)."""
    cat = signal.get("category", "disaster")
    imp = signal.get("importance", 50)
    title = signal.get("title", "Event")
    geo = signal.get("geography") or ["the affected area"]
    direct_sectors, indirect_sectors = SECTOR_MAP.get(cat, DEFAULT_SECTORS)
    sev, isev = severity_from(imp), severity_from(max(0, imp - 25))

    direct = [{"sector": s, "severity": sev,
               "description": f"{title} — direct pressure on {s.lower()}."} for s in direct_sectors]
    indirect = [{"sector": s, "severity": isev,
                 "description": f"Second-order pressure on {s.lower()}."} for s in indirect_sectors]
    chain = [
        {"type": "VERIFIED FACT", "content": signal.get("summary") or title},
        {"type": "INFERRED MECHANISM",
         "content": f"{', '.join(direct_sectors)} exposed across {', '.join(geo[:3])}."},
        {"type": "SPECULATIVE EFFECT",
         "content": f"Knock-on pressure on {', '.join(indirect_sectors) or 'connected sectors'} if conditions persist."},
    ]
    pred_score, pred_reasoning = predict_from(cat, imp, sev, geo, direct_sectors)
    return {
        "consensus_summary": signal.get("summary") or title,
        "consequence_chain": chain,
        "direct_impact": direct,
        "indirect_impact": indirect,
        "confidence": "high" if imp >= 70 else "medium",
        "sources_analyzed": [signal.get("source", "feed")],
        "disputed_points": [],
        "affected_sectors": direct_sectors + indirect_sectors,
        "prediction_score": pred_score,
        "prediction_reasoning": pred_reasoning,
    }
