from app.core.agents.supervisor import SupervisorAgent
from app.core.agents.appointment import AppointmentAgent
from app.core.agents.report_status import ReportStatusAgent
from app.core.agents.ticket import TicketAgent
from app.core.prompts import (
    SUPERVISOR_INSTRUCTIONS,
    APPOINTMENT_INSTRUCTIONS,
    REPORT_STATUS_INSTRUCTIONS,
    TICKET_INSTRUCTIONS,
)


def _tool_names(agent) -> set[str]:
    """
    Extract function names from LiveKit FunctionTool wrappers or plain callables.
    """
    names: set[str] = set()
    for t in agent.tools or []:
        if hasattr(t, "__name__") and not str(type(t)).endswith("FunctionTool'>"):
            names.add(t.__name__)
            continue

        for attr in ("__livekit_tool_info", "__livekit_agents_ai_callable", "info"):
            info = getattr(t, attr, None)
            if info is not None and getattr(info, "name", None):
                names.add(info.name)
                break
        else:
            if getattr(t, "name", None):
                names.add(t.name)
            elif getattr(t, "__name__", None):
                names.add(t.__name__)
            elif callable(getattr(t, "execute", None)) and hasattr(t.execute, "__name__"):
                names.add(t.execute.__name__)
            else:
                names.add(str(t))
    return names

def test_supervisor_uses_supervisor_instructions():
    agent = SupervisorAgent()
    assert agent.instructions == SUPERVISOR_INSTRUCTIONS

def test_appointment_agent_has_booking_tools():
    agent = AppointmentAgent()
    assert agent.instructions == APPOINTMENT_INSTRUCTIONS
    names = _tool_names(agent)
    for name in (
        "check_prescription_requirement",
        "get_slots",
        "select_slot",
        "finalize_appointment",
    ):
        assert name in names, f"{name} not in {names}"

def test_report_status_agent_has_report_tools():
    agent = ReportStatusAgent()
    assert agent.instructions == REPORT_STATUS_INSTRUCTIONS
    names = _tool_names(agent)
    for name in ("verify_patient_identity", "check_report_status", "raise_ticket"):
        assert name in names, f"{name} not in {names}"

def test_ticket_agent_has_support_tools():
    agent = TicketAgent()
    assert agent.instructions == TICKET_INSTRUCTIONS
    names = _tool_names(agent)
    for name in ("verify_patient_identity", "update_email_on_file", "raise_ticket"):
        assert name in names, f"{name} not in {names}"

def test_specialists_expose_handoff_to_supervisor():
    for AgentCls in (AppointmentAgent, ReportStatusAgent, TicketAgent):
        agent = AgentCls()
        assert hasattr(agent, "handoff_to_supervisor")

def test_supervisor_exposes_handoffs():
    agent = SupervisorAgent()
    assert hasattr(agent, "handoff_to_appointment")
    assert hasattr(agent, "handoff_to_report_status")
    assert hasattr(agent, "handoff_to_ticket")


def test_check_medical_guardrail_blocks_clinical_advice_requests():
    from app.core.guardrails import DEFLECTION_MESSAGE, check_medical_guardrail

    clinical_questions = [
        "Should I take a CBC test after my surgery?",
        "Is it safe to do a blood test without a doctor?",
        "Can I get checked for cancer and book a test tomorrow?",
    ]

    for question in clinical_questions:
        assert check_medical_guardrail(question) == DEFLECTION_MESSAGE


def test_check_medical_guardrail_allows_booking_requests_without_medical_advice():
    from app.core.guardrails import check_medical_guardrail

    booking_questions = [
        "I want to book a CBC test",
        "What is the price of the lipid profile?",
        "Which centre is available for a home visit?",
    ]

    for question in booking_questions:
        assert check_medical_guardrail(question) is None