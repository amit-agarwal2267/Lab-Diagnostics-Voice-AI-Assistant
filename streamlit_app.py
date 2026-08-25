import asyncio
import os
import uuid
import streamlit as st
import streamlit.components.v1 as components
from livekit import api
from app.config.config import get_settings
from dotenv import load_dotenv

load_dotenv()

settings = get_settings()

st.set_page_config(page_title="Lab Diagnostic Voice Agent", page_icon="🧪")
st.title("Lab Diagnostic Voice Agent")
st.caption("Talk to the appointment / report status / support assistant.")

_LIVEKIT_JS_PATH = os.path.join(os.path.dirname(__file__), "livekit_client_script/livekit-client.umd.min.js")
with open(_LIVEKIT_JS_PATH, "r", encoding="utf-8") as f:
    LIVEKIT_CLIENT_JS = f.read()


def create_room_token(identity: str, room_name: str) -> str:
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


async def dispatch_agent(room_name: str) -> None:
    """Explicitly tell LiveKit to send our agent worker into this room.
    Required unless main.py's worker is registered for automatic dispatch.
    agent_name here MUST match whatever name main.py registers itself under.
    """
    lk_api = api.LiveKitAPI(
        settings.livekit_url,
        settings.livekit_api_key.get_secret_value(),
        settings.livekit_api_secret.get_secret_value(),
    )
    try:
        await lk_api.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(agent_name=settings.livekit_agent_name, room=room_name)
        )
    finally:
        await lk_api.aclose()


if "room_name" not in st.session_state:
    st.session_state.room_name = f"lab-call-{uuid.uuid4().hex[:8]}"
    st.session_state.identity = f"caller-{uuid.uuid4().hex[:6]}"
    st.session_state.call_started = False

if not st.session_state.call_started:
    if st.button("Start Call"):
        asyncio.run(dispatch_agent(st.session_state.room_name))
        st.session_state.call_started = True
        st.rerun()
else:
    token = create_room_token(st.session_state.identity, st.session_state.room_name)

    components.html(
      f"""
      <div id="status" style="font-family: sans-serif;">Loading LiveKit client...</div>
      <audio id="agent-audio" autoplay></audio>
      <script>
        {LIVEKIT_CLIENT_JS}
      </script>
      <script>
        async function main() {{
          const statusEl = document.getElementById("status");
          statusEl.innerText = "Connecting to room...";

          const room = new LivekitClient.Room();

          room.on(LivekitClient.RoomEvent.TrackSubscribed, (track) => {{
            if (track.kind === "audio") {{
              track.attach(document.getElementById("agent-audio"));
            }}
          }});

          room.on(LivekitClient.RoomEvent.ParticipantAttributesChanged, (changed, participant) => {{
            if (participant.isLocal) return;
            const state = participant.attributes["lk.agent.state"];
            if (state === "listening" || state === "speaking") {{
              markReady();
            }}
          }});

          room.on(LivekitClient.RoomEvent.ParticipantConnected, (participant) => {{
            if (participant.isLocal) return;
            statusEl.innerText = "Agent joined – waiting until ready...";
            const state = participant.attributes["lk.agent.state"];
            if (state === "listening" || state === "speaking") {{
              markReady();
            }}
          }});

          // Keep mic enabled for the whole call; never toggle it off.
          room.on(LivekitClient.RoomEvent.LocalTrackUnpublished, async (pub) => {{
            if (pub.kind === "audio" || pub.source === "microphone") {{
              try {{
                await room.localParticipant.setMicrophoneEnabled(true);
              }} catch (e) {{}}
            }}
          }});

          let ready = false;
          async function markReady() {{
            if (ready) return;
            ready = true;
            statusEl.innerText = "Agent ready – mic is on, you can speak anytime.";
            await room.localParticipant.setMicrophoneEnabled(true);
          }}

          try {{
            await room.connect("{settings.livekit_url}", "{token}");
            // Enable mic immediately on connect and leave it on for the full call.
            await room.localParticipant.setMicrophoneEnabled(true);
            statusEl.innerText = "Connected – mic on, waiting for agent...";

            setTimeout(() => {{
              if (!ready) {{
                statusEl.innerText = "Agent is taking longer than expected. Mic is still on – still waiting...";
              }}
            }}, 8000);
          }} catch (err) {{
            statusEl.innerText = "Connection failed: " + err;
          }}
        }}

        main();
      </script>
      """,
      height=150,
  )

    if st.button("End Call"):
        st.session_state.call_started = False
        st.rerun()