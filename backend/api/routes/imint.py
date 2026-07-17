"""
IMINT — POST /api/v1/imint.

Upload an image the operator already has; get back an imagery-intelligence read-out
(what it shows + the OODA reasoning trace, see backend/services/imint.py). Scope is
honestly bounded: interpretation of provided imagery only — no satellite tasking, no
commercial-imagery purchase. Paid-tier feature. Runs free on a local multimodal model
or Claude vision when paid APIs are enabled; degrades to an honest "unavailable"
result instead of fabricating an assessment.
"""

import asyncio
import base64
import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.api.dependencies import DbDep, UserDep
from backend.services import cost_guard, imint

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/imint", tags=["imint"])

_MAX_BYTES = 8 * 1024 * 1024  # 8 MB — generous for a photo/frame, bounds memory/cost
_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


@router.post("")
async def interpret_image(db: DbDep, user: UserDep, file: UploadFile = File(...)) -> dict:
    if user.tier == "free":
        raise HTTPException(status_code=402, detail="Imagery interpretation is a paid feature.")

    media_type = (file.content_type or "").lower()
    if media_type not in _ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, WebP or GIF image.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 8 MB).")

    # Blocks paid spend unless the active provider is free OR within the hard cap.
    if not await cost_guard.llm_allowed(db):
        raise HTTPException(status_code=503, detail="IMINT is temporarily unavailable (LLM budget or model offline).")

    image_b64 = base64.b64encode(data).decode("ascii")
    try:
        # interpret() wraps a synchronous, blocking vision call — offload it.
        return await asyncio.to_thread(imint.interpret, image_b64, media_type)
    except Exception as exc:  # noqa: BLE001 — safety net; the service degrades internally
        logger.error("IMINT interpretation failed: %s", exc)
        raise HTTPException(status_code=502, detail="The IMINT interpreter is unavailable right now.")
