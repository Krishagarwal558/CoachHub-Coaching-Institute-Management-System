import os
import sqlite3
from datetime import date, datetime
from functools import wraps
from pathlib import Path

from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "coaching.db"
UPLOAD_DIR = BASE_DIR / "static" / "uploads"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-coachhub-secret")
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def query(sql, args=(), one=False):
    rows = db().execute(sql, args).fetchall()
    return (rows[0] if rows else None) if one else rows


def execute(sql, args=()):
    cursor = db().execute(sql, args)
    db().commit()
    return cursor


def init_db():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    schema = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin','teacher','student')),
        subject TEXT,
        class_name TEXT,
        phone TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        fee_status TEXT NOT NULL DEFAULT 'unpaid',
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS marks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        teacher_id INTEGER NOT NULL,
        subject TEXT NOT NULL,
        test_name TEXT NOT NULL,
        score REAL NOT NULL,
        max_score REAL NOT NULL,
        test_date TEXT NOT NULL,
        FOREIGN KEY(student_id) REFERENCES users(id),
        FOREIGN KEY(teacher_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        teacher_id INTEGER NOT NULL,
        class_date TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('present','absent')),
        UNIQUE(student_id, class_date),
        FOREIGN KEY(student_id) REFERENCES users(id),
        FOREIGN KEY(teacher_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS content (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        subject TEXT NOT NULL,
        content_type TEXT NOT NULL CHECK(content_type IN ('note','assignment','lecture')),
        description TEXT,
        file_path TEXT,
        video_url TEXT,
        due_date TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(teacher_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        note TEXT,
        file_path TEXT,
        submitted_at TEXT NOT NULL,
        UNIQUE(assignment_id, student_id),
        FOREIGN KEY(assignment_id) REFERENCES content(id),
        FOREIGN KEY(student_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        author_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        audience TEXT NOT NULL DEFAULT 'all',
        created_at TEXT NOT NULL,
        FOREIGN KEY(author_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS doubts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        teacher_id INTEGER,
        question TEXT NOT NULL,
        answer TEXT,
        status TEXT NOT NULL DEFAULT 'open',
        created_at TEXT NOT NULL,
        answered_at TEXT,
        FOREIGN KEY(student_id) REFERENCES users(id),
        FOREIGN KEY(teacher_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        rating INTEGER NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(student_id) REFERENCES users(id)
    );
    """
    db().executescript(schema)


@app.before_request
def bootstrap():
    init_db()


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return query("SELECT * FROM users WHERE id=?", (user_id,), one=True)


def has_admin():
    return query("SELECT id FROM users WHERE role='admin' LIMIT 1", one=True) is not None


@app.context_processor
def inject_globals():
    return {"current_user": current_user(), "year": datetime.now().year}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user():
            return view(*args, **kwargs)
        return redirect(url_for("login", next=request.path))
    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                return redirect(url_for("login", next=request.path))
            if user["role"] not in roles:
                flash("You do not have access to that workspace.", "error")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def save_upload(field_name):
    file = request.files.get(field_name)
    if not file or not file.filename:
        return None
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(file.filename)}"
    path = app.config["UPLOAD_FOLDER"] / filename
    file.save(path)
    return f"uploads/{filename}"


def attendance_percent(student_id):
    rows = query("SELECT status FROM attendance WHERE student_id=?", (student_id,))
    if not rows:
        return 0
    present = sum(1 for row in rows if row["status"] == "present")
    return round((present / len(rows)) * 100)


def average_score(student_id):
    row = query("SELECT AVG(score * 100.0 / max_score) AS avg_score FROM marks WHERE student_id=?", (student_id,), one=True)
    return round(row["avg_score"] or 0)


def dashboard_metrics():
    students = query("SELECT * FROM users WHERE role='student' ORDER BY name")
    teachers = query("SELECT * FROM users WHERE role='teacher' ORDER BY name")
    all_marks = query("SELECT m.*, u.name AS student_name FROM marks m JOIN users u ON u.id=m.student_id ORDER BY test_date")
    class_avg = round(sum((m["score"] / m["max_score"]) * 100 for m in all_marks) / len(all_marks)) if all_marks else 0
    return {
        "students": students,
        "teachers": teachers,
        "classes": sorted({row["class_name"] for row in students if row["class_name"]}),
        "unpaid": [row for row in students if row["fee_status"] == "unpaid"],
        "class_avg": class_avg,
    }


@app.route("/")
def home():
    if current_user():
        return redirect(url_for("dashboard"))
    return render_template("home.html", has_admin=has_admin())


@app.route("/setup-admin", methods=["GET", "POST"])
def setup_admin():
    if has_admin():
        flash("Admin setup is already complete.", "success")
        return redirect(url_for("login"))
    if request.method == "POST":
        execute(
            """INSERT INTO users (name,email,password_hash,role,phone,status,fee_status,created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                request.form["name"].strip(),
                request.form["email"].strip().lower(),
                generate_password_hash(request.form["password"]),
                "admin",
                request.form.get("phone", "").strip(),
                "active",
                "paid",
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        flash("Admin account created. Sign in to start adding teachers and students.", "success")
        return redirect(url_for("login"))
    return render_template("auth/setup_admin.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        if query("SELECT id FROM users WHERE email=?", (email,), one=True):
            flash("An account with this email already exists.", "error")
            return redirect(url_for("register"))
        execute(
            """INSERT INTO users (name,email,password_hash,role,class_name,phone,created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                request.form["name"].strip(),
                email,
                generate_password_hash(request.form["password"]),
                "student",
                request.form.get("class_name", "Class 10").strip(),
                request.form.get("phone", "").strip(),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        flash("Registration submitted. You can sign in as a student now.", "success")
        return redirect(url_for("login"))
    return render_template("auth/register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        user = query("SELECT * FROM users WHERE email=? AND status='active'", (email,), one=True)
        if user and check_password_hash(user["password_hash"], request.form["password"]):
            session.clear()
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['name'].split()[0]}.", "success")
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Invalid email or password.", "error")
    return render_template("auth/login.html", has_admin=has_admin())


@app.route("/logout")
def logout():
    session.clear()
    flash("Signed out securely.", "success")
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    metrics = dashboard_metrics()
    announcements = query(
        """SELECT a.*, u.name AS author_name FROM announcements a
           JOIN users u ON u.id=a.author_id
           WHERE audience IN ('all', ?) ORDER BY a.created_at DESC LIMIT 6""",
        (f"{user['role']}s",),
    )
    content = query("SELECT c.*, u.name AS teacher_name FROM content c JOIN users u ON u.id=c.teacher_id ORDER BY c.created_at DESC")
    marks = query(
        """SELECT m.*, u.name AS student_name FROM marks m JOIN users u ON u.id=m.student_id
           WHERE ? != 'student' OR m.student_id=? ORDER BY m.test_date DESC""",
        (user["role"], user["id"]),
    )
    attendance = query(
        """SELECT a.*, s.name AS student_name FROM attendance a JOIN users s ON s.id=a.student_id
           WHERE ? != 'student' OR a.student_id=? ORDER BY a.class_date DESC LIMIT 30""",
        (user["role"], user["id"]),
    )
    doubts = query(
        """SELECT d.*, s.name AS student_name, t.name AS teacher_name FROM doubts d
           JOIN users s ON s.id=d.student_id LEFT JOIN users t ON t.id=d.teacher_id
           WHERE ? != 'student' OR d.student_id=? ORDER BY d.created_at DESC""",
        (user["role"], user["id"]),
    )
    feedback_rows = query("SELECT f.*, u.name AS student_name FROM feedback f JOIN users u ON u.id=f.student_id ORDER BY f.created_at DESC")
    chart = {
        "labels": [m["test_name"] for m in reversed(marks[-8:])] or ["No tests"],
        "scores": [round(m["score"] * 100 / m["max_score"]) for m in reversed(marks[-8:])] or [0],
        "students": [s["name"] for s in metrics["students"]],
        "studentScores": [average_score(s["id"]) for s in metrics["students"]],
        "attendance": [attendance_percent(s["id"]) for s in metrics["students"]],
    }
    return render_template(
        "dashboard.html",
        user=user,
        metrics=metrics,
        announcements=announcements,
        content=content,
        marks=marks,
        attendance=attendance,
        doubts=doubts,
        feedback_rows=feedback_rows,
        chart=chart,
        today=date.today().isoformat(),
    )


@app.route("/users/create", methods=["POST"])
@roles_required("admin")
def create_user():
    email = request.form["email"].strip().lower()
    if query("SELECT id FROM users WHERE email=?", (email,), one=True):
        flash("That email is already registered.", "error")
        return redirect(url_for("dashboard"))
    execute(
        """INSERT INTO users (name,email,password_hash,role,subject,class_name,phone,fee_status,created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            request.form["name"].strip(),
            email,
            generate_password_hash(request.form["password"]),
            request.form["role"],
            request.form.get("subject", "").strip(),
            request.form.get("class_name", "").strip(),
            request.form.get("phone", "").strip(),
            request.form.get("fee_status", "unpaid"),
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    flash("User created and ready to sign in.", "success")
    return redirect(url_for("dashboard"))


@app.route("/users/<int:user_id>/update", methods=["POST"])
@roles_required("admin")
def update_user(user_id):
    execute(
        "UPDATE users SET name=?, role=?, subject=?, class_name=?, phone=?, fee_status=?, status=? WHERE id=?",
        (
            request.form["name"].strip(),
            request.form["role"],
            request.form.get("subject", "").strip(),
            request.form.get("class_name", "").strip(),
            request.form.get("phone", "").strip(),
            request.form.get("fee_status", "unpaid"),
            request.form.get("status", "active"),
            user_id,
        ),
    )
    flash("User profile updated.", "success")
    return redirect(url_for("dashboard"))


@app.route("/users/<int:user_id>/delete", methods=["POST"])
@roles_required("admin")
def delete_user(user_id):
    if user_id == current_user()["id"]:
        flash("Admins cannot delete their own active session.", "error")
    else:
        execute("DELETE FROM users WHERE id=?", (user_id,))
        flash("User deleted.", "success")
    return redirect(url_for("dashboard"))


@app.route("/marks", methods=["POST"])
@roles_required("teacher", "admin")
def add_mark():
    execute(
        "INSERT INTO marks (student_id,teacher_id,subject,test_name,score,max_score,test_date) VALUES (?,?,?,?,?,?,?)",
        (
            request.form["student_id"],
            current_user()["id"],
            request.form["subject"].strip(),
            request.form["test_name"].strip(),
            request.form["score"],
            request.form["max_score"],
            request.form["test_date"],
        ),
    )
    flash("Marks saved to the performance record.", "success")
    return redirect(url_for("dashboard"))


@app.route("/attendance", methods=["POST"])
@roles_required("teacher", "admin")
def mark_attendance():
    teacher_id = current_user()["id"]
    class_date = request.form["class_date"]
    for student in query("SELECT id FROM users WHERE role='student'"):
        status = request.form.get(f"student_{student['id']}", "absent")
        execute(
            """INSERT INTO attendance (student_id,teacher_id,class_date,status) VALUES (?,?,?,?)
               ON CONFLICT(student_id, class_date) DO UPDATE SET status=excluded.status, teacher_id=excluded.teacher_id""",
            (student["id"], teacher_id, class_date, status),
        )
    flash("Attendance updated for the selected date.", "success")
    return redirect(url_for("dashboard"))


@app.route("/content", methods=["POST"])
@roles_required("teacher", "admin")
def add_content():
    file_path = save_upload("file")
    execute(
        """INSERT INTO content (teacher_id,title,subject,content_type,description,file_path,video_url,due_date,created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            current_user()["id"],
            request.form["title"].strip(),
            request.form["subject"].strip(),
            request.form["content_type"],
            request.form.get("description", "").strip(),
            file_path,
            request.form.get("video_url", "").strip(),
            request.form.get("due_date", "").strip(),
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    flash("Learning content published.", "success")
    return redirect(url_for("dashboard"))


@app.route("/submit-assignment/<int:assignment_id>", methods=["POST"])
@roles_required("student")
def submit_assignment(assignment_id):
    file_path = save_upload("file")
    execute(
        """INSERT INTO submissions (assignment_id,student_id,note,file_path,submitted_at) VALUES (?,?,?,?,?)
           ON CONFLICT(assignment_id, student_id) DO UPDATE SET note=excluded.note, file_path=excluded.file_path, submitted_at=excluded.submitted_at""",
        (assignment_id, current_user()["id"], request.form.get("note", "").strip(), file_path, datetime.now().isoformat(timespec="seconds")),
    )
    flash("Assignment submitted.", "success")
    return redirect(url_for("dashboard"))


@app.route("/announcements", methods=["POST"])
@roles_required("teacher", "admin")
def post_announcement():
    execute(
        "INSERT INTO announcements (author_id,title,body,audience,created_at) VALUES (?,?,?,?,?)",
        (current_user()["id"], request.form["title"].strip(), request.form["body"].strip(), request.form["audience"], datetime.now().isoformat(timespec="seconds")),
    )
    flash("Announcement posted.", "success")
    return redirect(url_for("dashboard"))


@app.route("/doubts", methods=["POST"])
@roles_required("student")
def ask_doubt():
    execute(
        "INSERT INTO doubts (student_id,question,created_at) VALUES (?,?,?)",
        (current_user()["id"], request.form["question"].strip(), datetime.now().isoformat(timespec="seconds")),
    )
    flash("Your doubt was sent to the teaching team.", "success")
    return redirect(url_for("dashboard"))


@app.route("/doubts/<int:doubt_id>/answer", methods=["POST"])
@roles_required("teacher", "admin")
def answer_doubt(doubt_id):
    execute(
        "UPDATE doubts SET teacher_id=?, answer=?, status='answered', answered_at=? WHERE id=?",
        (current_user()["id"], request.form["answer"].strip(), datetime.now().isoformat(timespec="seconds"), doubt_id),
    )
    flash("Doubt answered.", "success")
    return redirect(url_for("dashboard"))


@app.route("/feedback", methods=["POST"])
@roles_required("student")
def submit_feedback():
    execute(
        "INSERT INTO feedback (student_id,rating,message,created_at) VALUES (?,?,?,?)",
        (current_user()["id"], request.form["rating"], request.form["message"].strip(), datetime.now().isoformat(timespec="seconds")),
    )
    flash("Thanks for the feedback.", "success")
    return redirect(url_for("dashboard"))


@app.route("/api/analytics")
@login_required
def analytics_api():
    metrics = dashboard_metrics()
    return jsonify(
        students=[row["name"] for row in metrics["students"]],
        scores=[average_score(row["id"]) for row in metrics["students"]],
        attendance=[attendance_percent(row["id"]) for row in metrics["students"]],
        classAverage=metrics["class_avg"],
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=True, use_reloader=False)
