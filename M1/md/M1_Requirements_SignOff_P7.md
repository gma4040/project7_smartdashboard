# M1 — Requirements Sign-off
## Project P7: Smart Hospital Dashboards (PRD-08)
**Team:** Greeshma & Sudhanva Holla
**Date:** 11 July 2026
**Scope:** Phase-1 / MVP, S-tier (●) requirements only

---

# 1. Scoped Requirement List

Only the following Phase-1, S-tier requirements from PRD-08 are in scope for this sprint:

| FR | Requirement | Build Spec (what we will actually build) |
|---|---|---|
| **FR-3** | Role-based dashboards with unit/department scoping and drill-down permission gates | A dashboard view that changes based on logged-in role (e.g. Dept Head sees only their ward; Superintendent sees all). Clicking a tile drills into row-level detail *only* if the role is permitted. |
| **FR-5** | Statutory report generator: HMIS monthly format, review-and-submit workflow | A button that compiles seeded event data into an HMIS-style monthly report (fixed columns/format), shows a preview screen, and requires a manual "Submit" click before it's marked final. |
| **FR-7** | Scheduled digests (daily/weekly) per role via email/WhatsApp | A script that generates a plain-text/HTML digest (census, admissions, discharges, flags) and either emails it or logs a mock "WhatsApp send" (stub, since no real gateway). |
| **FR-10** | De-identification layer: de-identified default views, small-cell suppression | Patient names/IDs replaced with pseudonymised tokens by default on all dashboard/wall views. A toggle can reveal identified data only for permitted roles. Any breakdown with <5 records in a cell is suppressed/shown as "—". |
| **FR-14** | Audit of dashboard access & exports (who saw/exported what) | Every dashboard view and every report export writes a row to an `audit_log` table: user, timestamp, what was viewed/exported. |

**Explicitly out of scope for M1–M4:** Command centre, alerting engine, NABH QI module, self-service explorer, surge feeds, benchmarking, AI features (all Phase 2/3 or M/L tier).

---

## 2. User Story Shortlist (≤6)

1. As a **department head**, I want my dashboard filtered to my unit with drill-down to (permission-gated) patient level so I can act, not just observe. *(FR-3)*
2. As an **MRD/statistics officer**, I want monthly HMIS reports generated from the warehouse with a review-and-submit step so compilation effort drops to minutes. *(FR-5)*
3. As an **owner (S tier)**, I want a daily digest — census, admissions, discharges, flags — on email/WhatsApp so I don't have to log in to stay informed. *(FR-7)*
4. As a **DPO**, I want certainty that wall displays and exports show de-identified data by default, with identified drill-down only for authorised roles. *(FR-10)*
5. As an **admin/compliance officer**, I want an audit trail of who viewed or exported what data, so we can prove accountability if questioned. *(FR-14)*
6. As a **medical superintendent**, I want a single top-level view across departments (even if basic) so I can spot which unit needs attention. *(light FR-3 extension)*

---

## 3. Data Model Draft (ERD — Star Schema)

**Fact table: `FACT_EVENTS`**
| Column | Type | Notes |
|---|---|---|
| event_id | INTEGER PK | |
| date_key | INTEGER FK | → DIM_DATE |
| ward_key | INTEGER FK | → DIM_WARD |
| payer_key | INTEGER FK | → DIM_PAYER |
| patient_pseudo_id | TEXT | de-identified token, not real UHID |
| event_type | TEXT | admission / discharge / transfer / ED_registration / doctor_consult |
| event_timestamp | DATETIME | |
| admission_duration | INTEGER | length of stay in days, populated on discharge events |
| door_to_doctor_minutes | INTEGER | populated on doctor_consult events |
| occupied_beds | INTEGER | ward occupancy snapshot at event time |
| role_scope | TEXT | which role(s) can see this row identified |

**Dimension tables:**
- `DIM_DATE` (date_key PK, full_date, day, month, year, weekday)
- `DIM_WARD` (ward_key PK, ward_name, department, total_beds)
- `DIM_PAYER` (payer_key PK, payer_name, payer_type)
- `DIM_USER` (user_key PK, username, role, department) — drives FR-3 & FR-10 gating; replaces a separate role-dimension table by folding role/department directly onto the user

**Relationships:** FACT_EVENTS `uses` DIM_DATE, `occurs_in` DIM_WARD, `billed_to` DIM_PAYER, `viewed_by` DIM_USER — each a many-to-one from fact to dimension.

**Support tables (not fact/dim, but needed for FRs):**
- `audit_log` (log_id, user_id, role, action, target_view_or_report, timestamp) — FR-14
- `reports_generated` (report_id, report_type, period, status[draft/submitted], generated_at, submitted_by) — FR-5
- `digest_log` (digest_id, role, channel[email/whatsapp_stub], sent_at, content_snapshot) — FR-7

**KPI Definitions (formulas):**
- **Occupancy %** = (occupied_beds ÷ total_beds) × 100 — `occupied_beds` now lives directly on `FACT_EVENTS` as a per-event snapshot, joined to `DIM_WARD.total_beds`
- **ALOS (Average Length of Stay)** = average of `admission_duration` across discharge events in the period (pre-aggregated at event time rather than computed by subtracting timestamps downstream)
- **Door-to-doctor time** = average of `door_to_doctor_minutes` across doctor_consult events in the period (same pattern — captured on the event, not derived later)

**Design note vs. the M1 draft:** the earlier draft computed ALOS and door-to-doctor by subtracting timestamps at query time. This revision pushes that calculation upstream — the source system (or ingestion pipeline) writes the duration directly onto the event row. This trades a small amount of ingestion complexity for much simpler, faster dashboard queries (no timestamp math needed on every tile refresh).

---

## 4. Compliance Checklist (from PRD-08 §8 Regulatory)

| Instrument | Obligation | Feature it forces |
|---|---|---|
| **DPDP Act 2023 + Rules 2025** | Purpose limitation; de-identified by default; access logging; data minimisation in exports | FR-10 (de-identification), FR-14 (audit log) |
| **DPDP Act 2023** | Breach-notification readiness | FR-14 (audit trail is first evidence source in a breach review) |
| **HMIS/NHM reporting formats** | Faithful mapping to current HMIS indicators | FR-5 (report generator uses HMIS column format) |
| **CERT-In directions 2022** | Log retention (180 days), India-time NTP sync | `audit_log` retention policy note (even if demo only keeps short window, document the requirement) |
| **ABDM / EHR Standards 2016** | Coding standards for comparable metrics | Noted as N/A for MVP demo (no real ABDM integration; stub only) |

**Viva prep — "which rule forces this feature?":**
- De-identified default view → **DPDP purpose limitation + data minimisation**
- Audit log on every view/export → **DPDP access-logging obligation + CERT-In log retention**
- Review-and-submit step on reports (not auto-submit) → **DPDP + HMIS accountability** — a human must own what's submitted to a statutory body
- Small-cell suppression → **DPDP re-identification risk control**

---

**Data source decision (needed before M2):** Coordinate with a P1 (Patient Registration) or P2 (Bed Management) team for a live event feed if possible; otherwise commit to the provided sample CSVs. *(Decide and note here before Sunday's design freeze.)*

---

