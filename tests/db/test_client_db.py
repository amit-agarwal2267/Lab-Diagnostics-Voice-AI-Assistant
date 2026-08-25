import uuid
from datetime import datetime, timedelta, UTC
import pytest
from app.db import client

@pytest.fixture
def db_connection():
    """
    Verifies that the test can connect to PostgreSQL.
    """
    conn = client.get_connection()
    try:
        yield conn
    finally:
        conn.close()

@pytest.fixture
def seeded_centre_uuid():
    """
    Resolves the centre_uuid that init_db.sql seeded slot_inventory rows
    against for CURRENT_DATE + 1, rather than hardcoding one. Keeps tests
    decoupled from a specific centre's uuid/code.
    """
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).date()
    with client.get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT centre_uuid FROM slot_inventory "
            "WHERE slot_date = %s AND is_booked = FALSE LIMIT 1",
            (tomorrow,),
        )
        row = cur.fetchone()
    assert row is not None, "No seeded, unbooked slot_inventory found for tomorrow"
    return str(row["centre_uuid"])

@pytest.fixture
def any_active_centre_uuid():
    """Any active centre, for tests that just need a valid FK target."""
    with client.get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT uuid FROM centre WHERE is_active = TRUE LIMIT 1")
        row = cur.fetchone()
    assert row is not None, "No active centre seeded"
    return str(row["uuid"])

def test_get_connection(db_connection):
    assert db_connection is not None
    assert not db_connection.closed

def test_get_test_info_existing():
    result = client.get_test_info("CBC")

    assert result is not None
    assert result["test_name"] == "CBC"
    assert result["price"] == 350
    assert result["requires_prescription"] is False

def test_get_test_info_unknown():
    with pytest.raises(ValueError, match="Unknown test"):
        client.get_test_info("DOES NOT EXIST")

def test_search_lab_tests_query():
    results = client.search_lab_tests(query="CBC")

    assert isinstance(results, list)
    assert any(t["test_name"] == "CBC" for t in results)

def test_search_lab_tests_no_query_returns_all():
    results = client.search_lab_tests()

    assert isinstance(results, list)
    assert len(results) >= 1

def test_search_centres_no_filters_returns_active_only():
    results = client.search_centres()

    assert isinstance(results, list)
    assert len(results) >= 1

def test_search_centres_filters_by_home_visit_support():
    results = client.search_centres(requires_home_visit=True)

    assert all(c["supports_home_visit"] for c in results)

def test_search_centres_filters_by_visit_center_support():
    results = client.search_centres(requires_visit_center=True)

    assert all(c["supports_visit_center"] for c in results)

def test_search_centres_unmatched_location_returns_empty():
    results = client.search_centres(pincode="000000")

    assert results == []


def test_search_centres_matches_city_within_spoken_phrase():
    """STT often yields 'Kota Rajasthan'; DB city is just 'Kota'."""
    results = client.search_centres(city="Kota Rajasthan", requires_home_visit=True)

    assert len(results) >= 1
    assert any(c["city"].lower() == "kota" for c in results)
    assert all(c["supports_home_visit"] for c in results)


def test_search_centres_matches_city_alone():
    results = client.search_centres(city="Kota", requires_home_visit=True)

    assert len(results) >= 1
    assert any("kota" in c["city"].lower() for c in results)


def test_get_centre_by_code_existing(any_active_centre_uuid):
    with client.get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT code FROM centre WHERE uuid = %s", (any_active_centre_uuid,))
        code = cur.fetchone()["code"]

    centre = client.get_centre_by_code(code)

    assert centre is not None
    assert centre["uuid"] == any_active_centre_uuid

def test_get_centre_by_code_unknown():
    centre = client.get_centre_by_code("DOES-NOT-EXIST")

    assert centre is None

def test_get_available_slots(seeded_centre_uuid):
    """
    init_db.sql creates slots for CURRENT_DATE + 1.
    """
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).date()

    slots = client.get_available_slots(seeded_centre_uuid, str(tomorrow))

    assert isinstance(slots, list)
    assert len(slots) >= 1

def test_reserve_slot(seeded_centre_uuid):
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).date()

    slots = client.get_available_slots(seeded_centre_uuid, str(tomorrow))
    assert slots

    slot = slots[0]

    client.reserve_slot(seeded_centre_uuid, slot)

    try:
        remaining_slots = client.get_available_slots(seeded_centre_uuid, str(tomorrow))
        assert slot not in remaining_slots
    finally:
        
        with client.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE slot_inventory SET is_booked = FALSE "
                "WHERE centre_uuid = %s AND slot_datetime = %s",
                (seeded_centre_uuid, slot),
            )
            conn.commit()

def test_reserve_slot_already_booked_raises(seeded_centre_uuid):
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).date()
    slots = client.get_available_slots(seeded_centre_uuid, str(tomorrow))
    assert slots
    slot = slots[0]

    client.reserve_slot(seeded_centre_uuid, slot)
    try:
        with pytest.raises(ValueError, match="no longer available"):
            client.reserve_slot(seeded_centre_uuid, slot)
    finally:
        with client.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE slot_inventory SET is_booked = FALSE "
                "WHERE centre_uuid = %s AND slot_datetime = %s",
                (seeded_centre_uuid, slot),
            )
            conn.commit()

def test_get_patient_by_details_matching_phone_last_four_digits():
    """
    The current implementation intentionally compares only the
    last four digits of the phone number.
    """
    patient = client.get_patient_by_details(
        name="Amit Agarwal",
        age=23,
        phone="1234561111",
    )

    assert patient is not None
    assert patient["name"] == "Amit Agarwal"
    assert patient["phone_number"] == "9990001111"

def test_get_patient_by_details_wrong_name():
    patient = client.get_patient_by_details(
        name="Unknown Person",
        age=23,
        phone="9990001111",
    )

    assert patient is None

def test_get_patient_by_details_wrong_age():
    patient = client.get_patient_by_details(
        name="Amit Agarwal",
        age=99,
        phone="9990001111",
    )

    assert patient is None

def test_update_patient_email():
    patient_uuid = "e1111111-1111-1111-1111-111111111111"
    original_email = "amit.test@example.com"
    new_email = f"test-{uuid.uuid4()}@example.com"

    try:
        client.update_patient_email(patient_uuid, new_email)

        with client.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT email_address FROM patient WHERE uuid = %s",
                (patient_uuid,),
            )
            row = cur.fetchone()

        assert row["email_address"] == new_email

    finally:
        client.update_patient_email(patient_uuid, original_email)

def test_create_appointment_existing_patient(any_active_centre_uuid):
    appointment_id = client.create_appointment(
        patient_name="Amit Agarwal",
        patient_age=23,
        patient_email="amit.test@example.com",
        centre_uuid=any_active_centre_uuid,
        test_uuids=[],
        slot="2030-01-01 10:00:00",
        requires_prescription=False,
        mode_of_sample_collection="Visit Center",
        mode_of_payment="UPI",
    )

    assert appointment_id is not None

    with client.get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT uuid, patient_uuid, centre_uuid, status, requires_prescription
            FROM appointment
            WHERE uuid = %s
            """,
            (appointment_id,),
        )
        appointment = cur.fetchone()

        cur.execute(
            "DELETE FROM appointment WHERE uuid = %s",
            (appointment_id,),
        )
        conn.commit()

    assert appointment["uuid"] == appointment_id
    assert str(appointment["patient_uuid"]) == (
        "e1111111-1111-1111-1111-111111111111"
    )
    assert str(appointment["centre_uuid"]) == any_active_centre_uuid
    assert appointment["status"] == "awaiting_payment"
    assert appointment["requires_prescription"] is False

def test_create_appointment_requires_prescription(any_active_centre_uuid):
    appointment_id = client.create_appointment(
        patient_name="Amit Agarwal",
        patient_age=23,
        patient_email="amit.test@example.com",
        centre_uuid=any_active_centre_uuid,
        test_uuids=[],
        slot="2030-01-02 10:00:00",
        requires_prescription=True,
        mode_of_sample_collection="Home Visit",
        mode_of_payment="Cash on Visit",
    )

    try:
        with client.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT status, requires_prescription,
                       mode_of_sample_collection,
                       mode_of_payment
                FROM appointment
                WHERE uuid = %s
                """,
                (appointment_id,),
            )

            appointment = cur.fetchone()

        assert appointment["status"] == "pending_confirmation"
        assert appointment["requires_prescription"] is True
        assert appointment["mode_of_sample_collection"] == "Home Visit"
        assert appointment["mode_of_payment"] == "Cash on Visit"

    finally:
        with client.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM appointment WHERE uuid = %s",
                (appointment_id,),
            )
            conn.commit()

def test_create_appointment_links_tests_via_junction_table(any_active_centre_uuid):
    cbc = client.get_test_info("CBC")

    appointment_id = client.create_appointment(
        patient_name="Amit Agarwal",
        patient_age=23,
        patient_email="amit.test@example.com",
        centre_uuid=any_active_centre_uuid,
        test_uuids=[cbc["uuid"]],
        slot="2030-01-03 10:00:00",
        requires_prescription=False,
        mode_of_sample_collection="Visit Center",
        mode_of_payment="UPI",
    )

    try:
        linked_tests = client.get_appointment_tests(appointment_id)
        assert len(linked_tests) == 1
        assert linked_tests[0]["test_name"] == "CBC"
    finally:
        with client.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM appointment WHERE uuid = %s",
                (appointment_id,),
            )
            conn.commit()

def test_get_report_status():
    patient_uuid = "e1111111-1111-1111-1111-111111111111"

    result = client.get_report_status(patient_uuid)

    assert result["uuid"] == "b1111111-1111-1111-1111-111111111111"
    assert result["status"] == "ready"

def test_get_report_status_no_report():
    
    patient_uuid = str(uuid.uuid4())

    with pytest.raises(ValueError, match="No report found"):
        client.get_report_status(patient_uuid)

def test_resend_report():
    report_uuid = "b1111111-1111-1111-1111-111111111111"

    client.resend_report(report_uuid, "email")

    with client.get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT last_resent_at, last_resent_channel
            FROM report
            WHERE uuid = %s
            """,
            (report_uuid,),
        )

        report = cur.fetchone()

    assert report["last_resent_at"] is not None
    assert report["last_resent_channel"] == "email"

def test_get_expired_reports():
    reports = client.get_expired_reports(days=14)

    assert isinstance(reports, list)

    for report in reports:
        assert "uuid" in report
        assert "storage_path" in report
        assert report["storage_path"] is not None

def test_clear_report_storage_path():
    report_uuid = "b1111111-1111-1111-1111-111111111111"

    with client.get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT storage_path FROM report WHERE uuid = %s",
            (report_uuid,),
        )
        original = cur.fetchone()["storage_path"]

    try:
        client.clear_report_storage_path(report_uuid)

        with client.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT storage_path, deleted_at
                FROM report
                WHERE uuid = %s
                """,
                (report_uuid,),
            )

            report = cur.fetchone()

        assert report["storage_path"] is None
        assert report["deleted_at"] is not None

    finally:
        with client.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE report
                SET storage_path = %s,
                    deleted_at = NULL
                WHERE uuid = %s
                """,
                (original, report_uuid),
            )
            conn.commit()

def test_create_ticket():
    patient_uuid = "e1111111-1111-1111-1111-111111111111"
    ticket_id = client.create_ticket(
        patient_uuid=patient_uuid,
        category="email_correction",
        description="Please update my email address.",
    )
    try:
        with client.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT uuid, patient_uuid, category, description, status
                FROM ticket
                WHERE uuid = %s
                """,
                (ticket_id,),
            )

            ticket = cur.fetchone()
        assert ticket["uuid"] == ticket_id
        assert str(ticket["patient_uuid"]) == patient_uuid
        assert ticket["category"] == "email_correction"
        assert ticket["description"] == "Please update my email address."
        assert ticket["status"] == "open"
    finally:
        with client.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM ticket WHERE uuid = %s",
                (ticket_id,),
            )
            conn.commit()

def test_create_ticket_without_patient():
    ticket_id = client.create_ticket(
        patient_uuid=None,
        category="general",
        description="General support request.",
    )
    try:
        with client.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT patient_uuid, category, status
                FROM ticket
                WHERE uuid = %s
                """,
                (ticket_id,),
            )
            ticket = cur.fetchone()
        assert ticket["patient_uuid"] is None
        assert ticket["category"] == "general"
        assert ticket["status"] == "open"
    finally:
        with client.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM ticket WHERE uuid = %s",
                (ticket_id,),
            )
            conn.commit()

def test_generate_prescription_upload_link(monkeypatch):
    monkeypatch.setenv(
        "PRESCRIPTION_UPLOAD_BASE_URL",
        "https://test.example.com/upload",
    )
    appointment_id = "abc-123"
    result = client.generate_prescription_upload_link(appointment_id)
    assert result == "https://test.example.com/upload/abc-123"

def test_generate_payment_link(monkeypatch):
    monkeypatch.setenv(
        "PAYMENT_BASE_URL",
        "https://test.example.com/pay",
    )
    appointment_id = "abc-123"
    result = client.generate_payment_link(appointment_id)
    assert result == "https://test.example.com/pay/abc-123"