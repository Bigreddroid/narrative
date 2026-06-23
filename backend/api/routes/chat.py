"""
AI analyst chat — POST /api/v1/chat.

Natural-language Q&A grounded ONLY in the live event graph + CPE exposure model
(see backend/services/analyst.py). Paid-tier feature (it spends model budget);
degrades gracefully to 503 when no Anthropic key is configured.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.api.dependencies import DbDep, UserDep
from backend.config import get_settings
from backend.services import analyst

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])
settings = get_settings()


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)


@router.post("")
async def chat(body: ChatRequest, db: DbDep, user: UserDep) -> dict:
    if user.tier == "free":
        raise HTTPException(status_code=402, detail="Analyst chat is a paid feature.")
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="Analyst chat is not configured yet.")
    try:
        return await analyst.answer_question(db, body.question.strip())
    except Exception as exc:  # noqa: BLE001
        logger.error("Analyst chat failed: %s", exc)
        raise HTTPException(status_code=502, detail="The analyst is unavailable right now.")
