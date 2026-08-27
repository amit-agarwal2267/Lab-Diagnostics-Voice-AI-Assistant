from __future__ import annotations
from fastapi import APIRouter
from app.config.config import get_settings

router = APIRouter(prefix="/api/v1", tags=["config"])


@router.get("/agent-config")
async def agent_config() -> dict:
    settings = get_settings()
    return {
        "vad": "silero",
        "stt": {"provider": "groq", "model": settings.stt_model},
        "llm": {"provider": "google", "model": settings.llm_model},
        "tts": {"provider": "piper", "model": "en_US-ryan-high", "voice": "ryan"},
        "enhancements": {
            "turn_detection": True,
            "noise_cancellation": True,
            "expressiveness": False,
        },
    }