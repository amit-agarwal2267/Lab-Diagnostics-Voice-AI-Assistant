# app/core/config.py
from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    livekit_url: str = Field(..., alias="LIVEKIT_URL")
    livekit_api_key: SecretStr = Field(..., alias="LIVEKIT_API_KEY")
    livekit_api_secret: SecretStr = Field(..., alias="LIVEKIT_API_SECRET")
    livekit_agent_name: str = Field("supervisor-agent", alias="LIVEKIT_AGENT_NAME")

    google_api_key: Optional[SecretStr] = Field(None, alias="GOOGLE_API_KEY")
    groq_api_key: Optional[SecretStr] = Field(None, alias="GROQ_API_KEY")

    llm_model: str = Field("gemini-3.5-flash-lite", alias="LLM_MODEL")        # Only google models
    stt_model: str = Field("whisper-large-v3-turbo", alias="STT_MODEL")       # Only groq models
    tts_model_path: str = Field(
        "models/piper/en_US-ryan-high.onnx", alias="TTS_MODEL_PATH"           # Stored voice model
    )
    tts_speed: float = Field(1.0, alias="TTS_SPEED")

    db_url: SecretStr = Field(..., alias="DB_URL")

    lab_name: str = Field("Dino Labs", alias="LAB_NAME")
    prescription_upload_base_url: str = Field(
        "https://lab.example.com/upload", alias="PRESCRIPTION_UPLOAD_BASE_URL"
    )
    payment_base_url: str = Field(
        "https://lab.example.com/pay", alias="PAYMENT_BASE_URL"
    )
    max_verification_attempts: int = Field(2, alias="MAX_VERIFICATION_ATTEMPTS")
    report_ttl_days: int = Field(14, alias="REPORT_TTL_DAYS")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        "INFO", alias="LOG_LEVEL"
    )
    environment: Literal["development", "staging", "production"] = Field(
        "development", alias="ENVIRONMENT"
    )

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()