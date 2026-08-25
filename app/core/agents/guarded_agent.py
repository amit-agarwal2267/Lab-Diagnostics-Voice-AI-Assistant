from __future__ import annotations
from livekit.agents import Agent
from livekit.agents.llm import ChatContext, ChatMessage, StopResponse
from app.core.guardrails import check_medical_guardrail

class GuardedAgent(Agent):
    """Agent subclass that blocks clinically sensitive turns.

    On every user turn, runs ``check_medical_guardrail``.  If a deflection
    is returned the agent speaks it and raises ``StopResponse`` so the LLM
    never sees the message.  Otherwise the normal pipeline continues.
    """

    async def on_user_turn_completed(
        self,
        turn_ctx: ChatContext,
        new_message: ChatMessage,
    ) -> None:
        deflection = check_medical_guardrail(new_message.text_content)

        if deflection:
            await self.session.say(deflection)
            raise StopResponse()

        await super().on_user_turn_completed(turn_ctx, new_message)
