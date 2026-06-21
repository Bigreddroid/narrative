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
}
DEFAULT_SECTORS = (["Infrastructure"], ["Energy"])


def severity_from(importance: float) -> str:
    if importance >= 80:
        return "critical"
    if importance >= 60:
        return "high"
    if importance >= 40:
        return "medium"
    return "low"


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
    return {
        "consensus_summary": signal.get("summary") or title,
        "consequence_chain": chain,
        "direct_impact": direct,
        "indirect_impact": indirect,
        "confidence": "high" if imp >= 70 else "medium",
        "sources_analyzed": [signal.get("source", "feed")],
        "disputed_points": [],
        "affected_sectors": direct_sectors + indirect_sectors,
    }
