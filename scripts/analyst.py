"""
The Narrative — terminal analyst.

Ask the SAME analyst the app uses, straight from a terminal. It reuses the live
services (retrieval + local $0 LLM), so answers match the app's /chat exactly and
the model is chosen by USE CASE, never hardcoded:

  - text question  -> backend.services.analyst.answer_question   -> llm.complete       -> local_llm_model (llama3.2)
  - --deep         -> backend.services.reasoner.answer_question_deep (OODA)
  - --image PATH   -> backend.services.geolocate.geolocate        -> llm.complete_vision -> vision model (llava)

If the needed model isn't reachable it degrades to an honest "unavailable" / templated
answer instead of a silently wrong one (the whole point of routing by use case).

Run (inside the demo stack):
    docker compose exec api python scripts/analyst.py "biggest risk to shipping"
    docker compose exec api python scripts/analyst.py --deep "how could a Hormuz closure hit me"
    docker compose exec api python scripts/analyst.py --image /path/to/photo.jpg
Or via the launchers:  ./analyst.sh "..."   |   analyst.cmd "..."
"""

import argparse
import asyncio
import base64
import itertools
import logging
import os
import sys
import time

# Make `backend` importable however this is launched (script dir is on sys.path,
# not the repo root, when run as `python scripts/analyst.py`).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importing backend.database creates the DB engine with echo=True, which raises the
# sqlalchemy.engine logger to INFO. Import it now, THEN clamp the noisy loggers back
# to WARNING — otherwise the analyst's answer is buried under raw SQL. This is a
# human-facing terminal tool, so quiet is correct here (the app keeps its logging).
import backend.database  # noqa: E402,F401 — imported for the engine-creation side effect
# echo=True emits SQL at INFO regardless of logger level, so turn echo off on the
# engine directly (the reliable switch), then also clamp the other chatty loggers.
try:
    backend.database.engine.echo = False
    backend.database.engine.sync_engine.echo = False
except Exception:  # noqa: BLE001 — best-effort quieting, never block the CLI
    pass
for _noisy in ("sqlalchemy.engine", "sqlalchemy.engine.Engine", "httpx", "backend"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

# ANSI (matches the boot intro's hacker-green palette).
ESC = "\033"
GRN = f"{ESC}[38;5;46m"
CYN = f"{ESC}[38;5;51m"
DIM = f"{ESC}[38;5;28m"
RED = f"{ESC}[38;5;196m"
RST = f"{ESC}[0m"


async def _with_spinner(coro, label: str):
    """Await `coro` while animating a green braille spinner + elapsed seconds, so a
    slow local ($0, CPU) model shows life instead of a dead terminal."""
    task = asyncio.ensure_future(coro)
    frames = itertools.cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
    start = time.perf_counter()
    interactive = sys.stdout.isatty()
    try:
        while not task.done():
            if interactive:
                el = time.perf_counter() - start
                sys.stdout.write(f"\r{GRN}> {label} {CYN}{next(frames)}{GRN} {el:4.0f}s{RST}")
                sys.stdout.flush()
            await asyncio.sleep(0.1)
    finally:
        if interactive:
            sys.stdout.write("\r" + " " * 60 + "\r")  # wipe the spinner line
            sys.stdout.flush()
    return await task


def _print_answer(res: dict) -> None:
    tag = f"{RED}[templated — live AI unavailable]{RST} " if res.get("degraded") else ""
    print(f"\n{CYN}◆ ANSWER{RST} {tag}\n")
    print(res.get("answer", "").strip() + "\n")

    pressure = res.get("pressure")
    if pressure is not None:
        print(f"{DIM}exposure pressure:{RST} {pressure}")
    if res.get("sectors"):
        print(f"{DIM}top sectors:{RST} {', '.join(res['sectors'][:6])}")
    if res.get("regions"):
        print(f"{DIM}top regions:{RST} {', '.join(res['regions'][:6])}")

    sources = res.get("sources") or []
    if sources:
        print(f"\n{DIM}sources ([n] cited above):{RST}")
        for i, s in enumerate(sources[:8], 1):
            title = (s.get("title") or s.get("canonical_title") or "").strip()
            print(f"  {CYN}[{i}]{RST} {title[:90]}")


async def _run_text(question: str, deep: bool) -> None:
    from backend.database import AsyncSessionLocal
    if deep:
        from backend.services.reasoner import answer_question_deep as run
    else:
        from backend.services.analyst import answer_question as run
    async with AsyncSessionLocal() as db:
        res = await _with_spinner(run(db, question), "thinking (deep)" if deep else "thinking")
    _print_answer(res)


async def _run_image(path: str) -> None:
    # Vision use case → geolocate → llm.complete_vision → llava. geolocate() is sync,
    # so run it in a thread and animate the same spinner.
    from backend.services.geolocate import geolocate
    try:
        with open(path, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode()
    except OSError as exc:
        print(f"{RED}Cannot read image: {exc}{RST}")
        return
    ext = os.path.splitext(path)[1].lower().lstrip(".") or "jpeg"
    media = "image/png" if ext == "png" else "image/jpeg"
    res = await _with_spinner(asyncio.to_thread(geolocate, b64, media), "geolocating")
    if not res.get("available", True) and "reason" in res:
        print(f"\n{RED}◆ VISION UNAVAILABLE{RST}\n{res['reason']}")
        print(f"{DIM}(pull the vision model:  docker compose exec ollama ollama pull llava){RST}")
        return
    print(f"\n{CYN}◆ GEOLOCATION{RST}\n")
    import json
    print(json.dumps(res, indent=2, default=str)[:2000])


def main() -> None:
    ap = argparse.ArgumentParser(description="The Narrative — terminal analyst (local, $0).")
    ap.add_argument("question", nargs="*", help="the question to ask the analyst")
    ap.add_argument("--deep", action="store_true", help="multi-step OODA reasoner (slower, deeper)")
    ap.add_argument("--image", metavar="PATH", help="geolocate a photo (vision model / llava)")
    args = ap.parse_args()

    print(f"{GRN}the narrative // terminal analyst{RST}")
    if args.image:
        asyncio.run(_run_image(args.image))
        return
    question = " ".join(args.question).strip()
    if not question:
        ap.error("ask a question, e.g.  analyst \"biggest risk to shipping right now\"")
    asyncio.run(_run_text(question, args.deep))


if __name__ == "__main__":
    main()
