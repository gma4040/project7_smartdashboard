# MediOps — Smart Hospital Dashboards (Project P7)

Full-stack MVP: a **Python backend** (stdlib `http.server` + `sqlite3`, no dependencies)
that implements the PRD-08 star-schema data model, computes KPIs from event data,
enforces role-based access and de-identification, generates an HMIS-style monthly
report, and records an access audit — with a clean web dashboard front end.

## Run it

```bash
cd hospital-ops-mvp
python3 server.py
# open http://localhost:4173
```

The SQLite database is **rebuilt and re-seeded deterministically on every startup**,
so the demo is repeatable. No external packages, no build step.

## The end-to-end flow

1. **Load events** — the backend seeds `fact_events` (admissions, discharges,
   transfers, ED registrations, doctor consults) across six wards.
2. **Live KPI tiles** — six KPIs computed on request from the events:
   Bed Occupancy %, Active Inpatients, Admissions Today, Discharges Today,
   Avg Length of Stay (30d), Avg Door-to-Doctor (today).
3. **Drill-down (permission-gated)** — click any tile for row-level detail.
   A **Department Head** is scoped to their unit (ICU); the **Superintendent**
   sees all wards.
4. **De-identified wall mode** — on by default; patients appear as pseudonymous
   tokens (`PT-…`). The top-bar toggle requests identified data. The **server**
   decides: authorised roles see names + UHID; the **DPO is denied** and the
   attempt is logged. Aggregate cells with **< 5 records are suppressed (—)**.
5. **HMIS monthly report** — compile the month's events into the HMIS/NHM column
   format, review the figures, then **deliberately Submit** (draft → submitted;
   a human owns the statutory submission).
6. **Access audit** — every view, drill-down, reveal attempt, report action, and
   denial is written to `audit_log` and shown in the Access Audit view.

## Roles (personas)

| Role | Scope | Reveal identified? | HMIS report | Audit |
|------|-------|--------------------|-------------|-------|
| **Medical Superintendent** (Dr. A. Rao) | All wards | ✅ | ✅ | ✅ |
| **Department Head — ICU** (Dr. S. Nair) | ICU only | ✅ (within unit) | — | — |
| **Data Protection Officer** (P. Menon) | All wards | ❌ always denied | — | ✅ |

## PRD-08 requirement mapping

- **FR-3** role-based dashboards + unit scoping + permission-gated drill-down
- **FR-5** HMIS report generator with review-and-submit workflow
- **FR-10** de-identified-by-default views + small-cell (<5) suppression
- **FR-14** access & export audit on every action

## API (backend)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET  | `/api/roles` | list personas |
| GET  | `/api/kpis?role=` | KPI tiles, ward occupancy, case-mix matrix |
| GET  | `/api/drilldown?role=&metric=&ward=&reveal=` | gated row-level events |
| POST | `/api/report/generate?role=` | build HMIS draft |
| POST | `/api/report/submit` | mark submitted |
| GET  | `/api/audit?role=` | access log (audit-permitted roles only) |
| POST | `/api/log?role=` | client action logging (toggle/export) |

## Data model (star schema)

- **Fact:** `fact_events` — event grain, with de-identified token + gated
  identified fields (`patient_name`, `patient_uhid`).
- **Dimensions:** `dim_ward`, `dim_role`.
- **Support:** `audit_log` (FR-14), `reports_generated` (FR-5).

## Files
| File | Purpose |
|------|---------|
| `server.py` | Backend: DB init/seed, KPI computation, gating, report, audit, static serving |
| `index.html` | App shell (login, sidebar, top bar) |
| `styles.css` | Styling + responsive rules |
| `app.js` | Front-end: role routing, drill-down, de-id toggle, report, audit |

## Notes
- KPIs are all **derived from `fact_events`**, not hardcoded (change the seed and
  the tiles move).
- De-identification and suppression are enforced **server-side** — the browser
  never receives identified data it isn't authorised to see.
- Responsive: full sidebar on wide screens; compact top nav on narrow ones.
