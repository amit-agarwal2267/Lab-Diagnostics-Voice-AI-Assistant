from livekit.agents import Agent
from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext

from app.core.state import UserData
from app.core.prompts import REPORT_STATUS_INSTRUCTIONS
from app.core.tools import (
    verify_patient_identity,
    check_report_status,
    raise_ticket,
)


class ReportStatusAgent(Agent):
    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=REPORT_STATUS_INSTRUCTIONS,
            tools=[
                verify_patient_identity,
                check_report_status,
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
        """Hand off back to the front desk if the caller's request is not
        about report status (e.g. they want to book a new test).
        """
        from app.core.agents.supervisor import SupervisorAgent
        return SupervisorAgent(chat_ctx=self.chat_ctx.copy(exclude_instructions=True))