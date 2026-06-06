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

from datetime import datetime

app = Flask(__name__)
app.secret_key = "secure"

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def db():

    return sqlite3.connect("database.db")


def init():

    conn = db()
    c = conn.cursor()

    # STUDENTS
    c.execute("""
    CREATE TABLE IF NOT EXISTS students(
        student_id TEXT PRIMARY KEY,
        name TEXT,
        has_voted INTEGER DEFAULT 0
    )
    """)

    # PORTFOLIOS
    c.execute("""
    CREATE TABLE IF NOT EXISTS portfolios(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT
    )
    """)

    # CANDIDATES
    c.execute("""
    CREATE TABLE IF NOT EXISTS candidates(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        portfolio_id INTEGER,
        image TEXT
    )
    """)

    # VOTES
    c.execute("""
    CREATE TABLE IF NOT EXISTS votes(
        student_id TEXT,
        candidate_id INTEGER,
        portfolio_id INTEGER
    )
    """)

    # SETTINGS
    c.execute("""
    CREATE TABLE IF NOT EXISTS settings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        school_name TEXT,
        election_year TEXT,
        logo TEXT,
        start_time TEXT,
        end_time TEXT
    )
    """)

    # ARCHIVED VOTES
    c.execute("""
    CREATE TABLE IF NOT EXISTS archived_votes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        candidate_id INTEGER,
        portfolio_id INTEGER,
        archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # RESET LOGS
    c.execute("""
    CREATE TABLE IF NOT EXISTS reset_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin TEXT,
        action TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # GROUPS
    c.execute("""
    CREATE TABLE IF NOT EXISTS groups(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_name TEXT UNIQUE
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS admins(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        students_permission INTEGER DEFAULT 1,
        candidates_permission INTEGER DEFAULT 1,
        results_permission INTEGER DEFAULT 1,
        settings_permission INTEGER DEFAULT 1
    )
    """)
    try:
        c.execute("""
            ALTER TABLE admins
            ADD COLUMN students_permission INTEGER DEFAULT 1
        """)
    except:
        pass

    try:
        c.execute("""
            ALTER TABLE admins
            ADD COLUMN candidates_permission INTEGER DEFAULT 1
        """)
    except:
        pass

    try:
        c.execute("""
            ALTER TABLE admins
            ADD COLUMN results_permission INTEGER DEFAULT 1
        """)
    except:
        pass

    try:
        c.execute("""
            ALTER TABLE admins
            ADD COLUMN settings_permission INTEGER DEFAULT 1
        """)
    except:
            pass

    admin_exists = c.execute("""
    SELECT id
    FROM admins
    LIMIT 1
    """).fetchone()

    if not admin_exists:

        c.execute("""
        INSERT INTO admins(
            username,
            password
        )
        VALUES (?, ?)
        """, (
            "admin",
            "Fred@_1993"
        ))

    # Add group_id to students
    try:
        c.execute("""
            ALTER TABLE students
            ADD COLUMN group_id INTEGER
        """)
    except:
        pass


    try:
        c.execute("""
        ALTER TABLE students
        ADD COLUMN group_name TEXT
    """)
    except:
        pass

    # Add group_id to portfolios
    try:
        c.execute("""
            ALTER TABLE portfolios
            ADD COLUMN group_id INTEGER
        """)
    except:
        pass

    try:
        c.execute("""
        ALTER TABLE portfolios
        ADD COLUMN is_global INTEGER DEFAULT 0
    """)
    except:
        pass

  

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

@app.route("/admin", methods=["POST"])
def admin():

    username = request.form.get("username")
    password = request.form.get("password")

    conn = db()

    admin = conn.execute("""
        SELECT *
        FROM admins
        WHERE username=?
        AND password=?
    """, (
        username,
        password
    )).fetchone()

    conn.close()

    if admin:

        session["admin"] = True
        session["username"] = username
        session["admin_id"] = admin[0]

        session["students_permission"] = admin[7]
        session["candidates_permission"] = admin[8]
        session["results_permission"] = admin[9]
        session["settings_permission"] = admin[10]


        flash("Login successful")

        return redirect("/dashboard")

    flash("Invalid username or password")

    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ================= GROUPS =================

@app.route("/add_group", methods=["POST"])
def add_group():

    if "admin" not in session:
        return redirect("/")

    group_name = request.form.get("group_name")

    if not group_name:
        flash("Group name is required")
        return redirect("/dashboard?section=groups")

    conn = db()

    try:

        conn.execute("""
            INSERT INTO groups(group_name)
            VALUES (?)
        """, (group_name,))

        conn.commit()

        flash("Group created successfully")

    except:

        flash("Group already exists")

    conn.close()

    return redirect("/dashboard?section=groups")


@app.route("/delete_group/<int:gid>")
def delete_group(gid):

    if "admin" not in session:
        return redirect("/")

    conn = db()

    student_count = conn.execute("""
        SELECT COUNT(*)
        FROM students
        WHERE group_id=?
    """, (gid,)).fetchone()[0]

    if student_count > 0:

        conn.close()

        flash(
            "Cannot delete house. Students are assigned to it."
        )

        return redirect("/dashboard?section=groups")

    portfolio_count = conn.execute("""
        SELECT COUNT(*)
        FROM portfolios
        WHERE group_id=?
    """, (gid,)).fetchone()[0]

    if portfolio_count > 0:

        conn.close()

        flash(
            "Cannot delete house. Portfolios are assigned to it."
        )

        return redirect("/dashboard?section=groups")
    conn.execute("""
        DELETE FROM groups
        WHERE id=?
    """, (gid,))

    conn.commit()
    conn.close()

    flash("House deleted successfully")

    return redirect("/dashboard?section=groups")

@app.route("/edit_group/<int:gid>", methods=["POST"])
def edit_group(gid):

    if "admin" not in session:
        return redirect("/")

    group_name = request.form.get("group_name")

    conn = db()

    conn.execute("""
        UPDATE groups
        SET group_name=?
        WHERE id=?
    """, (group_name, gid))

    conn.commit()
    conn.close()

    flash("House updated successfully")

    return redirect("/dashboard?section=groups")


@app.route("/assign_portfolio/<int:pid>", methods=["POST"])
def assign_portfolio(pid):

    if "admin" not in session:
        return redirect("/")

    assignment_type = request.form.get(
        "assignment_type"
    )

    group_id = request.form.get(
        "group_id"
    )

    conn = db()

    if assignment_type == "global":

        conn.execute("""
            UPDATE portfolios
            SET is_global=1,
                group_id=NULL
            WHERE id=?
        """, (pid,))

    else:

        conn.execute("""
            UPDATE portfolios
            SET is_global=0,
                group_id=?
            WHERE id=?
        """, (
            group_id,
            pid
        ))

    conn.commit()
    conn.close()

    flash(
        "Portfolio assignment updated"
    )

    return redirect("/dashboard?section=portfolios")


# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():

    if "admin" not in session:
        return redirect("/")

    conn = db()

    portfolios = conn.execute("""
    SELECT
        portfolios.*,
        groups.group_name
    FROM portfolios
    LEFT JOIN groups
    ON portfolios.group_id = groups.id
    ORDER BY portfolios.name
""").fetchall()
    
    global_portfolios = []
    house_portfolios = []

    for p in portfolios:

        if p[3] == 1:

            global_portfolios.append(p)

        else:

            house_portfolios.append(p)


    candidates = conn.execute("""
        SELECT
            candidates.*,
            portfolios.name,
            portfolios.is_global,
            groups.group_name
        FROM candidates
        JOIN portfolios
            ON portfolios.id = candidates.portfolio_id
        LEFT JOIN groups
            ON portfolios.group_id = groups.id
        ORDER BY portfolios.name,
                candidates.name
    """).fetchall()

    import sys

    print("\n====================")
    print("TOTAL CANDIDATES:", len(candidates))

    for c in candidates:
        print(c)

    print("====================\n")
    sys.stdout.flush()       

    global_candidate_groups = {}
    house_candidate_groups = {}

    for c in candidates:

        portfolio_name = c[4]

        if c[5] == 1:

            if portfolio_name not in global_candidate_groups:
                global_candidate_groups[portfolio_name] = []

            global_candidate_groups[portfolio_name].append(c)

        else:

            if portfolio_name not in house_candidate_groups:
                house_candidate_groups[portfolio_name] = []

            house_candidate_groups[portfolio_name].append(c)


    students = conn.execute("""
        SELECT
            students.*,
            groups.group_name
        FROM students
        LEFT JOIN groups
        ON students.group_id = groups.id
    """).fetchall()

    groups = conn.execute("""
    SELECT *
    FROM groups
    ORDER BY group_name
    """).fetchall()

    house_stats = []

    for g in groups:

        total = conn.execute("""
            SELECT COUNT(*)
            FROM students
            WHERE group_id=?
        """, (g[0],)).fetchone()[0]

        voted = conn.execute("""
            SELECT COUNT(*)
            FROM students
            WHERE group_id=?
            AND has_voted=1
        """, (g[0],)).fetchone()[0]

        not_voted = total - voted

        house_stats.append({
            "house": g[1],
            "total": total,
            "voted": voted,
            "not_voted": not_voted
        })


    total_students = len(students)

    voted_students = conn.execute("""
        SELECT COUNT(*)
        FROM students
        WHERE has_voted=1
    """).fetchone()[0]

    not_voted = total_students - voted_students

    try:

        admins = conn.execute("""
            SELECT *
            FROM admins
            ORDER BY username
        """).fetchall()

        for a in admins:
            print("ADMIN:", a)


    except:

        admins = []

    conn.close()

    section = request.args.get(
        "section",
        "dashboard"
    )

    return render_template(
        "admin.html",
        portfolios=portfolios,
        global_portfolios=global_portfolios,
        house_portfolios=house_portfolios,
        candidates=candidates,
        students=students,
        groups=groups,
        admins=admins,
        total_students=total_students,
        voted_students=voted_students,
        not_voted=not_voted,
        section=section,
        global_candidate_groups=global_candidate_groups,
        house_candidate_groups=house_candidate_groups,
        house_stats=house_stats
    )




@app.route("/add_portfolio", methods=["POST"])
def add_portfolio():

    if "admin" not in session:
        return redirect("/")

    name = request.form.get("name")

    assignment_type = request.form.get(
        "assignment_type"
    )

    group_id = request.form.get(
        "group_id"
    )

    conn = db()

    if assignment_type == "global":

        conn.execute("""
            INSERT INTO portfolios(
                name,
                is_global,
                group_id
            )
            VALUES (?, 1, NULL)
        """, (name,))

    else:

        conn.execute("""
            INSERT INTO portfolios(
                name,
                is_global,
                group_id
            )
            VALUES (?, 0, ?)
        """, (
            name,
            group_id
        ))

    conn.commit()
    conn.close()




    flash(
        "Portfolio added successfully"
    )

    return redirect("/dashboard?section=portfolios")


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

    return redirect("/dashboard?section=portfolios")

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

    return redirect("/dashboard?section=candidates")


@app.route("/upload_students", methods=["POST"])
def upload_students():

    if "admin" not in session:
        return redirect("/")

    file = request.files.get("file")

    if not file or file.filename == "":
        flash("No file selected")
        return redirect("/dashboard?section=students")

    try:

        df = pd.read_excel(file)

        df.columns = [
            col.strip().lower()
            for col in df.columns
        ]

        if (
            "student_id" not in df.columns or
            "name" not in df.columns or
            "group_name" not in df.columns
        ):

            flash(
                "Excel must contain student_id, name and group_name columns"
            )

            return redirect("/dashboard?section=students")

        conn = db()

        inserted = 0

        for _, row in df.iterrows():

            student_id = str(
                row["student_id"]
            ).strip()

            name = str(
                row["name"]
            ).strip()

            group_name = str(
                row["group_name"]
            ).strip()

            if not (
                student_id and
                name and
                group_name
            ):
                continue

            group_row = conn.execute("""
                SELECT id
                FROM groups
                WHERE group_name=?
            """, (
                group_name,
            )).fetchone()

            if not group_row:
                continue

            conn.execute("""
                INSERT OR IGNORE INTO students(
                    student_id,
                    name,
                    has_voted,
                    group_id,
                    group_name
                )
                VALUES (?, ?, 0, ?, ?)
            """, (
                student_id,
                name,
                group_row[0],
                group_name
            ))

            inserted += 1

        conn.commit()
        conn.close()

        flash(
            f"{inserted} students uploaded successfully"
        )

        return redirect("/dashboard?section=students")

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

    student_row = cur.execute("""
        SELECT group_id
        FROM students
        WHERE student_id=?
    """, (
        session["student"],
    )).fetchone()

    if not student_row:

        conn.close()

        return "Student group not found"


    student_group_id = student_row[0]


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
            WHERE is_global=1
            OR group_id=?
        """, (
            student_group_id,
        )).fetchall()

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
        WHERE is_global=1
        OR group_id=?
        ORDER BY name
    """, (
        student_group_id,
    )).fetchall()
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



# ================= RESULTS =================
@app.route("/results")
def results():

    if "admin" not in session:
        return redirect("/")    
    conn = db()

    rows = conn.execute("""
        SELECT
            portfolios.name,
            portfolios.is_global,
            portfolios.group_id,
            candidates.name,
            candidates.image,
            COUNT(votes.rowid) as total_votes
        FROM candidates
        JOIN portfolios
            ON portfolios.id = candidates.portfolio_id
        LEFT JOIN votes
            ON votes.candidate_id = candidates.id
        GROUP BY candidates.id
        ORDER BY portfolios.name, total_votes DESC
    """).fetchall()

    conn.close()

    global_portfolios = {}
    house_portfolios = {}

    for p, is_global, group_id, c, img, v in rows:

        target = (
            global_portfolios
            if is_global == 1
            else house_portfolios
        )

        if p not in target:
            target[p] = []

        target[p].append({
            "name": c,
            "votes": v,
            "image": img
        })


    # percentages
    for collection in [
        global_portfolios,
        house_portfolios
    ]:

        for p in collection:

            total_votes = sum(
                c["votes"]
                for c in collection[p]
            ) or 1

            for c in collection[p]:

                c["percent"] = round(
                    (c["votes"] / total_votes) * 100,
                    1
                )

    return render_template(
        "results.html",
        global_portfolios=global_portfolios,
        house_portfolios=house_portfolios
    )



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
        SELECT
            portfolios.name,
            portfolios.is_global,
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

    global_portfolios = {}
    house_portfolios = {}

    for portfolio, is_global, candidate, votes in rows:

        target = (
            global_portfolios
            if is_global == 1
            else house_portfolios
        )

        if portfolio not in target:

            target[portfolio] = {
                "labels": [],
                "votes": []
            }

        target[portfolio]["labels"].append(
            candidate
        )

        target[portfolio]["votes"].append(
            votes
        )

    return render_template(
        "charts.html",
        global_portfolios=global_portfolios,
        house_portfolios=house_portfolios
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

    return redirect("/dashboard?section=candidates")

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

        return redirect("/dashboard?section=students")

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

    return redirect("/dashboard?section=students")

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

    # SHOW CONFIRM PAGE
    if request.method == "GET":
        return render_template("reset_confirm.html")

    password = request.form.get("password")

    # verify admin password
    if password != "Fred@_1993":
        from flask import flash
        flash("Incorrect admin password")
        return redirect("/reset")

    conn = db()
    cur = conn.cursor()

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
        """, v)

    # =========================
    # LOG RESET ACTION
    # =========================
    cur.execute("""
        INSERT INTO reset_logs(admin, action)
        VALUES (?, ?)
    """, (
        "admin",
        "Full election reset"
    ))

    # =========================
    # DELETE VOTES
    # =========================
    cur.execute("DELETE FROM votes")

    # unlock students
    cur.execute("""
        UPDATE students
        SET has_voted=0
    """)

    conn.commit()
    conn.close()

    from flask import flash
    flash("Election reset completed successfully")

    return redirect("/dashboard?section=dashboard")

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

    return redirect("/dashboard?section=students")

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

    return redirect("/dashboard?section=students")


@app.route("/download_students")
def download_students():

    if "admin" not in session:
        return redirect("/")

    conn = db()

    students = conn.execute("""
        SELECT
            student_id,
            name,
            group_name,
            has_voted
        FROM students
        ORDER BY group_name, name
    """).fetchall()

    conn.close()

    df = pd.DataFrame(
        students,
        columns=[
            "Student ID",
            "Name",
            "House",
            "Has Voted"
        ]
    )
    file_path = "students.xlsx"

    df["Has Voted"] = df["Has Voted"].map({
        1: "YES",
        0: "NO"
    })


    df.to_excel(file_path, index=False)

    return send_file(file_path, as_attachment=True)

@app.route("/voter_register")
def voter_register():

    if "admin" not in session:
        return redirect("/")

    conn = db()

    students = conn.execute("""
        SELECT
            students.student_id,
            students.name,
            students.has_voted,
            groups.group_name
        FROM students
        LEFT JOIN groups
            ON students.group_id = groups.id
        ORDER BY students.name
    """).fetchall()

    conn.close()

    return render_template(
        "voter_register.html",
        students=students
    )
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

    return redirect("/dashboard?section=students")

@app.route(
    "/reset_admin_password/<int:admin_id>",
    methods=["POST"]
)
def reset_admin_password(admin_id):

    if "admin" not in session:
        return redirect("/")

    conn = db()

    conn.execute("""
        UPDATE admins
        SET password=?
        WHERE id=?
    """, (
        "Fred@_1993",
        admin_id
    ))

    conn.commit()
    conn.close()

    flash(
        "Password reset to Fred@_1993"
    )

    return redirect(
        "/dashboard?section=users"
    )

@app.route(
    "/change_admin_password/<int:admin_id>",
    methods=["POST"]
)
def change_admin_password(admin_id):

    if "admin" not in session:
        return redirect("/")

    password = request.form.get(
        "new_password"
    )

    conn = db()

    conn.execute("""
        UPDATE admins
        SET password=?
        WHERE id=?
    """, (
        password,
        admin_id
    ))

    conn.commit()
    conn.close()

    flash(
        "Password updated successfully"
    )

    return redirect(
        "/dashboard?section=users"
    )


@app.route("/add_admin", methods=["POST"])
def add_admin():

    if "admin" not in session:
        return redirect("/")

    username = request.form.get("username")
    password = request.form.get("password")

    students_permission = 1 if request.form.get(
        "students_permission"
    ) else 0

    candidates_permission = 1 if request.form.get(
        "candidates_permission"
    ) else 0

    results_permission = 1 if request.form.get(
        "results_permission"
    ) else 0

    settings_permission = 1 if request.form.get(
        "settings_permission"
    ) else 0


    conn = db()

    try:

        print(
            "PERMISSIONS:",
            students_permission,
            candidates_permission,
            results_permission,
            settings_permission
        )



        conn.execute("""
            INSERT INTO admins(
                username,
                password,
                students_permission,
                candidates_permission,
                results_permission,
                settings_permission
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            username,
            password,
            students_permission,
            candidates_permission,
            results_permission,
            settings_permission
        ))

        conn.commit()

        flash("Admin created successfully")

    except Exception as e:

        print("ADD ADMIN ERROR:", e)

        flash(str(e))

    conn.close()

    return redirect("/dashboard?section=users")

@app.route("/delete_admin/<int:admin_id>")
def delete_admin(admin_id):

    if "admin" not in session:
        return redirect("/")

    if admin_id == session.get("admin_id"):

        flash(
            "You cannot delete your own account"
        )

        return redirect(
            "/dashboard?section=users"
        )

    conn = db()

    total_admins = conn.execute("""
        SELECT COUNT(*)
        FROM admins
    """).fetchone()[0]

    if total_admins <= 1:

        conn.close()

        flash(
            "Cannot delete the last admin"
        )

        return redirect(
            "/dashboard?section=users"
        )

    conn.execute("""
        DELETE FROM admins
        WHERE id=?
    """, (admin_id,))

    conn.commit()
    conn.close()

    flash(
        "Admin deleted successfully"
    )

    return redirect(
        "/dashboard?section=users"
    )

@app.route(
    "/edit_candidate/<int:cid>",
    methods=["GET", "POST"]
)
def edit_candidate(cid):

    if "admin" not in session:
        return redirect("/")

    conn = db()

    if request.method == "POST":

        name = request.form.get("name")
        portfolio_id = request.form.get(
            "portfolio_id"
        )

        file = request.files.get("image")

        if file and file.filename != "":

            filename = file.filename

            file.save(
                os.path.join(
                    UPLOAD_FOLDER,
                    filename
                )
            )

            conn.execute("""
                UPDATE candidates
                SET name=?,
                    portfolio_id=?,
                    image=?
                WHERE id=?
            """, (
                name,
                portfolio_id,
                filename,
                cid
            ))

        else:

            conn.execute("""
                UPDATE candidates
                SET name=?,
                    portfolio_id=?
                WHERE id=?
            """, (
                name,
                portfolio_id,
                cid
            ))

        conn.commit()
        conn.close()

        flash(
            "Candidate updated successfully"
        )

        return redirect(
            "/dashboard?section=candidates"
        )

    candidate = conn.execute("""
        SELECT *
        FROM candidates
        WHERE id=?
    """, (cid,)).fetchone()

    portfolios = conn.execute("""
        SELECT *
        FROM portfolios
        ORDER BY name
    """).fetchall()

    conn.close()

    return render_template(
        "edit_candidate.html",
        candidate=candidate,
        portfolios=portfolios
    )



if __name__ == "__main__":

    init()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )

