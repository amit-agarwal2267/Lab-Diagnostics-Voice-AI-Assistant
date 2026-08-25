from __future__ import annotations
import errno
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

logger = logging.getLogger(__name__)

def _check_db() -> tuple[bool, str]:
    """Return (ok, detail). Isolates DB import so health module stays light."""
    try:
        from app.db.client import get_connection

        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True, "ok"
    except Exception as exc:
        return False, str(exc)

class _HealthHandler(BaseHTTPRequestHandler):
    ready_check: Callable[[], tuple[bool, str]] = staticmethod(_check_db)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        logger.debug("health %s - %s", self.address_string(), format % args)

    def _send(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0].rstrip("/") or "/"

        if path in ("/healthz", "/health", "/"):
            self._send(200, {"status": "ok"})
            return

        if path == "/readyz":
            ok, detail = self.ready_check()
            if ok:
                self._send(200, {"status": "ready", "db": detail})
            else:
                self._send(503, {"status": "not_ready", "db": detail})
            return

        self._send(404, {"status": "not_found", "path": path})

class _ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True

def start_health_server(
    host: str = "0.0.0.0",
    port: int = 8080,
    ready_check: Callable[[], tuple[bool, str]] | None = None,
) -> ThreadingHTTPServer | None:
    """Start the health HTTP server on a daemon thread.

    Returns the server instance, or None if the port is already bound
    (expected in LiveKit job worker child processes).
    """
    if ready_check is not None:
        _HealthHandler.ready_check = staticmethod(ready_check)

    try:
        server = _ReusableThreadingHTTPServer((host, port), _HealthHandler)
    except OSError as exc:
        if exc.errno in (errno.EADDRINUSE, getattr(errno, "WSAEADDRINUSE", 98)):
            logger.debug(
                "Health port %s:%s already in use; skipping bind in this process",
                host,
                port,
            )
            return None
        raise

    thread = threading.Thread(
        target=server.serve_forever,
        name="health-server",
        daemon=True,
    )
    thread.start()
    logger.info("Health server listening on http://%s:%s (/healthz, /readyz)", host, port)
    return server