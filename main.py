import logging
from dataclasses import asdict, is_dataclass
from livekit import agents
import asyncio
import json
from livekit.agents import (
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    room_io,
    inference,
    TurnHandlingOptions,
    metrics,
    UserStateChangedEvent,
    llm,
)
from app.core.closing import (
    pick, 
    FOLLOWUP_LINES_FIRST, 
    FOLLOWUP_LINES_SECOND, 
    CLOSING_LINES,
)
from livekit.plugins import noise_cancellation, groq, google, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from app.core.state import UserData
from app.core.agents.supervisor import SupervisorAgent
from local_livekit_plugins import PiperTTS
from app.config.config import get_settings
from app.health import start_health_server
from app.logging_config import configure_logging
from dotenv import load_dotenv

load_dotenv()

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("voice-agent")

server = AgentServer(
    num_idle_processes=settings.num_idle_processes,
    load_threshold=settings.load_threshold,
    job_memory_warn_mb=settings.job_memory_warn_mb,
    job_memory_limit_mb=settings.job_memory_limit_mb,
    drain_timeout=settings.drain_timeout,
)

_METRIC_LABELS = {
    "stt_metrics": "stt",
    "llm_metrics": "llm",
    "tts_metrics": "tts",
    "eou_metrics": "eou",
}

def _prewarm(proc: JobProcess) -> None:
    """
    Runs once per idle process before any job is assigned.

    Load models / warm caches here so the first call does not pay cold-start cost.
    """
    logger.info(
        "Prewarming job process",
        extra={"pid": proc.pid if hasattr(proc, "pid") else None},
    )

server.setup_fnc = _prewarm

def _extract_duration_ms(m) -> float | None:
    for field in ("duration", "ttft", "ttfb", "end_of_utterance_delay"):
        val = getattr(m, field, None)
        if isinstance(val, (int, float)):
            return round(val * 1000, 1)
    return None

def _metrics_to_dict(m) -> dict:
    """
    Best-effort conversion of a metrics object to a JSON-serializable dict.
    """
    if is_dataclass(m):
        return asdict(m)
    if hasattr(m, "__dict__"):
        return {k: v for k, v in vars(m).items() if not k.startswith("_")}
    return {"repr": repr(m)}


def _attach_metrics(session: AgentSession, ctx: JobContext) -> None:
    usage_collector = metrics.UsageCollector()

    def _on_metrics_collected(ev) -> None:
        m = getattr(ev, "metrics", ev)
        try:
            metrics.log_metrics(m)
        except Exception:
            logger.debug("metrics.log_metrics failed", exc_info=True)
        try:
            usage_collector.collect(m)
        except Exception:
            pass

        logger.info(
            "metrics_collected",
            extra={
                "room": ctx.room.name,
                "metrics_type": getattr(m, "type", type(m).__name__),
                "metrics": _metrics_to_dict(m),
            },
        )

        metric_type = getattr(m, "type", type(m).__name__)
        label = _METRIC_LABELS.get(metric_type) or _METRIC_LABELS.get(type(m).__name__.lower())
        duration_ms = _extract_duration_ms(m)
        if label and duration_ms is not None:
            payload = json.dumps({"metric": label, "duration_ms": duration_ms})
            try:
                asyncio.create_task(
                    ctx.room.local_participant.publish_data(
                        payload.encode("utf-8"),
                        reliable=True,
                        topic="agent-metrics",
                    )
                )
            except Exception:
                logger.debug("publish_data for metrics failed", exc_info=True)

    def _on_session_usage_updated(ev) -> None:
        usage = getattr(ev, "usage", None)
        logger.info(
            "session_usage_updated",
            extra={
                "room": ctx.room.name,
                "usage": _metrics_to_dict(usage) if usage is not None else None,
            },
        )

    session.on("metrics_collected", _on_metrics_collected)
    try:
        session.on("session_usage_updated", _on_session_usage_updated)
    except Exception:
        pass

    async def _log_usage_on_shutdown() -> None:
        summary = usage_collector.get_summary()
        logger.info(
            "session_usage_summary",
            extra={
                "room": ctx.room.name,
                "llm_prompt_tokens": getattr(summary, "llm_prompt_tokens", 0),
                "llm_completion_tokens": getattr(summary, "llm_completion_tokens", 0),
                "tts_characters_count": getattr(summary, "tts_characters_count", 0),
                "stt_audio_duration": getattr(summary, "stt_audio_duration", 0.0),
            },
        )

    ctx.add_shutdown_callback(_log_usage_on_shutdown)

@server.rtc_session(agent_name=settings.livekit_agent_name)
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    logger.info("Job started", extra={"room": ctx.room.name})

    session = AgentSession[UserData](
        vad=silero.VAD.load(min_speech_duration=0.3, min_silence_duration=0.4),
        userdata=UserData(),
        stt=groq.STT(
            model=settings.stt_model,
            api_key=settings.groq_api_key.get_secret_value() if settings.groq_api_key else None,
            language="en",
            prompt=(
                "Common Indian names: Agarwal, Sharma, Gupta, Kumar, Reddy, Iyer, Patel, "
                "Nair, Chatterjee, Bhatt, Rajasthan, Kota, Jaipur, Udaipur, CBC, lipid profile, "
                "thyroid panel. Appointment options: Home visit, Visit Center, Home, Center. "
                "Payment: UPI, Cash on Visit."
            ),
        ),
        llm=llm.FallbackAdapter(
            llm=[
                groq.LLM(
                    model=settings.fallback_llm_model,
                    api_key=settings.groq_api_key.get_secret_value() if settings.groq_api_key else None,
                ),
                google.LLM(
                    model=settings.llm_model,
                    api_key=settings.google_api_key.get_secret_value() if settings.google_api_key else None,
                ),
            ]
        ),
        
        tts=PiperTTS(
            model_path="models/piper/en_US-ryan-high.onnx",
            use_cuda=False,
            speed=0.95,
        ),
        max_tool_steps=8,
        user_away_timeout=30.0,
        
        turn_handling=TurnHandlingOptions(
            turn_detection=MultilingualModel(),
            endpointing={
                "mode": "dynamic",
                "min_delay": 0.8,
                "max_delay": 3.5,
            },
            interruption={
                "enabled": True,
                "mode": "adaptive",
                "min_duration": 0.7,
                "min_words": 2,
                "resume_false_interruption": True,
            },
        ),
    )

    _attach_metrics(session, ctx)
    _attach_inactivity_handler(session, session.userdata)

    await session.start(
        agent=SupervisorAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            delete_room_on_close=True,
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=noise_cancellation.BVC(),
            ),
        ),
    )

def _attach_inactivity_handler(session: AgentSession, userdata: UserData) -> None:
    inactivity_task: asyncio.Task | None = None

    async def check_if_user_present() -> None:
        userdata.followup_attempts += 1
        await session.say(pick(FOLLOWUP_LINES_FIRST))
        await asyncio.sleep(15)

        userdata.followup_attempts += 1
        await session.say(pick(FOLLOWUP_LINES_SECOND))
        await asyncio.sleep(15)

        await session.say(pick(CLOSING_LINES), allow_interruptions=False)
        session.shutdown()

    def _on_user_state_changed(ev: UserStateChangedEvent) -> None:
        nonlocal inactivity_task
        if ev.new_state == "away":
            inactivity_task = asyncio.create_task(check_if_user_present())
            return
        if inactivity_task is not None:
            inactivity_task.cancel()
            inactivity_task = None
            userdata.reset_followups()

    session.on("user_state_changed", _on_user_state_changed)

if __name__ == "__main__":
    start_health_server(host=settings.health_host, port=settings.health_port)

    logger.info(
        "Starting agent server",
        extra={
            "agent_name": settings.livekit_agent_name,
            "num_idle_processes": settings.num_idle_processes,
            "load_threshold": settings.load_threshold,
            "job_memory_warn_mb": settings.job_memory_warn_mb,
            "environment": settings.environment,
        },
    )
    agents.cli.run_app(server)