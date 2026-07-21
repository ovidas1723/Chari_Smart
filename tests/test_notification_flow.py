"""Functional test for approval/rejection notifications.

Run from the repository root after installing requirements:
    python tests/test_notification_flow.py

The test does not send a real email or SMS. It replaces both delivery functions
with local fakes and validates the approval/rejection workflow, notification log,
and optional rejection reason.
"""

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src" / "complete-source-code"
TEST_DB = ROOT / "tests" / "notification_test.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["SEED_DEMO"] = "false"
os.environ["NOTIFICATION_EMAIL_ENABLED"] = "false"
os.environ["NOTIFICATION_SMS_ENABLED"] = "false"

spec = importlib.util.spec_from_file_location("charismart_test_app", SOURCE_ROOT / "app.py")
module = importlib.util.module_from_spec(spec)
sys.modules["charismart_test_app"] = module
spec.loader.exec_module(module)

app = module.app
emails = []
texts = []
module.send_email = lambda to, subject, body: emails.append((to, subject, body)) or True
module.send_sms = lambda phone, message: texts.append((phone, message)) or True

with app.app_context():
    admin = module.User.query.filter_by(email="admin@example.com").first()
    donor = module.User(
        name="Notification Donor",
        email="donor@example.test",
        password_hash="x",
        role="donor",
        area="Dhaka",
        phone="01712345678",
    )
    recipient = module.User(
        name="Notification NGO",
        email="ngo@example.test",
        password_hash="x",
        role="recipient",
        area="Dhaka",
        phone="01812345678",
    )
    module.db.session.add_all([donor, recipient])
    module.db.session.commit()

    now = module.datetime.utcnow()
    donation = module.Donation(
        food_name="Rice Meal",
        donor_type="restaurant",
        quantity_meals=20,
        area="Dhaka",
        pickup_address="Road 1",
        pickup_window_start=now,
        pickup_window_end=now + module.timedelta(hours=1),
        expire_at=now + module.timedelta(hours=3),
        donor_id=donor.id,
    )
    food_request = module.FoodRequest(
        beneficiary_group="Children",
        quantity_needed=15,
        area="Dhaka",
        delivery_address="Road 2",
        needed_before=now + module.timedelta(hours=3),
        recipient_id=recipient.id,
    )
    module.db.session.add_all([donation, food_request])
    module.db.session.commit()
    admin_id = admin.id
    donation_id = donation.id
    request_id = food_request.id

client = app.test_client()
with client.session_transaction() as session:
    session["user_id"] = admin_id

response = client.post(
    f"/admin/donation/{donation_id}/approved",
    data={"reason": "Safety details checked."},
    follow_redirects=True,
)
assert response.status_code == 200

response = client.post(
    f"/admin/request/{request_id}/rejected",
    data={"reason": "Please correct the delivery address."},
    follow_redirects=True,
)
assert response.status_code == 200

with app.app_context():
    donation = module.db.session.get(module.Donation, donation_id)
    food_request = module.db.session.get(module.FoodRequest, request_id)
    assert donation.status == "approved"
    assert donation.admin_note == "Safety details checked."
    assert food_request.status == "rejected"
    assert food_request.admin_note == "Please correct the delivery address."
    assert module.Notification.query.filter_by(receiver_email="donor@example.test").count() == 1
    assert module.Notification.query.filter_by(receiver_email="ngo@example.test").count() == 1

assert len(emails) == 2
assert len(texts) == 2
assert "Donation Approved" in emails[0][1]
assert "Food Request Rejected" in emails[1][1]
print("PASS: approval/rejection email and SMS notification flow")

if TEST_DB.exists():
    TEST_DB.unlink()
