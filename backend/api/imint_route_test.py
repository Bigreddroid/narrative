"""
Property tests for the /imint route's hash-first dedupe. Run from repo root:
    python -m backend.api.imint_route_test

No DB and no model: the session and vision services are stubbed so the contract
under test is exactly the one that matters — a re-upload of bytes we already
interpreted must be answered from the database BEFORE any vision call is made
(two llava passes cost minutes on CPU) and before the cost guard is consulted
(dedupe spends nothing, so it must keep working while the LLM budget is out).
"""

import asyncio
import io
import sys
import uuid
from types import SimpleNamespace

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252

from starlette.datastructures import Headers, UploadFile

from backend.api.routes import imint as route
from backend.services import cost_guard, imint

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


# ── Stubs ─────────────────────────────────────────────────────────────────────

class _Result:
    def __init__(self, row):
        self._row = row

    def scalars(self):
        return self

    def first(self):
        return self._row


class _Db:
    """Stands in for the AsyncSession: every execute() returns the configured row."""

    def __init__(self, row=None):
        self.row = row
        self.executed = 0

    async def execute(self, _query):
        self.executed += 1
        return _Result(self.row)


def _upload(data=b"not-really-a-jpeg", content_type="image/jpeg"):
    return UploadFile(file=io.BytesIO(data), filename="photo.jpg",
                      headers=Headers({"content-type": content_type}))


_user = SimpleNamespace(tier="pro")


# ── _existing_event_id resolves rows the way the operator should land on them ──

ok("no prior upload → None",
   asyncio.run(route._existing_event_id(_Db(None), "abc")) is None)

_eid = uuid.uuid4()
ok("prior upload → its event id",
   asyncio.run(route._existing_event_id(_Db(SimpleNamespace(id=_eid, merged_into_id=None)), "abc")) == str(_eid))

_canon = uuid.uuid4()
ok("a folded event points at its canonical",
   asyncio.run(route._existing_event_id(
       _Db(SimpleNamespace(id=_eid, merged_into_id=_canon)), "abc")) == str(_canon))


# ── The route answers a re-upload without touching the model or the budget ────
# Tripwires: if the dedupe path ever calls the interpreter or the cost guard,
# these raise and the test fails loudly.

def _no_vision(*_a, **_k):
    raise AssertionError("vision was called on a deduped upload")


async def _no_budget_check(_db):
    raise AssertionError("cost guard was consulted on a deduped upload")


_real_interpret = imint.interpret
_real_allowed = cost_guard.llm_allowed
try:
    imint.interpret = _no_vision
    cost_guard.llm_allowed = _no_budget_check

    out = asyncio.run(route.interpret_image(
        db=_Db(SimpleNamespace(id=_eid, merged_into_id=None)),
        user=_user, file=_upload(), persist=True))
    ok("re-upload is answered from the database", out.get("deduped") is True)
    ok("the existing event id is returned", out["event"]["event_id"] == str(_eid))
    ok("the dedupe response reads as a persisted event", out["event"]["persisted"] is True)
    ok("honest scope note rides the dedupe response too",
       "no satellite tasking" in out.get("scope", "").lower())
finally:
    imint.interpret = _real_interpret
    cost_guard.llm_allowed = _real_allowed


# ── A first-time upload must NOT be short-circuited ───────────────────────────
# The db has no row for this sha, so the request proceeds to the cost guard —
# proven by the guard being reached (it reports the budget exhausted, which the
# route surfaces as 503 rather than silently swallowing).

async def _budget_out(_db):
    return False


_real_allowed = cost_guard.llm_allowed
try:
    cost_guard.llm_allowed = _budget_out
    try:
        asyncio.run(route.interpret_image(db=_Db(None), user=_user, file=_upload(), persist=True))
        ok("fresh upload proceeds past dedupe to the cost guard", False)
    except Exception as exc:  # noqa: BLE001 — expecting the route's own HTTPException
        ok("fresh upload proceeds past dedupe to the cost guard",
           getattr(exc, "status_code", None) == 503)
finally:
    cost_guard.llm_allowed = _real_allowed


# ── persist=false is an explicit request for a fresh read-out ─────────────────
# Even with a matching row in the db, the interpreter must run. The stub model is
# unavailable, which the service reports honestly — proof the vision leg was taken.

_real_interpret = imint.interpret
_real_allowed = cost_guard.llm_allowed
try:
    imint.interpret = lambda *_a, **_k: {"available": False, "reason": "stub", "scope": imint.SCOPE_NOTE}

    async def _allowed(_db):
        return True

    cost_guard.llm_allowed = _allowed
    db = _Db(SimpleNamespace(id=_eid, merged_into_id=None))
    out = asyncio.run(route.interpret_image(db=db, user=_user, file=_upload(), persist=False))
    ok("persist=false skips dedupe and reaches the interpreter",
       out.get("deduped") is None and out["reason"] == "stub")
    ok("persist=false never queries for an existing event", db.executed == 0)
finally:
    imint.interpret = _real_interpret
    cost_guard.llm_allowed = _real_allowed


print(f"\nimint route: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
