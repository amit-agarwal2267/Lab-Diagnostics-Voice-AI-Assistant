INSERT INTO centre (uuid, name, code, address, pincode, city, state, supports_home_visit, supports_visit_center) VALUES
    ('c1111111-1111-1111-1111-111111111111', 'Main Diagnostics Kota', 'MDK01', 'Station Road', '324001', 'Kota', 'Rajasthan', TRUE, TRUE),
    ('c2222222-2222-2222-2222-222222222222', 'Jaipur Central Lab', 'JCL01', 'Malviya Nagar', '302017', 'Jaipur', 'Rajasthan', TRUE, TRUE);

INSERT INTO lab_test (uuid, test_name, price, requires_prescription, pre_test_instructions) VALUES
    ('d1111111-1111-1111-1111-111111111111', 'CBC', 350.00, FALSE, NULL),
    ('d2222222-2222-2222-2222-222222222222', 'HbA1c', 450.00, FALSE, 'No water intake restriction. Fasting not required.'),
    ('d3333333-3333-3333-3333-333333333333', 'Lipid Profile', 600.00, FALSE, '10-12 hour fasting required before sample collection.'),
    ('d4444444-4444-4444-4444-444444444444', 'Thyroid Profile (T3 T4 TSH)', 550.00, FALSE, NULL),
    ('d5555555-5555-5555-5555-555555555555', 'Liver Function Test', 500.00, TRUE, 'No alcohol intake for 24 hours before the test.'),
    ('d6666666-6666-6666-6666-666666666666', 'Kidney Function Test', 480.00, TRUE, 'No water intake 2 hours before the test.'),
    ('d7777777-7777-7777-7777-777777777777', 'MRI Brain', 4500.00, TRUE, 'Remove all metal objects. Inform staff of any implants.'),
    ('d8888888-8888-8888-8888-888888888888', 'Vitamin D', 900.00, FALSE, NULL),
    ('d9999999-9999-9999-9999-999999999999', 'Blood Culture', 1200.00, TRUE, 'Sample must be collected before starting antibiotics.');

INSERT INTO patient (uuid, name, age, phone_number, email_address, address) VALUES
    ('e1111111-1111-1111-1111-111111111111', 'Amit Agarwal', 23, '9990001111', 'amit.test@example.com', 'Kota, Rajasthan'),
    ('e2222222-2222-2222-2222-222222222222', 'Priya Sharma', 34, '9990002222', 'priya.sharma@example.com', 'Jaipur, Rajasthan');

INSERT INTO slot_inventory (centre_uuid, slot_date, slot_datetime, is_booked) VALUES
    ('c1111111-1111-1111-1111-111111111111', CURRENT_DATE + 1, (CURRENT_DATE + 1) + TIME '09:00', FALSE),
    ('c1111111-1111-1111-1111-111111111111', CURRENT_DATE + 1, (CURRENT_DATE + 1) + TIME '11:00', FALSE),
    ('c2222222-2222-2222-2222-222222222222', CURRENT_DATE + 1, (CURRENT_DATE + 1) + TIME '13:30', FALSE),
    ('c2222222-2222-2222-2222-222222222222', CURRENT_DATE + 1, (CURRENT_DATE + 1) + TIME '18:00', FALSE);

INSERT INTO appointment (uuid, patient_uuid, centre_uuid, slot_datetime, requires_prescription, status, mode_of_sample_collection, mode_of_payment) VALUES
    ('a1111111-1111-1111-1111-111111111111', 'e1111111-1111-1111-1111-111111111111', 'c1111111-1111-1111-1111-111111111111', CURRENT_DATE - 5 + TIME '10:00', FALSE, 'confirmed', 'Visit Center', 'UPI'),
    ('a2222222-2222-2222-2222-222222222222', 'e2222222-2222-2222-2222-222222222222', 'c2222222-2222-2222-2222-222222222222', CURRENT_DATE + 1 + TIME '11:00', TRUE, 'pending_confirmation', 'Home Visit', 'Cash on Visit');

INSERT INTO appointment_test (appointment_uuid, lab_test_uuid) VALUES
    ('a1111111-1111-1111-1111-111111111111', 'd1111111-1111-1111-1111-111111111111'),
    ('a1111111-1111-1111-1111-111111111111', 'd2222222-2222-2222-2222-222222222222'),
    ('a2222222-2222-2222-2222-222222222222', 'd5555555-5555-5555-5555-555555555555');

INSERT INTO report (uuid, patient_uuid, appointment_uuid, centre_uuid, sample_given_date, generation_date, status, storage_path) VALUES
    ('b1111111-1111-1111-1111-111111111111', 'e1111111-1111-1111-1111-111111111111', 'a1111111-1111-1111-1111-111111111111', 'c1111111-1111-1111-1111-111111111111', CURRENT_DATE - 5, CURRENT_DATE - 3, 'ready', 'reports/amit_cbc_hba1c.pdf'),
    ('b2222222-2222-2222-2222-222222222222', 'e2222222-2222-2222-2222-222222222222', 'a2222222-2222-2222-2222-222222222222', 'c2222222-2222-2222-2222-222222222222', NULL, NULL, 'in_progress', NULL);

INSERT INTO report_test (report_uuid, lab_test_uuid) VALUES
    ('b1111111-1111-1111-1111-111111111111', 'd1111111-1111-1111-1111-111111111111'),
    ('b1111111-1111-1111-1111-111111111111', 'd2222222-2222-2222-2222-222222222222'),
    ('b2222222-2222-2222-2222-222222222222', 'd5555555-5555-5555-5555-555555555555');