import logging
from livekit import agents
from livekit.agents import (
    AgentServer,
    AgentSession,
    JobContext,
    room_io,
    inference,
    TurnHandlingOptions,
)
from livekit.plugins import noise_cancellation, groq, google
from app.core.state import UserData
from app.core.agents.supervisor import SupervisorAgent
from local_livekit_plugins import PiperTTS
from app.config.config import get_settings
from dotenv import load_dotenv

load_dotenv()

settings = get_settings()

server = AgentServer()


@server.rtc_session(agent_name=settings.livekit_agent_name)
async def entrypoint(ctx: JobContext):
    session = AgentSession[UserData](
        userdata=UserData(),
        stt=groq.STT(
            model=settings.stt_model,
            api_key=settings.groq_api_key.get_secret_value() if settings.groq_api_key else None,
            language="en",
        ),
        llm=google.LLM(
            model=settings.llm_model,
            api_key=settings.google_api_key.get_secret_value() if settings.google_api_key else None,
        ),
        tts=PiperTTS(
            model_path="models/piper/en_US-ryan-high.onnx",
            use_cuda=False,
            speed=0.95,
        ),
        turn_handling=TurnHandlingOptions(
            turn_detection=inference.TurnDetector(),
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

    await session.start(
        agent=SupervisorAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=noise_cancellation.BVC(),
            ),
        ),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agents.cli.run_app(server)