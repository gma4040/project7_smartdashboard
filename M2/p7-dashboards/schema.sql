-- P7 Smart Hospital Dashboards — SQLite DDL
-- Star schema: fact_events + dimension tables, plus support tables for FR-5/7/14

PRAGMA foreign_keys = ON;

-- ===== DIMENSIONS =====

CREATE TABLE dim_date (
    date_key    INTEGER PRIMARY KEY,   -- YYYYMMDD
    date        TEXT NOT NULL,          -- ISO date
    day_of_week TEXT NOT NULL,
    month       INTEGER NOT NULL,
    year        INTEGER NOT NULL
);

CREATE TABLE dim_ward (
    ward_key     INTEGER PRIMARY KEY AUTOINCREMENT,
    ward_name    TEXT NOT NULL,
    department   TEXT NOT NULL,
    bed_capacity INTEGER NOT NULL
);

CREATE TABLE dim_payer (
    payer_key  INTEGER PRIMARY KEY AUTOINCREMENT,
    payer_type TEXT NOT NULL CHECK (payer_type IN ('cash','insurance','PMJAY','other'))
);

CREATE TABLE dim_role (
    role_key        INTEGER PRIMARY KEY AUTOINCREMENT,
    role_name       TEXT NOT NULL UNIQUE,   -- e.g. dept_head, superintendent, mrd_officer, dpo, finance_head
    permission_level TEXT NOT NULL CHECK (permission_level IN ('scoped','full','deidentified_only'))
);

-- ===== FACT TABLE =====

CREATE TABLE fact_events (
    event_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    date_key           INTEGER NOT NULL REFERENCES dim_date(date_key),
    ward_key           INTEGER NOT NULL REFERENCES dim_ward(ward_key),
    payer_key          INTEGER NOT NULL REFERENCES dim_payer(payer_key),
    patient_pseudo_id  TEXT NOT NULL,       -- de-identified token, never the real UHID
    event_type         TEXT NOT NULL CHECK (event_type IN
                        ('admission','discharge','transfer','ED_registration','doctor_consult')),
    event_timestamp    TEXT NOT NULL         -- ISO datetime
);

CREATE INDEX idx_fact_events_date ON fact_events(date_key);
CREATE INDEX idx_fact_events_ward ON fact_events(ward_key);

-- ===== SUPPORT TABLES (FR-5, FR-7, FR-14) =====

CREATE TABLE users (
    user_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    username  TEXT NOT NULL UNIQUE,
    role_key  INTEGER NOT NULL REFERENCES dim_role(role_key),
    ward_key  INTEGER REFERENCES dim_ward(ward_key)   -- NULL = not scoped to a single ward (e.g. superintendent)
);

CREATE TABLE audit_log (                       -- FR-14
    log_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(user_id),
    role       TEXT NOT NULL,
    action     TEXT NOT NULL,                  -- 'view_dashboard' | 'export_report' | 'view_digest'
    target     TEXT NOT NULL,                  -- e.g. 'ward:ICU' or 'report:HMIS_2026_06'
    timestamp  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE reports_generated (               -- FR-5
    report_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type   TEXT NOT NULL,               -- 'HMIS_monthly'
    period        TEXT NOT NULL,               -- e.g. '2026-06'
    status        TEXT NOT NULL CHECK (status IN ('draft','submitted')) DEFAULT 'draft',
    generated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    submitted_by  INTEGER REFERENCES users(user_id),
    submitted_at  TEXT
);

CREATE TABLE digest_log (                      -- FR-7
    digest_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    role              TEXT NOT NULL,
    channel           TEXT NOT NULL CHECK (channel IN ('email','whatsapp_stub')),
    sent_at           TEXT NOT NULL DEFAULT (datetime('now')),
    content_snapshot  TEXT NOT NULL
);
