from types import SimpleNamespace
from unittest.mock import patch, MagicMock
import pytest
from app.core.state import UserData

def _ctx(**userdata_kwargs) -> SimpleNamespace:
    """Minimal RunContext stand-in: tools only use context.userdata."""
    return SimpleNamespace(userdata=UserData(**userdata_kwargs))

@pytest.mark.asyncio
async def test_find_centres_empty():
    from app.core import tools

    with patch("app.core.tools.search_centres", return_value=[]):
        result = await tools.find_centres(_ctx())
    assert "No centres found" in result

@pytest.mark.asyncio
async def test_find_centres_formats_modes():
    from app.core import tools

    centres = [
        {
            "name": "Main Lab",
            "code": "MDK01",
            "address": "Station Road",
            "city": "Kota",
            "state": "Rajasthan",
            "pincode": "324001",
            "supports_visit_center": True,
            "supports_home_visit": True,
        }
    ]
    with patch("app.core.tools.search_centres", return_value=centres):
        result = await tools.find_centres(_ctx(), city="Kota")
    assert "Main Lab" in result
    assert "MDK01" in result
    assert "Visit Center" in result
    assert "Home Visit" in result

@pytest.mark.asyncio
async def test_get_lab_test_prices_none():
    from app.core import tools

    with patch("app.core.tools.search_lab_tests", return_value=[]):
        result = await tools.get_lab_test_prices(_ctx())
    assert "No matching tests" in result

@pytest.mark.asyncio
async def test_get_lab_test_prices_lists_tests():
    from app.core import tools

    tests = [
        {"test_name": "CBC", "price": 350, "requires_prescription": False},
        {"test_name": "MRI Brain", "price": 4500, "requires_prescription": True},
    ]
    with patch("app.core.tools.search_lab_tests", return_value=tests):
        result = await tools.get_lab_test_prices(_ctx(), query="CBC")
    assert "CBC: ₹350" in result
    assert "MRI Brain" in result
    assert "prescription required" in result

@pytest.mark.asyncio
async def test_resolve_home_visit_no_service():
    from app.core import tools

    with patch("app.core.tools.search_centres", return_value=[]):
        result = await tools.resolve_home_visit_centre(
            pincode="000000", city="Nowhere", context=_ctx()
        )
    assert result == "NO_SERVICE_IN_AREA"

@pytest.mark.asyncio
async def test_resolve_home_visit_sets_userdata():
    from app.core import tools

    centre = {"uuid": "c-1", "name": "Home Lab", "city": "Kota", "state": "Rajasthan"}
    with patch("app.core.tools.search_centres", return_value=[centre]):
        ctx = _ctx()
        result = await tools.resolve_home_visit_centre(
            pincode="324001", city="Kota", context=ctx
        )
    assert "Home Lab" in result
    assert ctx.userdata.centre_uuid == "c-1"
    assert ctx.userdata.centre_name == "Home Lab"
    assert ctx.userdata.mode_of_sample_collection == "Home Visit"

@pytest.mark.asyncio
async def test_resolve_home_visit_kota_rajasthan_phrase():
    """Agent may pass the full spoken phrase as city."""
    from app.core import tools

    centre = {
        "uuid": "c1111111-1111-1111-1111-111111111111",
        "name": "Main Diagnostics Kota",
        "city": "Kota",
        "state": "Rajasthan",
    }
    with patch("app.core.tools.search_centres", return_value=[centre]) as mock_search:
        ctx = _ctx()
        result = await tools.resolve_home_visit_centre(
            pincode=None, city="Kota Rajasthan", context=ctx, state=None
        )
    assert "NO_SERVICE" not in result
    assert "Main Diagnostics Kota" in result
    mock_search.assert_called()
    assert ctx.userdata.centre_uuid == centre["uuid"]

@pytest.mark.asyncio
async def test_select_visit_centre_by_code():
    from app.core import tools

    centre = {
        "uuid": "c-2",
        "name": "Walk-in Lab",
        "city": "Jaipur",
        "supports_visit_center": True,
    }
    with patch("app.core.tools.get_centre_by_code", return_value=centre):
        ctx = _ctx()
        result = await tools.select_visit_centre("JCL01", ctx)
    assert "Walk-in Lab" in result
    assert ctx.userdata.centre_uuid == "c-2"

@pytest.mark.asyncio
async def test_select_visit_centre_multiple_matches():
    from app.core import tools

    matches = [
        {"name": "A", "code": "A1", "supports_visit_center": True},
        {"name": "B", "code": "B1", "supports_visit_center": True},
    ]
    with (
        patch("app.core.tools.get_centre_by_code", return_value=None),
        patch("app.core.tools.search_centres", return_value=matches),
    ):
        result = await tools.select_visit_centre("Jaipur", _ctx())
    assert "Multiple centres" in result

@pytest.mark.asyncio
async def test_verify_patient_success():
    from app.core import tools

    patient = {
        "uuid": "p-1",
        "name": "Amit Agarwal",
        "phone_number": "9990001111",
    }
    with patch("app.core.tools.get_patient_by_details", return_value=patient):
        ctx = _ctx(verification_attempts=1)
        result = await tools.verify_patient_identity(
            name="Amit Agarwal", age=23, phone="1111", context=ctx
        )
    assert result == "Identity verified."
    assert ctx.userdata.patient_uuid == "p-1"
    assert ctx.userdata.is_new_customer is False
    assert ctx.userdata.verification_attempts == 0

@pytest.mark.asyncio
async def test_verify_patient_max_attempts():
    from app.core import tools

    with patch("app.core.tools.get_patient_by_details", return_value=None):
        ctx = _ctx(verification_attempts=1)
        result = await tools.verify_patient_identity(
            name="X", age=1, phone="0000", context=ctx
        )
    assert result == "VERIFICATION_FAILED_MAX_ATTEMPTS"
    assert ctx.userdata.verification_attempts == 2

@pytest.mark.asyncio
async def test_get_slots_requires_centre():
    from app.core import tools

    result = await tools.get_slots("2030-01-01", _ctx())
    assert "No centre resolved" in result

@pytest.mark.asyncio
async def test_get_slots_lists_times():
    from app.core import tools

    with patch(
        "app.core.tools.get_available_slots",
        return_value=["2030-01-01 09:00:00", "2030-01-01 11:00:00"],
    ):
        result = await tools.get_slots(
            "2030-01-01", _ctx(centre_uuid="c-1")
        )
    assert "09:00" in result
    assert "11:00" in result

@pytest.mark.asyncio
async def test_select_slot_records():
    from app.core import tools

    ctx = _ctx()
    result = await tools.select_slot("2030-01-01 10:00:00", ctx)
    assert "noted" in result
    assert ctx.userdata.chosen_slot == "2030-01-01 10:00:00"

@pytest.mark.asyncio
async def test_finalize_appointment_missing_prereqs():
    from app.core import tools

    result = await tools.finalize_appointment(
        patient_name="A",
        patient_age=20,
        patient_email="a@example.com",
        mode_of_sample_collection="Visit Center",
        mode_of_payment="UPI",
        context=_ctx(),
    )
    assert "No centre resolved" in result

@pytest.mark.asyncio
async def test_finalize_appointment_slot_taken():
    from app.core import tools

    ctx = _ctx(
        centre_uuid="c-1",
        chosen_slot="2030-01-01 10:00:00",
        pending_test_uuids=["t-1"],
        requires_prescription=False,
    )
    with patch(
        "app.core.tools.reserve_slot",
        side_effect=ValueError("Slot is no longer available."),
    ):
        result = await tools.finalize_appointment(
            patient_name="Amit",
            patient_age=23,
            patient_email="amit@example.com",
            mode_of_sample_collection="Visit Center",
            mode_of_payment="UPI",
            context=ctx,
        )
    assert "just taken" in result.lower() or "pick another" in result.lower()

@pytest.mark.asyncio
async def test_finalize_appointment_payment_link():
    from app.core import tools

    ctx = _ctx(
        centre_uuid="c-1",
        chosen_slot="2030-01-01 10:00:00",
        pending_test_uuids=["t-1"],
        requires_prescription=False,
    )
    with (
        patch("app.core.tools.reserve_slot"),
        patch("app.core.tools.create_appointment", return_value="appt-1"),
        patch(
            "app.core.tools.generate_payment_link",
            return_value="https://pay.example/appt-1",
        ),
    ):
        result = await tools.finalize_appointment(
            patient_name="Amit",
            patient_age=23,
            patient_email="amit@example.com",
            mode_of_sample_collection="Visit Center",
            mode_of_payment="UPI",
            context=ctx,
        )
    assert "https://pay.example/appt-1" in result
    assert "booked" in result.lower()

@pytest.mark.asyncio
async def test_check_report_status_not_verified():
    from app.core import tools

    result = await tools.check_report_status(_ctx())
    assert "not verified" in result.lower()

@pytest.mark.asyncio
async def test_check_report_status_ready():
    from app.core import tools

    report = {"uuid": "r-1", "status": "ready"}
    with (
        patch("app.core.tools.get_report_status", return_value=report),
        patch("app.core.tools.resend_report"),
        patch(
            "app.core.tools.get_report_tests",
            return_value=[{"test_name": "CBC"}],
        ),
    ):
        result = await tools.check_report_status(_ctx(patient_uuid="p-1"))
    assert "ready" in result.lower()
    assert "CBC" in result

@pytest.mark.asyncio
async def test_update_email_invalid():
    from app.core import tools

    result = await tools.update_email_on_file(
        "not-an-email", _ctx(patient_uuid="p-1")
    )
    assert "valid email" in result.lower()

@pytest.mark.asyncio
async def test_update_email_success():
    from app.core import tools

    with patch("app.core.tools.update_patient_email") as mock_upd:
        result = await tools.update_email_on_file(
            "new@example.com", _ctx(patient_uuid="p-1")
        )
    assert "updated" in result.lower()
    mock_upd.assert_called_once()

@pytest.mark.asyncio
async def test_raise_ticket_requires_description():
    from app.core import tools

    result = await tools.raise_ticket("general", "  ", _ctx())
    assert "description" in result.lower()

@pytest.mark.asyncio
async def test_raise_ticket_success():
    from app.core import tools

    with patch("app.core.tools.create_ticket") as mock_ticket:
        result = await tools.raise_ticket(
            "general", "Need help", _ctx(patient_uuid="p-1")
        )
    assert "Ticket raised" in result
    mock_ticket.assert_called_once()

@pytest.mark.asyncio
async def test_safe_tool_swallows_unexpected_errors():
    from app.core import tools

    with patch(
        "app.core.tools.search_centres",
        side_effect=RuntimeError("db down"),
    ):
        result = await tools.find_centres(_ctx())
    assert "something went wrong" in result.lower()