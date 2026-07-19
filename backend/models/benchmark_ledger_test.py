"""Asserts the forward-ledger hashing is deterministic, order-independent, and
idempotent - the properties the public audit claim rests on. Pure (no DB, no LLM).
Run from repo root:  python -m backend.models.benchmark_ledger_test
"""

import sys
from datetime import datetime, date, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.models import benchmark_ledger as L
from scripts import publish_ledger as P

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


CREATED = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)

# --- content hash: deterministic + sensitive to every field ---
h1 = L.compute_content_hash("Will X happen?", 72, CREATED)
h2 = L.compute_content_hash("Will X happen?", 72, CREATED)
ok("content_hash deterministic", h1 == h2)
ok("content_hash is sha256 hex (64 chars)", len(h1) == 64 and all(c in "0123456789abcdef" for c in h1))
ok("content_hash changes with score", h1 != L.compute_content_hash("Will X happen?", 73, CREATED))
ok("content_hash changes with question", h1 != L.compute_content_hash("Will Y happen?", 72, CREATED))
ok("content_hash changes with created_at",
   h1 != L.compute_content_hash("Will X happen?", 72,
                                datetime(2026, 7, 20, 12, 0, 0, tzinfo=timezone.utc)))

# --- root hash: order-independent over the SET, empty is defined ---
a, b, c = "aa" * 32, "bb" * 32, "cc" * 32
ok("root_hash order-independent",
   L.compute_root_hash([a, b, c]) == L.compute_root_hash([c, a, b]))
ok("root_hash changes with membership",
   L.compute_root_hash([a, b]) != L.compute_root_hash([a, b, c]))
import hashlib
ok("root_hash empty == sha256('')",
   L.compute_root_hash([]) == hashlib.sha256(b"").hexdigest())

# recompute-by-hand matches (the external verifier's exact procedure)
manual = hashlib.sha256("".join(sorted([a, b, c])).encode()).hexdigest()
ok("root_hash matches manual recompute", L.compute_root_hash([a, b, c]) == manual)

# --- publisher pure helpers: build_entries + manifest file text ---
today = date(2026, 7, 19)
rows = [
    {"consequence_map_id": "m1", "question_text": "Q1", "prediction_score": 65, "created_at": CREATED},
    {"consequence_map_id": "m2", "question_text": "Q2", "prediction_score": 80, "created_at": CREATED},
]
entries = P.build_entries(rows, today)
ok("build_entries hashes match the model helper",
   entries[0]["content_hash"] == L.compute_content_hash("Q1", 65, CREATED))
ok("build_entries assigns unique ids", entries[0]["id"] != entries[1]["id"])
ok("build_entries stamps manifest_date", all(e["manifest_date"] == today for e in entries))
# Idempotent hashing: rebuilding the same rows yields the same content hashes.
again = P.build_entries(rows, today)
ok("build_entries content hashes stable across runs",
   [e["content_hash"] for e in entries] == [e["content_hash"] for e in again])

hashes = [e["content_hash"] for e in entries]
root = L.compute_root_hash(hashes)
text = P.manifest_file_text(today, root, hashes)
ok("manifest file carries the root", f"root_hash: {root}" in text)
ok("manifest file lists sorted hashes", text.strip().endswith(sorted(hashes)[-1]))
ok("manifest file entry_count correct", f"entry_count: {len(hashes)}" in text)
ok("manifest file is pure ASCII", text.isascii())

print(f"\nbenchmark_ledger: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
