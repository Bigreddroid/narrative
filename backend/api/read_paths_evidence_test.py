"""
Every read path that serves a LIST of events applies both gates. Run from repo root:
    python -m backend.api.read_paths_evidence_test

This guards a defect that has now recurred twice, and the shared module's own
docstring names it: "a filter that only some callers apply is not a filter."

    Round 1  the evidence gate lived inside routes/events.py and was applied to one
             of four read paths. The one it missed produced the deck's headline
             exposure number: 190 of the top 200 events (95%) were severed.
    Round 2  after extraction to consequence_engine/evidence.py, /feed, /search and
             /graph still had not been given it. Measured on the live corpus,
             35.5% of the rows behind /feed and /search were severed or a merged
             duplicate, and 52% of the rows behind the world map were severed —
             2,174 of 4,177 dots that opened to nothing.

Both rounds were invisible to every existing test, because a route that simply
omits a WHERE clause still returns 200 with plausible-looking events. Nothing
asserted the clause was THERE. So this test reads the route sources and checks.

Deliberately static (ast + source text, stdlib only): it needs no database, no
fixtures and no running API, so it cannot be skipped in the environment where it
matters, and it fails on the code as written rather than on data that happens to
be clean today. A new route that serves events and forgets a gate fails here on
the commit that adds it.
"""

import ast
import pathlib
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

passed = failed = 0


def ok(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}{(' — ' + detail) if detail else ''}")


ROUTES = pathlib.Path(__file__).resolve().parent / "routes"

# (module, function) pairs that serve a COLLECTION of events to a client. Each must
# gate on both "we can back this up" and "this is not a duplicate of another row".
SERVED_COLLECTIONS = [
    ("events.py",   "list_events"),
    ("exposure.py", "_load_graph"),
    ("feed.py",     "get_feed"),
    ("graph.py",    "get_world_graph"),
    ("graph.py",    "get_event_graph"),
    ("search.py",   "search_events"),
]

# Selects that legitimately carry no gate, with the reason. Listed explicitly so
# the sweep below can assert the set of ungated selects has not silently grown.
EXEMPT = {
    ("events.py",   "events_corroboration"):
        "looks up ids the CALLER supplied; it answers about those rows, it does not choose them",
    ("events.py",   "_source_grade"):
        "corroboration sibling search — an internal count, and a severed row carries "
        "no outlets so it cannot corroborate anything anyway (it does gate on merges)",
    ("imint.py",    "_existing_event_id"):
        "dedupe lookup by content hash; imint is a structured feed, always evidenced",
    ("imint.py",    "_persist"):
        "same dedupe lookup, resolving the pin the operator should land on",
}

EVIDENCE_GATE = ("evidenced()",)
MERGE_GATE = ("merged_into_id.is_(None)",)


def functions_with_event_select(path):
    """{function_name: source_segment} for every function selecting NarrativeEvent."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        seg = ast.get_source_segment(path.read_text(encoding="utf-8"), node) or ""
        if "select(NarrativeEvent" in seg:
            out[node.name] = seg
    return out


print("\n-- every served collection carries both gates --")
for module, func in SERVED_COLLECTIONS:
    path = ROUTES / module
    funcs = functions_with_event_select(path)
    src = funcs.get(func)
    if src is None:
        ok(f"{module}::{func} exists and selects events", False,
           f"not found (renamed? then update this list) — saw {sorted(funcs)}")
        continue
    ok(f"{module}::{func} gates on evidence",
       any(g in src for g in EVIDENCE_GATE), "no evidenced() in this function")
    ok(f"{module}::{func} gates on merged duplicates",
       any(g in src for g in MERGE_GATE), "no merged_into_id.is_(None) in this function")

print("\n-- no ungated event select has appeared outside the known exemptions --")
known = {(m, f) for m, f in SERVED_COLLECTIONS} | set(EXEMPT)
surprises = []
for path in sorted(ROUTES.glob("*.py")):
    for func, src in functions_with_event_select(path).items():
        key = (path.name, func)
        if key in known:
            continue
        gated = any(g in src for g in EVIDENCE_GATE) and any(g in src for g in MERGE_GATE)
        if not gated:
            surprises.append(f"{path.name}::{func}")
ok("no unreviewed ungated event read path", not surprises,
   "ungated and not on either list: " + ", ".join(surprises)
   + " — add the gates, or add it to EXEMPT with the reason it does not need them")

# The gates are only meaningful if the shared module still exposes them under the
# names the routes call. A rename that silently turned every check above into a
# string match on dead code is exactly the kind of thing this file exists to stop.
print("\n-- the shared module still provides what the routes import --")
ev_src = (pathlib.Path(__file__).resolve().parents[1]
          / "consequence_engine" / "evidence.py").read_text(encoding="utf-8")
ok("evidence.evidenced() is defined", "def evidenced()" in ev_src)
ok("evidence.state() is defined", "def state(" in ev_src)
for module in sorted({m for m, _ in SERVED_COLLECTIONS}):
    src = (ROUTES / module).read_text(encoding="utf-8")
    if "evidenced()" not in src:
        continue
    # The module is imported under several spellings across the routes
    # (`import evidence`, `evidence as ev`, or alongside siblings on one line),
    # so match the import STATEMENT via ast rather than a fixed substring —
    # otherwise this check passes or fails on formatting rather than on fact.
    imported = False
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ImportFrom) and "consequence_engine" in (node.module or ""):
            if any(a.name == "evidence" for a in node.names):
                imported = True
        elif isinstance(node, ast.Import):
            if any("consequence_engine.evidence" in a.name for a in node.names):
                imported = True
    ok(f"{module} imports the shared evidence module", imported,
       "calls evidenced() without importing it from the shared module")

print(f"\nread_paths_evidence: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
