"""
Reverse-image geolocation — POST /api/v1/geolocate.

Upload a photo; get back where it was probably taken plus the DANA-style OODA
reasoning trace (see backend/services/geolocate.py). Paid-tier feature. Runs free
on a local multimodal model, or Claude vision when paid APIs are enabled; degrades
to an honest "unavailable" result instead of fabricating coordinates.
"""

import asyncio
import base64
import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.api.dependencies import DbDep, UserDep
from backend.services import cost_guard, geolocate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/geolocate", tags=["geolocate"])

_MAX_BYTES = 8 * 1024 * 1024  # 8 MB — generous for a phone photo, bounds memory/cost
_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


@router.post("")
async def geolocate_image(db: DbDep, user: UserDep, file: UploadFile = File(...)) -> dict:
    if user.tier == "free":
        raise HTTPException(status_code=402, detail="Image geolocation is a paid feature.")

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
        raise HTTPException(status_code=503, detail="Geolocation is temporarily unavailable (LLM budget or model offline).")

    image_b64 = base64.b64encode(data).decode("ascii")
    try:
        # geolocate() wraps a synchronous, blocking vision call — offload it.
        return await asyncio.to_thread(geolocate.geolocate, image_b64, media_type)
    except Exception as exc:  # noqa: BLE001 — safety net; the service degrades internally
        logger.error("Geolocation failed: %s", exc)
        raise HTTPException(status_code=502, detail="The geolocator is unavailable right now.")
