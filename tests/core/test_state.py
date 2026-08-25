from app.core.state import UserData

def test_defaults():
    ud = UserData()
    assert ud.patient_uuid is None
    assert ud.is_new_customer is True
    assert ud.pending_tests == []
    assert ud.pending_test_uuids == []
    assert ud.verification_attempts == 0
    assert ud.requires_prescription is None
    assert ud.prescription_upload_link_sent is False
    assert ud.chosen_slot is None

def test_is_identity_verified_false_by_default():
    assert UserData().is_identity_verified() is False

def test_is_identity_verified_true_when_uuid_set():
    ud = UserData(patient_uuid="e1111111-1111-1111-1111-111111111111")
    assert ud.is_identity_verified() is True

def test_is_centre_selected_false_by_default():
    assert UserData().is_centre_selected() is False

def test_is_centre_selected_true_when_uuid_set():
    ud = UserData(centre_uuid="c1111111-1111-1111-1111-111111111111")
    assert ud.is_centre_selected() is True

def test_reset_verification():
    ud = UserData(verification_attempts=3)
    ud.reset_verification()
    assert ud.verification_attempts == 0

def test_pending_lists_are_independent_instances():
    a = UserData()
    b = UserData()
    a.pending_tests.append("CBC")
    assert b.pending_tests == []