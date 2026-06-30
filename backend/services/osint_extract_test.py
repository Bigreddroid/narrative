"""Tests for server-side OSINT entity extraction (no network/DB).
Run from repo root:  python -m backend.services.osint_extract_test
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.services.osint_extract import extract_entities, entities_for_event

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


def kinds(text, **kw):
    return {(e["value"], e["kind"]) for e in extract_entities(text, **kw)}


# ── basic per-kind extraction ───────────────────────────────────────────────────
ok("extracts cve", ("CVE-2024-3094", "cve") in kinds("Patch for CVE-2024-3094 released."))
ok("extracts ip", ("8.8.8.8", "ip") in kinds("traffic to 8.8.8.8 spiked"))
ok("extracts crypto eth addr", ("0x" + "a" * 40, "crypto") in kinds("wallet 0x" + "a" * 40 + " drained"))
ok("extracts vessel imo", any(k == "vehicle" for _, k in kinds("vessel IMO 9074729 detained")))

# ── precision guards ─────────────────────────────────────────────────────────────
ok("rejects invalid ip octet", not any(k == "ip" for _, k in kinds("version 999.999.1.1 released")))
ok("rejects 0.0.0.0", not any(v == "0.0.0.0" for v, _ in kinds("bind 0.0.0.0 here")))
ok("empty text → none", extract_entities("") == [])
ok("plain prose → none", extract_entities("The president met with allies today.") == [])

# ── crypto wins over hash for 0x / base58 addresses ───────────────────────────────
eth = "0x" + "b" * 40
ek = {k for _, k in kinds(f"address {eth}")}
ok("eth address classed as crypto not hash", "crypto" in ek and "hash" not in {k for v, k in kinds(f"address {eth}") if v == eth})

# ── dedupe + cap ──────────────────────────────────────────────────────────────────
dup = extract_entities("8.8.8.8 and again 8.8.8.8")
ok("dedupes repeated value", len(dup) == 1)
many = "CVE-2020-0001 CVE-2020-0002 CVE-2020-0003 CVE-2020-0004"
ok("respects cap", len(extract_entities(many, cap=2)) == 2)

# ── entities_for_event scans consequence-map prose ────────────────────────────────
ev = entities_for_event(
    title="Cyber incident reported",
    summary="No indicators in summary.",
    consequence_map={"consensus_summary": "Exploit of CVE-2023-1234 observed from 1.2.3.4."},
)
ev_pairs = {(e["value"], e["kind"]) for e in ev}
ok("event extraction reads map prose (cve)", ("CVE-2023-1234", "cve") in ev_pairs)
ok("event extraction reads map prose (ip)", ("1.2.3.4", "ip") in ev_pairs)
ok("event extraction handles None map", isinstance(entities_for_event("hi 5.5.5.5", None, None), list))

print(f"\nosint_extract: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
