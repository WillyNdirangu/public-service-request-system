"""
Public Service Request System (Mini eCitizen-style)
---------------------------------------------------
Citizens register, log in and report problems (broken streetlight, water issue...).
Admins see all requests, change their status and view simple analytics.
Stack: Python Flask + SQLite (the database is just one file: service.db)
"""
import os, sqlite3, uuid
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, g)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import secrets
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "muranga-2026-xk39dj20sl"

# ---------- Settings ----------
BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "service.db")
UPLOAD_DIR = os.path.join(BASE, "static", "uploads")
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif"}          # image types we accept
CATEGORIES = ["Streetlight", "Water Issue", "Garbage Collection", "Road Damage", "Other"]
STATUSES = ["Pending", "In Progress", "Resolved"]    # the order of the workflow
PRIORITIES = ["Low", "Medium", "Urgent"]
DEMO_MODE = True   # True = show the reset link on screen. In real life it would be emailed.
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ---------- Database helpers ----------
def get_db():
    """Open one database connection per request and reuse it."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row   # lets us use row["name"] instead of row[0]
    return g.db

@app.teardown_appcontext
def close_db(error):
    """Close the connection when the request ends."""
    db = g.pop("db", None)
    if db:
        db.close()

def init_db():
    """Create the tables the first time the app runs, plus a default admin."""
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,            -- stored as a hash, never plain text
            is_admin INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            location TEXT NOT NULL,
            description TEXT NOT NULL,
            image TEXT,                        -- optional file name
            status TEXT DEFAULT 'Pending',
            admin_note TEXT,                   -- bonus: admin can leave a message
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS password_resets(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,        -- random secret code in the reset link
            expires_at TEXT NOT NULL,          -- link stops working after this time
            used INTEGER DEFAULT 0,            -- 1 once the link has been used
            FOREIGN KEY(user_id) REFERENCES users(id));
    """)
        # Add the "note_read" column (0 = unread, 1 = read). Skipped if it already exists.
    try:
        db.execute("ALTER TABLE requests ADD COLUMN note_read INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass   # the column is already there, nothing to do
            
        # Add the "priority" column. Old requests automatically become "Medium".
    try:
        db.execute("ALTER TABLE requests ADD COLUMN priority TEXT DEFAULT 'Medium'")
    except sqlite3.OperationalError:
        pass
    if not db.execute("SELECT 1 FROM users WHERE is_admin=1").fetchone():
        db.execute("INSERT INTO users(name,email,password,is_admin) VALUES(?,?,?,1)",
                   ("Administrator", "admin@city.go.ke", generate_password_hash("admin123")))
    db.commit()
    db.close()


# ---------- Access control ----------
def login_required(f):
    """Only logged-in users can open the page."""
    @wraps(f)
    def wrapper(*a, **kw):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return f(*a, **kw)
    return wrapper

def admin_required(f):
    """Only admins can open the page."""
    @wraps(f)
    def wrapper(*a, **kw):
        if not session.get("is_admin"):
            flash("Admins only.", "error")
            return redirect(url_for("index"))
        return f(*a, **kw)
    return wrapper

@app.context_processor
def inject_globals():
    """Make these values available in every HTML template."""
    unread = 0
    if session.get("user_id") and not session.get("is_admin"):
        # How many admin messages has this citizen not opened yet?
        unread = get_db().execute(
            "SELECT COUNT(*) FROM requests WHERE user_id=? AND note_read=0 "
            "AND admin_note IS NOT NULL AND admin_note != ''",
            (session["user_id"],)).fetchone()[0]
    return {"statuses": STATUSES, "unread_count": unread}


# ---------- Public pages ----------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        if not name or not email or len(password) < 6:
            flash("Fill all fields. Password must be at least 6 characters.", "error")
        else:
            try:
                get_db().execute("INSERT INTO users(name,email,password) VALUES(?,?,?)",
                                 (name, email, generate_password_hash(password)))
                get_db().commit()
                flash("Account created. You can log in now.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:      # email already exists
                flash("That email is already registered.", "error")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        user = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password"], request.form["password"]):
            session.clear()
            session["user_id"], session["name"] = user["id"], user["name"]
            session["is_admin"] = bool(user["is_admin"])
            return redirect(url_for("admin" if user["is_admin"] else "my_requests"))
        flash("Wrong email or password.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# ---------- Forgot / reset password ----------
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Step 1: the user enters their email and we create a reset link."""
    reset_link = None
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user:
            token = secrets.token_urlsafe(32)                        # long random code
            expires = (datetime.now() + timedelta(minutes=30)).isoformat()
            db.execute("INSERT INTO password_resets(user_id,token,expires_at) VALUES(?,?,?)",
                       (user["id"], token, expires))
            db.commit()
            link = url_for("reset_password", token=token, _external=True)
            print("PASSWORD RESET LINK:", link)                      # also shown in the terminal
            if DEMO_MODE:
                reset_link = link          # real system: email this link instead
        # Same message whether or not the email exists, so strangers can't guess who is registered
        flash("If that email is registered, a reset link has been created.", "success")
    return render_template("forgot_password.html", reset_link=reset_link)


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """Step 2: the user opens the link and chooses a new password."""
    db = get_db()
    row = db.execute("SELECT * FROM password_resets WHERE token=? AND used=0", (token,)).fetchone()
    # Reject unknown, already-used or expired links
    if not row or datetime.fromisoformat(row["expires_at"]) < datetime.now():
        flash("This reset link is invalid or has expired. Please request a new one.", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        password = request.form["password"]
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
        elif password != request.form["confirm"]:
            flash("The two passwords do not match.", "error")
        else:
            db.execute("UPDATE users SET password=? WHERE id=?",
                       (generate_password_hash(password), row["user_id"]))   # save as a hash
            db.execute("UPDATE password_resets SET used=1 WHERE id=?", (row["id"],))  # one-time use
            db.commit()
            flash("Password changed. You can log in now.", "success")
            return redirect(url_for("login"))
    return render_template("reset_password.html")


# ---------- Citizen pages ----------
@app.route("/submit", methods=["GET", "POST"])
@login_required
def submit():
    if request.method == "POST":
        category = request.form["category"]
        location = request.form["location"].strip()
        description = request.form["description"].strip()
        priority = request.form.get("priority", "Medium")
        if priority not in PRIORITIES:
            priority = "Medium"
        if category not in CATEGORIES or not location or not description:
            flash("Please fill in category, location and description.", "error")
            return render_template("submit.html", categories=CATEGORIES, priorities=PRIORITIES)

        # Image is optional: only save it if it is an allowed type
        filename = None
        file = request.files.get("image")
        if file and file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()
            if ext not in ALLOWED_EXT:
                flash("Image must be png, jpg, jpeg or gif.", "error")
                return render_template("submit.html", categories=CATEGORIES, priorities=PRIORITIES)
            filename = uuid.uuid4().hex + "_" + secure_filename(file.filename)  # unique name
            file.save(os.path.join(UPLOAD_DIR, filename))

        get_db().execute(
            "INSERT INTO requests(user_id,category,location,description,image,priority) "
            "VALUES(?,?,?,?,?,?)",
            (session["user_id"], category, location, description, filename, priority))
        get_db().commit()
        flash("Request submitted successfully!", "success")
        return redirect(url_for("my_requests"))
    return render_template("submit.html", categories=CATEGORIES, priorities=PRIORITIES)

@app.route("/my-requests")
@login_required
def my_requests():
    rows = get_db().execute(
        "SELECT * FROM requests WHERE user_id=? ORDER BY id DESC", (session["user_id"],)).fetchall()
    return render_template("my_requests.html", requests=rows)

@app.route("/requests/<int:req_id>/read", methods=["POST"])
@login_required
def mark_note_read(req_id):
    """Called when the citizen opens the message. Only their own requests can be changed."""
    get_db().execute("UPDATE requests SET note_read=1 WHERE id=? AND user_id=?",
                     (req_id, session["user_id"]))
    get_db().commit()
    return "", 204   # "done, nothing to show"

@app.route("/requests/<int:req_id>/edit", methods=["GET", "POST"])
@login_required
def edit_request(req_id):
    """Citizens can edit their own request, but only while it is still Pending."""
    db = get_db()
    r = db.execute("SELECT * FROM requests WHERE id=? AND user_id=?",
                   (req_id, session["user_id"])).fetchone()
    if not r:
        flash("Request not found.", "error")
        return redirect(url_for("my_requests"))
    if r["status"] != "Pending":
        flash("Only Pending requests can be edited.", "error")
        return redirect(url_for("my_requests"))

    if request.method == "POST":
        category = request.form["category"]
        location = request.form["location"].strip()
        description = request.form["description"].strip()
        priority = request.form.get("priority", "Medium")
        if category not in CATEGORIES or priority not in PRIORITIES or not location or not description:
            flash("Please fill in all fields.", "error")
        else:
            db.execute("UPDATE requests SET category=?, location=?, description=?, priority=? WHERE id=?",
                       (category, location, description, priority, req_id))
            db.commit()
            flash(f"Request #{req_id} updated.", "success")
            return redirect(url_for("my_requests"))
    return render_template("edit_request.html", r=r, categories=CATEGORIES, priorities=PRIORITIES)


@app.route("/requests/<int:req_id>/cancel", methods=["POST"])
@login_required
def cancel_request(req_id):
    """Citizens can cancel (delete) their own request, but only while it is still Pending."""
    db = get_db()
    r = db.execute("SELECT * FROM requests WHERE id=? AND user_id=? AND status='Pending'",
                   (req_id, session["user_id"])).fetchone()
    if r:
        if r["image"]:                       # also delete the uploaded photo from the disk
            try:
                os.remove(os.path.join(UPLOAD_DIR, r["image"]))
            except OSError:
                pass
        db.execute("DELETE FROM requests WHERE id=?", (req_id,))
        db.commit()
        flash(f"Request #{req_id} was cancelled.", "success")
    else:
        flash("Only your own Pending requests can be cancelled.", "error")
    return redirect(url_for("my_requests"))

# ---------- Admin pages ----------
@app.route("/admin")
@login_required
@admin_required
def admin():
    db = get_db()
    status_filter = request.args.get("status", "")           # bonus: filter by status
    sql = ("SELECT r.*, u.name AS citizen FROM requests r "
           "JOIN users u ON u.id = r.user_id ")
    args = ()
    if status_filter in STATUSES:
        sql += "WHERE r.status=? "
        args = (status_filter,)
    
    # Order: unresolved first, then Urgent -> Medium -> Low, then newest first
    order = ("ORDER BY CASE WHEN r.status='Resolved' THEN 1 ELSE 0 END, "
             "CASE r.priority WHEN 'Urgent' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END, r.id DESC")
    rows = db.execute(sql + order, args).fetchall()

    # Analytics: count requests per status and per category
    counts = {s: 0 for s in STATUSES}
    for r in db.execute("SELECT status, COUNT(*) c FROM requests GROUP BY status"):
        counts[r["status"]] = r["c"]
    by_cat = db.execute("SELECT category, COUNT(*) c FROM requests "
                        "GROUP BY category ORDER BY c DESC").fetchall()
    stats = {"total": sum(counts.values()),
             "open": counts["Pending"] + counts["In Progress"],   # not yet finished
             "resolved": counts["Resolved"], "counts": counts}
    return render_template("admin.html", requests=rows, stats=stats,
                           by_cat=by_cat, current=status_filter)

@app.route("/admin/update/<int:req_id>", methods=["POST"])
@login_required
@admin_required
def update_status(req_id):
    status = request.form["status"]
    note = request.form.get("note", "").strip()
    db = get_db()
    old = db.execute("SELECT status, admin_note FROM requests WHERE id=?", (req_id,)).fetchone()
    if old and status in STATUSES:
        # The citizen should see it as "new" if there is a note and
        # either the note text or the status has changed
        changed = (note != (old["admin_note"] or "")) or (status != old["status"])
        unread = 0 if (note and changed) else None
        if unread is None:
            db.execute("UPDATE requests SET status=?, admin_note=? WHERE id=?",
                       (status, note, req_id))
        else:
            db.execute("UPDATE requests SET status=?, admin_note=?, note_read=0 WHERE id=?",
                       (status, note, req_id))
        db.commit()
        flash(f"Request #{req_id} updated to {status}.", "success")
    return redirect(request.referrer or url_for("admin"))


if __name__ == "__main__":
    init_db()
    app.run()
