from __future__ import annotations
from app.api.schemas import HealthResponse, ReadyResponse
from fastapi import APIRouter, Response, status

router = APIRouter(tags=["health"])


def _check_db() -> tuple[bool, str]:
    try:
        from app.db.client import get_connection

        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True, "ok"
    except Exception as exc:
        return False, str(exc)

@router.get("/healthz", response_model=HealthResponse)
@router.get("/health", response_model=HealthResponse)
@router.get("/", response_model=HealthResponse, include_in_schema=False)
def healthz() -> HealthResponse:
    return HealthResponse(status="ok")

@router.get("/readyz", response_model=ReadyResponse)
def readyz(response: Response) -> ReadyResponse:
    ok, detail = _check_db()
    if ok:
        return ReadyResponse(status="ready", db=detail)
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadyResponse(status="not_ready", db=detail)