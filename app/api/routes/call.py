from __future__ import annotations
import uuid
from app.config.config import get_settings
from app.api.schemas import StartCallResponse
import logging
from livekit import api
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["call"])


def _create_room_token(identity: str, room_name: str) -> str:
    settings = get_settings()
    token = (
        api.AccessToken(
            settings.livekit_api_key.get_secret_value(),
            settings.livekit_api_secret.get_secret_value(),
        )
        .with_identity(identity)
        .with_name(identity)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            )
        )
    )
    return token.to_jwt()


async def _dispatch_agent(room_name: str) -> None:
    settings = get_settings()
    server_url = settings.livekit_api_url or settings.livekit_url
    lk_api = api.LiveKitAPI(
        server_url,
        settings.livekit_api_key.get_secret_value(),
        settings.livekit_api_secret.get_secret_value(),
    )
    try:
        await lk_api.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name=settings.livekit_agent_name,
                room=room_name,
            )
        )
    finally:
        await lk_api.aclose()


@router.post("/call/start", response_model=StartCallResponse)
async def start_call() -> StartCallResponse:
    """
    Create a unique room, dispatch the voice agent into it, and return
    LiveKit connection credentials for the frontend client.
    """
    settings = get_settings()
    room_name = f"lab-call-{uuid.uuid4().hex[:8]}"
    identity = f"caller-{uuid.uuid4().hex[:6]}"

    try:
        await _dispatch_agent(room_name)
    except Exception as exc:
        logger.exception("Failed to dispatch agent to room %s", room_name)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to dispatch agent: {exc}",
        ) from exc

    try:
        token = _create_room_token(identity, room_name)
    except Exception as exc:
        logger.exception("Failed to create LiveKit token for room %s", room_name)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create access token: {exc}",
        ) from exc

    logger.info(
        "Call started",
        extra={"room": room_name, "identity": identity},
    )

    return StartCallResponse(
        room_name=room_name,
        identity=identity,
        token=token,
        livekit_url=settings.livekit_url,
    )