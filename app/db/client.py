import os
import uuid
from datetime import datetime, timedelta, UTC
import psycopg2
import psycopg2.extras
from app.config.config import get_settings

settings = get_settings()

def get_connection():
    return psycopg2.connect(settings.db_url.get_secret_value(), cursor_factory=psycopg2.extras.RealDictCursor)

def get_test_info(test_name: str) -> dict:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT uuid, test_name, price, requires_prescription, pre_test_instructions "
            "FROM lab_test WHERE test_name ILIKE %s",
            (test_name,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Unknown test: {test_name}")
        return dict(row)

def get_available_slots(date: str) -> list[str]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT slot_datetime FROM slot_inventory "
            "WHERE slot_date = %s AND is_booked = FALSE ORDER BY slot_datetime",
            (date,),
        )
        return [str(row["slot_datetime"]) for row in cur.fetchall()]


def reserve_slot(slot_datetime: str) -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE slot_inventory SET is_booked = TRUE WHERE slot_datetime = %s",
            (slot_datetime,),
        )
        conn.commit()


def create_appointment(
    patient_name: str,
    patient_age: int,
    patient_email: str,
    tests: list[str],
    slot: str,
    requires_prescription: bool,
    mode_of_sample_collection: str,
    mode_of_payment: str,
) -> str:
    appointment_id = str(uuid.uuid4())
    status = "pending_confirmation" if requires_prescription else "awaiting_payment"

    with get_connection() as conn, conn.cursor() as cur:
        # find-or-create patient by name+email (simple match for MVP)
        cur.execute(
            "SELECT uuid FROM patient WHERE email_address = %s", (patient_email,)
        )
        existing = cur.fetchone()
        if existing:
            patient_uuid = existing["uuid"]
        else:
            cur.execute(
                "INSERT INTO patient (name, age, email_address, created_at) "
                "VALUES (%s, %s, %s, %s) RETURNING uuid",
                (patient_name, patient_age, patient_email, datetime.now(UTC)),
            )
            patient_uuid = cur.fetchone()["uuid"]

        cur.execute(
            "INSERT INTO appointment "
            "(uuid, patient_uuid, lab_test_uuids, slot_datetime, requires_prescription, "
            " status, mode_of_sample_collection, mode_of_payment, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                appointment_id, patient_uuid, tests, slot, requires_prescription,
                status, mode_of_sample_collection, mode_of_payment, datetime.now(UTC),
            ),
        )
        conn.commit()
    return appointment_id


def generate_prescription_upload_link(appointment_id: str) -> str:
    base_url = os.environ.get("PRESCRIPTION_UPLOAD_BASE_URL", "https://lab.example.com/upload")
    return f"{base_url}/{appointment_id}"


def generate_payment_link(appointment_id: str) -> str:
    base_url = os.environ.get("PAYMENT_BASE_URL", "https://lab.example.com/pay")
    return f"{base_url}/{appointment_id}"

def get_patient_by_details(name: str, age: int, phone: str) -> dict | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT uuid, name, phone_number FROM patient "
            "WHERE name ILIKE %s AND age = %s "
            "AND RIGHT(phone_number, 4) = RIGHT(%s, 4)",
            (name, age, phone),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def update_patient_email(patient_uuid: str, new_email: str) -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE patient SET email_address = %s WHERE uuid = %s",
            (new_email, patient_uuid),
        )
        conn.commit()

def get_report_status(patient_uuid: str) -> dict:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT uuid, status FROM report "
            "WHERE patient_uuid = %s ORDER BY generation_date DESC LIMIT 1",
            (patient_uuid,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError("No report found for this patient.")
        return dict(row)


def resend_report(report_uuid: str, channel: str) -> None:
    # placeholder -- wire into actual email/WhatsApp sending service
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE report SET last_resent_at = %s, last_resent_channel = %s WHERE uuid = %s",
            (datetime.now(UTC), channel, report_uuid),
        )
        conn.commit()

def create_ticket(patient_uuid: str | None, category: str, description: str) -> str:
    ticket_id = str(uuid.uuid4())
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO ticket (uuid, patient_uuid, category, description, status, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (ticket_id, patient_uuid, category, description, "open", datetime.now(UTC)),
        )
        conn.commit()
    return ticket_id

def get_expired_reports(days: int = 14) -> list[dict]:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT uuid, storage_path FROM report "
            "WHERE generation_date < %s AND storage_path IS NOT NULL",
            (cutoff,),
        )
        return [dict(row) for row in cur.fetchall()]


def clear_report_storage_path(report_uuid: str) -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE report SET storage_path = NULL, deleted_at = %s WHERE uuid = %s",
            (datetime.now(UTC), report_uuid),
        )
        conn.commit()