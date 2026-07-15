"""
Metadata endpoints — serve the canonical taxonomy so the frontend never hardcodes
(and drifts from) the backend's category/discipline vocabulary. Public, no auth:
this is static reference data, not user data.
"""

from fastapi import APIRouter

from backend import taxonomy

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/taxonomy")
async def get_taxonomy() -> dict:
    """The single source of truth for categories + INT disciplines.

    `category_discipline` lets the client resolve an event's discipline the same
    way the backend does, without shipping the logic twice.
    """
    return {
        "categories": list(taxonomy.CATEGORIES),
        "llm_categories": list(taxonomy.LLM_CATEGORIES),
        "disciplines": list(taxonomy.DISCIPLINES),
        "source_discipline": taxonomy.SOURCE_DISCIPLINE,
        "category_discipline": taxonomy.CATEGORY_DISCIPLINE,
        "default_discipline": taxonomy.DEFAULT_DISCIPLINE,
    }
