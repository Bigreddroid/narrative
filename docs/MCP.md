# Narrative MCP Server

Read-only **Model Context Protocol** server that exposes the platform's live risk
intelligence as tools, so Claude / other MCP clients can query it directly.

## Why it's a separate venv
The `mcp` SDK pins a newer Starlette than FastAPI 0.115 allows. To avoid breaking
the API, the MCP server is a **thin HTTP client to the running API** (it does not
import backend code) and runs in its **own venv**.

## Run

```bash
# one-time
python -m venv ~/nv-mcp-venv
source ~/nv-mcp-venv/bin/activate
pip install -r requirements-mcp.txt

# run (API must be up; token = any logged-in user's JWT)
export NARRATIVE_API_URL=http://localhost:8000
export NARRATIVE_API_TOKEN=<jwt>
python -m backend.mcp_server
```

Get a dev token locally:
```bash
curl -s -X POST $NARRATIVE_API_URL/api/v1/auth/dev-login \
  -H 'Content-Type: application/json' \
  -d '{"email":"enterprise@narrative.dev","password":"betatest1"}' | jq -r .access_token
```

## Tools
| Tool | Maps to | Returns |
|------|---------|---------|
| `get_exposure` | `GET /exposure` | overall pressure + per-sector/region CPE scores |
| `search_events` | `GET /search/` | events matching a text query |
| `get_world_graph` | `GET /graph/world` | full event graph (nodes + edges) |
| `get_event_graph` | `GET /graph/event/{id}` | one event + its consequence chain |

## Claude Desktop config (example)
```json
{
  "mcpServers": {
    "narrative": {
      "command": "/home/you/nv-mcp-venv/bin/python",
      "args": ["-m", "backend.mcp_server"],
      "cwd": "/path/to/Narrative v5",
      "env": { "NARRATIVE_API_URL": "http://localhost:8000", "NARRATIVE_API_TOKEN": "<jwt>" }
    }
  }
}
```

## Prod
Run as a small separate service (its own venv/image) alongside the API; point
`NARRATIVE_API_URL` at the internal API host and supply a service token.
