PRAGMA foreign_keys = ON;

-- Demonstration passwords:
-- admin@example.com       / admin123
-- demo.donor@example.com  / donor123
-- demo.ngo@example.com    / ngo123
-- demo.rider@example.com  / rider123

INSERT OR IGNORE INTO user
    (id, name, email, password_hash, role, area, phone, organization_type, capacity_meals, verified, is_blocked)
VALUES
    (1, 'Admin', 'admin@example.com',
     'scrypt:32768:8:1$ZU8mlQDu1AJGkZtl$71509eb1afed32c561a936b54df587b6a1f5b69a9a5875d14d73872c272b331e3eedec6a96e398690b0cc8605e9564ab61280241fb2692f0870bad4c6f75fddc',
     'admin', 'Dhaka', NULL, 'system', 0, 1, 0),
    (2, 'Demo Restaurant', 'demo.donor@example.com',
     'scrypt:32768:8:1$EDK60tnPBWdYhrCF$474be2f19aced1341e771f8dc9deb4a5d5a0c7e9292f6c29e8be668ba22280ce874b424fc38ef0fcb161d129bbb573f2c6e731023ddd593551e6a33ed303aaab',
     'donor', 'Dhaka', '01711111111', 'restaurant', 0, 1, 0),
    (3, 'Hope Orphanage', 'demo.ngo@example.com',
     'scrypt:32768:8:1$lSizWyQc6zDwLWi1$91e8f78f7d63053c308d41415f9e8837fa5bd09423b0c966e9553a77e77da9cfa88ec1bdea5ce17cdabc3b5b30c14ab0b462525e63c6f3912e9457c61e2e24c6',
     'recipient', 'Dhaka', '01811111111', 'orphanage', 80, 1, 0),
    (4, 'Demo Rider', 'demo.rider@example.com',
     'scrypt:32768:8:1$L7re95VwFbj6DwZw$907f35a7e5f24758ffd6c4f417e905c93add165e7159795d6fc7493005e461105ed70465db426764bf26cb539d2baebdec52345ed1ba2b32014fd7d44eae4d43',
     'volunteer', 'Dhaka', '01911111111', 'bike', 40, 1, 0);

INSERT OR IGNORE INTO donation
    (id, food_name, donor_type, quantity_meals, area, pickup_address,
     pickup_window_start, pickup_window_end, expire_at, storage_note,
     description, admin_note, status, donor_id)
VALUES
    (1, 'Rice and Chicken Meals', 'restaurant', 50, 'Dhaka',
     'Dhanmondi 27, Dhaka', datetime('now', '+1 hour'),
     datetime('now', '+2 hours'), datetime('now', '+5 hours'),
     'Keep covered and collect while warm.',
     'Fresh surplus meals prepared today.', 'Safety details checked.',
     'matched', 2);

INSERT OR IGNORE INTO food_request
    (id, beneficiary_group, requested_food_type, quantity_needed, area,
     delivery_address, needed_before, message, priority, admin_note, status,
     recipient_id)
VALUES
    (1, 'Children aged 6-14', 'Cooked meal', 40, 'Dhaka',
     'Mirpur 10, Dhaka', datetime('now', '+5 hours'),
     'Meals required for the evening programme.', 'urgent',
     'Recipient verified.', 'matched', 3);

INSERT OR IGNORE INTO food_match
    (id, donation_id, request_id, volunteer_id, meals_allocated, match_score,
     status)
VALUES
    (1, 1, 1, 4, 40, 95, 'assigned');

INSERT OR IGNORE INTO notification
    (id, receiver_email, title, message)
VALUES
    (1, 'demo.donor@example.com', 'ChariSmart: Donation Matched',
     'Your donation has been matched with Hope Orphanage for 40 meals.'),
    (2, 'demo.rider@example.com', 'Delivery assignment',
     'Collect the matched donation from Dhanmondi and deliver it to Mirpur.');

