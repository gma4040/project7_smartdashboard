"""
Deterministically seeded demo data generator for P7 Smart Hospital Dashboards.
Run: python generate_seed_data.py
Produces dim_date.csv and fact_events.csv in this folder.
"""
import csv
import random
from datetime import date, timedelta, datetime

random.seed(42)  # deterministic

START = date(2026, 6, 1)
DAYS = 30
WARD_KEYS = [1, 2, 3, 4, 5]
PAYER_KEYS = [1, 2, 3, 4]
EVENT_TYPES = ["admission", "discharge", "transfer", "ED_registration", "doctor_consult"]

# ---- dim_date ----
with open("dim_date.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["date_key", "date", "day_of_week", "month", "year"])
    for i in range(DAYS):
        d = START + timedelta(days=i)
        date_key = int(d.strftime("%Y%m%d"))
        w.writerow([date_key, d.isoformat(), d.strftime("%A"), d.month, d.year])

# ---- fact_events ----
with open("fact_events.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["event_id", "date_key", "ward_key", "payer_key",
                "patient_pseudo_id", "event_type", "event_timestamp"])
    event_id = 1
    for i in range(DAYS):
        d = START + timedelta(days=i)
        date_key = int(d.strftime("%Y%m%d"))
        n_events = random.randint(15, 35)  # events that day, hospital-wide
        for _ in range(n_events):
            ward_key = random.choice(WARD_KEYS)
            payer_key = random.choice(PAYER_KEYS)
            pseudo_id = f"PT-{random.randint(1000,9999)}"
            event_type = random.choice(EVENT_TYPES)
            hh = random.randint(0, 23)
            mm = random.randint(0, 59)
            ts = datetime(d.year, d.month, d.day, hh, mm).isoformat()
            w.writerow([event_id, date_key, ward_key, payer_key, pseudo_id, event_type, ts])
            event_id += 1

print("Generated dim_date.csv and fact_events.csv (seed=42, deterministic)")
