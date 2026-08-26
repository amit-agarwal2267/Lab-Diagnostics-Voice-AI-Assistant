import logging
from functools import wraps
from typing import Any, Callable, TypeVar
from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext
from app.core.state import UserData
from app.db.client import (
    get_test_info,
    search_lab_tests,
    search_centres,
    get_centre_by_code,
    get_available_slots,
    reserve_slot,
    create_appointment,
    generate_prescription_upload_link,
    generate_payment_link,
    get_patient_by_details,
    get_report_status,
    get_report_tests,
    resend_report,
    update_patient_email,
    create_ticket,
)
from app.core.closing import (
    pick, 
    FOLLOWUP_LINES_FIRST, 
    FOLLOWUP_LINES_SECOND, 
    CLOSING_LINES
)

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

_GENERIC_TOOL_ERROR = (
    "Sorry, something went wrong on our side while handling that. "
    "Please try again in a moment, or I can raise a support ticket for you."
)

def _safe_tool(fn: F) -> F:
    """
    Wrap a function tool so unexpected exceptions become a spoken error string instead of crashing the agent turn.
    """

    @wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> str:
        try:
            result = await fn(*args, **kwargs)
            return result if isinstance(result, str) else str(result)
        except ValueError as exc:
            msg = str(exc).strip() or _GENERIC_TOOL_ERROR
            logger.warning("Tool %s ValueError: %s", fn.__name__, msg)
            return msg
        except Exception as exc:
            logger.exception("Tool %s failed unexpectedly", fn.__name__)
            return _GENERIC_TOOL_ERROR

    return wrapper

def _normalize_slot_date(date: str) -> str:
    """
    Convert relative / spoken dates to YYYY-MM-DD (UTC calendar date).
    """
    from datetime import datetime, timedelta, UTC
    import re

    raw = (date or "").strip().lower()
    today = datetime.now(UTC).date()

    if raw in ("today", "todays", "to day"):
        return today.isoformat()
    if raw in ("tomorrow", "tommorow", "tomorow"):
        return (today + timedelta(days=1)).isoformat()
    if raw in ("day after tomorrow", "day after tommorow"):
        return (today + timedelta(days=2)).isoformat()

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw

    m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", raw)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}"

    months = {
        "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
        "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6,
        "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sep": 9,
        "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
    }
    tokens = re.findall(r"[a-z0-9]+", raw)
    month_num = day = year = None
    for t in tokens:
        if t in months:
            month_num = months[t]
        elif t.isdigit():
            n = int(t)
            if n > 31:
                year = n
            elif day is None:
                day = n
            elif month_num is None and 1 <= n <= 12:
                month_num = n
    if year and month_num and day:
        return f"{year:04d}-{month_num:02d}-{day:02d}"
    return date.strip()

@function_tool
@_safe_tool
async def find_centres(
    context: RunContext[UserData],
    pincode: str | None = None,
    city: str | None = None,
    state: str | None = None,
    country: str | None = None,
) -> str:
    """
    Look up lab centres, optionally filtered by pincode, city, state, or country. All filters are optional pass only what the caller gave you. Use this both for general "where is your centre" questions and to resolve a centre before booking.
    """
    centres = search_centres(pincode=pincode, city=city, state=state, country=country)
    if not centres:
        return "No centres found matching those filters."

    lines = []
    for c in centres:
        modes = []
        if c["supports_visit_center"]:
            modes.append("Visit Center")
        if c["supports_home_visit"]:
            modes.append("Home Visit")
        lines.append(
            f"{c['name']} (code: {c['code']}) {c['address']}, {c['city']}, "
            f"{c['state']} {c['pincode']}. Supports: {', '.join(modes) or 'none'}."
        )
    return "\n".join(lines)

@function_tool
@_safe_tool
async def get_lab_test_prices(
    context: RunContext[UserData],
    query: str | None = None,
) -> str:
    """
    Look up lab test prices. Pass a partial test name in `query` to search, or omit it to list all available tests. Use this for general pricing questions that aren't necessarily part of a booking.
    """
    tests = search_lab_tests(query=query)
    if not tests:
        return "No matching tests found."

    lines = [
        f"{t['test_name']}: ₹{t['price']}"
        + (f" (prescription required)" if t["requires_prescription"] else "")
        for t in tests
    ]
    return "\n".join(lines)

@function_tool
@_safe_tool
async def resolve_home_visit_centre(
    pincode: str | None,
    city: str,
    context: RunContext[UserData],
) -> str:
    """
    Automatically find and record the servicing centre for a HOME VISIT collection, using the caller's pincode (preferred, more precise) or city. The caller never needs to know or choose a centre for a home visit this just resolves it behind the scenes. Call this only when mode_of_sample_collection is "Home Visit".

    Returns NO_SERVICE_IN_AREA if nothing supports home visits there tell the caller we don't currently service that area and are still expanding, then offer to raise a general ticket or suggest Visit Center instead.
    """
    centre = None
    if pincode:
        matches = search_centres(pincode=pincode, requires_home_visit=True)
        if matches:
            centre = matches[0]

    if not centre:
        matches = search_centres(city=city, requires_home_visit=True)
        if matches:
            centre = matches[0]

    if not centre:
        return "NO_SERVICE_IN_AREA"

    context.userdata.centre_uuid = centre["uuid"]
    context.userdata.centre_name = centre["name"]
    return f"Home visit will be served by {centre['name']} ({centre['city']})."

@function_tool
@_safe_tool
async def select_visit_centre(
    centre_code_or_city: str,
    context: RunContext[UserData],
) -> str:
    """
    Resolve and record which centre the caller wants to VISIT in-person. Try centre code first; if that doesn't match, search by city (restricted to centres that support walk-in visits) and ask the caller to pick if there's more than one result. Call this only when mode_of_sample_collection is "Visit Center".
    """
    centre = get_centre_by_code(centre_code_or_city)
    if centre and not centre["supports_visit_center"]:
        centre = None

    if not centre:
        matches = search_centres(city=centre_code_or_city, requires_visit_center=True)
        if len(matches) == 1:
            centre = matches[0]
        elif len(matches) > 1:
            names = "; ".join(f"{m['name']} (code: {m['code']})" for m in matches)
            return f"Multiple centres found in that city: {names}. Ask the caller which one."
        else:
            return "No matching centre found. Ask the caller for their city or pincode."

    context.userdata.centre_uuid = centre["uuid"]
    context.userdata.centre_name = centre["name"]
    return f"Centre selected: {centre['name']} ({centre['city']})."

@function_tool
@_safe_tool
async def verify_patient_identity(
    name: str,
    age: int,
    phone: str,
    context: RunContext[UserData],
) -> str:
    """
    Verify a caller's identity against existing patient records.

    Call this before revealing report status or making changes to an existing booking (e.g. correcting an email). Do NOT call this for a brand-new customer with no prior booking that flow doesn't need identity verification.
    """
    patient = get_patient_by_details(name=name, age=age, phone=phone)

    if patient:
        context.userdata.patient_uuid = patient["uuid"]
        context.userdata.patient_name = patient["name"]
        context.userdata.patient_phone = patient["phone_number"]
        context.userdata.is_new_customer = False
        context.userdata.reset_verification()
        return "Identity verified."

    context.userdata.verification_attempts += 1
    if context.userdata.verification_attempts >= 2:
        return "VERIFICATION_FAILED_MAX_ATTEMPTS"
    return "No matching record found. Please double check the details and try again."

@function_tool
@_safe_tool
async def check_prescription_requirement(
    test_names: list[str],
    context: RunContext[UserData],
) -> str:
    """
    Check whether any of the requested lab tests require a prescription, and return each test's pre-test instructions (e.g. fasting requirements). Call this after a centre has been selected.
    """
    if not test_names:
        return "No test names provided. Ask the caller which tests they need."

    infos = []
    unknown = []
    for t in test_names:
        try:
            infos.append(get_test_info(t))
        except ValueError:
            unknown.append(t)

    if unknown and not infos:
        return f"Unknown test(s): {', '.join(unknown)}. Ask the caller to confirm the test names."

    context.userdata.pending_tests = [i["test_name"] for i in infos]
    context.userdata.pending_test_uuids = [i["uuid"] for i in infos]
    context.userdata.requires_prescription = any(i["requires_prescription"] for i in infos)

    lines = [
        f"{i['test_name']}: ₹{i['price']}"
        + (f", instructions: {i['pre_test_instructions']}" if i.get("pre_test_instructions") else "")
        for i in infos
    ]
    suffix = f"\nPrescription required: {context.userdata.requires_prescription}"
    if unknown:
        suffix += f"\nCould not find: {', '.join(unknown)}"
    return "\n".join(lines) + suffix

@function_tool
@_safe_tool
async def get_slots(date: str, context: RunContext[UserData]) -> str:
    """
    List available appointment slots for a given date at the already-resolved centre. The centre must already be set via resolve_home_visit_centre or select_visit_centre.

    Pass `date` as YYYY-MM-DD, or a relative word the tool understands:
    "today", "tomorrow", "day after tomorrow", or a spoken date like "24 August 2026". Call this ONCE per requested date - do not retry the same date if the result is empty; instead tell the caller and offer another day.
    """
    if not context.userdata.is_centre_selected():
        return "No centre resolved yet. Determine mode of sample collection and resolve the centre first."

    resolved = _normalize_slot_date(date)
    slots = get_available_slots(
        centre_uuid=context.userdata.centre_uuid, date=resolved
    )
    if slots:
        return f"Available slots on {resolved}: " + ", ".join(slots)

    return (
        f"No slots available on {resolved}. "
        "Tell the caller that date is full or has no openings, and ask them "
        "to pick another day (for example tomorrow). Do NOT call get_slots "
        "again for the same date."
    )

@function_tool
@_safe_tool
async def select_slot(slot_datetime: str, context: RunContext[UserData]) -> str:
    """Record the caller's chosen appointment slot after confirming availability."""
    if not slot_datetime or not str(slot_datetime).strip():
        return "No slot provided. Ask the caller to pick a time."
    context.userdata.chosen_slot = slot_datetime
    return f"Slot {slot_datetime} noted."

@function_tool
@_safe_tool
async def finalize_appointment(
    patient_name: str,
    patient_age: int,
    patient_email: str,
    mode_of_sample_collection: str,
    mode_of_payment: str,
    context: RunContext[UserData],
) -> str:
    """
    Create the appointment once centre, tests, slot, and patient info are all collected.

    If a prescription is required, this reserves the slot WITHOUT confirming it and sends a prescription-upload link, the booking stays pending until an executive confirms it manually. If no prescription is required, this sends a payment link instead.
    """
    if not context.userdata.is_centre_selected():
        return "No centre resolved. Determine mode of sample collection and resolve a centre before finalizing."
    if not context.userdata.chosen_slot:
        return "No slot selected. Call select_slot before finalizing."
    if not context.userdata.pending_test_uuids:
        return "No tests selected. Call check_prescription_requirement before finalizing."
    if not patient_name or not patient_email:
        return "Patient name and email are required before finalizing."

    context.userdata.patient_name = patient_name
    context.userdata.mode_of_sample_collection = mode_of_sample_collection
    context.userdata.mode_of_payment = mode_of_payment

    try:
        reserve_slot(context.userdata.centre_uuid, context.userdata.chosen_slot)
    except ValueError:
        return "That slot was just taken by someone else. Ask the caller to pick another time."

    appointment_id = create_appointment(
        patient_name=patient_name,
        patient_age=patient_age,
        patient_email=patient_email,
        centre_uuid=context.userdata.centre_uuid,
        test_uuids=context.userdata.pending_test_uuids,
        slot=context.userdata.chosen_slot,
        requires_prescription=bool(context.userdata.requires_prescription),
        mode_of_sample_collection=mode_of_sample_collection,
        mode_of_payment=mode_of_payment,
    )

    if context.userdata.requires_prescription:
        link = generate_prescription_upload_link(appointment_id)
        context.userdata.prescription_upload_link_sent = True
        return (
            f"Appointment reserved but not yet confirmed. "
            f"Upload your prescription here: {link}. "
            f"An executive will reach you shortly to confirm."
        )
    payment_link = generate_payment_link(appointment_id)
    return f"Appointment booked. Complete payment here: {payment_link}."

@function_tool
@_safe_tool
async def check_report_status(context: RunContext[UserData]) -> str:
    """
    Check whether the caller's lab report is ready. Requires identity verification first via verify_patient_identity.
    """
    if not context.userdata.is_identity_verified():
        return "Identity not verified yet."

    try:
        report = get_report_status(context.userdata.patient_uuid)
    except ValueError as exc:
        return str(exc) if str(exc).strip() else "No report found for this patient."

    if report["status"] == "ready":
        resend_report(report["uuid"], channel="email")
        tests = get_report_tests(report["uuid"])
        test_names = ", ".join(t["test_name"] for t in tests) or "your test(s)"
        return f"Report for {test_names} is ready -- resent to the patient's email."
    return "Report is still being processed."

@function_tool
@_safe_tool
async def update_email_on_file(
    new_email: str,
    context: RunContext[UserData],
) -> str:
    """
    Update the email on an existing booking. Requires identity verification first via verify_patient_identity.
    """
    if not context.userdata.is_identity_verified():
        return "Identity not verified yet."
    if not new_email or "@" not in new_email:
        return "That does not look like a valid email. Ask the caller to confirm the address."
    update_patient_email(context.userdata.patient_uuid, new_email)
    return "Email updated successfully."

@function_tool
@_safe_tool
async def raise_ticket(
    category: str,
    description: str,
    context: RunContext[UserData],
) -> str:
    """
    Raise a support ticket for human follow-up. Use this for:
    - new customers with a general inquiry (no verification needed)
    - failed identity verification after repeated attempts
    """
    if not description or not str(description).strip():
        return "A short description is required before raising a ticket."
    create_ticket(
        patient_uuid=context.userdata.patient_uuid,
        category=category or "general",
        description=description,
    )
    return "Ticket raised. An executive will call you back shortly."


@function_tool
@_safe_tool
async def offer_more_help(context: RunContext[UserData]) -> str:
    """
    Call this once the caller's current request is fully resolved. Handles asking if they need anything else, up to twice, then ends the call. Do not write your own follow-up or goodbye text.
    """
    ud = context.userdata
    ud.followup_attempts += 1

    if ud.followup_attempts == 1:
        await context.session.say(pick(FOLLOWUP_LINES_FIRST))
        return "Asked once. Wait for the caller's reply."
    elif ud.followup_attempts == 2:
        await context.session.say(pick(FOLLOWUP_LINES_SECOND))
        return "Asked a second time. Wait for the caller's reply."
    else:
        await context.session.say(pick(CLOSING_LINES), allow_interruptions=False)
        context.session.shutdown()
        return "Call ended after two unanswered follow-ups."

@function_tool
@_safe_tool
async def close_call(context: RunContext[UserData]) -> str:
    """
    Call this directly when the caller explicitly says no / goodbye / nothing else needed. Skips further follow-ups.
    """
    context.userdata.reset_followups()
    await context.session.say(pick(CLOSING_LINES), allow_interruptions=False)
    context.session.shutdown()
    return "Call ended."