#!/usr/bin/env python3
"""
MediOps backend — Smart Hospital Dashboards (Project P7)

Stdlib only (http.server + sqlite3). Implements the star-schema data model,
computes KPIs from fact_events, enforces role-based drill-down + de-identification
(small-cell suppression), generates an HMIS-style monthly report, and records an
access audit for every view/export.

Run:  python3 server.py   ->  http://localhost:4173
The DB is rebuilt and re-seeded deterministically on every startup (demo).
"""

import json
import os
import random
import sqlite3
import hashlib
from datetime import datetime, timedelta, date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "mediops.db")
PORT = int(os.environ.get("PORT", "4173"))

# "As of" clock — fixed so KPIs are stable in the demo.
NOW = datetime(2026, 7, 18, 9, 0, 0)
TODAY = NOW.date()

# ---------------------------------------------------------------------------
# Roles  (drives FR-3 scoping + FR-10 de-identification gating)
#   level:  full  -> all wards, may reveal identified data
#           unit  -> single ward scope, may reveal within scope
#           deid  -> all wards, identified reveal ALWAYS denied
# ---------------------------------------------------------------------------
ROLES = {
    "superintendent": {
        "user": "Dr. A. Rao", "title": "Medical Superintendent",
        "level": "full", "scope": None,
        "can_reveal": True, "can_report": True, "can_audit": True,
    },
    "dept_head": {
        "user": "Dr. S. Nair", "title": "Department Head — ICU",
        "level": "unit", "scope": "ICU",
        "can_reveal": True, "can_report": False, "can_audit": False,
    },
    "dpo": {
        "user": "P. Menon", "title": "Data Protection Officer",
        "level": "deid", "scope": None,
        "can_reveal": False, "can_report": False, "can_audit": True,
    },
}

WARDS = [
    ("ICU", "Critical Care", 20),
    ("Ward 2A", "General Medicine", 40),
    ("Ward 3B", "Surgery", 40),
    ("Pediatrics", "Pediatrics", 30),
    ("General", "General Medicine", 154),
    ("OT / Recovery", "Surgery", 16),
]
PAYERS = ["Cash", "Insurance", "PMJAY", "Other"]
DOCTORS = ["Dr. Iyer", "Dr. Khan", "Dr. Reddy", "Dr. Bose", "Dr. Pillai", "Dr. Shah"]
FIRST = ["Aarav", "Vivaan", "Aditya", "Diya", "Ananya", "Ishaan", "Kabir", "Meera",
         "Rohan", "Saanvi", "Arjun", "Riya", "Kavya", "Neha", "Farah", "Zoya",
         "Rahul", "Priya", "Sameer", "Tara", "Nikhil", "Anjali", "Vikram", "Pooja"]
LAST = ["Sharma", "Verma", "Nair", "Menon", "Reddy", "Rao", "Iyer", "Khan",
        "Bose", "Das", "Gupta", "Shah", "Pillai", "Fernandes", "Joshi", "Naidu"]

# target occupied beds per ward (point-in-time)
OCCUPIED = {"ICU": 18, "Ward 2A": 34, "Ward 3B": 38, "Pediatrics": 22,
            "General": 128, "OT / Recovery": 9}


def pseudo(uhid: str) -> str:
    return "PT-" + hashlib.sha1(uhid.encode()).hexdigest()[:6].upper()


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = db()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE dim_ward (
        ward_key INTEGER PRIMARY KEY, ward_name TEXT, department TEXT, bed_capacity INTEGER
    );
    CREATE TABLE dim_role (
        role_key TEXT PRIMARY KEY, role_name TEXT, permission_level TEXT, ward_scope TEXT
    );
    CREATE TABLE fact_events (
        event_id INTEGER PRIMARY KEY,
        episode_id TEXT,
        event_type TEXT,               -- admission/discharge/transfer/ED_registration/doctor_consult
        ward_key INTEGER,
        patient_pseudo_id TEXT,        -- de-identified token
        patient_name TEXT,             -- identified (gated)
        patient_uhid TEXT,             -- identified (gated)
        payer_type TEXT,
        doctor TEXT,
        event_timestamp TEXT
    );
    CREATE TABLE audit_log (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, user TEXT, role TEXT, action TEXT, target TEXT, detail TEXT
    );
    CREATE TABLE reports_generated (
        report_id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_type TEXT, period TEXT, status TEXT,
        generated_at TEXT, generated_by TEXT, submitted_at TEXT, submitted_by TEXT,
        payload_json TEXT
    );
    """)

    ward_key = {}
    for i, (name, dept, cap) in enumerate(WARDS, start=1):
        ward_key[name] = i
        c.execute("INSERT INTO dim_ward VALUES (?,?,?,?)", (i, name, dept, cap))
    for rk, r in ROLES.items():
        c.execute("INSERT INTO dim_role VALUES (?,?,?,?)",
                  (rk, r["title"], r["level"], r["scope"] or "ALL"))

    rnd = random.Random(7)
    events = []
    eid = [0]
    uhid_seq = [100000]

    def new_patient():
        uhid_seq[0] += rnd.randint(1, 4)
        uhid = f"UHID-{uhid_seq[0]}"
        name = f"{rnd.choice(FIRST)} {rnd.choice(LAST)}"
        return uhid, name, pseudo(uhid)

    def add(ep, etype, ward, uhid, name, ptok, payer, doctor, ts):
        eid[0] += 1
        events.append((eid[0], ep, etype, ward_key[ward], ptok, name, uhid,
                       payer, doctor, ts.strftime("%Y-%m-%dT%H:%M:%S")))

    ep_seq = [0]

    def new_ep():
        ep_seq[0] += 1
        return f"EP-{ep_seq[0]:05d}"

    # 1) Current inpatients (occupied beds, no discharge) — drives occupancy.
    #    ~12% admitted today so "admissions today" is computed, not hardcoded.
    for ward, occ in OCCUPIED.items():
        for _ in range(occ):
            uhid, name, ptok = new_patient()
            payer = rnd.choices(PAYERS, weights=[3, 4, 3, 1])[0]
            if rnd.random() < 0.12:
                adm = NOW - timedelta(hours=rnd.randint(1, 8))          # today
            else:
                adm = NOW - timedelta(days=rnd.randint(1, 14), hours=rnd.randint(0, 23))
            ep = new_ep()
            add(ep, "admission", ward, uhid, name, ptok, payer, rnd.choice(DOCTORS), adm)

    # 2) Discharged episodes over the last 30 days — drives ALOS + discharges.
    for _ in range(190):
        ward = rnd.choices([w[0] for w in WARDS], weights=[2, 4, 4, 3, 8, 2])[0]
        uhid, name, ptok = new_patient()
        payer = rnd.choices(PAYERS, weights=[3, 4, 3, 1])[0]
        disch = NOW - timedelta(days=rnd.randint(0, 29), hours=rnd.randint(0, 23))
        los = rnd.randint(1, 11)
        adm = disch - timedelta(days=los)
        ep = new_ep()
        doc = rnd.choice(DOCTORS)
        add(ep, "admission", ward, uhid, name, ptok, payer, doc, adm)
        add(ep, "discharge", ward, uhid, name, ptok, payer, doc, disch)

    # 3) ED registrations + first doctor consult — drives door-to-doctor.
    for _ in range(60):
        ward = rnd.choice(["ICU", "Ward 2A", "Ward 3B", "General"])
        uhid, name, ptok = new_patient()
        payer = rnd.choices(PAYERS, weights=[4, 3, 3, 1])[0]
        if rnd.random() < 0.5:
            reg = NOW - timedelta(hours=rnd.randint(0, 8), minutes=rnd.randint(0, 59))  # today
        else:
            reg = NOW - timedelta(days=rnd.randint(1, 20), hours=rnd.randint(0, 23))
        wait = rnd.randint(6, 70)
        ep = new_ep()
        doc = rnd.choice(DOCTORS)
        add(ep, "ED_registration", ward, uhid, name, ptok, payer, doc, reg)
        add(ep, "doctor_consult", ward, uhid, name, ptok, payer, doc, reg + timedelta(minutes=wait))

    c.executemany(
        "INSERT INTO fact_events (event_id,episode_id,event_type,ward_key,"
        "patient_pseudo_id,patient_name,patient_uhid,payer_type,doctor,event_timestamp)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)", events)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Audit helper
# ---------------------------------------------------------------------------
def audit(conn, role_key, action, target, detail=""):
    r = ROLES.get(role_key, {"user": "unknown"})
    conn.execute(
        "INSERT INTO audit_log (ts,user,role,action,target,detail) VALUES (?,?,?,?,?,?)",
        (datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
         r["user"], role_key, action, target, detail))
    conn.commit()


# ---------------------------------------------------------------------------
# KPI computation (all derived from fact_events)
# ---------------------------------------------------------------------------
def load_events(conn):
    rows = conn.execute(
        "SELECT f.*, w.ward_name, w.bed_capacity FROM fact_events f "
        "JOIN dim_ward w ON f.ward_key = w.ward_key").fetchall()
    return [dict(r) for r in rows]


def compute_kpis(conn, scope_ward=None):
    evs = load_events(conn)
    if scope_ward:
        evs = [e for e in evs if e["ward_name"] == scope_ward]

    def ts(e):
        return datetime.strptime(e["event_timestamp"], "%Y-%m-%dT%H:%M:%S")

    # episodes with an admission and no discharge = active inpatients
    disch_eps = {e["episode_id"] for e in evs if e["event_type"] == "discharge"}
    adm_eps = [e for e in evs if e["event_type"] == "admission"]
    active = [e for e in adm_eps if e["episode_id"] not in disch_eps]
    active_count = len(active)

    if scope_ward:
        cap = next((w[2] for w in WARDS if w[0] == scope_ward), 0)
    else:
        cap = sum(w[2] for w in WARDS)
    occupancy = round(active_count / cap * 100, 1) if cap else 0

    adm_today = [e for e in adm_eps if ts(e).date() == TODAY]
    disch_events = [e for e in evs if e["event_type"] == "discharge"]
    disch_today = [e for e in disch_events if ts(e).date() == TODAY]

    # ALOS (30d): pair admission+discharge by episode
    adm_by_ep = {e["episode_id"]: ts(e) for e in adm_eps}
    los_days = []
    cutoff = NOW - timedelta(days=30)
    for d in disch_events:
        if ts(d) >= cutoff and d["episode_id"] in adm_by_ep:
            los_days.append((ts(d) - adm_by_ep[d["episode_id"]]).total_seconds() / 86400)
    alos = round(sum(los_days) / len(los_days), 1) if los_days else 0

    # Door-to-doctor (today): first consult after ED registration
    reg = {e["episode_id"]: ts(e) for e in evs if e["event_type"] == "ED_registration"}
    con = {}
    for e in evs:
        if e["event_type"] == "doctor_consult":
            con.setdefault(e["episode_id"], ts(e))
    waits = []
    for ep, rts in reg.items():
        if rts.date() == TODAY and ep in con:
            waits.append((con[ep] - rts).total_seconds() / 60)
    d2d = round(sum(waits) / len(waits)) if waits else 0

    kpis = [
        {"key": "occupancy", "label": "Bed Occupancy", "value": occupancy, "unit": "%",
         "sub": f"{active_count} / {cap} beds", "tone": "warn" if occupancy >= 85 else "ok"},
        {"key": "active", "label": "Active Inpatients", "value": active_count, "unit": "",
         "sub": "currently admitted", "tone": "neutral"},
        {"key": "adm_today", "label": "Admissions · Today", "value": len(adm_today), "unit": "",
         "sub": TODAY.strftime("%d %b %Y"), "tone": "neutral"},
        {"key": "disch_today", "label": "Discharges · Today", "value": len(disch_today), "unit": "",
         "sub": TODAY.strftime("%d %b %Y"), "tone": "neutral"},
        {"key": "alos", "label": "Avg Length of Stay", "value": alos, "unit": "d",
         "sub": "rolling 30 days", "tone": "neutral"},
        {"key": "d2d", "label": "Avg Door-to-Doctor", "value": d2d, "unit": "min",
         "sub": "ED · today", "tone": "warn" if d2d >= 40 else "ok"},
    ]

    # Occupancy by ward
    ward_occ = []
    for name, dept, cap_w in WARDS:
        if scope_ward and name != scope_ward:
            continue
        a = len([e for e in active if e["ward_name"] == name])
        ward_occ.append({"ward": name, "occ": a, "cap": cap_w,
                         "pct": round(a / cap_w * 100) if cap_w else 0})

    # Case mix (30d) discharges by ward x payer, with <5 small-cell suppression (FR-10)
    matrix = {}
    for d in disch_events:
        if ts(d) >= cutoff:
            matrix.setdefault(d["ward_name"], {p: 0 for p in PAYERS})
            matrix[d["ward_name"]][d["payer_type"]] += 1
    casemix = []
    for name, dept, cap_w in WARDS:
        if scope_ward and name != scope_ward:
            continue
        row = matrix.get(name, {p: 0 for p in PAYERS})
        cells = []
        for p in PAYERS:
            v = row[p]
            cells.append("—" if 0 < v < 5 else (v if v >= 5 else 0))
        casemix.append({"ward": name, "cells": cells})

    return {"kpis": kpis, "wardOccupancy": ward_occ,
            "caseMix": {"payers": PAYERS, "rows": casemix},
            "asOf": NOW.strftime("%Y-%m-%dT%H:%M:%S")}


# metric -> which events feed a drill-down
def drilldown_rows(conn, metric, scope_ward, ward_filter):
    evs = load_events(conn)

    def ts(e):
        return datetime.strptime(e["event_timestamp"], "%Y-%m-%dT%H:%M:%S")

    disch_eps = {e["episode_id"] for e in evs if e["event_type"] == "discharge"}
    if metric == "active" or metric == "occupancy":
        rows = [e for e in evs if e["event_type"] == "admission" and e["episode_id"] not in disch_eps]
    elif metric == "adm_today":
        rows = [e for e in evs if e["event_type"] == "admission" and ts(e).date() == TODAY]
    elif metric == "disch_today":
        rows = [e for e in evs if e["event_type"] == "discharge" and ts(e).date() == TODAY]
    elif metric == "alos":
        cutoff = NOW - timedelta(days=30)
        rows = [e for e in evs if e["event_type"] == "discharge" and ts(e) >= cutoff]
    elif metric == "d2d":
        rows = [e for e in evs if e["event_type"] == "ED_registration" and ts(e).date() == TODAY]
    else:
        rows = [e for e in evs if e["event_type"] == "admission" and e["episode_id"] not in disch_eps]

    if scope_ward:
        rows = [e for e in rows if e["ward_name"] == scope_ward]
    if ward_filter and ward_filter != "ALL":
        rows = [e for e in rows if e["ward_name"] == ward_filter]
    rows.sort(key=lambda e: e["event_timestamp"], reverse=True)
    return rows


def build_hmis(conn):
    k = compute_kpis(conn)
    kv = {x["key"]: x["value"] for x in k["kpis"]}
    evs = load_events(conn)

    def ts(e):
        return datetime.strptime(e["event_timestamp"], "%Y-%m-%dT%H:%M:%S")

    month_start = date(NOW.year, NOW.month, 1)
    adm_month = len([e for e in evs if e["event_type"] == "admission" and ts(e).date() >= month_start])
    disch_month = len([e for e in evs if e["event_type"] == "discharge" and ts(e).date() >= month_start])
    ed_month = len([e for e in evs if e["event_type"] == "ED_registration" and ts(e).date() >= month_start])
    rows = [
        ["M1.1", "Total inpatient admissions (MTD)", adm_month],
        ["M1.2", "Total discharges (MTD)", disch_month],
        ["M2.1", "Total ED registrations (MTD)", ed_month],
        ["M3.1", "Bed occupancy rate (point-in-time)", f"{kv['occupancy']} %"],
        ["M3.2", "Average length of stay", f"{kv['alos']} days"],
        ["M4.1", "Average door-to-doctor time", f"{kv['d2d']} min"],
        ["M5.1", "Active inpatients (census)", kv["active"]],
    ]
    return {"columns": ["HMIS Code", "Indicator", "Value"], "rows": rows,
            "period": NOW.strftime("%B %Y"), "format": "HMIS Monthly (NHM)"}


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _role(self, q):
        rk = (q.get("role", ["superintendent"])[0])
        return rk if rk in ROLES else "superintendent"

    # ------- GET -------
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/api/roles":
            return self._json({"roles": [
                {"key": k, "user": v["user"], "title": v["title"], "level": v["level"],
                 "scope": v["scope"], "canReveal": v["can_reveal"],
                 "canReport": v["can_report"], "canAudit": v["can_audit"]}
                for k, v in ROLES.items()]})

        if u.path == "/api/kpis":
            rk = self._role(q)
            r = ROLES[rk]
            conn = db()
            data = compute_kpis(conn, scope_ward=r["scope"])
            data["role"] = {"key": rk, **{kk: r[kk] for kk in
                            ("user", "title", "level", "scope")},
                            "canReveal": r["can_reveal"], "canReport": r["can_report"],
                            "canAudit": r["can_audit"]}
            audit(conn, rk, "VIEW_DASHBOARD", "KPI overview",
                  f"scope={r['scope'] or 'ALL wards'}")
            conn.close()
            return self._json(data)

        if u.path == "/api/drilldown":
            rk = self._role(q)
            r = ROLES[rk]
            metric = q.get("metric", ["active"])[0]
            reveal = q.get("reveal", ["0"])[0] == "1"
            ward_filter = q.get("ward", ["ALL"])[0]
            conn = db()
            rows = drilldown_rows(conn, metric, r["scope"], ward_filter)
            # de-identification gate
            allow_identified = reveal and r["can_reveal"]
            denied = reveal and not r["can_reveal"]
            out = []
            for e in rows[:200]:
                item = {"episode": e["episode_id"], "type": e["event_type"],
                        "ward": e["ward_name"], "payer": e["payer_type"],
                        "when": e["event_timestamp"], "token": e["patient_pseudo_id"]}
                if allow_identified:
                    item["name"] = e["patient_name"]
                    item["uhid"] = e["patient_uhid"]
                out.append(item)
            detail = ("identified (revealed)" if allow_identified
                      else ("reveal DENIED — insufficient permission" if denied
                            else "de-identified"))
            action = "REVEAL_ATTEMPT_DENIED" if denied else "DRILL_DOWN"
            audit(conn, rk, action, f"{metric} · {ward_filter}", detail)
            conn.close()
            return self._json({"rows": out, "identified": allow_identified,
                               "denied": denied, "count": len(rows),
                               "shown": len(out)})

        if u.path == "/api/audit":
            rk = self._role(q)
            r = ROLES[rk]
            conn = db()
            if not r["can_audit"]:
                audit(conn, rk, "VIEW_AUDIT_DENIED", "audit log", "insufficient permission")
                conn.close()
                return self._json({"error": "forbidden", "rows": []}, 403)
            audit(conn, rk, "VIEW_AUDIT", "audit log", "")
            rows = conn.execute(
                "SELECT ts,user,role,action,target,detail FROM audit_log "
                "ORDER BY log_id DESC LIMIT 200").fetchall()
            conn.close()
            return self._json({"rows": [dict(x) for x in rows]})

        # static files
        return self._static(u.path)

    # ------- POST -------
    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(body or b"{}")
        except Exception:
            payload = {}

        if u.path == "/api/log":
            # client-side action logging (e.g. toggle wall mode, export)
            rk = self._role(q)
            conn = db()
            audit(conn, rk, payload.get("action", "ACTION"),
                  payload.get("target", ""), payload.get("detail", ""))
            conn.close()
            return self._json({"ok": True})

        if u.path == "/api/report/generate":
            rk = self._role(q)
            r = ROLES[rk]
            conn = db()
            if not r["can_report"]:
                audit(conn, rk, "GENERATE_REPORT_DENIED", "HMIS monthly", "insufficient permission")
                conn.close()
                return self._json({"error": "forbidden"}, 403)
            rep = build_hmis(conn)
            cur = conn.execute(
                "INSERT INTO reports_generated (report_type,period,status,generated_at,"
                "generated_by,payload_json) VALUES (?,?,?,?,?,?)",
                ("HMIS Monthly", rep["period"], "draft",
                 datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), r["user"],
                 json.dumps(rep)))
            conn.commit()
            rid = cur.lastrowid
            audit(conn, rk, "GENERATE_REPORT", f"HMIS Monthly · {rep['period']}", "status=draft")
            conn.close()
            rep["reportId"] = rid
            rep["status"] = "draft"
            return self._json(rep)

        if u.path == "/api/report/submit":
            rk = self._role(q)
            r = ROLES[rk]
            conn = db()
            if not r["can_report"]:
                conn.close()
                return self._json({"error": "forbidden"}, 403)
            rid = payload.get("reportId")
            conn.execute(
                "UPDATE reports_generated SET status='submitted', submitted_at=?, "
                "submitted_by=? WHERE report_id=?",
                (datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), r["user"], rid))
            conn.commit()
            audit(conn, rk, "SUBMIT_REPORT", f"report #{rid}",
                  "human review-and-submit (statutory accountability)")
            conn.close()
            return self._json({"ok": True, "reportId": rid, "status": "submitted"})

        return self._json({"error": "not found"}, 404)

    # ------- static -------
    def _static(self, path):
        if path == "/" or path == "":
            path = "/index.html"
        path = path.split("?")[0]
        safe = os.path.normpath(path).lstrip("/\\")
        full = os.path.join(HERE, safe)
        if not full.startswith(HERE) or not os.path.isfile(full):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return
        ctype = {
            ".html": "text/html", ".css": "text/css", ".js": "application/javascript",
            ".json": "application/json", ".svg": "image/svg+xml",
        }.get(os.path.splitext(full)[1], "application/octet-stream")
        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    init_db()
    ThreadingHTTPServer.allow_reuse_address = True
    try:
        srv = ThreadingHTTPServer(("", PORT), H)
    except OSError as e:
        if e.errno in (48, 98):  # address already in use (macOS / Linux)
            print(f"\n  Port {PORT} is already in use.")
            print(f"  Something else (maybe an old MediOps) is running there.\n")
            print(f"  Free it:   lsof -ti tcp:{PORT} | xargs kill")
            print(f"  Or pick another port:   PORT=4180 python3 server.py\n")
            raise SystemExit(1)
        raise
    print(f"MediOps backend on http://localhost:{PORT}  (db reseeded)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
