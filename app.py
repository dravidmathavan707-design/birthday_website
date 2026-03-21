import os
import re
import smtplib
from email.message import EmailMessage

from flask import Flask, flash, redirect, render_template, request, session
from pymongo import MongoClient
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "secret123")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "dravid707@gmail.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "dravid7.dm")
MAIL_SENDER = os.getenv("MAIL_SENDER", "")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))

MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb+srv://mathan2192003_db_user:dravid_mathavan07_dm@cluster0.nxyoghv.mongodb.net/?appName=Cluster0",
)

client = MongoClient(MONGO_URI)
db = client["birthdayDB"]
users = db["users"]
users.create_index("email", unique=True)


def current_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_admin_account():
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


ensure_admin_account()


def get_next_birthday(birthday_string):
    today = datetime.now().date()
    birthday = datetime.strptime(birthday_string, "%Y-%m-%d").date()
    candidate = birthday.replace(year=today.year)
    if candidate < today:
        candidate = candidate.replace(year=today.year + 1)
    return candidate


def can_access_birthday(user_document):
    today = datetime.now().date()
    birthday = datetime.strptime(user_document["birthday"], "%Y-%m-%d").date()
    return today.month == birthday.month and today.day == birthday.day


def send_birthday_email(to_email, user_name):
    if not MAIL_SENDER or not MAIL_PASSWORD:
        return

    message = EmailMessage()
    message["Subject"] = "Happy Birthday! Your surprise is ready 🎂"
    message["From"] = MAIL_SENDER
    message["To"] = to_email
    message.set_content(
        f"Hi {user_name},\n\n"
        "Happy Birthday! Open your birthday website now to see your celebration page.\n\n"
        "Have an amazing day!"
    )

    with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as smtp:
        smtp.starttls()
        smtp.login(MAIL_SENDER, MAIL_PASSWORD)
        smtp.send_message(message)


def birthday_reminder_job():
    today = datetime.now().date()
    for user in users.find({"role": "user"}):
        try:
            birthday = datetime.strptime(user["birthday"], "%Y-%m-%d").date()
        except (ValueError, KeyError):
            continue

        if birthday.month == today.month and birthday.day == today.day:
            send_birthday_email(user["email"], user.get("name") or user["email"])


scheduler = BackgroundScheduler()
scheduler.add_job(birthday_reminder_job, "cron", hour=11, minute=57)
if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    scheduler.start()


@app.before_request
def update_user_activity():
    if "user" not in session:
        return

    endpoint = request.endpoint or ""
    if endpoint.startswith("static"):
        return

    users.update_one(
        {"email": session["user"]},
        {"$set": {"last_activity_at": current_timestamp()}},
    )

# REGISTER
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
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
                "role": "user",
                "notes": [],
                "created_at": current_timestamp(),
                "last_login_at": None,
                "last_activity_at": None,
                "login_count": 0,
                "birthday_viewed_on": None,
            }
        )
        flash("Registration successful. Please login.")
        return redirect("/")
    return render_template("register.html")

# LOGIN
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
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
    if "user" not in session:
        return redirect("/")

    if session.get("role") == "admin":
        return redirect("/admin")

    user = users.find_one({"email": session["user"]})
    if not user:
        session.clear()
        return redirect("/")

    next_birthday = get_next_birthday(user["birthday"])
    days_left = (next_birthday - datetime.now().date()).days
    is_birthday = can_access_birthday(user)
    today_string = datetime.now().strftime("%Y-%m-%d")
    birthday_viewed_today = user.get("birthday_viewed_on") == today_string
    desktop_unlocked = is_birthday and birthday_viewed_today

    if is_birthday and not birthday_viewed_today:
        flash("Open your birthday animation first to unlock your desktop for today.")
        return redirect("/birthday")

    return render_template(
        "dashboard.html",
        user=user,
        days_left=days_left,
        next_birthday=next_birthday.strftime("%d/%m/%Y"),
        is_birthday=is_birthday,
        desktop_unlocked=desktop_unlocked,
    )

# BIRTHDAY
@app.route("/birthday")
def birthday():
    if "user" not in session:
        return redirect("/")

    if session.get("role") == "admin":
        return render_template("birthday.html", name="Admin", preview=True)

    user = users.find_one({"email": session["user"]})
    if not user:
        return redirect("/")

    if can_access_birthday(user):
        users.update_one(
            {"email": user["email"]},
            {"$set": {"birthday_viewed_on": datetime.now().strftime("%Y-%m-%d")}},
        )
        return render_template("birthday.html", name=user.get("name") or user["email"], preview=False)

    flash("This website opens the birthday screen only on your birthday.")
    return redirect("/dashboard")

# ADD NOTE
@app.route("/add_note", methods=["POST"])
def add_note():
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

# ADMIN
@app.route("/admin")
def admin():
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
    total_users = users.count_documents({"role": "user"})
    return render_template("admin.html", users=all_users, total_users=total_users, search_query=search_query)


@app.route("/admin/send_email/<email>")
def admin_send_email(email):
    if session.get("role") != "admin":
        return redirect("/")

    user = users.find_one({"email": email, "role": "user"})
    if not user:
        flash("User not found")
        return redirect("/admin")

    send_birthday_email(user["email"], user.get("name") or user["email"])
    flash(f"Birthday email sent to {user['email']}")
    return redirect("/admin")


@app.route("/admin/send_today_emails")
def admin_send_today_emails():
    if session.get("role") != "admin":
        return redirect("/")

    birthday_reminder_job()
    flash("Birthday emails for today's users have been triggered")
    return redirect("/admin")


@app.route("/birthdays")
def birthdays():
    if session.get("role") != "admin":
        return redirect("/")

    today = datetime.now().date()
    user_list = []
    for user in users.find({"role": "user"}):
        try:
            next_birthday = get_next_birthday(user["birthday"])
            days_left = (next_birthday - today).days
        except (ValueError, KeyError):
            next_birthday = today + timedelta(days=365)
            days_left = 365

        user_list.append(
            {
                "name": user.get("name") or user["email"],
                "email": user["email"],
                "birthday": user.get("birthday", ""),
                "days_left": days_left,
            }
        )

    user_list.sort(key=lambda item: item["days_left"])
    return render_template("birthdays.html", users=user_list)

# PREVIEW USER
@app.route("/preview/<email>")
def preview(email):
    if session.get("role") != "admin":
        return redirect("/")

    user = users.find_one({"email": email})
    if not user:
        return redirect("/admin")

    return render_template("birthday.html", name=user.get("name") or user["email"], preview=True)


@app.route("/notes/<email>")
def user_notes(email):
    if session.get("role") != "admin":
        return redirect("/")

    user = users.find_one({"email": email})
    if not user:
        return redirect("/admin")

    return render_template("notes.html", user=user)


@app.route("/edit_user/<email>", methods=["GET", "POST"])
def edit_user(email):
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
        return redirect("/admin")

    return render_template("edit_user.html", user=user)


@app.route("/delete_user/<email>")
def delete_user(email):
    if session.get("role") != "admin":
        return redirect("/")

    users.delete_one({"email": email})
    return redirect("/admin")

# LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=debug_mode, use_reloader=False)