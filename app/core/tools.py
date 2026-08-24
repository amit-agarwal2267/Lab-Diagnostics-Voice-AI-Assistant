from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext

from app.core.state import UserData
from app.db.client import (
    get_test_info,
    get_available_slots,
    reserve_slot,
    create_appointment,
    generate_prescription_upload_link,
    get_patient_by_details,
    get_report_status,
    resend_report,
    update_patient_email,
    create_ticket,
    generate_payment_link,
)

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
    """
    context.userdata.pending_tests = test_names
    infos = [get_test_info(t) for t in test_names]
    context.userdata.requires_prescription = any(i["requires_prescription"] for i in infos)

    lines = [
        f"{i['test_name']}: ₹{i['price']}"
        + (f", instructions: {i['pre_test_instructions']}" if i.get("pre_test_instructions") else "")
        for i in infos
    ]
    return "\n".join(lines) + f"\nPrescription required: {context.userdata.requires_prescription}"


@function_tool
async def get_slots(date: str, context: RunContext[UserData]) -> str:
    """List available appointment slots for a given date."""
    slots = get_available_slots(date=date)
    return ", ".join(slots)


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
    """Create the appointment once tests, slot, and patient info are all collected.

    If a prescription is required, this reserves the slot WITHOUT confirming
    it and sends a prescription-upload link -- the booking stays pending
    until an executive confirms it manually. If no prescription is required,
    this sends a payment link instead.
    """
    context.userdata.patient_name = patient_name
    context.userdata.mode_of_sample_collection = mode_of_sample_collection
    context.userdata.mode_of_payment = mode_of_payment

    appointment_id = create_appointment(
        patient_name=patient_name,
        patient_age=patient_age,
        patient_email=patient_email,
        tests=context.userdata.pending_tests,
        slot=context.userdata.chosen_slot,
        requires_prescription=context.userdata.requires_prescription,
        mode_of_sample_collection=mode_of_sample_collection,
        mode_of_payment=mode_of_payment,
    )
    reserve_slot(context.userdata.chosen_slot)

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
        return "Report is ready -- resent to the patient's email."
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
        patient_uuid=context.userdata.patient_uuid,   # may be None for new customers
        category=category,
        description=description,
    )
    return "Ticket raised. An executive will call you back shortly."