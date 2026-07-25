# M2 — Design Freeze
## Project P7: Smart Hospital Dashboards (PRD-08)
**Team:** Greeshma & Sudhanva Holla
**Date:** 12 July 2026

---

## 1. Final ERD + SQLite DDL

Star schema — fact table `fact_events` with dimensions `dim_date`, `dim_ward`,
`dim_payer`, `dim_role`, plus support tables `users`, `audit_log`,
`reports_generated`, `digest_log`.

Full DDL: see `schema.sql` in the repo. Summary:

- **fact_events**: event_id, date_key, ward_key, payer_key, patient_pseudo_id,
  event_type, event_timestamp
- **dim_date / dim_ward / dim_payer / dim_role**: standard star-schema dimensions
- **users**: links a demo login to a role and (optionally) a ward scope
- **audit_log**: FR-14 — every dashboard view/export writes a row
- **reports_generated**: FR-5 — tracks draft → submitted status per HMIS report
- **digest_log**: FR-7 — records each digest send (email or WhatsApp stub)

No table stores a real patient name or UHID anywhere — `patient_pseudo_id`
is the only patient-level identifier, which is the structural half of FR-10.

## 2. API / Route List

See `API_ROUTES.md` in the repo for the full table (14 routes mapped to
FR-3/5/7/10/14). Built for M2: `/`, `/login`, `/dashboard`. Stubbed:
`/reports/hmis`, `/digest/preview`, `/audit`, and the drill-down/toggle
variants — these are M3 work.

## 3. Wireframes (5 screens)

All in `wireframes/` as SVGs:

1. **Login** — demo role picker, no password (`01_login.svg`)
2. **Role dashboard** — scoped tiles, occupancy live from data (`02_dashboard.svg`)
3. **Full view + drill-down** — superintendent sees all wards, click-through to
   pseudonymised row-level detail (`03_full_view_drilldown.svg`)
4. **HMIS report preview** — draft report, review-and-submit workflow (`04_hmis_report.svg`)
5. **De-identified wall mode** — toggle + small-cell suppression example (`05_deidentified_wall_mode.svg`)

## 4. Seeded Sample Dataset

Deterministic generator (`data/generate_seed_data.py`, `random.seed(42)`):

- 30 days of synthetic events (1 Jun–30 Jun 2026), 15–35 events/day
- 5 wards, 4 payer types, 5 event types
- Same output every run — reproducible for grading/demo

Dimension CSVs (wards, payers, roles, demo users) are hand-authored and
checked into `data/`.

## 5. Walking-Skeleton Repo

Boots with `python app.py`. One real end-to-end flow works, not just stubs:

**Login → role-scoped dashboard → occupancy % computed live from
`fact_events` → audit_log row written on view.**

Verified with an automated boot test (login as `dr_mehta`, confirm
dashboard renders an occupancy tile, confirm `audit_log` gets a new row).
Superintendent login (`dr_rao`) confirmed to show all wards vs the
ward-scoped dept_head view — proves FR-3 scoping logic works, not just
the route.

## Known Gaps Going Into M3

- FR-5 (HMIS report), FR-7 (digest), FR-14 (audit UI) are route stubs only
- ALOS and door-to-doctor KPI formulas are defined (M1 doc) but not yet
  wired into a live tile — only occupancy is computed
- Identified-view toggle (permission override on FR-10) not built yet
- No real authentication — acceptable for a synthetic-data classroom demo,
  flagged as a gap for the report

---

