from pydantic import Field, SecretStr
from typing import Literal, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    livekit_url: str = Field(..., alias="LIVEKIT_URL")
    livekit_api_url: Optional[str] = Field(None, alias="LIVEKIT_API_URL")
    livekit_api_key: SecretStr = Field(..., alias="LIVEKIT_API_KEY")
    livekit_api_secret: SecretStr = Field(..., alias="LIVEKIT_API_SECRET")
    livekit_agent_name: str = Field("supervisor-agent", alias="LIVEKIT_AGENT_NAME")

    google_api_key: Optional[SecretStr] = Field(None, alias="GOOGLE_API_KEY")
    openrouter_api_key: Optional[SecretStr] = Field(None, alias="OPENROUTER_API_KEY")
    groq_api_key: Optional[SecretStr] = Field(None, alias="GROQ_API_KEY")

    llm_model: str = Field("gemini-3.5-flash-lite", alias="LLM_MODEL")        # Only google models
    fallback_llm_model: str = Field("gemini-3.5-flash-lite", alias="FALLBACK_LLM_MODEL")        # Only openrouter models
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

    health_host: str = Field("0.0.0.0", alias="HEALTH_HOST")
    health_port: int = Field(8080, alias="HEALTH_PORT")

    api_host: str = Field("0.0.0.0", alias="API_HOST")
    api_port: int = Field(8000, alias="API_PORT")

    cors_origins_raw: str = Field(
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173",
        alias="CORS_ORIGINS",
    )
    frontend_url: str = Field("", alias="FRONTEND_URL")

    num_idle_processes: int = Field(2, alias="NUM_IDLE_PROCESSES")
    load_threshold: float = Field(0.75, alias="LOAD_THRESHOLD")
    job_memory_warn_mb: float = Field(1000, alias="JOB_MEMORY_WARN_MB")
    job_memory_limit_mb: float = Field(0, alias="JOB_MEMORY_LIMIT_MB")
    drain_timeout: int = Field(1800, alias="DRAIN_TIMEOUT")

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