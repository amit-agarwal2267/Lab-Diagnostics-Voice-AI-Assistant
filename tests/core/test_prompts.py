from app.core import prompts

def test_supervisor_routes_all_specialists():
    text = prompts.SUPERVISOR_INSTRUCTIONS
    assert "handoff_to_appointment" in text
    assert "handoff_to_report_status" in text
    assert "handoff_to_ticket" in text
    assert "finish" in text.lower() or "wait" in text.lower()

def test_appointment_booking_sequence_present():
    text = prompts.APPOINTMENT_INSTRUCTIONS
    assert "check_prescription_requirement" in text
    assert "get_slots" in text
    assert "select_slot" in text
    assert "finalize_appointment" in text
    assert "handoff_to_supervisor" in text

def test_report_status_requires_verification():
    text = prompts.REPORT_STATUS_INSTRUCTIONS
    assert "verify_patient_identity" in text
    assert "check_report_status" in text
    assert "VERIFICATION_FAILED_MAX_ATTEMPTS" in text

def test_ticket_covers_email_and_general():
    text = prompts.TICKET_INSTRUCTIONS
    assert "update_email_on_file" in text
    assert "raise_ticket" in text
    assert "email_correction" in text or "CASE 1" in text

def test_prompts_are_non_empty_strings():
    for name in (
        "SUPERVISOR_INSTRUCTIONS",
        "APPOINTMENT_INSTRUCTIONS",
        "REPORT_STATUS_INSTRUCTIONS",
        "TICKET_INSTRUCTIONS",
    ):
        value = getattr(prompts, name)
        assert isinstance(value, str)
        assert len(value.strip()) > 50