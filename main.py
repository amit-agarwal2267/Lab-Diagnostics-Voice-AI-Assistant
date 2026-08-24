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

settings = get_settings()

server = AgentServer()


@server.rtc_session(agent_name=settings.livekit_agent_name)
async def entrypoint(ctx: JobContext):
    session = AgentSession[UserData](
        userdata=UserData(),
        stt=groq.STT(
            model=settings.stt_model,
            api_key=settings.groq_api_key,
            language="en",
        ),
        llm=google.LLM(
            model=settings.llm_model,
            api_key=settings.google_api_key
        ),
        tts=PiperTTS(
            model_path="models/piper/en_US-ryan-high.onnx",
            use_cuda=False,
            speed=1.0,
        ),
        turn_handling=TurnHandlingOptions(
            turn_detection=inference.TurnDetector(),
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