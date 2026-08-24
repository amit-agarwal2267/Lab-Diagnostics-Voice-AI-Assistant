from livekit.agents import Agent
from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext

from app.core.state import UserData
from app.core.prompts import TICKET_INSTRUCTIONS
from app.core.tools import (
    verify_patient_identity,
    update_email_on_file,
    raise_ticket,
)


class TicketAgent(Agent):
    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=TICKET_INSTRUCTIONS,
            tools=[
                verify_patient_identity,
                update_email_on_file,
                raise_ticket,
            ],
            chat_ctx=chat_ctx,
        )

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions=(
                "You have just received this call from the front desk. "
                "Continue the conversation from the most recent user messages. "
                "Do not re-greet or restart the interaction."
            )
        )

    @function_tool
    async def handoff_to_supervisor(self, context: RunContext[UserData]):
        """Hand off back to the front desk if the caller's request turns
        out to be about booking or report status instead.
        """
        from app.core.agents.supervisor import SupervisorAgent
        return SupervisorAgent(chat_ctx=self.chat_ctx.copy(exclude_instructions=True))