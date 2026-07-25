"""
P7 Smart Hospital Dashboards — Walking Skeleton (M2)
Boots, loads seed data into SQLite on first run, and runs ONE real
end-to-end flow: login (stub) -> role dashboard -> occupancy KPI tile
computed live from fact_events -> audit_log row written on view.

Everything else in API_ROUTES.md is present as a route stub only.
"""
import csv
import os
import sqlite3
from datetime import datetime
from flask import Flask, session, redirect, url_for, render_template, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dashboards.db")
DATA_DIR = os.path.join(BASE_DIR, "data")

app = Flask(__name__)
app.secret_key = "dev-only-not-for-production"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create schema + load seed CSVs, only if the DB doesn't exist yet."""
    fresh = not os.path.exists(DB_PATH)
    conn = get_db()
    if fresh:
        with open(os.path.join(BASE_DIR, "schema.sql")) as f:
            conn.executescript(f.read())
        _load_csv(conn, "dim_ward.csv", "dim_ward",
                  ["ward_key", "ward_name", "department", "bed_capacity"])
        _load_csv(conn, "dim_payer.csv", "dim_payer", ["payer_key", "payer_type"])
        _load_csv(conn, "dim_role.csv", "dim_role",
                  ["role_key", "role_name", "permission_level"])
        _load_csv(conn, "users.csv", "users",
                  ["user_id", "username", "role_key", "ward_key"], allow_null_last=True)
        _load_csv(conn, "dim_date.csv", "dim_date",
                  ["date_key", "date", "day_of_week", "month", "year"])
        _load_csv(conn, "fact_events.csv", "fact_events",
                  ["event_id", "date_key", "ward_key", "payer_key",
                   "patient_pseudo_id", "event_type", "event_timestamp"])
        conn.commit()
        print("Initialised dashboards.db from schema.sql + seed CSVs.")
    conn.close()


def _load_csv(conn, filename, table, columns, allow_null_last=False):
    path = os.path.join(DATA_DIR, filename)
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            vals = [row[c] if row[c] != "" else None for c in columns]
            rows.append(vals)
    placeholders = ",".join("?" for _ in columns)
    conn.executemany(
        f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})", rows
    )


def log_audit(user_id, role, action, target):
    conn = get_db()
    conn.execute(
        "INSERT INTO audit_log (user_id, role, action, target, timestamp) VALUES (?,?,?,?,?)",
        (user_id, role, action, target, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():
    """Stub auth: pick a seeded user by username, no password check (demo only)."""
    username = request.form.get("username")
    conn = get_db()
    user = conn.execute(
        "SELECT u.user_id, u.username, u.ward_key, r.role_name, r.permission_level "
        "FROM users u JOIN dim_role r ON u.role_key = r.role_key "
        "WHERE u.username = ?", (username,),
    ).fetchone()
    conn.close()
    if not user:
        return render_template("login.html", error="Unknown demo user. Try dr_mehta or dr_rao.")
    session["user_id"] = user["user_id"]
    session["username"] = user["username"]
    session["role_name"] = user["role_name"]
    session["permission_level"] = user["permission_level"]
    session["ward_key"] = user["ward_key"]
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/dashboard")
def dashboard():
    """
    REAL end-to-end flow for M2:
    - scoped to user's ward if role permission_level == 'scoped'
    - occupancy % computed live from fact_events (admissions - discharges)
    - writes an audit_log row on every view (FR-14)
    """
    if "user_id" not in session:
        return redirect(url_for("index"))

    conn = get_db()
    ward_filter = ""
    params = []
    if session["permission_level"] == "scoped" and session["ward_key"]:
        ward_filter = "WHERE w.ward_key = ?"
        params.append(session["ward_key"])

    wards = conn.execute(
        f"SELECT w.ward_key, w.ward_name, w.department, w.bed_capacity "
        f"FROM dim_ward w {ward_filter}", params,
    ).fetchall()

    tiles = []
    for ward in wards:
        admissions = conn.execute(
            "SELECT COUNT(*) FROM fact_events WHERE ward_key=? AND event_type='admission'",
            (ward["ward_key"],),
        ).fetchone()[0]
        discharges = conn.execute(
            "SELECT COUNT(*) FROM fact_events WHERE ward_key=? AND event_type='discharge'",
            (ward["ward_key"],),
        ).fetchone()[0]
        occupied = max(admissions - discharges, 0)
        occupancy_pct = round(
            min(occupied, ward["bed_capacity"]) / ward["bed_capacity"] * 100, 1
        )
        tiles.append({
            "ward_name": ward["ward_name"],
            "department": ward["department"],
            "occupancy_pct": occupancy_pct,
            "admissions": admissions,
            "discharges": discharges,
        })
    conn.close()

    log_audit(session["user_id"], session["role_name"], "view_dashboard",
              f"ward_scope={session.get('ward_key') or 'ALL'}")

    return render_template("dashboard.html", tiles=tiles, role=session["role_name"],
                            username=session["username"])


# ---- Route stubs only (built out in M3) — see API_ROUTES.md ----

@app.route("/reports/hmis")
def reports_hmis_stub():
    return "STUB — FR-5 HMIS report preview. Build in M3.", 200


@app.route("/digest/preview")
def digest_preview_stub():
    return "STUB — FR-7 digest preview. Build in M3.", 200


@app.route("/audit")
def audit_stub():
    return "STUB — FR-14 audit log view. Build in M3.", 200


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
