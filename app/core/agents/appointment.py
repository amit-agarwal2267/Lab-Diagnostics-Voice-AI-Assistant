from app.core.agents.guarded_agent import GuardedAgent
from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext

from app.core.state import UserData
from app.core.prompts import APPOINTMENT_INSTRUCTIONS
from app.core.tools import (
    check_prescription_requirement,
    get_slots,
    select_slot,
    finalize_appointment,
    offer_more_help, 
    close_call,
)


class AppointmentAgent(GuardedAgent):
    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=APPOINTMENT_INSTRUCTIONS,
            tools=[
                check_prescription_requirement,
                get_slots,
                select_slot,
                finalize_appointment,
                offer_more_help, 
                close_call,
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
        """
        Hand off back to the front desk if the caller's request is no longer about booking (e.g. they ask about report status or want to raise a complaint mid-booking). Whatever has been collected so far (tests, slot, etc.) stays in UserData and is not lost.
        """
        from app.core.agents.supervisor import SupervisorAgent
        return SupervisorAgent(chat_ctx=self.chat_ctx.copy(exclude_instructions=True))