# API / Route List — P7 Smart Hospital Dashboards

| Method | Route | FR | Purpose | Auth/Role gate |
|---|---|---|---|---|
| GET | `/` | — | Landing / role login (stub) | none |
| POST | `/login` | — | Sets session role (stub, no real auth) | none |
| GET | `/dashboard` | FR-3 | Role-scoped dashboard: KPI tiles filtered to user's ward/dept | logged-in session |
| GET | `/dashboard/<ward>` | FR-3 | Drill-down into a specific ward's detail (row-level) | permission_level = 'full' or ward matches user's own |
| GET | `/api/kpi/occupancy` | FR-3 | JSON: current occupancy % by ward | scoped by role |
| GET | `/api/kpi/alos` | FR-3 | JSON: ALOS for selected period | scoped by role |
| GET | `/api/kpi/door-to-doctor` | FR-3 | JSON: avg door-to-doctor time | scoped by role |
| GET | `/reports/hmis` | FR-5 | Preview screen: compiled HMIS-format report (draft) | mrd_officer, superintendent |
| POST | `/reports/hmis/submit` | FR-5 | Marks report `submitted`, logs submitted_by/at | mrd_officer, superintendent |
| GET | `/digest/preview` | FR-7 | Renders today's digest content (email/WhatsApp text) | owner, superintendent |
| POST | `/digest/send` | FR-7 | Stub-sends digest, writes to `digest_log` | owner, superintendent |
| GET | `/dashboard?mode=deidentified` | FR-10 | Toggle: wall/export view with pseudonymised patient data (default ON) | all roles |
| GET | `/dashboard?mode=identified` | FR-10 | Reveals identified data — only for permitted roles | permission_level = 'full' |
| GET | `/audit` | FR-14 | View audit log (who viewed/exported what) | dpo, superintendent |
| *(middleware)* | every route above | FR-14 | Every dashboard view / report export / digest send auto-writes a row to `audit_log` | — |

**Stubbed for M2 walking skeleton:** only `/`, `/login`, `/dashboard` (occupancy tile from seed data), and the audit-log write on that view. Everything else is a route stub returning a placeholder — filled in during M3.
