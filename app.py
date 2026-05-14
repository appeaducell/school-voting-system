from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    send_file,
    flash
)

import sqlite3
import os
import pandas as pd

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


from datetime import datetime

app = Flask(__name__)
app.secret_key = "secure"

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def db():

    return sqlite3.connect("database.db")




def init():

    conn = db()
    cur = conn.cursor()

    # ================= STUDENTS =================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS students(
        student_id TEXT PRIMARY KEY,
        name TEXT,
        has_voted INTEGER DEFAULT 0
    )
    """)

    # ================= PORTFOLIOS =================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS portfolios(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT
    )
    """)

    # ================= CANDIDATES =================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS candidates(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        portfolio_id INTEGER,
        image TEXT
    )
    """)

    # ================= VOTES =================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS votes(
        student_id TEXT,
        candidate_id INTEGER,
        portfolio_id INTEGER
    )
    """)

    # ================= SETTINGS =================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        school_name TEXT,
        election_year TEXT,
        logo TEXT,
        start_time TEXT,
        end_time TEXT
    )
    """)

    # ================= ARCHIVED VOTES =================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS archived_votes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        candidate_id INTEGER,
        portfolio_id INTEGER,
        archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ================= RESET LOGS =================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS reset_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin TEXT,
        action TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ================= ADMINS =================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS admins(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        can_manage_students INTEGER DEFAULT 0,
        can_manage_candidates INTEGER DEFAULT 0,
        can_manage_results INTEGER DEFAULT 0,
        can_manage_settings INTEGER DEFAULT 0
    )
    """)

    # ================= DEFAULT ADMIN =================
    admin_exists = cur.execute(
        "SELECT * FROM admins WHERE username=?",
        ("admin",)
    ).fetchone()

    if not admin_exists:

        hashed = generate_password_hash("admin123")

        cur.execute("""
            INSERT INTO admins(
                username,
                password,
                can_manage_students,
                can_manage_candidates,
                can_manage_results,
                can_manage_settings
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            "admin",
            hashed,
            1,
            1,
            1,
            1
        ))

    conn.commit()
    conn.close()

init()




@app.context_processor
def inject_settings():

    conn = db()
    cur = conn.cursor()

    data = cur.execute("""
        SELECT *
        FROM settings
        ORDER BY id DESC
        LIMIT 1
    """).fetchone()

    conn.close()

    if data:

        return dict(
            school_name=data[1],
            election_year=data[2],
            logo=data[3],
            start_time=data[4],
            end_time=data[5]
        )

    return dict(
        school_name="School Voting System",
        election_year="2026",
        logo="",
        start_time="",
        end_time=""
    )

# ================= LOGIN =================
@app.route("/")
def home():
    return render_template("login.html")

@app.route("/admin")
def admin():

    if "admin" not in session:
        return redirect("/")

    return redirect("/dashboard")



@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():

    if "admin" not in session:
        return redirect("/")

    conn = db()
    cur = conn.cursor()

    portfolios = cur.execute("""
        SELECT *
        FROM portfolios
    """).fetchall()

    candidates = cur.execute("""
        SELECT *
        FROM candidates
    """).fetchall()

    students = cur.execute("""
        SELECT *
        FROM students
    """).fetchall()

    admins = cur.execute("""
        SELECT *
        FROM admins
    """).fetchall()

    total_students = len(students)

    voted_students = cur.execute("""
        SELECT COUNT(*)
        FROM students
        WHERE has_voted=1
    """).fetchone()[0]

    not_voted = total_students - voted_students

    conn.close()

    return render_template(
        "admin.html",
        portfolios=portfolios,
        candidates=candidates,
        students=students,
        admins=admins,
        total_students=total_students,
        voted_students=voted_students,
        not_voted=not_voted
    )


# ================= PORTFOLIO =================
@app.route("/add_portfolio", methods=["POST"])
def add_portfolio():

    if "admin" not in session:
        return redirect("/")

    conn = db()

    conn.execute("""
        INSERT INTO portfolios(name)
        VALUES (?)
    """, (request.form["name"],))

    conn.commit()
    conn.close()

    flash("Portfolio added successfully")

    return redirect("/dashboard")


@app.route("/delete_portfolio/<pid>")
def delete_portfolio(pid):

    if "admin" not in session:
        return redirect("/")

    conn = db()

    # delete votes first
    conn.execute("""
        DELETE FROM votes
        WHERE portfolio_id=?
    """, (pid,))

    # delete candidates
    conn.execute("""
        DELETE FROM candidates
        WHERE portfolio_id=?
    """, (pid,))

    # delete portfolio
    conn.execute("""
        DELETE FROM portfolios
        WHERE id=?
    """, (pid,))

    conn.commit()
    conn.close()

    flash("Portfolio deleted successfully")

    return redirect("/dashboard")

# ================= CANDIDATES =================
@app.route("/add_candidate", methods=["POST"])
def add_candidate():

    if "admin" not in session:
        return redirect("/")

    name = request.form["name"]
    pid = request.form["portfolio"]

    file = request.files.get("image")

    filename = ""

    if file and file.filename != "":

        filename = file.filename

        file.save(
            os.path.join(
                UPLOAD_FOLDER,
                filename
            )
        )

    conn = db()

    conn.execute("""
        INSERT INTO candidates(
            name,
            portfolio_id,
            image
        )
        VALUES (?, ?, ?)
    """, (
        name,
        pid,
        filename
    ))

    conn.commit()
    conn.close()

    flash("Candidate added successfully")

    return redirect("/dashboard")

@app.route("/upload_students", methods=["POST"])
def upload_students():
    if "admin" not in session:
        return redirect("/")

    file = request.files.get("file")

    # ❌ No file selected
    if not file or file.filename == "":
        flash("No file selected")
        return redirect("/dashboard")

    try:
        # Read Excel
        df = pd.read_excel(file)

        # Normalize column names (lowercase, strip spaces)
        df.columns = [col.strip().lower() for col in df.columns]

        # Validate required columns
        if "student_id" not in df.columns or "name" not in df.columns:
            flash("Excel must contain 'student_id' and 'name' columns")
            return redirect("/dashboard")

        conn = db()
        inserted = 0

        for _, row in df.iterrows():
            student_id = str(row["student_id"]).strip()
            name = str(row["name"]).strip()

            if student_id and name:
                conn.execute(
                    "INSERT OR IGNORE INTO students(student_id, name, has_voted) VALUES (?, ?, 0)",
                    (student_id, name)
                )
                inserted += 1

        conn.commit()
        conn.close()

        flash(f"{inserted} students uploaded successfully")
        return redirect("/dashboard")

    except Exception as e:
        return f"Upload failed: {str(e)}"

# ================= STUDENT =================
@app.route("/student", methods=["POST"])
def student():
    sid = request.form["student_id"]

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT has_voted FROM students WHERE student_id=?", (sid,))
    res = cur.fetchone()
    conn.close()

    if res and res[0] == 0:
        session["student"] = sid
        return redirect("/vote")

    return "Invalid or already voted"

# ================= VOTING =================
@app.route("/vote", methods=["GET", "POST"])
def vote():

    # must login first
    if "student" not in session:
        return redirect("/")

    conn = db()
    cur = conn.cursor()

    # check if student exists
    cur.execute("""
        SELECT has_voted
        FROM students
        WHERE student_id=?
    """, (session["student"],))

    row = cur.fetchone()

    if not row:

        conn.close()

        return "Student not found"

    # already voted
    if row[0] == 1:
        
        conn.close()

        return "You have already voted."

    # =========================
    # CHECK ELECTION END TIME
    # =========================
    settings = cur.execute("""
        SELECT end_time
        FROM settings
        LIMIT 1
    """).fetchone()

    if settings and settings[0]:

        end_time = datetime.fromisoformat(
    settings[0]
)

        if datetime.now() > end_time:

            conn.close()

            return "Voting period has ended."

    # =========================
    # FINAL SUBMIT
    # =========================
    if request.method == "POST":

        portfolios = cur.execute("""
            SELECT *
            FROM portfolios
        """).fetchall()

        # ensure every portfolio selected
        for p in portfolios:

            portfolio_id = str(p[0])

            if portfolio_id not in request.form:

                conn.close()

                return f"You must vote for {p[1]}"

        # save votes
        for portfolio_id in request.form:

            candidate_id = request.form[portfolio_id]

            cur.execute("""
                INSERT INTO votes(
                    student_id,
                    candidate_id,
                    portfolio_id
                )
                VALUES (?, ?, ?)
            """, (
                session["student"],
                candidate_id,
                portfolio_id
            ))

        # mark student voted
        cur.execute("""
            UPDATE students
            SET has_voted=1
            WHERE student_id=?
        """, (session["student"],))

        conn.commit()
        conn.close()

        return redirect("/thanks")

    # =========================
    # LOAD BALLOT
    # =========================
    portfolios = cur.execute("""
        SELECT *
        FROM portfolios
    """).fetchall()

    data = {}

    for p in portfolios:

        candidates = cur.execute("""
            SELECT *
            FROM candidates
            WHERE portfolio_id=?
        """, (p[0],)).fetchall()

        data[p[1]] = {
            "id": p[0],
            "candidates": candidates
        }

    conn.close()

    return render_template(
        "vote.html",
        data=data
    )

@app.route("/delete_admin/<aid>")
def delete_admin(aid):

    if "admin" not in session:
        return redirect("/")

    # only main admin can delete
    if session["admin"] != "admin":
        return "Access Denied"

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM admins
        WHERE id=?
    """, (aid,))

    conn.commit()
    conn.close()

    flash("Admin deleted successfully")

    return redirect("/dashboard")



# ================= RESULTS =================
@app.route("/results")
def results():

    if "admin" not in session:
        return redirect("/")    
    conn = db()

    rows = conn.execute("""
        SELECT portfolios.name,
               candidates.name,
               candidates.image,
               COUNT(votes.rowid) as total_votes
        FROM candidates
        JOIN portfolios ON portfolios.id = candidates.portfolio_id
        LEFT JOIN votes ON votes.candidate_id = candidates.id
        GROUP BY candidates.id
        ORDER BY portfolios.name, total_votes DESC
    """).fetchall()

    conn.close()

    portfolios = {}

    for p, c, img, v in rows:

        if p not in portfolios:
            portfolios[p] = []

        portfolios[p].append({
            "name": c,
            "votes": v,
            "image": img
        })

    # percentages
    for p in portfolios:

        total_votes = sum(c["votes"] for c in portfolios[p]) or 1

        for c in portfolios[p]:
            c["percent"] = round((c["votes"] / total_votes) * 100, 1)

    return render_template("results.html", portfolios=portfolios)

@app.route("/export_results")
def export_results():

    if "admin" not in session:
        return redirect("/")

    conn = db()

    rows = conn.execute("""
        SELECT portfolios.name,
               candidates.name,
               COUNT(votes.rowid) as votes
        FROM candidates
        JOIN portfolios
            ON portfolios.id = candidates.portfolio_id
        LEFT JOIN votes
            ON votes.candidate_id = candidates.id
        GROUP BY candidates.id
        ORDER BY portfolios.name, votes DESC
    """).fetchall()

    conn.close()

    df = pd.DataFrame(
        rows,
        columns=[
            "Portfolio",
            "Candidate",
            "Votes"
        ]
    )

    file_path = "election_results.xlsx"

    df.to_excel(file_path, index=False)

    return send_file(
        file_path,
        as_attachment=True
    )

@app.route("/charts")
def charts():

    if "admin" not in session:
        return redirect("/")

    conn = db()

    rows = conn.execute("""
        SELECT portfolios.name,
               candidates.name,
               COUNT(votes.rowid) as votes
        FROM candidates
        JOIN portfolios
            ON portfolios.id = candidates.portfolio_id
        LEFT JOIN votes
            ON votes.candidate_id = candidates.id
        GROUP BY candidates.id
        ORDER BY portfolios.name
    """).fetchall()

    conn.close()

    portfolios = {}

    for p, c, v in rows:

        if p not in portfolios:

            portfolios[p] = {
                "labels": [],
                "votes": []
            }

        portfolios[p]["labels"].append(c)
        portfolios[p]["votes"].append(v)

    return render_template(
        "charts.html",
        portfolios=portfolios
    )

@app.route("/settings", methods=["GET", "POST"])
def settings():

    if "admin" not in session:
        return redirect("/")

    conn = db()
    cur = conn.cursor()

    if request.method == "POST":

        school = request.form.get("school")
        year = request.form.get("year")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")

        logo_name = None

        file = request.files.get("logo")

        # upload logo
        if file and file.filename != "":

            logo_name = file.filename

            file.save(
                os.path.join(
                    "static/uploads",
                    logo_name
                )
            )

        existing = cur.execute("""
            SELECT *
            FROM settings
            LIMIT 1
        """).fetchone()

        if existing:

            if not logo_name:
                logo_name = existing[3]

            cur.execute("""
                UPDATE settings
                SET school_name=?,
                    election_year=?,
                    logo=?,
                    start_time=?,
                    end_time=?
                WHERE id=?
            """, (
                school,
                year,
                logo_name,
                start_time,
                end_time,
                existing[0]
            ))

        else:

            cur.execute("""
                INSERT INTO settings(
                    school_name,
                    election_year,
                    logo,
                    start_time,
                    end_time
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                school,
                year,
                logo_name if logo_name else "",
                start_time,
                end_time
            ))

        conn.commit()
        conn.close()

        from flask import flash
        flash("Settings updated successfully")

        return redirect("/settings")

    data = cur.execute("""
        SELECT *
        FROM settings
        LIMIT 1
    """).fetchone()

    conn.close()

    return render_template(
        "settings.html",
        data=data
    )

@app.route("/delete_candidate/<int:cid>")
def delete_candidate(cid):
    if "admin" not in session:
        return redirect("/")

    conn = db()
    conn.execute("DELETE FROM candidates WHERE id=?", (cid,))
    conn.commit()
    conn.close()

    from flask import flash
    flash("Candidate deleted successfully")

    return redirect("/dashboard")

@app.route("/download_candidates")
def download_candidates():

    if "admin" not in session:
        return redirect("/")

    conn = db()

    portfolios = conn.execute("""
        SELECT *
        FROM portfolios
        ORDER BY name
    """).fetchall()

    file_path = "statement_of_poll.txt"

    with open(file_path, "w", encoding="utf-8") as f:

        f.write("OFFICIAL STATEMENT OF POLL\n")
        f.write("=" * 40 + "\n\n")

        for p in portfolios:

            f.write(f"{p[1].upper()}\n")
            f.write("-" * 30 + "\n")

            candidates = conn.execute("""
                SELECT name
                FROM candidates
                WHERE portfolio_id=?
                ORDER BY name
            """, (p[0],)).fetchall()

            for i, c in enumerate(candidates, start=1):

                f.write(f"{i}. {c[0]}\n")

            f.write("\n\n")

    conn.close()

    return send_file(
        file_path,
        as_attachment=True
    )

@app.route("/delete_students", methods=["POST"])
def delete_students():

    if "admin" not in session:
        return redirect("/")

    student_ids = request.form.getlist("student_ids")

    if not student_ids:

        flash("No students selected")

        return redirect("/dashboard")

    conn = db()

    for sid in student_ids:

        # delete votes first
        conn.execute("""
            DELETE FROM votes
            WHERE student_id=?
        """, (sid,))

        # delete student
        conn.execute("""
            DELETE FROM students
            WHERE student_id=?
        """, (sid,))

    conn.commit()
    conn.close()

    flash(f"{len(student_ids)} students deleted successfully")

    return redirect("/dashboard")

@app.route("/print_results")
def print_results():

    if "admin" not in session:
        return redirect("/")

    conn = db()

    rows = conn.execute("""
        SELECT portfolios.name,
               candidates.name,
               COUNT(votes.rowid)
        FROM candidates
        JOIN portfolios
            ON portfolios.id = candidates.portfolio_id
        LEFT JOIN votes
            ON votes.candidate_id = candidates.id
        GROUP BY candidates.id
        ORDER BY portfolios.name
    """).fetchall()

    conn.close()

    return render_template(
        "print.html",
        rows=rows
    )

@app.route("/reset", methods=["GET", "POST"])
def reset():

    if "admin" not in session:
        return redirect("/")

    # show confirmation page
    if request.method == "GET":
        return render_template("reset_confirm.html")

    password = request.form.get("password")

    conn = db()
    cur = conn.cursor()

    # verify current admin password
    admin_username = session.get("admin")

    admin = cur.execute("""
        SELECT password
        FROM admins
        WHERE username=?
    """, (admin_username,)).fetchone()

    if not admin or not check_password_hash(admin[0], password):

        flash("Incorrect admin password")

        conn.close()

        return redirect("/reset")

    # =========================
    # ARCHIVE CURRENT VOTES
    # =========================

    votes = cur.execute("""
        SELECT student_id, candidate_id, portfolio_id
        FROM votes
    """).fetchall()

    for v in votes:

        cur.execute("""
            INSERT INTO archived_votes(
                student_id,
                candidate_id,
                portfolio_id
            )
            VALUES (?, ?, ?)
        """, (
            v[0],
            v[1],
            v[2]
        ))

    # =========================
    # RESET VOTES
    # =========================

    cur.execute("DELETE FROM votes")

    cur.execute("""
        UPDATE students
        SET has_voted=0
    """)

    # =========================
    # LOG RESET
    # =========================

    cur.execute("""
        INSERT INTO reset_logs(
            admin,
            action
        )
        VALUES (?, ?)
    """, (
        admin_username,
        "Reset entire election"
    ))

    conn.commit()
    conn.close()

    flash("Election reset successfully")

    return redirect("/dashboard")


@app.route("/reset_admin_password", methods=["POST"])
def reset_admin_password():

    if "admin" not in session:
        return redirect("/")

    username = request.form.get("username")
    new_password = request.form.get("new_password")

    hashed = generate_password_hash(new_password)

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE admins
        SET password=?
        WHERE username=?
    """, (
        hashed,
        username
    ))

    conn.commit()
    conn.close()

    flash("Admin password updated successfully")

    return redirect("/dashboard")


    cur.execute("""
        UPDATE admins
        SET password=?
        WHERE username=?
    """, (
        hashed,
        username
    ))

    conn.commit()
    conn.close()

    flash("Password reset successfully")

    return redirect("/dashboard")



@app.route("/thanks")
def thanks():
    return render_template("thanks.html")

@app.route("/reset_student/<sid>")
def reset_student(sid):

    if "admin" not in session:
        return redirect("/")

    conn = db()
    cur = conn.cursor()

    # remove student's votes
    cur.execute("""
        DELETE FROM votes
        WHERE student_id=?
    """, (sid,))

    # unlock student
    cur.execute("""
        UPDATE students
        SET has_voted=0
        WHERE student_id=?
    """, (sid,))

    conn.commit()
    conn.close()

    from flask import flash
    flash("Student voting reset successfully")

    return redirect("/dashboard")

@app.route("/reset_portfolio/<pid>")
def reset_portfolio(pid):

    if "admin" not in session:
        return redirect("/")

    conn = db()
    cur = conn.cursor()

    # delete votes for that portfolio
    cur.execute("""
        DELETE FROM votes
        WHERE portfolio_id=?
    """, (pid,))

    # unlock all students
    cur.execute("""
        UPDATE students
        SET has_voted=0
    """)

    conn.commit()
    conn.close()

    from flask import flash
    flash("Portfolio votes reset successfully")

    return redirect("/dashboard")

@app.route("/download_students")
def download_students():

    if "admin" not in session:
        return redirect("/")

    conn = db()

    students = conn.execute("""
        SELECT student_id, name, has_voted
        FROM students
    """).fetchall()

    conn.close()

    df = pd.DataFrame(
        students,
        columns=["Student ID", "Name", "Has Voted"]
    )

    file_path = "students.xlsx"

    df.to_excel(file_path, index=False)

    return send_file(file_path, as_attachment=True)


@app.route("/voter_register")
def voter_register():

    if "admin" not in session:
        return redirect("/")

    conn = db()

    students = conn.execute("""
        SELECT student_id, name, has_voted
        FROM students
    """).fetchall()

    conn.close()

    return render_template(
        "voter_register.html",
        students=students
    )

@app.route("/create_admin", methods=["POST"])
def create_admin():

    if "admin" not in session:
        return redirect("/")

    username = request.form.get("username")
    password = request.form.get("password")

    can_students = 1 if request.form.get("students") else 0
    can_candidates = 1 if request.form.get("candidates") else 0
    can_results = 1 if request.form.get("results") else 0
    can_settings = 1 if request.form.get("settings") else 0

    hashed = generate_password_hash(password)

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO admins(
            username,
            password,
            can_manage_students,
            can_manage_candidates,
            can_manage_results,
            can_manage_settings
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        username,
        hashed,
        can_students,
        can_candidates,
        can_results,
        can_settings
    ))

    conn.commit()
    conn.close()

    flash("Admin created successfully")

    return redirect("/dashboard")



@app.route("/admin_login", methods=["POST"])
def admin_login():

    username = request.form.get("username")
    password = request.form.get("password")

    conn = db()
    cur = conn.cursor()

    admin = cur.execute("""
        SELECT *
        FROM admins
        WHERE username=?
    """, (username,)).fetchone()

    conn.close()

    if admin and check_password_hash(admin[2], password):

        session["admin"] = username

        session["permissions"] = {
            "students": admin[3],
            "candidates": admin[4],
            "results": admin[5],
            "settings": admin[6]
        }

        return redirect("/dashboard")

    flash("Invalid admin login")

    return redirect("/")



@app.route("/delete_student/<sid>")
def delete_student(sid):

    if "admin" not in session:
        return redirect("/")

    conn = db()

    # delete votes first
    conn.execute("""
        DELETE FROM votes
        WHERE student_id=?
    """, (sid,))

    # delete student
    conn.execute("""
        DELETE FROM students
        WHERE student_id=?
    """, (sid,))

    conn.commit()
    conn.close()

    flash("Student deleted successfully")

    return redirect("/dashboard")

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
)