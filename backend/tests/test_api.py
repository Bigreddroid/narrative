"""Core API smoke + auth tests (run against the local DB)."""
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from backend.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_feed_requires_auth():
    r = client.get("/api/v1/feed/")
    assert r.status_code == 401


async def _login(ac: AsyncClient) -> str:
    r = await ac.post("/api/v1/auth/dev-login", json={"email": "pytest@narrative.local", "password": "x"})
    assert r.status_code == 200
    return r.json()["access_token"]


async def test_dev_login_then_feed_returns_real_data():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        token = await _login(ac)
        assert token
        r = await ac.get("/api/v1/feed/", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert "feed" in r.json()


async def test_graph_world_shape():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        token = await _login(ac)
        r = await ac.get("/api/v1/graph/world", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        body = r.json()
        assert "nodes" in body and isinstance(body["nodes"], list)
