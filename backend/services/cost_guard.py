"""
Budget gate for LLM calls.

The only LLM provider is free/local (Ollama), so there is never any spend to
cap: `claude_allowed` always returns True. The function is kept (name and
signature unchanged) so existing callers that gate a call on it keep working
without edits; `llm_allowed` additionally checks the provider is actually up.
"""

import logging

from backend.services import llm

logger = logging.getLogger(__name__)


async def claude_allowed(db) -> bool:
    """Always True — the local LLM is free, so no budget can be exceeded.

    Retained for call-site compatibility (workers gate paid-era calls on this)."""
    return True


async def llm_allowed(db) -> bool:
    """True if the local LLM provider is up and can serve a request now."""
    return llm.available()
