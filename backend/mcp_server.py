"""
The Narrative — MCP server (read-only agent access to live risk intelligence).

Lets Claude / other MCP clients query the platform's live data as tools. It is a
THIN HTTP CLIENT to the running API (not an importer of backend code) on purpose:
the `mcp` SDK pins a newer Starlette than FastAPI allows, so this MUST run in its
OWN venv, isolated from the API. See docs/MCP.md.

Run (separate venv):
    python -m venv ~/nv-mcp-venv && source ~/nv-mcp-venv/bin/activate
    pip install -r requirements-mcp.txt
    NARRATIVE_API_URL=http://localhost:8000 NARRATIVE_API_TOKEN=<jwt> python -m backend.mcp_server

Env:
    NARRATIVE_API_URL    base URL of the API (default http://localhost:8000)
    NARRATIVE_API_TOKEN  bearer token (a logged-in user's JWT) for authed endpoints
"""

import os

import httpx
from mcp.server.fastmcp import FastMCP

API_URL = os.environ.get("NARRATIVE_API_URL", "http://localhost:8000").rstrip("/")
API_TOKEN = os.environ.get("NARRATIVE_API_TOKEN", "")

mcp = FastMCP("narrative")


def _headers() -> dict:
    return {"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {}


async def _get(path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        r = await client.get(f"{API_URL}/api/v1{path}", params=params, headers=_headers())
        if r.status_code == 401:
            return {"error": "unauthorized — set NARRATIVE_API_TOKEN to a valid bearer token"}
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def get_exposure() -> dict:
    """Current world consequence exposure: overall pressure + per-sector and per-region
    risk scores from the Consequence Propagation Engine."""
    return await _get("/exposure")


@mcp.tool()
async def search_events(query: str, limit: int = 20) -> dict:
    """Search live narrative events by text (title/summary/category). Returns matching
    events with importance, status, geography, and coordinates."""
    return await _get("/search/", {"q": query, "limit": limit})


@mcp.tool()
async def country_risk(top: int = 30) -> dict:
    """Per-country (geographic) risk index — ranked hotspots by importance × recency
    over the live event graph. A 'country instability' style view."""
    return await _get("/exposure/countries", {"top": top})


@mcp.tool()
async def get_world_graph() -> dict:
    """The full live event graph: nodes (events) + edges (causal/consequence links)."""
    return await _get("/graph/world")


@mcp.tool()
async def get_event_graph(event_id: str) -> dict:
    """A single event with its connected events and connections (the consequence chain)."""
    return await _get(f"/graph/event/{event_id}")


if __name__ == "__main__":
    mcp.run()
