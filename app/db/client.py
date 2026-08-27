import os
import uuid
from datetime import datetime, timedelta, UTC
import psycopg2
import psycopg2.extras
from app.config.config import get_settings

settings = get_settings()

def get_connection():
    return psycopg2.connect(
        settings.db_url.get_secret_value(),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )

def get_test_info(test_name: str) -> dict:
    """
    Resolve a lab test by name. Accepts full names or common short forms
    (e.g. "CBC", "HbA1c") via case-insensitive exact then substring match.
    Prefers the shortest matching name when multiple rows contain the query.
    """
    q = (test_name or "").strip()
    if not q:
        raise ValueError("Unknown test: (empty)")

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT uuid, test_name, price, requires_prescription, pre_test_instructions "
            "FROM lab_test WHERE test_name ILIKE %s",
            (q,),
        )
        row = cur.fetchone()
        if row:
            return dict(row)

        cur.execute(
            "SELECT uuid, test_name, price, requires_prescription, pre_test_instructions "
            "FROM lab_test WHERE test_name ILIKE %s ORDER BY length(test_name) ASC, test_name",
            (f"%{q}%",),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Unknown test: {test_name}")
        return dict(row)

def search_lab_tests(query: str | None = None) -> list[dict]:
    """General-query lookup for test prices. If query is given, does a
    fuzzy ILIKE match on test_name; otherwise returns all tests.
    """
    with get_connection() as conn, conn.cursor() as cur:
        if query:
            cur.execute(
                "SELECT uuid, test_name, price, requires_prescription, pre_test_instructions "
                "FROM lab_test WHERE test_name ILIKE %s ORDER BY test_name",
                (f"%{query}%",),
            )
        else:
            cur.execute(
                "SELECT uuid, test_name, price, requires_prescription, pre_test_instructions "
                "FROM lab_test ORDER BY test_name"
            )
        return [dict(row) for row in cur.fetchall()]

def search_centres(
    pincode: str | None = None,
    city: str | None = None,
    state: str | None = None,
    country: str | None = None,
    requires_home_visit: bool = False,
    requires_visit_center: bool = False,
) -> list[dict]:
    """
    Return active centres matching any combination of the given filters. All location filters are optional and AND-combined; omit a filter to not constrain by it. Set requires_home_visit / requires_visit_center to restrict to centres that support that collection mode.

    City/state matching is token-aware: a spoken phrase like "Kota Rajasthan" matches a row with city='Kota' (and optionally state='Rajasthan') because each significant word is tried with ILIKE.
    """
    clauses = ["is_active = TRUE"]
    params: list = []

    if pincode:
        clauses.append("pincode = %s")
        params.append(pincode.replace(" ", "").strip())
    if city:
        city_tokens = _location_tokens(city)
        if city_tokens:
            token_clauses = []
            for tok in city_tokens:
                token_clauses.append("city ILIKE %s")
                params.append(f"%{tok}%")
            clauses.append("(" + " OR ".join(token_clauses) + ")")
    if state:
        state_tokens = _location_tokens(state)
        if state_tokens:
            token_clauses = []
            for tok in state_tokens:
                token_clauses.append("state ILIKE %s")
                params.append(f"%{tok}%")
            clauses.append("(" + " OR ".join(token_clauses) + ")")
    if country:
        clauses.append("country ILIKE %s")
        params.append(f"%{country.strip()}%")
    if requires_home_visit:
        clauses.append("supports_home_visit = TRUE")
    if requires_visit_center:
        clauses.append("supports_visit_center = TRUE")

    query = (
        "SELECT uuid, name, code, address, phone_number, email, pincode, city, "
        "district, state, country, map_location, supports_home_visit, "
        "supports_visit_center FROM centre WHERE " + " AND ".join(clauses) +
        " ORDER BY city, name"
    )

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]

def _location_tokens(value: str) -> list[str]:
    """Split a free-form location phrase into searchable tokens.

    Drops tiny words (e.g. "in", "of") so "home visit in Kota, Rajasthan"
    still yields ["Kota", "Rajasthan"].
    """
    import re

    raw = re.split(r"[\s,;/|]+", (value or "").strip())
    return [t for t in raw if len(t) >= 3]

def get_centre_by_code(code: str) -> dict | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT uuid, name, code, address, phone_number, email, pincode, city, "
            "district, state, country, map_location, supports_home_visit, "
            "supports_visit_center FROM centre WHERE code = %s AND is_active = TRUE",
            (code,),
        )
        row = cur.fetchone()
        return dict(row) if row else None

def get_available_slots(centre_uuid: str, date: str) -> list[str]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT slot_datetime FROM slot_inventory "
            "WHERE centre_uuid = %s AND slot_date = %s AND is_booked = FALSE "
            "ORDER BY slot_datetime",
            (centre_uuid, date),
        )
        return [str(row["slot_datetime"]) for row in cur.fetchall()]

def reserve_slot(centre_uuid: str, slot_datetime: str) -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE slot_inventory SET is_booked = TRUE "
            "WHERE centre_uuid = %s AND slot_datetime = %s AND is_booked = FALSE",
            (centre_uuid, slot_datetime),
        )
        if cur.rowcount == 0:
            raise ValueError("Slot is no longer available.")
        conn.commit()

def create_appointment(
    patient_name: str,
    patient_age: int,
    patient_email: str,
    centre_uuid: str,
    test_uuids: list[str],
    slot: str,
    requires_prescription: bool,
    mode_of_sample_collection: str,
    mode_of_payment: str | None,
) -> str:
    """Creates (or reuses) the patient, creates the appointment, and links
    every test in `test_uuids` via the appointment_test junction table.
    Does NOT reserve the slot -- call reserve_slot separately, ideally
    before this, since the appointment references a slot_datetime rather
    than the slot_inventory row itself.
    """
    appointment_id = str(uuid.uuid4())
    status = "pending_confirmation" if requires_prescription else "awaiting_payment"

    with get_connection() as conn, conn.cursor() as cur:
        
        cur.execute(
            "SELECT uuid FROM patient WHERE email_address = %s", (patient_email,)
        )
        existing = cur.fetchone()
        if existing:
            patient_uuid = existing["uuid"]
        else:
            cur.execute(
                "INSERT INTO patient (name, age, email_address, created_at) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (email_address) DO UPDATE SET name = EXCLUDED.name "
                "RETURNING uuid",
                (patient_name, patient_age, patient_email, datetime.now(UTC)),
            )
            patient_uuid = cur.fetchone()["uuid"]

        cur.execute(
            "INSERT INTO appointment "
            "(uuid, patient_uuid, centre_uuid, slot_datetime, requires_prescription, "
            " status, mode_of_sample_collection, mode_of_payment, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                appointment_id, patient_uuid, centre_uuid, slot, requires_prescription,
                status, mode_of_sample_collection, mode_of_payment, datetime.now(UTC),
            ),
        )

        cur.executemany(
            "INSERT INTO appointment_test (appointment_uuid, lab_test_uuid) VALUES (%s, %s)",
            [(appointment_id, test_uuid) for test_uuid in test_uuids],
        )

        conn.commit()
    return appointment_id

def get_appointment_tests(appointment_uuid: str) -> list[dict]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT lt.uuid, lt.test_name, lt.price "
            "FROM appointment_test at "
            "JOIN lab_test lt ON lt.uuid = at.lab_test_uuid "
            "WHERE at.appointment_uuid = %s",
            (appointment_uuid,),
        )
        return [dict(row) for row in cur.fetchall()]

def generate_prescription_upload_link(appointment_id: str) -> str:
    base_url = os.environ.get("PRESCRIPTION_UPLOAD_BASE_URL", settings.prescription_upload_base_url)
    return f"{base_url}/{appointment_id}"

def generate_payment_link(appointment_id: str) -> str:
    base_url = os.environ.get("PAYMENT_BASE_URL", settings.payment_base_url)
    return f"{base_url}/{appointment_id}"

def get_patient_by_details(name: str, age: int, phone: str) -> dict | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT uuid, name, phone_number FROM patient "
            "WHERE name ILIKE %s AND age = %s AND RIGHT(phone_number,4)=RIGHT(%s,4)",
            (name, age, phone),
        )
        row = cur.fetchone()
        if row:
            return dict(row)

        cur.execute(
            "SELECT uuid, name, phone_number FROM patient "
            "WHERE dmetaphone(name) = dmetaphone(%s) AND age = %s "
            "AND RIGHT(phone_number,4) = RIGHT(%s,4)",
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
            "SELECT uuid, status, sample_given_date, generation_date, storage_path "
            "FROM report "
            "WHERE patient_uuid = %s AND deleted_at IS NULL "
            "ORDER BY generation_date DESC NULLS LAST LIMIT 1",
            (patient_uuid,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError("No report found for this patient.")
        return dict(row)

def get_report_tests(report_uuid: str) -> list[dict]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT lt.uuid, lt.test_name "
            "FROM report_test rt "
            "JOIN lab_test lt ON lt.uuid = rt.lab_test_uuid "
            "WHERE rt.report_uuid = %s",
            (report_uuid,),
        )
        return [dict(row) for row in cur.fetchall()]

def resend_report(report_uuid: str, channel: str) -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE report SET last_resent_at = %s, last_resent_channel = %s WHERE uuid = %s",
            (datetime.now(UTC), channel, report_uuid),
        )
        conn.commit()

def get_expired_reports(days: int | None = None) -> list[dict]:
    days = days if days is not None else settings.report_ttl_days
    cutoff = (datetime.now(UTC) - timedelta(days=days)).date()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT uuid, storage_path FROM report "
            "WHERE generation_date < %s AND storage_path IS NOT NULL AND deleted_at IS NULL",
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