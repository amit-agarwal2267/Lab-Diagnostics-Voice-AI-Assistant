import json
import socket
from urllib.request import urlopen, Request
from urllib.error import HTTPError
import pytest
from app.health import start_health_server

def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

@pytest.fixture
def health_server():
    port = _free_port()
    server = start_health_server(
        host="127.0.0.1",
        port=port,
        ready_check=lambda: (True, "ok"),
    )
    base = f"http://127.0.0.1:{port}"
    yield base, server
    server.shutdown()

def _get(url: str) -> tuple[int, dict]:
    try:
        with urlopen(Request(url), timeout=2) as resp:
            return resp.status, json.loads(resp.read().decode())
    except HTTPError as e:
        body = e.read().decode()
        return e.code, json.loads(body) if body else {}

def test_healthz_returns_ok(health_server):
    base, _ = health_server
    status, body = _get(f"{base}/healthz")
    assert status == 200
    assert body["status"] == "ok"

def test_health_alias(health_server):
    base, _ = health_server
    status, body = _get(f"{base}/health")
    assert status == 200
    assert body["status"] == "ok"

def test_readyz_when_db_ok(health_server):
    base, _ = health_server
    status, body = _get(f"{base}/readyz")
    assert status == 200
    assert body["status"] == "ready"
    assert body["db"] == "ok"

def test_readyz_when_db_down():
    port = _free_port()
    server = start_health_server(
        host="127.0.0.1",
        port=port,
        ready_check=lambda: (False, "connection refused"),
    )
    try:
        status, body = _get(f"http://127.0.0.1:{port}/readyz")
        assert status == 503
        assert body["status"] == "not_ready"
        assert "connection refused" in body["db"]
    finally:
        server.shutdown()

def test_unknown_path_404(health_server):
    base, _ = health_server
    status, body = _get(f"{base}/nope")
    assert status == 404
    assert body["status"] == "not_found"