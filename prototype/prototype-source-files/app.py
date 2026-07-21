from datetime import datetime, timedelta
import base64
import os
import re
import smtplib
from email.message import EmailMessage
from functools import wraps
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///charismart.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

ROLES = ["admin", "donor", "recipient", "volunteer"]
DONOR_TYPES = ["restaurant", "wedding_hall", "household", "other"]
DONATION_STATUSES = ["pending", "approved", "rejected", "matched", "assigned", "picked_up", "delivered", "expired", "cancelled"]
REQUEST_STATUSES = ["pending", "approved", "rejected", "matched", "fulfilled", "cancelled"]
MATCH_STATUSES = ["pending", "accepted", "assigned", "picked_up", "delivered", "cancelled"]


# ---------------- Models ----------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, donor, recipient, volunteer
    area = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    organization_type = db.Column(db.String(80), nullable=True)  # donor/recipient/volunteer type
    capacity_meals = db.Column(db.Integer, default=0)  # recipient daily capacity or volunteer capacity
    verified = db.Column(db.Boolean, default=False)
    is_blocked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    donations = db.relationship("Donation", backref="donor", lazy=True, foreign_keys="Donation.donor_id")
    food_requests = db.relationship("FoodRequest", backref="recipient", lazy=True, foreign_keys="FoodRequest.recipient_id")
    assigned_matches = db.relationship("FoodMatch", backref="volunteer", lazy=True, foreign_keys="FoodMatch.volunteer_id")


class Donation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    food_name = db.Column(db.String(150), nullable=False)
    donor_type = db.Column(db.String(50), nullable=False)
    quantity_meals = db.Column(db.Integer, nullable=False)
    area = db.Column(db.String(120), nullable=False)
    pickup_address = db.Column(db.String(255), nullable=False)
    pickup_window_start = db.Column(db.DateTime, nullable=False)
    pickup_window_end = db.Column(db.DateTime, nullable=False)
    expire_at = db.Column(db.DateTime, nullable=False)
    storage_note = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    verification_note = db.Column(db.String(255), nullable=True)
    admin_note = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(30), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    donor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    matches = db.relationship("FoodMatch", backref="donation", lazy=True, cascade="all, delete-orphan")


class FoodRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    beneficiary_group = db.Column(db.String(150), nullable=False)
    requested_food_type = db.Column(db.String(150), nullable=True)
    quantity_needed = db.Column(db.Integer, nullable=False)
    area = db.Column(db.String(120), nullable=False)
    delivery_address = db.Column(db.String(255), nullable=False)
    needed_before = db.Column(db.DateTime, nullable=False)
    message = db.Column(db.Text, nullable=True)
    priority = db.Column(db.String(20), default="normal")
    admin_note = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(30), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    matches = db.relationship("FoodMatch", backref="food_request", lazy=True, cascade="all, delete-orphan")


class FoodMatch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    donation_id = db.Column(db.Integer, db.ForeignKey("donation.id"), nullable=False)
    request_id = db.Column(db.Integer, db.ForeignKey("food_request.id"), nullable=False)
    volunteer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    meals_allocated = db.Column(db.Integer, nullable=False)
    match_score = db.Column(db.Integer, default=0)
    status = db.Column(db.String(30), default="pending")
    pickup_confirmed_at = db.Column(db.DateTime, nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)
    delivery_note = db.Column(db.Text, nullable=True)
    recipient_rating = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    receiver_email = db.Column(db.String(150), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------- Helpers ----------------

def normalize_area(area):
    return " ".join((area or "").strip().split()).title()


def parse_datetime(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except ValueError:
        return None


def parse_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@app.template_filter("datetime_format")
def datetime_format(value):
    if not value:
        return "Not set"
    return value.strftime("%d %b %Y, %I:%M %p")


@app.template_filter("role_label")
def role_label(value):
    labels = {"recipient": "NGO/Orphanage", "donor": "Donor", "volunteer": "Volunteer", "admin": "Admin"}
    return labels.get(value, value.title() if value else "")


def get_admin_email():
    return os.getenv("MAIL_USERNAME", "admin@example.com") or "admin@example.com"


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            flash("Please login first.", "warning")
            return redirect(url_for("login"))
        if user.is_blocked:
            session.clear()
            flash("Your account has been blocked by admin.", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def role_required(role):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user or user.role != role:
                flash("You are not allowed to access this page.", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return wrapper
    return decorator


@app.context_processor
def inject_user():
    return {"auth_user": current_user(), "admin_email": get_admin_email(), "now": datetime.utcnow()}


def env_true(name, default=False):
    value = os.getenv(name, str(default)).strip().lower()
    return value in {"1", "true", "yes", "on"}


def send_email(to_email, subject, body):
    """Send a real email when SMTP variables are configured.

    When SMTP is not configured, the message is printed in the terminal so the
    notification workflow can still be demonstrated during the lab viva.
    """
    if not env_true("NOTIFICATION_EMAIL_ENABLED", True):
        return False

    mail_server = os.getenv("MAIL_SERVER", "").strip()
    mail_port = int(os.getenv("MAIL_PORT", "587"))
    mail_username = os.getenv("MAIL_USERNAME", "").strip()
    mail_password = os.getenv("MAIL_PASSWORD", "").strip()
    mail_from = os.getenv("MAIL_FROM", mail_username or "no-reply@charismart.local").strip()
    use_tls = env_true("EMAIL_USE_TLS", True)
    use_ssl = env_true("EMAIL_USE_SSL", False)

    if not mail_server or not mail_username or not mail_password:
        print("\n========== EMAIL NOT CONFIGURED ==========")
        print(f"To: {to_email}\nSubject: {subject}\n{body}")
        print("==========================================\n")
        return False

    msg = EmailMessage()
    msg["From"] = mail_from
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_class(mail_server, mail_port, timeout=20) as smtp:
        smtp.ehlo()
        if use_tls and not use_ssl:
            smtp.starttls()
            smtp.ehlo()
        smtp.login(mail_username, mail_password)
        smtp.send_message(msg)
    return True


def normalize_phone_for_sms(phone):
    """Convert common Bangladeshi mobile-number formats to E.164."""
    raw = (phone or "").strip()
    if not raw:
        return ""
    compact = re.sub(r"[\s().-]", "", raw)
    if compact.startswith("+"):
        digits = "+" + re.sub(r"\D", "", compact[1:])
        return digits
    digits = re.sub(r"\D", "", compact)
    if len(digits) == 11 and digits.startswith("01"):
        return "+88" + digits
    if len(digits) == 13 and digits.startswith("8801"):
        return "+" + digits
    return "+" + digits if digits else ""


def send_sms(phone, message):
    """Send an optional SMS using Twilio's Messages API.

    SMS is intentionally optional: email continues to work even if no SMS
    provider is configured. Configure SMS_PROVIDER=twilio and the Twilio
    variables in .env to activate it.
    """
    if not env_true("NOTIFICATION_SMS_ENABLED", False):
        return False

    provider = os.getenv("SMS_PROVIDER", "").strip().lower()
    destination = normalize_phone_for_sms(phone)
    if not destination:
        print("SMS skipped: recipient has no valid phone number.")
        return False

    if provider != "twilio":
        print("SMS skipped: set SMS_PROVIDER=twilio and add Twilio credentials in .env.")
        return False

    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    from_number = os.getenv("TWILIO_FROM_NUMBER", "").strip()
    if not account_sid or not auth_token or not from_number:
        print("SMS skipped: Twilio credentials are incomplete.")
        return False

    endpoint = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    payload = urlencode({"To": destination, "From": from_number, "Body": message[:480]}).encode("utf-8")
    request_obj = Request(endpoint, data=payload, method="POST")
    token = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("ascii")
    request_obj.add_header("Authorization", f"Basic {token}")
    request_obj.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urlopen(request_obj, timeout=20) as response:
            return 200 <= response.status < 300
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"SMS failed for {destination}: {exc}")
        return False


def notify_user(user, title, message, sms_message=None):
    """Store an in-app notification and attempt email/SMS delivery."""
    db.session.add(Notification(receiver_email=user.email, title=title, message=message))
    results = {"email": False, "sms": False}
    try:
        results["email"] = send_email(user.email, title, message)
    except Exception as exc:
        print(f"Email failed for {user.email}: {exc}")
    try:
        results["sms"] = send_sms(user.phone, sms_message or message)
    except Exception as exc:
        print(f"SMS failed for {user.name}: {exc}")
    return results


def delivery_text(results):
    channels = []
    if results.get("email"):
        channels.append("email")
    if results.get("sms"):
        channels.append("SMS")
    return " and ".join(channels) if channels else "in-app notification log"


def decision_notification(item_type, item_label, status, reason=""):
    decision = "approved" if status == "approved" else "rejected"
    subject = f"ChariSmart: {item_type} {decision.title()}"
    body = [
        "Hello,",
        "",
        f"Your {item_type.lower()} '{item_label}' has been {decision} by the ChariSmart admin.",
    ]
    if reason:
        body.extend(["", f"Admin note: {reason}"])
    if status == "approved":
        body.extend(["", "You can log in to ChariSmart to view the next steps."])
    else:
        body.extend(["", "You may update the information and submit a new entry if needed."])
    body.extend(["", "— ChariSmart Team"])
    sms = f"ChariSmart: Your {item_type.lower()} '{item_label}' is {decision}."
    if reason:
        sms += f" Note: {reason}"
    return subject, "\n".join(body), sms


def auto_expire_donations():
    expired_items = Donation.query.filter(
        Donation.status.in_(["approved", "matched", "assigned"]),
        Donation.expire_at < datetime.utcnow(),
    ).all()
    for item in expired_items:
        item.status = "expired"
        notify_user(item.donor, "Donation expired", f"Your donation '{item.food_name}' expired before delivery.")
    if expired_items:
        db.session.commit()
    return len(expired_items)


@app.before_request
def before_every_request():
    if request.endpoint != "static":
        try:
            auto_expire_donations()
        except Exception as exc:
            print(f"Auto expiry skipped: {exc}")


def admin_stats():
    return {
        "donors": User.query.filter_by(role="donor").count(),
        "recipients": User.query.filter_by(role="recipient").count(),
        "volunteers": User.query.filter_by(role="volunteer").count(),
        "pending_donations": Donation.query.filter_by(status="pending").count(),
        "approved_requests": FoodRequest.query.filter_by(status="approved").count(),
        "open_matches": FoodMatch.query.filter(FoodMatch.status.in_(["pending", "accepted", "assigned", "picked_up"])).count(),
        "delivered": FoodMatch.query.filter_by(status="delivered").count(),
        "expired": Donation.query.filter_by(status="expired").count(),
    }


def calculate_match_score(donation, food_request):
    score = 0
    if donation.area == food_request.area:
        score += 50
    if donation.quantity_meals >= food_request.quantity_needed:
        score += 20
    elif donation.quantity_meals > 0:
        score += 10
    if donation.expire_at and food_request.needed_before and donation.expire_at >= datetime.utcnow():
        score += 15
    if food_request.priority == "urgent":
        score += 10
    if donation.donor.verified:
        score += 5
    return min(score, 100)


def best_request_candidates(donation):
    candidates = FoodRequest.query.filter_by(status="approved", area=donation.area).order_by(FoodRequest.created_at.asc()).all()
    scored = [(request_item, calculate_match_score(donation, request_item)) for request_item in candidates]
    return sorted(scored, key=lambda item: item[1], reverse=True)


# ---------------- Routes ----------------

@app.route("/")
def home():
    donations = Donation.query.filter(Donation.status.in_(["approved", "matched", "assigned"])).order_by(Donation.created_at.desc()).limit(6).all()
    delivered = FoodMatch.query.filter_by(status="delivered").count()
    return render_template("home.html", donations=donations, delivered=delivered)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "")
        area = normalize_area(request.form.get("area", ""))
        phone = request.form.get("phone", "").strip()
        organization_type = request.form.get("organization_type", "").strip()
        capacity_meals = parse_int(request.form.get("capacity_meals"), 0)

        if role not in ["donor", "recipient", "volunteer"]:
            flash("Please select Donor, NGO/Orphanage, or Volunteer.", "danger")
            return redirect(url_for("register"))
        if not name or not email or not password or not area:
            flash("Name, email, password and area are required.", "danger")
            return redirect(url_for("register"))
        if User.query.filter_by(email=email).first():
            flash("Email already registered. Please login.", "warning")
            return redirect(url_for("login"))

        user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            role=role,
            area=area,
            phone=phone,
            organization_type=organization_type,
            capacity_meals=capacity_meals,
            verified=False,
        )
        db.session.add(user)
        db.session.commit()
        flash("Registration successful. Admin will verify the account before field operations.", "success")
        return redirect(url_for("login"))
    return render_template("register.html", donor_types=DONOR_TYPES)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            if user.is_blocked:
                flash("Your account is blocked. Please contact admin.", "danger")
                return redirect(url_for("login"))
            session["user_id"] = user.id
            flash("Login successful.", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "danger")
        return redirect(url_for("login"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    if user.role == "admin":
        return render_template(
            "admin_dashboard.html",
            stats=admin_stats(),
            donations=Donation.query.order_by(Donation.created_at.desc()).all(),
            requests=FoodRequest.query.order_by(FoodRequest.created_at.desc()).all(),
            matches=FoodMatch.query.order_by(FoodMatch.created_at.desc()).all(),
            volunteers=User.query.filter_by(role="volunteer", is_blocked=False).order_by(User.name).all(),
        )
    if user.role == "donor":
        donations = Donation.query.filter_by(donor_id=user.id).order_by(Donation.created_at.desc()).all()
        return render_template("donor_dashboard.html", donations=donations)
    if user.role == "recipient":
        requests = FoodRequest.query.filter_by(recipient_id=user.id).order_by(FoodRequest.created_at.desc()).all()
        matches = FoodMatch.query.join(FoodRequest).filter(FoodRequest.recipient_id == user.id).order_by(FoodMatch.created_at.desc()).all()
        return render_template("recipient_dashboard.html", requests=requests, matches=matches)
    matches = FoodMatch.query.filter_by(volunteer_id=user.id).order_by(FoodMatch.created_at.desc()).all()
    open_matches = FoodMatch.query.filter_by(status="accepted", volunteer_id=None).order_by(FoodMatch.created_at.desc()).all()
    return render_template("volunteer_dashboard.html", matches=matches, open_matches=open_matches)


@app.route("/donate", methods=["GET", "POST"])
@login_required
@role_required("donor")
def donate():
    if request.method == "POST":
        food_name = request.form.get("food_name", "").strip()
        donor_type = request.form.get("donor_type", "")
        quantity_meals = parse_int(request.form.get("quantity_meals"), 0)
        area = normalize_area(request.form.get("area", current_user().area))
        pickup_address = request.form.get("pickup_address", "").strip()
        pickup_start = parse_datetime(request.form.get("pickup_window_start", ""))
        pickup_end = parse_datetime(request.form.get("pickup_window_end", ""))
        expire_at = parse_datetime(request.form.get("expire_at", ""))
        storage_note = request.form.get("storage_note", "").strip()
        description = request.form.get("description", "").strip()
        if donor_type not in DONOR_TYPES or not food_name or quantity_meals <= 0 or not pickup_address or not pickup_start or not pickup_end or not expire_at:
            flash("Please provide valid food, quantity, donor type, pickup window, expiry and address.", "danger")
            return redirect(url_for("donate"))
        if not (pickup_start < pickup_end <= expire_at):
            flash("Pickup window must end before the expiry time.", "danger")
            return redirect(url_for("donate"))
        donation = Donation(
            food_name=food_name,
            donor_type=donor_type,
            quantity_meals=quantity_meals,
            area=area,
            pickup_address=pickup_address,
            pickup_window_start=pickup_start,
            pickup_window_end=pickup_end,
            expire_at=expire_at,
            storage_note=storage_note,
            description=description,
            donor_id=current_user().id,
        )
        db.session.add(donation)
        db.session.commit()
        flash("Donation submitted. Admin will verify safety, pickup window and donor identity.", "success")
        return redirect(url_for("dashboard"))
    return render_template("donate.html", donor_types=DONOR_TYPES)


@app.route("/request-food", methods=["GET", "POST"])
@login_required
@role_required("recipient")
def request_food():
    user = current_user()
    if request.method == "POST":
        beneficiary_group = request.form.get("beneficiary_group", "").strip()
        requested_food_type = request.form.get("requested_food_type", "").strip()
        quantity_needed = parse_int(request.form.get("quantity_needed"), 0)
        area = normalize_area(request.form.get("area", user.area))
        delivery_address = request.form.get("delivery_address", "").strip()
        needed_before = parse_datetime(request.form.get("needed_before", ""))
        priority = request.form.get("priority", "normal")
        message = request.form.get("message", "").strip()
        if not beneficiary_group or quantity_needed <= 0 or not area or not delivery_address or not needed_before:
            flash("Please fill beneficiary group, quantity, area, address and needed-before time.", "danger")
            return redirect(url_for("request_food"))
        request_item = FoodRequest(
            beneficiary_group=beneficiary_group,
            requested_food_type=requested_food_type,
            quantity_needed=quantity_needed,
            area=area,
            delivery_address=delivery_address,
            needed_before=needed_before,
            priority=priority if priority in ["normal", "urgent"] else "normal",
            message=message,
            recipient_id=user.id,
        )
        db.session.add(request_item)
        db.session.commit()
        flash("Food request submitted. Admin will verify before matching.", "success")
        return redirect(url_for("dashboard"))
    return render_template("request_food.html")


@app.route("/requests")
@login_required
def requests_list():
    user = current_user()
    if user.role == "recipient":
        requests_data = FoodRequest.query.filter_by(recipient_id=user.id).order_by(FoodRequest.created_at.desc()).all()
    else:
        requests_data = FoodRequest.query.order_by(FoodRequest.created_at.desc()).all()
    return render_template("requests.html", requests_data=requests_data)


@app.route("/admin/request/<int:request_id>/<status>", methods=["POST"])
@login_required
@role_required("admin")
def update_request_status(request_id, status):
    request_item = FoodRequest.query.get_or_404(request_id)
    if status not in ["approved", "rejected"]:
        flash("Only approval or rejection is allowed from this action.", "danger")
        return redirect(url_for("dashboard"))
    if request_item.status != "pending":
        flash("This request has already been processed.", "warning")
        return redirect(url_for("dashboard"))

    reason = request.form.get("reason", "").strip()[:255]
    request_item.status = status
    request_item.admin_note = reason or None
    label = f"request for {request_item.quantity_needed} meals"
    subject, body, sms = decision_notification("Food Request", label, status, reason)
    result = notify_user(request_item.recipient, subject, body, sms)
    db.session.commit()
    flash(f"Request {status}. Notification delivered through {delivery_text(result)}.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/donation/<int:donation_id>/<status>", methods=["POST"])
@login_required
@role_required("admin")
def update_donation_status(donation_id, status):
    donation = Donation.query.get_or_404(donation_id)
    if status not in ["approved", "rejected"]:
        flash("Only approval or rejection is allowed from this action.", "danger")
        return redirect(url_for("dashboard"))
    if donation.status != "pending":
        flash("This donation has already been processed.", "warning")
        return redirect(url_for("dashboard"))

    reason = request.form.get("reason", "").strip()[:255]
    donation.status = status
    donation.admin_note = reason or None
    subject, body, sms = decision_notification("Donation", donation.food_name, status, reason)
    result = notify_user(donation.donor, subject, body, sms)
    db.session.commit()
    flash(f"Donation {status}. Notification delivered through {delivery_text(result)}.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/donation/<int:donation_id>/auto-match", methods=["POST"])
@login_required
@role_required("admin")
def auto_match_donation(donation_id):
    donation = Donation.query.get_or_404(donation_id)
    if donation.status not in ["approved", "pending"]:
        flash("Only pending/approved donations can be matched.", "warning")
        return redirect(url_for("dashboard"))

    was_pending = donation.status == "pending"
    donation.status = "approved"
    candidates = best_request_candidates(donation)
    if not candidates:
        result = {"email": False, "sms": False}
        if was_pending:
            subject, body, sms = decision_notification("Donation", donation.food_name, "approved")
            result = notify_user(donation.donor, subject, body, sms)
        db.session.commit()
        suffix = f" Notification delivered through {delivery_text(result)}." if was_pending else ""
        flash("Donation approved, but no approved same-area request is available yet." + suffix, "info")
        return redirect(url_for("dashboard"))

    request_item, score = candidates[0]
    meals = min(donation.quantity_meals, request_item.quantity_needed)
    existing = FoodMatch.query.filter_by(donation_id=donation.id, request_id=request_item.id).first()
    if existing:
        flash("A match already exists for this donation and request.", "warning")
        return redirect(url_for("dashboard"))
    match = FoodMatch(donation_id=donation.id, request_id=request_item.id, meals_allocated=meals, match_score=score, status="accepted")
    donation.status = "matched"
    request_item.status = "matched"
    db.session.add(match)
    donor_title = "ChariSmart: Donation Approved and Matched" if was_pending else "ChariSmart: Donation Matched"
    donor_body = f"Hello,\n\nYour donation '{donation.food_name}' has been approved and matched with {request_item.recipient.name} for {meals} meals.\n\n— ChariSmart Team"
    donor_sms = f"ChariSmart: Your donation '{donation.food_name}' is approved and matched for {meals} meals."
    notify_user(donation.donor, donor_title, donor_body, donor_sms)
    notify_user(request_item.recipient, "ChariSmart: Food Request Matched", f"Hello,\n\nA donation has been matched for {meals} meals.\n\n— ChariSmart Team", f"ChariSmart: A donation has been matched for {meals} meals.")
    db.session.commit()
    flash(f"Auto-match created with score {score}.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/match/<int:match_id>/assign", methods=["POST"])
@login_required
@role_required("admin")
def assign_volunteer(match_id):
    match = FoodMatch.query.get_or_404(match_id)
    volunteer_id = parse_int(request.form.get("volunteer_id"), 0)
    volunteer = User.query.filter_by(id=volunteer_id, role="volunteer", is_blocked=False).first()
    if not volunteer:
        flash("Please select a valid volunteer.", "danger")
        return redirect(url_for("dashboard"))
    match.volunteer_id = volunteer.id
    match.status = "assigned"
    match.donation.status = "assigned"
    notify_user(volunteer, "Delivery assignment", f"Pickup {match.donation.food_name} from {match.donation.pickup_address} and deliver to {match.food_request.delivery_address}.")
    db.session.commit()
    flash("Volunteer assigned to the matched donation.", "success")
    return redirect(url_for("dashboard"))


@app.route("/match/<int:match_id>/<status>", methods=["POST"])
@login_required
def update_match_status(match_id, status):
    user = current_user()
    match = FoodMatch.query.get_or_404(match_id)
    allowed = False
    if user.role == "admin":
        allowed = True
    elif user.role == "volunteer" and match.volunteer_id == user.id and status in ["picked_up", "delivered"]:
        allowed = True
    elif user.role == "recipient" and match.food_request.recipient_id == user.id and status == "delivered":
        allowed = True
    if not allowed or status not in MATCH_STATUSES:
        flash("You are not allowed to update this match.", "danger")
        return redirect(url_for("dashboard"))
    match.status = status
    if status == "picked_up":
        match.pickup_confirmed_at = datetime.utcnow()
        match.donation.status = "picked_up"
    elif status == "delivered":
        match.delivered_at = datetime.utcnow()
        match.donation.status = "delivered"
        match.food_request.status = "fulfilled"
        rating = parse_int(request.form.get("recipient_rating"), 0)
        if 1 <= rating <= 5:
            match.recipient_rating = rating
        note = request.form.get("delivery_note", "").strip()
        if note:
            match.delivery_note = note
    db.session.commit()
    flash(f"Match status updated to {status}.", "success")
    return redirect(url_for("dashboard"))


@app.route("/donation/<int:donation_id>/delete", methods=["POST"])
@login_required
def delete_donation(donation_id):
    user = current_user()
    donation = Donation.query.get_or_404(donation_id)
    if user.role != "admin" and not (user.role == "donor" and donation.donor_id == user.id):
        flash("You are not allowed to delete this donation.", "danger")
        return redirect(url_for("dashboard"))
    db.session.delete(donation)
    db.session.commit()
    flash("Donation deleted.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/users")
@login_required
@role_required("admin")
def manage_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("manage_users.html", users=users)


@app.route("/admin/user/<int:user_id>/toggle-block", methods=["POST"])
@login_required
@role_required("admin")
def toggle_block_user(user_id):
    target = User.query.get_or_404(user_id)
    if target.role == "admin":
        flash("Admin account cannot be blocked.", "danger")
        return redirect(url_for("manage_users"))
    target.is_blocked = not target.is_blocked
    db.session.commit()
    flash(f"{target.name} has been {'blocked' if target.is_blocked else 'unblocked'}.", "success")
    return redirect(url_for("manage_users"))


@app.route("/admin/user/<int:user_id>/toggle-verified", methods=["POST"])
@login_required
@role_required("admin")
def toggle_verified_user(user_id):
    target = User.query.get_or_404(user_id)
    if target.role == "admin":
        flash("Admin account is already trusted.", "info")
        return redirect(url_for("manage_users"))
    target.verified = not target.verified
    db.session.commit()
    flash(f"{target.name} verification status updated.", "success")
    return redirect(url_for("manage_users"))


@app.route("/admin/user/<int:user_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_user(user_id):
    target = User.query.get_or_404(user_id)
    if target.role == "admin":
        flash("Admin account cannot be deleted.", "danger")
        return redirect(url_for("manage_users"))
    db.session.delete(target)
    db.session.commit()
    flash("User deleted successfully.", "success")
    return redirect(url_for("manage_users"))


# ---------------- Database setup ----------------

def seed_admin():
    admin = User.query.filter_by(email="admin@example.com").first()
    if not admin:
        admin = User(
            name="Admin",
            email="admin@example.com",
            password_hash=generate_password_hash("admin123"),
            role="admin",
            verified=True,
        )
        db.session.add(admin)
        db.session.commit()


def seed_demo_data():
    if os.getenv("SEED_DEMO", "false").lower() not in ["true", "1", "yes"]:
        return
    if User.query.filter_by(email="demo.donor@example.com").first():
        return
    donor = User(name="Demo Restaurant", email="demo.donor@example.com", password_hash=generate_password_hash("donor123"), role="donor", area="Dhaka", organization_type="restaurant", verified=True)
    recipient = User(name="Hope Orphanage", email="demo.ngo@example.com", password_hash=generate_password_hash("ngo123"), role="recipient", area="Dhaka", organization_type="orphanage", capacity_meals=80, verified=True)
    volunteer = User(name="Demo Rider", email="demo.rider@example.com", password_hash=generate_password_hash("rider123"), role="volunteer", area="Dhaka", organization_type="bike", capacity_meals=40, verified=True)
    db.session.add_all([donor, recipient, volunteer])
    db.session.commit()


def ensure_sqlite_schema():
    """Small backward-compatible migration for databases created before admin_note."""
    if not app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        return
    for table_name in ("donation", "food_request"):
        columns = {row[1] for row in db.session.execute(text(f"PRAGMA table_info({table_name})")).all()}
        if "admin_note" not in columns:
            db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN admin_note VARCHAR(255)"))
    db.session.commit()


with app.app_context():
    db.create_all()
    ensure_sqlite_schema()
    seed_admin()
    seed_demo_data()


if __name__ == "__main__":
    app.run(debug=True)
