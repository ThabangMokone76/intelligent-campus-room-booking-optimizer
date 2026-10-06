# Project Structure

```text
campus_timetable_optimizer_final/
├── app.py                         Flask web application
├── requirements.txt
├── run.ps1                        Windows quick-start
├── final_check.py                 Test + latest timetable validation
├── database/
│   ├── schema.sql                 Canonical schema
│   ├── db.py                      SQLite connection helpers
│   ├── security.py                Password hashing
│   ├── seed_demo.py               Synthetic demonstration dataset
│   ├── upgrade_existing.py        Safely upgrades an existing project DB
│   └── init_db.py
├── scheduler/
│   ├── policy.py                  Duration/splitting policy
│   ├── engine.py                  Hybrid CSP scheduler
│   ├── validator.py               Independent hard-constraint validator
│   └── run_scheduler.py           CLI generation + validation
├── services/
│   ├── setup_service.py           Creates offerings/templates/sessions
│   ├── timetable_service.py       Workflow, locks and manual moves
│   ├── import_service.py          CSV/XLSX preview + commit
│   └── export_service.py          PDF/XLSX export
├── templates/                     Admin/Lecturer/Student UI
├── static/style.css               Professional responsive styling
├── data/templates/                Import templates
└── tests/                         High-value regression tests
```
