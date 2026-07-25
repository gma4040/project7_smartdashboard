# Setup Guide — MediOps (P7 Smart Hospital Dashboards)

This project has **zero external dependencies** — no pip installs, no npm, no
build step. It's just Python's built-in `http.server` + `sqlite3` on the
backend, and plain HTML/CSS/JS on the frontend. If Python is installed, you
can run this in under a minute.

---

## 1. Check you have Python installed

Open a terminal (Mac/Linux) or PowerShell (Windows) and run:

**Mac / Linux:**
```bash
python3 --version
```

**Windows:**
```powershell
python --version
```

You need **Python 3.8 or newer**. If a version number prints, skip to Step 2.

**If it says "not found" (Windows especially):** Windows often ships a fake
`python3`/`python` command that just opens the Microsoft Store instead of
running anything. Do **not** install from that Store prompt. Instead:
1. Go to **https://python.org/downloads**
2. Download the installer and run it
3. On the very first install screen, **check the box "Add python.exe to PATH"**
   — this is the #1 reason people hit "Python not found" later
4. Close and **reopen** your terminal/PowerShell window (it won't see the new
   PATH in the same window) and re-run the version check

---

## 2. Get the project files

If you have the zip: extract it anywhere (e.g. Desktop or Downloads). You
should end up with a folder called `hospital-ops-mvp` containing:

```
hospital-ops-mvp/
├── server.py
├── index.html
├── styles.css
├── app.js
├── run-mac.command
├── run-windows.bat
└── README.md
```

If you have it as a Git repo instead:
```bash
git clone <your-repo-url>
cd hospital-ops-mvp
```

---

## 3. Run the server

Navigate into the folder first:
```bash
cd hospital-ops-mvp
```

Then start it:

| OS | Command |
|---|---|
| **Mac / Linux** | `python3 server.py` |
| **Windows** | `python server.py` |

You should see something like:
```
Serving MediOps on http://localhost:4173
```

**Shortcuts, if you'd rather not type a command:**
- **Mac:** double-click `run-mac.command` (first time, you may need to
  right-click → Open, since it's from an unidentified source)
- **Windows:** double-click `run-windows.bat`

---

## 4. Open it in a browser

Go to:
```
http://localhost:4173
```

You should land on a role picker with three personas: **Medical
Superintendent**, **Department Head (ICU)**, and **Data Protection Officer**.
Pick any one to load the dashboard.

---

## 5. Stopping and resetting

- **To stop the server:** go back to the terminal window and press `Ctrl + C`
- **To reset the demo data:** just stop and restart the server — the SQLite
  database is rebuilt and re-seeded **deterministically every time it starts**,
  so you always get the same clean demo state. There's nothing to manually
  delete or clean up.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `python3: command not found` | You're likely on Windows — use `python` instead. See Step 1. |
| `Python was not found; run without arguments to install from the Microsoft Store` | Don't follow that prompt — install from python.org instead (Step 1), making sure "Add to PATH" is checked. |
| `Address already in use` / port 4173 busy | Another instance is already running — check for an old terminal window still open, or another process using that port. |
| Browser shows nothing / connection refused | Make sure the terminal still shows the server running (didn't crash or get closed) and that you typed the URL exactly as `http://localhost:4173`. |
| `py` works but `python`/`python3` don't (Windows) | Use `py server.py` instead — some Windows installs only register the `py` launcher. |

---

## What you'll see once it's running

- **Live KPI tiles** computed from seeded hospital event data (occupancy, ALOS,
  door-to-doctor, admissions/discharges today)
- **Role-based dashboards** — Department Head sees only ICU, Superintendent
  sees everything
- **Drill-down** into any tile for row-level detail, permission-gated by role
- **De-identified/identified toggle** — DPO is always denied identified data,
  even if they try
- **HMIS-style monthly report** — draft, then a separate submit step
- **Access audit log** — every view, drill-down, and report action is recorded
