from livekit.agents import Agent
from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext

from app.core.state import UserData
from app.core.prompts import SUPERVISOR_INSTRUCTIONS


class SupervisorAgent(Agent):
    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=SUPERVISOR_INSTRUCTIONS,
            chat_ctx=chat_ctx,
        )

    async def on_enter(self) -> None:
        has_prior_user_turn = any(
            getattr(item, "role", None) == "user"
            for item in (self.chat_ctx.items if self.chat_ctx else [])
        )

        if not has_prior_user_turn:
            await self.session.generate_reply(
                instructions=(
                    "Greet the caller briefly as the front desk of Dr. Lal Path Labs "
                    "and ask how you can help. One short sentence only."
                )
            )
        else:
            await self.session.generate_reply(
                instructions=(
                    "The caller was just transferred back to the front desk. "
                    "Look at the recent messages and either continue helping or "
                    "hand them to the correct specialist. Do not greet again."
                )
            )

    @function_tool
    async def handoff_to_appointment(self, context: RunContext[UserData]):
        """Hand off to the appointment booking specialist. Call this when
        the caller wants to book a lab test or asks about tests/prices/slots.
        """
        from app.core.agents.appointment import AppointmentAgent
        return AppointmentAgent(chat_ctx=self.chat_ctx.copy(exclude_instructions=True))

    @function_tool
    async def handoff_to_report_status(self, context: RunContext[UserData]):
        """Hand off to the report status specialist. Call this when the
        caller asks if their report is ready or wants it resent.
        """
        from app.core.agents.report_status import ReportStatusAgent
        return ReportStatusAgent(chat_ctx=self.chat_ctx.copy(exclude_instructions=True))

    @function_tool
    async def handoff_to_ticket(self, context: RunContext[UserData]):
        """Hand off to the support ticket specialist. Call this for wrong
        email/booking corrections, complaints, or any general inquiry.
        """
        from app.core.agents.ticket import TicketAgent
        return TicketAgent(chat_ctx=self.chat_ctx.copy(exclude_instructions=True))