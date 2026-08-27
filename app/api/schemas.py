from __future__ import annotations
from pydantic import BaseModel, Field

class StartCallResponse(BaseModel):
    """Credentials the frontend needs to join a LiveKit room and talk to the agent."""

    room_name: str = Field(..., description="LiveKit room the agent was dispatched to")
    identity: str = Field(..., description="Participant identity for this caller")
    token: str = Field(..., description="JWT access token for LiveKit")
    livekit_url: str = Field(..., description="LiveKit WebSocket URL")

class HealthResponse(BaseModel):
    status: str

class ReadyResponse(BaseModel):
    status: str
    db: str
