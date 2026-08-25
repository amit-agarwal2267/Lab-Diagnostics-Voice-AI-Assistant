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

@function_tool
async def find_centres(
    context: RunContext[UserData],
    pincode: str | None = None,
    city: str | None = None,
    state: str | None = None,
    country: str | None = None,
) -> str:
    """Look up lab centres, optionally filtered by pincode, city, state,
    and/or country. All filters are optional -- pass only what the caller
    gave you. Use this both for general "where is your centre" questions
    and to resolve a centre before booking.
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
            f"{c['name']} (code: {c['code']}) -- {c['address']}, {c['city']}, "
            f"{c['state']} {c['pincode']}. Supports: {', '.join(modes) or 'none'}."
        )
    return "\n".join(lines)

@function_tool
async def get_lab_test_prices(
    context: RunContext[UserData],
    query: str | None = None,
) -> str:
    """Look up lab test prices. Pass a partial test name in `query` to
    search, or omit it to list all available tests. Use this for general
    pricing questions that aren't necessarily part of a booking yet.
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
async def resolve_home_visit_centre(
    pincode: str | None,
    city: str,
    context: RunContext[UserData],
) -> str:
    """Automatically find and record the servicing centre for a HOME VISIT
    collection, using the caller's pincode (preferred, more precise) or
    city. The caller never needs to know or choose a centre for a home
    visit -- this just resolves it behind the scenes. Call this only when
    mode_of_sample_collection is "Home Visit".

    Returns NO_SERVICE_IN_AREA if nothing supports home visits there --
    tell the caller we don't currently service that area and are still
    expanding, then offer to raise a general ticket or suggest Visit Center
    instead.
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
async def select_visit_centre(
    centre_code_or_city: str,
    context: RunContext[UserData],
) -> str:
    """Resolve and record which centre the caller wants to VISIT in
    person. Try centre code first; if that doesn't match, search by city
    (restricted to centres that support walk-in visits) and ask the caller
    to pick if there's more than one result. Call this only when
    mode_of_sample_collection is "Visit Center".
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
async def verify_patient_identity(
    name: str,
    age: int,
    phone: str,
    context: RunContext[UserData],
) -> str:
    """Verify a caller's identity against existing patient records.

    Call this before revealing report status or making changes to an
    existing booking (e.g. correcting an email). Do NOT call this for
    a brand-new customer with no prior booking -- that flow doesn't
    need identity verification.
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
async def check_prescription_requirement(
    test_names: list[str],
    context: RunContext[UserData],
) -> str:
    """Check whether any of the requested lab tests require a prescription,
    and return each test's pre-test instructions (e.g. fasting requirements).
    Call this after a centre has been selected.
    """
    infos = [get_test_info(t) for t in test_names]
    context.userdata.pending_tests = [i["test_name"] for i in infos]
    context.userdata.pending_test_uuids = [i["uuid"] for i in infos]
    context.userdata.requires_prescription = any(i["requires_prescription"] for i in infos)

    lines = [
        f"{i['test_name']}: ₹{i['price']}"
        + (f", instructions: {i['pre_test_instructions']}" if i.get("pre_test_instructions") else "")
        for i in infos
    ]
    return "\n".join(lines) + f"\nPrescription required: {context.userdata.requires_prescription}"

@function_tool
async def get_slots(date: str, context: RunContext[UserData]) -> str:
    """List available appointment slots for a given date at the
    already-resolved centre. The centre must already be set via
    resolve_home_visit_centre or select_visit_centre."""
    if not context.userdata.is_centre_selected():
        return "No centre resolved yet. Determine mode of sample collection and resolve the centre first."
    slots = get_available_slots(centre_uuid=context.userdata.centre_uuid, date=date)
    return ", ".join(slots) if slots else "No slots available on that date."

@function_tool
async def select_slot(slot_datetime: str, context: RunContext[UserData]) -> str:
    """Record the caller's chosen appointment slot after confirming availability."""
    context.userdata.chosen_slot = slot_datetime
    return f"Slot {slot_datetime} noted."

@function_tool
async def finalize_appointment(
    patient_name: str,
    patient_age: int,
    patient_email: str,
    mode_of_sample_collection: str,
    mode_of_payment: str,
    context: RunContext[UserData],
) -> str:
    """Create the appointment once centre, tests, slot, and patient info
    are all collected.

    If a prescription is required, this reserves the slot WITHOUT confirming
    it and sends a prescription-upload link -- the booking stays pending
    until an executive confirms it manually. If no prescription is required,
    this sends a payment link instead.
    """
    if not context.userdata.is_centre_selected():
        return "No centre resolved. Determine mode of sample collection and resolve a centre before finalizing."
    if not context.userdata.chosen_slot:
        return "No slot selected. Call select_slot before finalizing."
    if not context.userdata.pending_test_uuids:
        return "No tests selected. Call check_prescription_requirement before finalizing."

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
        requires_prescription=context.userdata.requires_prescription,
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
async def check_report_status(context: RunContext[UserData]) -> str:
    """Check whether the caller's lab report is ready. Requires identity
    verification first via verify_patient_identity.
    """
    if not context.userdata.is_identity_verified():
        return "Identity not verified yet."

    report = get_report_status(context.userdata.patient_uuid)
    if report["status"] == "ready":
        resend_report(report["uuid"], channel="email")
        tests = get_report_tests(report["uuid"])
        test_names = ", ".join(t["test_name"] for t in tests) or "your test(s)"
        return f"Report for {test_names} is ready -- resent to the patient's email."
    return "Report is still being processed."

@function_tool
async def update_email_on_file(
    new_email: str,
    context: RunContext[UserData],
) -> str:
    """Update the email on an existing booking. Requires identity
    verification first via verify_patient_identity.
    """
    if not context.userdata.is_identity_verified():
        return "Identity not verified yet."
    update_patient_email(context.userdata.patient_uuid, new_email)
    return "Email updated successfully."

@function_tool
async def raise_ticket(
    category: str,
    description: str,
    context: RunContext[UserData],
) -> str:
    """Raise a support ticket for human follow-up. Use this for:
    - new customers with a general inquiry (no verification needed)
    - failed identity verification after repeated attempts
    """
    create_ticket(
        patient_uuid=context.userdata.patient_uuid,   
        category=category,
        description=description,
    )
    return "Ticket raised. An executive will call you back shortly."