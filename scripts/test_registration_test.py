"""Guard: every *_test.py under backend/ and scripts/ must be registered in
scripts/run_backend_tests.sh. This is the recurrence guard for the failure where a
hand-maintained bash array silently dropped the core tracer_test (45 assertions) so
it ran neither locally nor in CI. Pure — no network, no DB.

Run:  python -m scripts.test_registration_test
"""
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name}")


ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "scripts" / "run_backend_tests.sh"

# Parse the MODULES=( ... ) array: dotted module names, one per line.
runner_text = RUNNER.read_text(encoding="utf-8")
registered = set(re.findall(r"^\s*((?:backend|scripts)\.[A-Za-z0-9_.]+_test)\s*$",
                            runner_text, re.MULTILINE))
ok("runner parsed a non-empty MODULES array", len(registered) > 0)

# Discover every test module that actually exists on disk under the two roots.
discovered = set()
for base in ("backend", "scripts"):
    for path in (ROOT / base).rglob("*_test.py"):
        # skip caches / stale worktree copies that aren't part of the tree
        parts = path.relative_to(ROOT).parts
        if any(p in ("__pycache__", ".venv", "node_modules", ".claude") for p in parts):
            continue
        module = ".".join(path.relative_to(ROOT).with_suffix("").parts)
        discovered.add(module)

ok("discovered test modules on disk", len(discovered) > 0)

missing = sorted(discovered - registered)
ok(
    "every *_test.py is registered in run_backend_tests.sh"
    + (f" (MISSING: {', '.join(missing)})" if missing else ""),
    not missing,
)

# Also catch the reverse: a registered module whose file was deleted/renamed.
stale = sorted(m for m in registered if not (ROOT / (m.replace(".", "/") + ".py")).exists())
ok(
    "no registered module points at a missing file"
    + (f" (STALE: {', '.join(stale)})" if stale else ""),
    not stale,
)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
