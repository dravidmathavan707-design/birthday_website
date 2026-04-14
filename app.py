import os
import re
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

from apscheduler.schedulers.background import BackgroundScheduler
from bson import ObjectId
from flask import Flask, flash, redirect, render_template, request, session, url_for
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from pymongo import MongoClient
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "secret123")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "dravid707@gmail.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "dravid7.dm")
MAIL_SENDER = os.getenv("MAIL_SENDER", "")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
AUTO_TOMORROW_REMINDER_ENABLED = os.getenv("AUTO_TOMORROW_REMINDER_ENABLED", "yes").strip().lower() in {"1", "true", "yes", "on"}

MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb+srv://mathan2192003_db_user:dravid_mathavan07_dm@cluster0.nxyoghv.mongodb.net/?appName=Cluster0",
)

client = None
db = None
users = None
friends = None
messages = None
gifts = None
friend_requests = None


def current_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_database():
    global client, db, users, friends, messages, gifts, friend_requests

    if users is not None and friends is not None and messages is not None and gifts is not None and friend_requests is not None:
        return True

    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
        db = client["birthdayDB"]
        users = db["users"]
        friends = db["friends"]
        messages = db["messages"]
        gifts = db["gifts"]
        friend_requests = db["friend_requests"]

        users.create_index("email", unique=True)
        friends.create_index([("owner_email", 1), ("email", 1)], unique=True)
        messages.create_index([("owner_email", 1), ("friend_id", 1), ("kind", 1), ("created_at", 1)])
        gifts.create_index([("owner_email", 1), ("friend_id", 1), ("created_at", 1)])
        friend_requests.create_index([("from_email", 1), ("to_email", 1), ("status", 1)])

        return True
    except Exception as exc:
        app.logger.error(f"MongoDB connection failed: {exc}")
        client = None
        db = None
        users = None
        friends = None
        messages = None
        gifts = None
        friend_requests = None
        return False


def database_ready_or_flash():
    if init_database():
        return True
    flash("Database is not connected right now. Please try again in a moment.")
    return False


def ensure_admin_account():
    if users is None:
        return

    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        return

    existing_admin = users.find_one({"email": ADMIN_EMAIL.strip().lower()})
    if existing_admin:
        users.update_one(
            {"email": ADMIN_EMAIL.strip().lower()},
            {
                "$set": {
                    "password": generate_password_hash(ADMIN_PASSWORD),
                    "role": "admin",
                    "gender": existing_admin.get("gender") or "Not specified",
                    "birthday": existing_admin.get("birthday") or "2000-01-01",
                }
            },
        )
        return

    users.insert_one(
        {
            "name": "Administrator",
            "email": ADMIN_EMAIL.strip().lower(),
            "password": generate_password_hash(ADMIN_PASSWORD),
            "gender": "Not specified",
            "birthday": "2000-01-01",
            "role": "admin",
            "notes": [],
            "created_at": current_timestamp(),
            "last_login_at": None,
            "last_activity_at": None,
            "login_count": 0,
        }
    )

if init_database():
    ensure_admin_account()


def get_serializer():
    return URLSafeTimedSerializer(app.secret_key)


def get_base_url():
    configured = os.getenv("APP_BASE_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    return "https://birthday-website-jlv9.onrender.com"


def create_friend_birthday_token(friend_document):
    serializer = get_serializer()
    return serializer.dumps(
        {
            "friend_id": str(friend_document["_id"]),
            "owner_email": friend_document["owner_email"],
            "friend_email": friend_document.get("email", ""),
        },
        salt="friend-birthday",
    )


def read_friend_birthday_token(token, max_age_seconds=60 * 60 * 24 * 45):
    serializer = get_serializer()
    try:
        return serializer.loads(token, salt="friend-birthday", max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None


def get_next_birthday(birthday_string):
    today = datetime.now().date()
    birthday = datetime.strptime(birthday_string, "%Y-%m-%d").date()
    candidate = birthday.replace(year=today.year)
    if candidate < today:
        candidate = candidate.replace(year=today.year + 1)
    return candidate


def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def is_birthday_today(birthday_string):
    birthday_date = parse_date(birthday_string)
    if not birthday_date:
        return False

    today = datetime.now().date()
    return birthday_date.month == today.month and birthday_date.day == today.day


def is_birthday_tomorrow(birthday_string):
    birthday_date = parse_date(birthday_string)
    if not birthday_date:
        return False

    tomorrow = datetime.now().date() + timedelta(days=1)
    return birthday_date.month == tomorrow.month and birthday_date.day == tomorrow.day


def can_access_birthday(user_document):
    today = datetime.now().date()
    birthday = datetime.strptime(user_document["birthday"], "%Y-%m-%d").date()
    return today.month == birthday.month and today.day == birthday.day


def send_birthday_email(to_email, user_name, link_url=None):
    if not MAIL_SENDER or not MAIL_PASSWORD:
        return

    message = EmailMessage()
    message["Subject"] = "Happy Birthday! Your surprise is ready 🎂"
    message["From"] = MAIL_SENDER
    message["To"] = to_email
    message.set_content(
        f"Hi {user_name},\n\n"
        "Happy Birthday! Open your birthday website now to see your celebration page.\n\n"
        f"{link_url or get_base_url()}\n\n"
        "Have an amazing day!"
    )

    with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as smtp:
        smtp.starttls()
        smtp.login(MAIL_SENDER, MAIL_PASSWORD)
        smtp.send_message(message)


def send_tomorrow_birthday_reminder_email(to_email, user_name, link_url=None):
    if not MAIL_SENDER or not MAIL_PASSWORD:
        return

    message = EmailMessage()
    message["Subject"] = "Reminder: Birthday celebration unlocks tomorrow 🎉"
    message["From"] = MAIL_SENDER
    message["To"] = to_email
    message.set_content(
        f"Hi {user_name},\n\n"
        "Reminder: your birthday celebration is tomorrow!\n"
        "Open this link tomorrow to start your celebration page:\n\n"
        f"{link_url or get_base_url()}\n\n"
        "See you tomorrow and have an amazing birthday!"
    )

    with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as smtp:
        smtp.starttls()
        smtp.login(MAIL_SENDER, MAIL_PASSWORD)
        smtp.send_message(message)


def birthday_reminder_job():
    global AUTO_TOMORROW_REMINDER_ENABLED

    if not init_database():
        return

    if not AUTO_TOMORROW_REMINDER_ENABLED:
        return

    today = datetime.now().strftime("%Y-%m-%d")

    for user in users.find({"role": "user"}):
        if not is_birthday_tomorrow(user.get("birthday")):
            continue

        if user.get("birthday_reminder_email_sent_on") == today:
            continue

        user_link = f"{get_base_url()}/birthday"
        send_tomorrow_birthday_reminder_email(user.get("email", ""), user.get("name") or "Friend", link_url=user_link)
        users.update_one(
            {"_id": user["_id"]},
            {"$set": {"birthday_reminder_email_sent_on": today}},
        )

    for friend in friends.find({}):
        if not is_birthday_tomorrow(friend.get("birthday")):
            continue

        if friend.get("last_birthday_reminder_email_sent") == today:
            continue

        token = create_friend_birthday_token(friend)
        link = f"{get_base_url()}/birthday/friend/{token}"
        send_tomorrow_birthday_reminder_email(friend.get("email", ""), friend.get("name") or "Friend", link_url=link)
        friends.update_one(
            {"_id": friend["_id"]},
            {"$set": {"last_birthday_reminder_email_sent": today}},
        )


scheduler = BackgroundScheduler()
scheduler.add_job(birthday_reminder_job, "cron", hour=11, minute=57)
if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    scheduler.start()


@app.before_request
def update_user_activity():
    if not init_database():
        return

    if "user" not in session:
        return

    endpoint = request.endpoint or ""
    if endpoint.startswith("static"):
        return

    users.update_one(
        {"email": session["user"]},
        {"$set": {"last_activity_at": current_timestamp()}},
    )


@app.after_request
def add_no_cache_headers(response):
    endpoint = request.endpoint or ""
    if not endpoint.startswith("static"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


def resolve_owner_email(friend_document):
    owner_email = friend_document.get("owner_email", "")
    if session.get("role") == "admin":
        form_owner = request.form.get("owner_email", "").strip().lower()
        if form_owner:
            owner_email = form_owner
    return owner_email


def get_friend_or_redirect(friend_id):
    if not database_ready_or_flash():
        return None, redirect("/")

    try:
        object_id = ObjectId(friend_id)
    except Exception:
        flash("Invalid friend id")
        return None, redirect("/dashboard")

    friend_document = friends.find_one({"_id": object_id})
    if not friend_document:
        flash("Friend not found")
        return None, redirect("/dashboard")

    if session.get("role") != "admin" and friend_document.get("owner_email") != session.get("user"):
        flash("You cannot access this profile")
        return None, redirect("/dashboard")

    return friend_document, None


def create_friend_profile_from_user(owner_email, target_user):
    if not owner_email or not target_user:
        return

    target_email = (target_user.get("email") or "").strip().lower()
    if not target_email:
        return

    if friends.find_one({"owner_email": owner_email, "email": target_email}):
        return

    friends.insert_one(
        {
            "owner_email": owner_email,
            "name": target_user.get("name") or target_email,
            "email": target_email,
            "birthday": target_user.get("birthday") or "2000-01-01",
            "profile_image": target_user.get("profile_image", ""),
            "created_at": current_timestamp(),
            "last_birthday_email_sent": None,
        }
    )

# REGISTER
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if not database_ready_or_flash():
            return redirect("/register")

        email = request.form["email"].strip().lower()
        password = request.form["password"]
        birthday = request.form["birthday"]
        gender = request.form["gender"]
        name = request.form["name"].strip()

        if users.find_one({"email": email}):
            flash("Email already registered. Please login.")
            return redirect("/register")

        users.insert_one(
            {
                "name": name,
                "email": email,
                "password": generate_password_hash(password),
                "gender": gender,
                "birthday": birthday,
                "profile_image": "",
                "role": "user",
                "notes": [],
                "created_at": current_timestamp(),
                "last_login_at": None,
                "last_activity_at": None,
                "login_count": 0,
                "birthday_viewed_on": None,
                "birthday_email_sent_on": None,
            }
        )
        flash("Registration successful. Please login.")
        return redirect("/")
    return render_template("register.html")

# LOGIN
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not database_ready_or_flash():
            return redirect("/")

        email = request.form["email"].strip().lower()
        password = request.form["password"]

        user = users.find_one({"email": email})

        if user and check_password_hash(user.get("password", ""), password):
            session["user"] = user["email"]
            session["role"] = user.get("role", "user")
            users.update_one(
                {"email": user["email"]},
                {
                    "$set": {
                        "last_login_at": current_timestamp(),
                        "last_activity_at": current_timestamp(),
                    },
                    "$inc": {"login_count": 1},
                },
            )
            if session["role"] == "admin":
                return redirect("/admin")
            return redirect("/dashboard")

        flash("Invalid email or password")

    return render_template("login.html")

# DASHBOARD
@app.route("/dashboard")
def dashboard():
    if not database_ready_or_flash():
        return redirect("/")

    if "user" not in session:
        return redirect("/")

    if session.get("role") == "admin":
        return redirect("/admin")

    user = users.find_one({"email": session["user"]})
    if not user:
        user = {
            "name": session["user"].split("@")[0],
            "email": session["user"],
            "birthday": None,
            "role": "user",
        }

    all_friends = []
    suggestions = []
    incoming_requests = []
    outgoing_requests = []
    suggested_users = []
    birthday_today_count = 0
    upcoming_window_days = 5

    for friend in friends.find({"owner_email": user["email"]}):
        birthday_date = parse_date(friend.get("birthday"))
        next_birthday = get_next_birthday(friend.get("birthday")) if birthday_date else None
        days_left = (next_birthday - datetime.now().date()).days if next_birthday else 9999
        friend_is_birthday = is_birthday_today(friend.get("birthday"))

        if friend_is_birthday:
            birthday_today_count += 1

        birthday_link = None
        if friend_is_birthday:
            token = create_friend_birthday_token(friend)
            birthday_link = f"/birthday/friend/{token}"

        hidden_count = messages.count_documents(
            {
                "owner_email": user["email"],
                "friend_id": friend["_id"],
                "kind": "birthday",
            }
        )

        all_friends.append(
            {
                "id": str(friend["_id"]),
                "name": friend.get("name", "Friend"),
                "email": friend.get("email", ""),
                "birthday": friend.get("birthday", ""),
                "profile_image": friend.get("profile_image", ""),
                "days_left": days_left,
                "is_birthday_today": friend_is_birthday,
                "birthday_link": birthday_link,
                "hidden_birthday_messages": 0 if friend_is_birthday else hidden_count,
                "gift_count": gifts.count_documents({"owner_email": user["email"], "friend_id": friend["_id"]}),
            }
        )

        if friend_is_birthday:
            suggestions.append(
                {
                    "type": "today",
                    "priority": "today",
                    "friend_name": friend.get("name", "Friend"),
                    "days_left": 0,
                    "friend_id": str(friend["_id"]),
                    "birthday_link": birthday_link,
                    "message": f"{friend.get('name', 'Friend')}'s birthday is today — start the birthday experience now.",
                }
            )
        elif days_left <= upcoming_window_days:
            urgency = "soon" if days_left <= 2 else "normal"
            suggestions.append(
                {
                    "type": "upcoming",
                    "priority": urgency,
                    "friend_name": friend.get("name", "Friend"),
                    "days_left": days_left,
                    "friend_id": str(friend["_id"]),
                    "birthday_link": None,
                    "message": f"{friend.get('name', 'Friend')}'s birthday is in {days_left} day(s) — plan a gift now.",
                }
            )

    all_friends.sort(key=lambda item: item.get("days_left", 9999))
    suggestions.sort(key=lambda item: item.get("days_left", 9999))
    suggestions = suggestions[:4]

    existing_friend_emails = {friend_item["email"] for friend_item in all_friends}

    incoming_pending_docs = list(friend_requests.find({"to_email": user["email"], "status": "pending"}))
    outgoing_pending_docs = list(friend_requests.find({"from_email": user["email"], "status": "pending"}))

    pending_incoming_emails = set()
    pending_outgoing_emails = set()

    for request_doc in incoming_pending_docs:
        from_email = request_doc.get("from_email", "")
        pending_incoming_emails.add(from_email)
        from_user = users.find_one({"email": from_email}) or {}
        incoming_requests.append(
            {
                "id": str(request_doc["_id"]),
                "from_email": from_email,
                "from_name": from_user.get("name") or from_email,
            }
        )

    for request_doc in outgoing_pending_docs:
        to_email = request_doc.get("to_email", "")
        pending_outgoing_emails.add(to_email)
        to_user = users.find_one({"email": to_email}) or {}
        outgoing_requests.append(
            {
                "to_email": to_email,
                "to_name": to_user.get("name") or to_email,
            }
        )

    excluded_emails = existing_friend_emails | pending_incoming_emails | pending_outgoing_emails | {user["email"]}
    for suggested in users.find({"role": "user", "email": {"$ne": user["email"]}}):
        suggested_email = suggested.get("email", "")
        if suggested_email in excluded_emails:
            continue

        birthday_value = suggested.get("birthday")
        birthday_days_left = 9999
        if parse_date(birthday_value):
            birthday_days_left = (get_next_birthday(birthday_value) - datetime.now().date()).days

        suggested_users.append(
            {
                "name": suggested.get("name") or suggested_email,
                "email": suggested_email,
                "birthday": birthday_value or "",
                "days_left": birthday_days_left,
            }
        )

    suggested_users.sort(key=lambda item: item.get("days_left", 9999))
    suggested_users = suggested_users[:8]

    today = datetime.now()
    user_birthday = parse_date(user.get("birthday"))
    if user_birthday:
        next_user_birthday = get_next_birthday(user.get("birthday"))
        target_datetime = datetime.combine(next_user_birthday, datetime.min.time())
        initial_seconds = max(0, int((target_datetime - today).total_seconds()))
    else:
        next_user_birthday = datetime.now().date()
        target_datetime = datetime.now()
        initial_seconds = 0

    hero_days = initial_seconds // 86400
    hero_hours = (initial_seconds % 86400) // 3600
    hero_minutes = (initial_seconds % 3600) // 60

    return render_template(
        "dashboard.html",
        user=user,
        friends=all_friends,
        suggestions=suggestions,
        birthday_today_count=birthday_today_count,
        incoming_requests=incoming_requests,
        outgoing_requests=outgoing_requests,
        suggested_users=suggested_users,
        hero_target_iso=target_datetime.isoformat(),
        hero_days=hero_days,
        hero_hours=hero_hours,
        hero_minutes=hero_minutes,
        self_birthday_today=is_birthday_today(user.get("birthday")),
    )


@app.route("/me")
def profile():
    if "user" not in session:
        return redirect("/")

    if session.get("role") == "admin":
        return redirect("/admin")

    current_user = {
        "name": session["user"].split("@")[0],
        "email": session["user"],
        "gender": "Not specified",
        "birthday": "Not set",
    }
    friend_count = 0
    message_count = 0
    gift_count = 0

    if init_database():
        db_user = users.find_one({"email": session["user"]})
        if db_user:
            current_user = {
                "name": db_user.get("name") or current_user["name"],
                "email": db_user.get("email") or current_user["email"],
                "gender": db_user.get("gender") or current_user["gender"],
                "birthday": db_user.get("birthday") or current_user["birthday"],
            }

        try:
            friend_count = friends.count_documents({"owner_email": session["user"]})
            message_count = messages.count_documents({"owner_email": session["user"]})
            gift_count = gifts.count_documents({"owner_email": session["user"]})
        except Exception:
            friend_count = 0
            message_count = 0
            gift_count = 0

    return render_template(
        "profile.html",
        user=current_user,
        friend_count=friend_count,
        message_count=message_count,
        gift_count=gift_count,
    )


@app.route("/profile")
def profile_alias():
    return redirect("/me")


@app.route("/friend_request/send/<email>")
def send_friend_request(email):
    if not database_ready_or_flash():
        return redirect("/")

    if "user" not in session or session.get("role") != "user":
        return redirect("/")

    to_email = (email or "").strip().lower()
    from_email = session["user"]

    if not to_email or to_email == from_email:
        flash("Invalid friend request target")
        return redirect("/dashboard")

    target_user = users.find_one({"email": to_email, "role": "user"})
    if not target_user:
        flash("User not found")
        return redirect("/dashboard")

    if friends.find_one({"owner_email": from_email, "email": to_email}):
        flash("You are already friends")
        return redirect("/dashboard")

    existing_pending = friend_requests.find_one(
        {
            "$or": [
                {"from_email": from_email, "to_email": to_email, "status": "pending"},
                {"from_email": to_email, "to_email": from_email, "status": "pending"},
            ]
        }
    )
    if existing_pending:
        flash("A friend request is already pending")
        return redirect("/dashboard")

    friend_requests.insert_one(
        {
            "from_email": from_email,
            "to_email": to_email,
            "status": "pending",
            "created_at": current_timestamp(),
            "responded_at": None,
        }
    )
    flash("Friend request sent")
    return redirect("/dashboard")


@app.route("/friend_request/respond/<request_id>", methods=["POST"])
def respond_friend_request(request_id):
    if not database_ready_or_flash():
        return redirect("/")

    if "user" not in session or session.get("role") != "user":
        return redirect("/")

    action = request.form.get("action", "").strip().lower()
    if action not in {"accept", "reject"}:
        flash("Invalid action")
        return redirect("/dashboard")

    try:
        request_object_id = ObjectId(request_id)
    except Exception:
        flash("Invalid request id")
        return redirect("/dashboard")

    request_doc = friend_requests.find_one({"_id": request_object_id, "status": "pending"})
    if not request_doc or request_doc.get("to_email") != session["user"]:
        flash("Friend request not found")
        return redirect("/dashboard")

    new_status = "accepted" if action == "accept" else "rejected"
    friend_requests.update_one(
        {"_id": request_object_id},
        {"$set": {"status": new_status, "responded_at": current_timestamp()}},
    )

    if action == "accept":
        sender = users.find_one({"email": request_doc.get("from_email")})
        receiver = users.find_one({"email": request_doc.get("to_email")})
        create_friend_profile_from_user(request_doc.get("from_email"), receiver)
        create_friend_profile_from_user(request_doc.get("to_email"), sender)
        flash("Friend request accepted")
    else:
        flash("Friend request rejected")

    return redirect("/dashboard")


@app.route("/friend/add", methods=["POST"])
def add_friend():
    if not database_ready_or_flash():
        return redirect("/")

    if "user" not in session or session.get("role") != "user":
        return redirect("/")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    birthday = request.form.get("birthday", "").strip()
    profile_image = request.form.get("profile_image", "").strip()

    if not name or not email or not birthday:
        flash("Please fill all required friend fields")
        return redirect("/dashboard")

    try:
        friends.insert_one(
            {
                "owner_email": session["user"],
                "name": name,
                "email": email,
                "birthday": birthday,
                "profile_image": profile_image,
                "created_at": current_timestamp(),
                "last_birthday_email_sent": None,
            }
        )
        flash("Friend profile added")
    except Exception:
        flash("Friend with this email already exists in your list")

    return redirect("/dashboard")


@app.route("/friend/<friend_id>")
def friend_profile(friend_id):
    if "user" not in session:
        return redirect("/")

    friend_document, redirect_response = get_friend_or_redirect(friend_id)
    if redirect_response:
        return redirect_response

    owner_email = friend_document.get("owner_email", "")
    can_view_birthday_messages = is_birthday_today(friend_document.get("birthday")) or session.get("role") == "admin"

    daily_messages = list(
        messages.find(
            {
                "owner_email": owner_email,
                "friend_id": friend_document["_id"],
                "kind": "daily",
            }
        ).sort("created_at", 1)
    )

    birthday_messages = list(
        messages.find(
            {
                "owner_email": owner_email,
                "friend_id": friend_document["_id"],
                "kind": "birthday",
            }
        ).sort("created_at", 1)
    )

    hidden_count = 0
    if not can_view_birthday_messages:
        hidden_count = len(birthday_messages)
        birthday_messages = []

    friend_gifts = list(
        gifts.find(
            {
                "owner_email": owner_email,
                "friend_id": friend_document["_id"],
            }
        ).sort("created_at", -1)
    )

    next_birthday = get_next_birthday(friend_document["birthday"])
    days_left = (next_birthday - datetime.now().date()).days

    return render_template(
        "friend_profile.html",
        friend=friend_document,
        daily_messages=daily_messages,
        birthday_messages=birthday_messages,
        hidden_birthday_count=hidden_count,
        gifts=friend_gifts,
        days_left=days_left,
        next_birthday=next_birthday.strftime("%d/%m/%Y"),
        can_view_birthday_messages=can_view_birthday_messages,
        admin_mode=session.get("role") == "admin",
    )


@app.route("/friend/<friend_id>/daily_chat", methods=["POST"])
def add_daily_chat(friend_id):
    if "user" not in session:
        return redirect("/")

    friend_document, redirect_response = get_friend_or_redirect(friend_id)
    if redirect_response:
        return redirect_response

    text = request.form.get("text", "").strip()
    if not text:
        return redirect(f"/friend/{friend_id}")

    messages.insert_one(
        {
            "owner_email": resolve_owner_email(friend_document),
            "friend_id": friend_document["_id"],
            "kind": "daily",
            "sender_email": session.get("user"),
            "text": text,
            "created_at": current_timestamp(),
        }
    )
    return redirect(f"/friend/{friend_id}")


@app.route("/friend/<friend_id>/birthday_message", methods=["POST"])
def add_birthday_message(friend_id):
    if "user" not in session:
        return redirect("/")

    friend_document, redirect_response = get_friend_or_redirect(friend_id)
    if redirect_response:
        return redirect_response

    text = request.form.get("text", "").strip()
    if not text:
        return redirect(f"/friend/{friend_id}")

    messages.insert_one(
        {
            "owner_email": resolve_owner_email(friend_document),
            "friend_id": friend_document["_id"],
            "kind": "birthday",
            "sender_email": session.get("user"),
            "text": text,
            "created_at": current_timestamp(),
        }
    )
    return redirect(f"/friend/{friend_id}")


@app.route("/friend/<friend_id>/gift", methods=["POST"])
def add_gift(friend_id):
    if "user" not in session:
        return redirect("/")

    friend_document, redirect_response = get_friend_or_redirect(friend_id)
    if redirect_response:
        return redirect_response

    title = request.form.get("title", "").strip()
    details = request.form.get("details", "").strip()
    budget = request.form.get("budget", "").strip()
    purchase_link = request.form.get("purchase_link", "").strip()

    if not title:
        flash("Gift title is required")
        return redirect(f"/friend/{friend_id}")

    gifts.insert_one(
        {
            "owner_email": resolve_owner_email(friend_document),
            "friend_id": friend_document["_id"],
            "title": title,
            "details": details,
            "budget": budget,
            "purchase_link": purchase_link,
            "created_at": current_timestamp(),
        }
    )
    return redirect(f"/friend/{friend_id}")


@app.route("/friend/<friend_id>/delete")
def delete_friend(friend_id):
    if "user" not in session:
        return redirect("/")

    friend_document, redirect_response = get_friend_or_redirect(friend_id)
    if redirect_response:
        return redirect_response

    owner_email = friend_document.get("owner_email")
    messages.delete_many({"owner_email": owner_email, "friend_id": friend_document["_id"]})
    gifts.delete_many({"owner_email": owner_email, "friend_id": friend_document["_id"]})
    friends.delete_one({"_id": friend_document["_id"]})

    flash("Friend profile and related data deleted")
    if session.get("role") == "admin":
        return redirect("/admin")
    return redirect("/dashboard")

# BIRTHDAY
@app.route("/birthday")
def birthday():
    if not database_ready_or_flash():
        return redirect("/")

    if "user" not in session:
        return redirect("/")

    if session.get("role") == "admin":
        return render_template(
            "birthday.html",
            name="Admin Preview",
            preview=True,
            owner_name="Admin",
            birthday_messages=[{"text": "This is a preview birthday message."}],
            gifts=[{"title": "Preview Gift", "details": "A surprise gift preview.", "budget": "", "purchase_link": ""}],
            slideshow_images=[url_for("static", filename="images/img1.jpg")],
        )

    user = users.find_one({"email": session["user"]})
    if not user:
        return redirect("/")

    if can_access_birthday(user):
        return render_template(
            "birthday.html",
            name=user.get("name") or user["email"],
            preview=False,
            owner_name="Your friends",
            birthday_messages=[{"text": "Wishing you happiness, growth, and endless smiles."}],
            gifts=[],
            slideshow_images=[url_for("static", filename="images/img1.jpg")],
        )

    flash("This website opens the birthday screen only on your birthday.")
    return redirect("/dashboard")

# ADD NOTE
@app.route("/add_note", methods=["POST"])
def add_note():
    if not database_ready_or_flash():
        return redirect("/")

    if "user" not in session or session.get("role") != "user":
        return redirect("/")

    next_path = request.args.get("next", "/dashboard")
    if next_path not in {"/dashboard", "/birthday"}:
        next_path = "/dashboard"

    note = request.form["note"]
    if not note.strip():
        return redirect(next_path)

    users.update_one(
        {"email": session["user"]},
        {"$push": {
            "notes": {
                "text": note,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
        }}
    )
    return redirect(next_path)


@app.route("/birthday/friend/<token>")
def friend_birthday(token):
    if not database_ready_or_flash():
        return redirect("/")

    payload = read_friend_birthday_token(token)
    if not payload:
        flash("Birthday link is invalid or expired")
        return redirect("/")

    try:
        friend_id = ObjectId(payload.get("friend_id", ""))
    except Exception:
        flash("Birthday link is malformed")
        return redirect("/")

    friend_document = friends.find_one({"_id": friend_id})
    if not friend_document:
        flash("Friend profile not found")
        return redirect("/")

    is_admin = session.get("role") == "admin"
    if not is_admin and not is_birthday_today(friend_document.get("birthday")):
        flash("This birthday experience opens only on the birthday date")
        return redirect("/")

    owner_document = users.find_one({"email": friend_document.get("owner_email")}) or {}
    owner_name = owner_document.get("name") or friend_document.get("owner_email", "Friend")

    friend_messages = list(
        messages.find(
            {
                "owner_email": friend_document.get("owner_email"),
                "friend_id": friend_document["_id"],
                "kind": "birthday",
            }
        ).sort("created_at", 1)
    )

    friend_gifts = list(
        gifts.find(
            {
                "owner_email": friend_document.get("owner_email"),
                "friend_id": friend_document["_id"],
            }
        ).sort("created_at", -1)
    )

    slideshow_images = [
        url_for("static", filename="images/img1.jpg"),
        url_for("static", filename="images/cake.png"),
        url_for("static", filename="images/img1.jpg"),
    ]

    return render_template(
        "birthday.html",
        name=friend_document.get("name") or "Friend",
        preview=is_admin,
        owner_name=owner_name,
        birthday_messages=friend_messages,
        gifts=friend_gifts,
        slideshow_images=slideshow_images,
    )

# ADMIN
@app.route("/admin")
def admin():
    if not database_ready_or_flash():
        return redirect("/")

    if session.get("role") != "admin":
        return redirect("/")

    search_query = request.args.get("q", "").strip()
    user_filter = {"role": "user"}
    if search_query:
        safe_pattern = re.escape(search_query)
        user_filter["$or"] = [
            {"name": {"$regex": safe_pattern, "$options": "i"}},
            {"email": {"$regex": safe_pattern, "$options": "i"}},
        ]

    all_users = list(users.find(user_filter).sort("created_at", -1))

    friend_filter = {}
    if search_query:
        safe_pattern = re.escape(search_query)
        friend_filter["$or"] = [
            {"name": {"$regex": safe_pattern, "$options": "i"}},
            {"email": {"$regex": safe_pattern, "$options": "i"}},
            {"owner_email": {"$regex": safe_pattern, "$options": "i"}},
        ]

    all_friends = []
    for friend in friends.find(friend_filter).sort("created_at", -1):
        all_friends.append(
            {
                "id": str(friend["_id"]),
                "name": friend.get("name", "Friend"),
                "email": friend.get("email", ""),
                "owner_email": friend.get("owner_email", ""),
                "birthday": friend.get("birthday", ""),
                "is_today": is_birthday_today(friend.get("birthday")),
                "daily_count": messages.count_documents({
                    "owner_email": friend.get("owner_email"),
                    "friend_id": friend["_id"],
                    "kind": "daily",
                }),
                "birthday_count": messages.count_documents({
                    "owner_email": friend.get("owner_email"),
                    "friend_id": friend["_id"],
                    "kind": "birthday",
                }),
                "gift_count": gifts.count_documents({
                    "owner_email": friend.get("owner_email"),
                    "friend_id": friend["_id"],
                }),
            }
        )

    total_users = users.count_documents({"role": "user"})
    total_friends = friends.count_documents({})
    return render_template(
        "admin.html",
        users=all_users,
        friends=all_friends,
        total_users=total_users,
        total_friends=total_friends,
        search_query=search_query,
        auto_tomorrow_reminder_enabled=AUTO_TOMORROW_REMINDER_ENABLED,
    )


@app.route("/admin/send_email/<email>")
def admin_send_email(email):
    if not database_ready_or_flash():
        return redirect("/")

    if session.get("role") != "admin":
        return redirect("/")

    friend = friends.find_one({"email": email})
    if not friend:
        flash("Friend not found")
        return redirect("/admin")

    token = create_friend_birthday_token(friend)
    link = f"{get_base_url()}/birthday/friend/{token}"
    send_birthday_email(friend["email"], friend.get("name") or friend["email"], link_url=link)
    flash(f"Birthday email sent to {friend['email']}")
    return redirect("/admin")


@app.route("/admin/send_today_emails")
def admin_send_today_emails():
    if not database_ready_or_flash():
        return redirect("/")

    if session.get("role") != "admin":
        return redirect("/")

    birthday_reminder_job()
    if AUTO_TOMORROW_REMINDER_ENABLED:
        flash("Tomorrow birthday reminder emails have been triggered")
    else:
        flash("Reminder mode is OFF. Turn it ON to send tomorrow reminder emails.")
    return redirect("/admin")


@app.route("/admin/reminder_mode/<mode>")
def admin_set_reminder_mode(mode):
    global AUTO_TOMORROW_REMINDER_ENABLED

    if not database_ready_or_flash():
        return redirect("/")

    if session.get("role") != "admin":
        return redirect("/")

    normalized = (mode or "").strip().lower()
    if normalized in {"yes", "on", "true", "1"}:
        AUTO_TOMORROW_REMINDER_ENABLED = True
        flash("Automatic tomorrow reminder mode set to YES")
    elif normalized in {"no", "off", "false", "0"}:
        AUTO_TOMORROW_REMINDER_ENABLED = False
        flash("Automatic tomorrow reminder mode set to NO")
    else:
        flash("Invalid mode. Use yes or no.")

    return redirect("/admin")


@app.route("/birthdays")
def birthdays():
    if not database_ready_or_flash():
        return redirect("/")

    if session.get("role") != "admin":
        return redirect("/")

    today = datetime.now().date()
    friend_list = []
    for friend in friends.find({}):
        birthday_value = friend.get("birthday")
        birthday_date = parse_date(birthday_value)
        if birthday_date:
            next_birthday = get_next_birthday(birthday_value)
            days_left = (next_birthday - today).days
        else:
            days_left = 365

        friend_list.append(
            {
                "name": friend.get("name") or "Friend",
                "email": friend.get("email") or "",
                "owner_email": friend.get("owner_email") or "",
                "birthday": birthday_value or "",
                "days_left": days_left,
            }
        )

    friend_list.sort(key=lambda item: item["days_left"])
    return render_template("birthdays.html", users=friend_list)

# PREVIEW USER
@app.route("/preview/<email>")
def preview(email):
    if not database_ready_or_flash():
        return redirect("/")

    if session.get("role") != "admin":
        return redirect("/")

    friend = friends.find_one({"email": email})
    if not friend:
        return redirect("/admin")

    token = create_friend_birthday_token(friend)
    return redirect(f"/birthday/friend/{token}")


@app.route("/notes/<email>")
def user_notes(email):
    if not database_ready_or_flash():
        return redirect("/")

    if session.get("role") != "admin":
        return redirect("/")

    user = users.find_one({"email": email})
    if not user:
        return redirect("/admin")

    return render_template("notes.html", user=user)


@app.route("/edit_user/<email>", methods=["GET", "POST"])
def edit_user(email):
    if not database_ready_or_flash():
        return redirect("/")

    if session.get("role") != "admin":
        return redirect("/")

    user = users.find_one({"email": email})
    if not user:
        return redirect("/admin")

    if request.method == "POST":
        new_email = request.form["email"].strip().lower()
        birthday = request.form["birthday"]
        gender = request.form["gender"]
        name = request.form["name"].strip()

        if new_email != email and users.find_one({"email": new_email}):
            flash("New email already exists")
            return redirect(f"/edit_user/{email}")

        users.update_one(
            {"email": email},
            {"$set": {"email": new_email, "birthday": birthday, "gender": gender, "name": name}},
        )

        if new_email != email:
            friends.update_many({"owner_email": email}, {"$set": {"owner_email": new_email}})
            friends.update_many({"email": email}, {"$set": {"email": new_email, "name": name, "birthday": birthday}})
            messages.update_many({"owner_email": email}, {"$set": {"owner_email": new_email}})
            gifts.update_many({"owner_email": email}, {"$set": {"owner_email": new_email}})
            friend_requests.update_many({"from_email": email}, {"$set": {"from_email": new_email}})
            friend_requests.update_many({"to_email": email}, {"$set": {"to_email": new_email}})

        return redirect("/admin")

    return render_template("edit_user.html", user=user)


@app.route("/delete_user/<email>")
def delete_user(email):
    if not database_ready_or_flash():
        return redirect("/")

    if session.get("role") != "admin":
        return redirect("/")

    user_friends = list(friends.find({"owner_email": email}))
    for friend in user_friends:
        messages.delete_many({"owner_email": email, "friend_id": friend["_id"]})
        gifts.delete_many({"owner_email": email, "friend_id": friend["_id"]})

    friends.delete_many({"owner_email": email})
    friends.delete_many({"email": email})
    friend_requests.delete_many({"$or": [{"from_email": email}, {"to_email": email}]})
    users.delete_one({"email": email})
    return redirect("/admin")

# LOGOUT (safe alias)
@app.route("/logout", methods=["GET", "POST"])
def logout_alias():
    if session.get("role") == "admin":
        return redirect("/admin")

    return redirect("/profile")


@app.route("/signout", methods=["POST"])
def signout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=debug_mode, use_reloader=False)