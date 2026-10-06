if (-not (Test-Path ".venv")) {
    py -m venv .venv
}
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
if (-not (Test-Path "database\campus_timetable.db")) {
    py -m database.seed_demo
}
py app.py
