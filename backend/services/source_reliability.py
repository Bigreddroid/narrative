"""
NATO Admiralty source-reliability grading — deterministic, no LLM.

HUMINT's missing layer (Phase 2e): an open-source report is only as trustworthy as
its provenance and how many *independent* sources corroborate it. This turns those
two signals into the standard NATO Admiralty grade — a letter for SOURCE RELIABILITY
and a digit for INFORMATION CREDIBILITY (e.g. "B2") — so an analyst can weigh a
HUMINT card at a glance, exactly as they would a real intelligence report.

    Reliability (source):   A completely · B usually · C fairly · D not usually ·
                            E unreliable · F cannot be judged
    Credibility (info):     1 confirmed · 2 probably true · 3 possibly true ·
                            4 doubtful · 5 improbable · 6 cannot be judged

Both axes are computed from things we already measure, with NO model call:

  • RELIABILITY (letter) — a provenance prior for the source family (primary sensors
    and agencies rank high; open aggregators lower; unknown = "cannot be judged"),
    nudged by the source's own OSINT-triage track record (kept-rate + confidence)
    when we have enough decisions to be meaningful.
  • CREDIBILITY (digit) — how many *independent* feeds corroborated the report in
    geo+time (from consequence_engine.corroboration). More convergence ⇒ a lower,
    stronger digit. This is what makes the grade *rise with corroboration*.

Deterministic and explainable by construction: same inputs → same grade, with a
rationale list a human can audit. Nothing here leaks the tuned CPE constants.
"""

from __future__ import annotations

from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.osint_triage_decision import OsintTriageDecision

# ── The Admiralty scales ──────────────────────────────────────────────────────
RELIABILITY_CODES = ("A", "B", "C", "D", "E", "F")
RELIABILITY_LABELS = {
    "A": "Completely reliable",
    "B": "Usually reliable",
    "C": "Fairly reliable",
    "D": "Not usually reliable",
    "E": "Unreliable",
    "F": "Cannot be judged",
}
CREDIBILITY_LABELS = {
    1: "Confirmed by other sources",
    2: "Probably true",
    3: "Possibly true",
    4: "Doubtful",
    5: "Improbable",
    6: "Cannot be judged",
}
_CANNOT_JUDGE_LETTER = 5  # index of "F"

# ── Provenance prior ──────────────────────────────────────────────────────────
# A source's baseline reliability from WHAT KIND of source it is, matched on
# substrings of the (lowercased) source string. Ordered most→least specific; first
# hit wins. Index maps into RELIABILITY_CODES (0 = A … 5 = F). Anything unmatched is
# treated as unknown provenance (see grade()), which — absent a track record — is F.
_PROVENANCE_PRIOR: tuple[tuple[tuple[str, ...], int], ...] = (
    # A — primary instruments / authoritative sensor feeds (direct measurement)
    (("usgs", "gdacs", "noaa", "nasa", "eonet", "opensky", "aisstream", "ais_", "gdelt_quake"), 0),
    # B — official agencies & established wires (curated, accountable)
    (("cisa", "nvd", "cve", "reuters", "apnews", "bbc", "gov", "official", "launch"), 1),
    # C — open aggregators / broad OSINT collectors (wide net, mixed quality)
    (("gdelt", "osint_gdelt", "market", "equit", "vix"), 2),
    # D — syndicated RSS / uncurated open feeds (highly variable)
    (("osint_rss", "rss", "blog", "telegram", "social"), 3),
)

# Enough logged triage decisions before a source's track record is allowed to move
# its letter — below this the sample is too small to trust either way.
_MIN_HISTORY = 8
_KEEP_STRONG = 0.70   # kept-rate at/above which a source earns a step toward A
_KEEP_WEAK = 0.30     # kept-rate below which a source loses a step toward F
_CONF_STRONG = 0.55   # avg triage confidence required alongside a strong kept-rate


def _provenance_index(source: str | None) -> int | None:
    """Baseline reliability index for a source family, or None if unrecognised."""
    if not source:
        return None
    s = source.lower()
    for needles, idx in _PROVENANCE_PRIOR:
        if any(n in s for n in needles):
            return idx
    return None


def _reliability(source: str | None, history: dict | None) -> tuple[int, list[str]]:
    """Resolve the reliability letter index (0=A … 5=F) with a rationale trail."""
    reasons: list[str] = []
    prior = _provenance_index(source)

    if prior is not None:
        idx = prior
        reasons.append(f"provenance: {RELIABILITY_LABELS[RELIABILITY_CODES[idx]].lower()} source class")
    elif history and history.get("n", 0) >= _MIN_HISTORY:
        # Unknown family but we've observed it — start cautious ("not usually reliable")
        # and let the track record move it from there.
        idx = 3
        reasons.append("provenance: unrecognised source, judged on track record")
    else:
        # No known class and no track record → genuinely cannot be judged.
        reasons.append("provenance: unknown source, no track record")
        return _CANNOT_JUDGE_LETTER, reasons

    # Track-record nudge from the OSINT triage flywheel, when the sample is large enough.
    if history and history.get("n", 0) >= _MIN_HISTORY:
        keep = history.get("kept_rate", 0.0)
        conf = history.get("avg_confidence") or 0.0
        n = history["n"]
        if keep >= _KEEP_STRONG and conf >= _CONF_STRONG and idx > 0:
            idx -= 1
            reasons.append(f"track record: {keep:.0%} kept over {n} decisions (conf {conf:.2f}) → +1 step")
        elif keep < _KEEP_WEAK and idx < _CANNOT_JUDGE_LETTER:
            idx += 1
            reasons.append(f"track record: only {keep:.0%} kept over {n} decisions → −1 step")
        else:
            reasons.append(f"track record: {keep:.0%} kept over {n} decisions (no change)")

    return idx, reasons


def _credibility(corroboration_count: int, reliability_idx: int) -> tuple[int, list[str]]:
    """Resolve the credibility digit (1=confirmed … 6=cannot be judged) from how many
    INDEPENDENT feeds corroborated the report. More convergence ⇒ stronger digit."""
    n = max(0, int(corroboration_count or 0))
    reasons: list[str] = []

    if n >= 3:
        digit = 1
        reasons.append(f"{n} independent sources converged → confirmed")
    elif n == 2:
        digit = 2
        reasons.append("2 independent sources converged → probably true")
    elif n == 1:
        digit = 3
        reasons.append("1 independent source corroborated → possibly true")
    else:
        # Uncorroborated: lean on the source's own reliability. A reliable single
        # source is "possibly true"; an unreliable one is "doubtful"; an unjudgeable
        # source with nothing to corroborate it "cannot be judged".
        if reliability_idx <= 1:        # A / B
            digit = 3
            reasons.append("single reliable source, no corroboration → possibly true")
        elif reliability_idx >= _CANNOT_JUDGE_LETTER:  # F
            digit = 6
            reasons.append("no corroboration and source cannot be judged")
        else:
            digit = 4
            reasons.append("single unverified source, no corroboration → doubtful")
    return digit, reasons


def grade(source: str | None, corroboration_count: int = 0,
          history: dict | None = None) -> dict:
    """The NATO Admiralty grade for one report — pure and deterministic.

    Args:
      source: the event's source string (e.g. "osint_gdelt", "usgs").
      corroboration_count: independent corroborating feeds (from corroboration.corroborate).
      history: optional {n, kept_rate, avg_confidence} triage track record for `source`.

    Returns a fully-labelled grade dict, e.g.:
      {"grade": "B2", "reliability": {"code": "B", "label": "Usually reliable"},
       "credibility": {"code": 2, "label": "Probably true"}, "rationale": [...]}
    """
    r_idx, r_reasons = _reliability(source, history)
    c_digit, c_reasons = _credibility(corroboration_count, r_idx)
    letter = RELIABILITY_CODES[r_idx]
    return {
        "grade": f"{letter}{c_digit}",
        "reliability": {"code": letter, "label": RELIABILITY_LABELS[letter]},
        "credibility": {"code": c_digit, "label": CREDIBILITY_LABELS[c_digit]},
        "rationale": r_reasons + c_reasons,
    }


async def attach_grades(db: AsyncSession, corroboration: dict, events: list[dict]) -> None:
    """Attach a NATO Admiralty reliability grade to each corroborated entry, in place.

    Shared by /exposure and the view-scoped /events/corroboration so both endpoints
    grade convergence identically: the reliability letter comes from the event's
    source provenance + its OSINT-triage track record, and the credibility digit from
    how many independent feeds corroborated it — so the grade a card shows literally
    *rises* with corroboration. Deterministic, no LLM.

    `events` is any list of dicts each carrying at least "id" and "source" (and
    optionally "discipline"). A corroboration entry with no matching event is graded
    on a null source (→ F, cannot be judged) rather than skipped, so every entry the
    UI renders carries a grade. One grouped history query for the whole set.
    """
    if not corroboration:
        return
    by_id = {e.get("id"): e for e in events}
    sources = [by_id.get(eid, {}).get("source") for eid in corroboration]
    history = await source_history_map(db, [s for s in sources if s])
    for eid, entry in corroboration.items():
        ev = by_id.get(eid) or {}
        src = ev.get("source")
        entry["reliability"] = grade(src, entry.get("count", 0), history.get(src))
        entry["discipline"] = ev.get("discipline")


async def source_history_map(db: AsyncSession, sources: list[str]) -> dict[str, dict]:
    """One grouped query → {source: {n, kept_rate, avg_confidence}} for the given
    sources, from the OSINT triage decision log. Sources with no rows are omitted
    (grade() then treats them as no-track-record)."""
    wanted = sorted({s for s in sources if s})
    if not wanted:
        return {}
    kept_int = func.sum(func.cast(OsintTriageDecision.kept, Integer))
    rows = (await db.execute(
        select(
            OsintTriageDecision.source,
            func.count().label("n"),
            kept_int.label("kept"),
            func.avg(OsintTriageDecision.confidence).label("avg_conf"),
        )
        .where(OsintTriageDecision.source.in_(wanted))
        .group_by(OsintTriageDecision.source)
    )).all()
    out: dict[str, dict] = {}
    for src, n, kept, avg_conf in rows:
        n = int(n or 0)
        out[src] = {
            "n": n,
            "kept_rate": (int(kept or 0) / n) if n else 0.0,
            "avg_confidence": float(avg_conf) if avg_conf is not None else None,
        }
    return out
