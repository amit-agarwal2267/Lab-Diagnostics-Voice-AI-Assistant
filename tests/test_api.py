from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from app.api.main import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app(cors_origins=["http://localhost:3000", "https://example.vercel.app"])
    return TestClient(app)


def test_healthz(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_alias(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_readyz_ok(client: TestClient) -> None:
    with patch("app.api.routes.health._check_db", return_value=(True, "ok")):
        resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready", "db": "ok"}


def test_readyz_down(client: TestClient) -> None:
    with patch("app.api.routes.health._check_db", return_value=(False, "connection refused")):
        resp = client.get("/readyz")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "not_ready"
    assert "connection refused" in body["db"]


def test_cors_preflight_allowed_origin(client: TestClient) -> None:
    resp = client.options(
        "/api/v1/call/start",
        headers={
            "Origin": "https://example.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "https://example.vercel.app"


def test_cors_disallowed_origin(client: TestClient) -> None:
    resp = client.options(
        "/api/v1/call/start",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert "access-control-allow-origin" not in resp.headers or resp.headers.get(
        "access-control-allow-origin"
    ) != "https://evil.example"


def test_start_call_success(client: TestClient) -> None:
    mock_token = "jwt-test-token"
    with (
        patch("app.api.routes.call._dispatch_agent", new_callable=AsyncMock) as mock_dispatch,
        patch("app.api.routes.call._create_room_token", return_value=mock_token) as mock_token_fn,
        patch("app.api.routes.call.get_settings") as mock_settings,
    ):
        settings = MagicMock()
        settings.livekit_url = "ws://localhost:7880"
        settings.livekit_agent_name = "supervisor-agent"
        mock_settings.return_value = settings

        resp = client.post("/api/v1/call/start")

    assert resp.status_code == 200
    body = resp.json()
    assert body["token"] == mock_token
    assert body["livekit_url"] == "ws://localhost:7880"
    assert body["room_name"].startswith("lab-call-")
    assert body["identity"].startswith("caller-")
    mock_dispatch.assert_awaited_once()
    mock_token_fn.assert_called_once()


def test_start_call_dispatch_failure(client: TestClient) -> None:
    with patch(
        "app.api.routes.call._dispatch_agent",
        new_callable=AsyncMock,
        side_effect=RuntimeError("livekit down"),
    ):
        resp = client.post("/api/v1/call/start")
    assert resp.status_code == 502
    assert "Failed to dispatch agent" in resp.json()["detail"]