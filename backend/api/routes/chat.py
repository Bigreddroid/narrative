"""
AI analyst chat — POST /api/v1/chat.

Natural-language Q&A grounded ONLY in the live event graph + CPE exposure model
(see backend/services/analyst.py). Paid-tier feature. Works with a free/local LLM
by default; when no LLM is available (or a paid provider hit its hard cap), the
analyst degrades to a templated, grounded answer rather than erroring.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.api.dependencies import DbDep, UserDep
from backend.services import analyst, operator_loop, reasoner

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    # "Deep analysis" runs the multi-step OODA reasoner (services/reasoner.py) instead
    # of the single-call analyst. Still free on local Ollama; still cost-gated per step.
    deep: bool = False
    # "Agent" runs the agentic operator loop (services/operator.py): the LLM calls the
    # platform's read-only tools mid-reasoning, then answers. Degrades to deep on failure.
    agent: bool = False


@router.post("")
async def chat(body: ChatRequest, db: DbDep, user: UserDep) -> dict:
    if user.tier == "free":
        raise HTTPException(status_code=402, detail="Analyst chat is a paid feature.")
    question = body.question.strip()
    try:
        if body.agent:
            return await operator_loop.answer_question_agentic(db, question, watched_assets=user.watched_assets)
        if body.deep:
            return await reasoner.answer_question_deep(db, question, watched_assets=user.watched_assets)
        return await analyst.answer_question(db, question)
    except Exception as exc:  # noqa: BLE001 — safety net; both paths degrade internally
        logger.error("Analyst chat failed: %s", exc)
        raise HTTPException(status_code=502, detail="The analyst is unavailable right now.")
