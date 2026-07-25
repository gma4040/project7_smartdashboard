# P7 — Smart Hospital Dashboards (PRD-08)

Walking-skeleton repo for M2 (Design Freeze, 12 Jul 2026). Scope: Phase-1,
S-tier FRs only — FR-3, FR-5, FR-7, FR-10, FR-14.

## What works right now (M2 walking skeleton)

- App boots (`python app.py`)
- Login (stub, no password) as any seeded demo user
- Role-scoped dashboard renders occupancy % tiles **computed live** from
  `fact_events` (FR-3)
- Every dashboard view writes a row to `audit_log` (FR-14)
- De-identification is structural by default: no patient name/UHID exists
  anywhere in the schema — only `patient_pseudo_id` (FR-10 baseline)

Everything else (`/reports/hmis`, `/digest/preview`, `/audit` view) is a
route stub returning a placeholder string — these get built out in M3.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open `http://localhost:5000`. Log in as `dr_mehta` (ward-scoped
dept_head) or `dr_rao` (superintendent, full view) to see the difference
in FR-3 scoping.

First run auto-creates `dashboards.db` from `schema.sql` and loads the
seed CSVs in `data/`. Delete `dashboards.db` and re-run to reset.

## Regenerating seed data

```bash
cd data
python generate_seed_data.py
```

Deterministic (`random.seed(42)`) — same output every run, per the
milestone-doc requirement for reproducible demo data.

## Repo structure

```
p7-dashboards/
├── app.py                  # Flask app — walking skeleton
├── schema.sql               # SQLite DDL — star schema + support tables
├── API_ROUTES.md             # full route list (built vs stubbed)
├── requirements.txt
├── data/
│   ├── generate_seed_data.py # deterministic seed generator
│   ├── dim_*.csv              # dimension tables
│   ├── fact_events.csv        # fact table (generated)
│   └── users.csv
├── templates/
│   ├── login.html
│   └── dashboard.html
├── static/style.css
└── wireframes/                # 5 screens, M2 design
    ├── 01_login.svg
    ├── 02_dashboard.svg
    ├── 03_full_view_drilldown.svg
    ├── 04_hmis_report.svg
    └── 05_deidentified_wall_mode.svg
```

## Known gaps (going into M3)

- `/reports/hmis` (FR-5): report compilation + review-and-submit workflow not built
- `/digest/preview` + send (FR-7): digest generation + email/WhatsApp stub not built
- `/audit` (FR-14): audit_log exists and is written to, but no UI to view it yet
- FR-10 identified-view toggle not built (currently de-identified is the
  *only* mode, which satisfies the default but not the permitted-role
  override)
- ALOS and door-to-doctor KPIs: formulas defined (see M1 doc), not yet
  wired into a dashboard tile — only occupancy is live
- No real auth — login is a username lookup only, fine for demo/DPDP
  synthetic-data discipline but flagged as a gap
