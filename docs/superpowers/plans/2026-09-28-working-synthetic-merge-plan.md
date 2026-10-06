# Working + Synthetic Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge the verified desktop/authentication build with the existing large synthetic academic dataset so the application remains a Monday–Friday daily teaching timetable system with individual Admin, Lecturer, and Student views.

**Architecture:** Use the verified FIXED build as the operational base. Add the synthetic schema, population loaders, personal-timetable filtering, and synthetic admin pages deliberately, while preserving the desktop launcher and fresh-start authentication safety. The exam-derived CSVs remain reference/source data only; scheduling continues to use the teaching timetable model and teaching-room catalogue.

**Tech Stack:** Python 3.12, Flask, SQLite, Werkzeug password hashing, PyWebView, unittest, ReportLab, openpyxl.

**Spec:** `docs/superpowers/specs/2026-09-28-working-synthetic-merge-design.md`

## Global Constraints

- Output is a Monday–Friday academic teaching timetable, not an exam timetable.
- Exam-derived data may supply programme/module relationships and enrolment targets only.
- Teaching rooms come from `data/source_teaching_rooms.csv`.
- Admin demo login remains `admin / admin123`.
- Student login rule is student number + `Tnu@` + final four digits.
- Lecturer login rule is staff number + `Tnu@` + final four digits.
- Passwords are stored hashed in SQLite.
- Fresh startup must never leave the application with an empty usable-user set.
- Existing BACKUP and WORKING folders are not modified.
- The merged deliverable is produced as a separate project/ZIP.
- Completion requires fresh verification; no success claim is made from code inspection alone.

## Review Focus

- **Repeated application startup:** must not duplicate thousands of synthetic students/users/registrations.
- **Database upgraded from the FIXED schema:** synthetic columns/tables must exist before population loading and foreign keys must remain valid.
- **Student visibility:** an individual student must never receive classes for another student's section merely because they share a programme.
- **Lecturer visibility:** lecturer filtering must use actual `offering_staff` assignments, not faculty or department membership.
- **Large-data publication/export:** published timetable, PDF export, and XLSX export must work after large synthetic seeding without using exam dates/sessions.

---

### Task 1: Merge the Synthetic Database Schema into the Verified Base

**Files:**
- Modify: `database/schema.sql`
- Modify: `database/db.py` only if schema initialization cannot apply the added objects safely
- Test: `tests/test_synthetic_schema.py`

**Interfaces:**
- Consumes: existing `init_database(path=None)` and `connect(path=None)`.
- Produces: schema containing `faculties.colour_hex`, `student_groups.section_code`, `students`, `programme_modules`, `student_group_members`, `student_module_registrations`, `section_student_assignments`, `users.student_id`, and synthetic indexes.

- [ ] **Step 1: Write the failing schema test**

Create `tests/test_synthetic_schema.py` with `test_fresh_database_contains_synthetic_tables_and_columns()` asserting that a temporary fresh database contains every required table/column/index from the approved design.

- [ ] **Step 2: Verify the schema test fails against the FIXED base**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_synthetic_schema -v
```

Expected: FAIL because the FIXED schema lacks the synthetic tables/columns.

- [ ] **Step 3: Merge only the required schema changes from the synthetic build**

Update `database/schema.sql` with the exact synthetic structures already present in the uploaded synthetic project. Do not add exam scheduling tables.

- [ ] **Step 4: Verify the schema test passes and foreign keys are clean**

Run the same unittest command and additionally execute `PRAGMA foreign_key_check` in the test.

Expected: PASS and no foreign-key rows.

- [ ] **Step 5: Commit**

```bash
git add database/schema.sql database/db.py tests/test_synthetic_schema.py
git commit -m "feat: add synthetic population schema"
```

### Task 2: Add Deterministic Synthetic Population Loading Without Breaking Fresh Startup

**Files:**
- Add from synthetic build: `services/source_catalog.py`
- Add from synthetic build: `services/synthetic_population.py`
- Add from synthetic build: `services/synthetic_load_service.py`
- Add from synthetic build: `services/academic_setup_service.py`
- Add from synthetic build: `database/seed_synthetic.py`
- Add from synthetic build: `build_synthetic_demo.py`
- Modify: `database/bootstrap.py`
- Modify: `database/upgrade_existing.py` only if needed for safe migration/bootstrap
- Copy: `data/generated_students.csv`
- Copy: `data/generated_lecturers.csv`
- Copy: `data/generated_registrations.csv`
- Copy: `data/generated_credentials.csv`
- Copy: `data/generation_report.csv`
- Copy: `data/programme_faculty_map.csv`
- Copy: `data/module_year_map.csv`
- Copy: `data/source_exam_modules.csv`
- Copy: `data/source_teaching_rooms.csv`
- Test: `tests/test_synthetic_population.py`
- Test: `tests/test_synthetic_bootstrap.py`

**Interfaces:**
- Consumes: `generate_population(data_dir)`, `load_population(conn, bundle, data_dir)`, `build_semester_offerings(conn, semester_id, data_dir, module_lecturer)`.
- Produces: `ensure_synthetic_ready(path=None)` that leaves one complete deterministic synthetic dataset in a fresh database and does not duplicate it on a second call.

- [ ] **Step 1: Restore the existing synthetic-generation test**

Bring over `tests/test_synthetic_population.py` and confirm it checks source validity, unique student numbers/emails, student `Tnu@last4` passwords, complete registrations, and lecturer credential rules.

- [ ] **Step 2: Write a failing idempotent-bootstrap test**

Create `tests/test_synthetic_bootstrap.py` with:
- `test_fresh_bootstrap_loads_admin_students_lecturers_and_registrations()`
- `test_second_bootstrap_does_not_duplicate_population()`
- `test_wrong_password_is_rejected()`

The first test must derive its sample student/lecturer from the generated bundle instead of hard-coding an account.

- [ ] **Step 3: Run the population/bootstrap tests and verify the bootstrap test fails**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_synthetic_population tests.test_synthetic_bootstrap -v
```

Expected: population generation may pass; bootstrap test FAILS because `ensure_synthetic_ready()` does not yet exist.

- [ ] **Step 4: Implement `ensure_synthetic_ready(path=None)` in `database/bootstrap.py`**

Behavior:
- initialize schema;
- if the database has no academic population, generate/load the approved synthetic dataset and build semester offerings;
- if the population already exists, do not reload/duplicate it;
- guarantee `admin / admin123` exists;
- preserve hashed passwords;
- verify required source catalogs before destructive seeding.

- [ ] **Step 5: Run the two tests again**

Expected: PASS, with identical counts before and after the second bootstrap call.

- [ ] **Step 6: Commit**

```bash
git add database/bootstrap.py database/seed_synthetic.py database/upgrade_existing.py build_synthetic_demo.py services/source_catalog.py services/synthetic_population.py services/synthetic_load_service.py services/academic_setup_service.py data tests/test_synthetic_population.py tests/test_synthetic_bootstrap.py
git commit -m "feat: load synthetic academic population safely"
```

### Task 3: Merge Individual Authentication and Role-Scoped Timetable Visibility

**Files:**
- Modify: `app.py`
- Modify: `services/timetable_service.py`
- Add: `templates/personal_timetable.html`
- Modify: `templates/base.html`
- Modify: `templates/dashboard.html`
- Test: `tests/test_auth_synthetic.py`
- Test: `tests/test_personal_timetable.py`

**Interfaces:**
- Consumes: users with `role`, `staff_id`, `group_id`, `student_id`; published timetable entries.
- Produces: `timetable_rows(conn, version_id, user=None)` filtering students by `section_student_assignments.student_id` and lecturers by `offering_staff.staff_id`; `timetable_grid(rows)`.

- [ ] **Step 1: Write failing authentication tests**

`tests/test_auth_synthetic.py` must prove:
- admin login succeeds with `admin123`;
- a generated student can authenticate with their documented password;
- a generated lecturer can authenticate with their documented password;
- a wrong password fails.

Use Flask's test client against a temporary synthetic database.

- [ ] **Step 2: Write failing timetable-visibility tests**

`tests/test_personal_timetable.py` must assert:
- Student A receives only sections assigned to Student A.
- Student A does not receive another student's section when both share a programme/year.
- Lecturer A receives only offerings linked through `offering_staff`.
- non-admin roles only receive a published version.

- [ ] **Step 3: Run both tests and verify they fail against the unmerged FIXED behavior**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_auth_synthetic tests.test_personal_timetable -v
```

- [ ] **Step 4: Merge the synthetic role-aware behavior**

In `app.py`:
- call the synthetic-safe bootstrap rather than demo-only startup;
- retain the current login route and password verification;
- choose `timetable.html` for Admin and `personal_timetable.html` for Lecturer/Student;
- pass the role-specific rows/grid.

In `services/timetable_service.py`:
- preserve the FIXED build's safe Draft → Review → Published transitions;
- merge the synthetic build's `student_id` and lecturer filtering;
- keep Draft-only move/lock protections.

- [ ] **Step 5: Run both tests**

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app.py services/timetable_service.py templates/personal_timetable.html templates/base.html templates/dashboard.html tests/test_auth_synthetic.py tests/test_personal_timetable.py
git commit -m "feat: add individual synthetic logins and personal timetables"
```

### Task 4: Restore Synthetic Admin Data Pages Without Introducing Exam Scheduling

**Files:**
- Modify: `app.py`
- Add: `templates/synthetic_data.html`
- Modify: `templates/admin.html` and/or `templates/base.html` for navigation
- Test: `tests/test_synthetic_admin.py`

**Interfaces:**
- Consumes: synthetic students, staff, programmes, modules, rooms, registrations.
- Produces: `/admin/synthetic` and `/admin/synthetic/credentials`.

- [ ] **Step 1: Write failing admin-page tests**

Assert:
- Admin receives HTTP 200 and database-derived counts.
- Student and Lecturer are forbidden/redirected from `/admin/synthetic`.
- credential export returns the generated credential CSV.
- rendered output contains no exam scheduling controls/routes.

- [ ] **Step 2: Run test and verify failure**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_synthetic_admin -v
```

- [ ] **Step 3: Merge the two synthetic admin routes and template**

Use the uploaded synthetic build's route logic, but leave exam source CSVs presented only as source/reference data.

- [ ] **Step 4: Run test and verify pass**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app.py templates/synthetic_data.html templates/admin.html templates/base.html tests/test_synthetic_admin.py
git commit -m "feat: add synthetic dataset administration"
```

### Task 5: Verify the Large Daily Teaching Scheduler and Published Workflow

**Files:**
- Bring over: `tests/test_large_scheduler.py`
- Modify only if required by proven failures: `scheduler/engine.py`, `scheduler/validator.py`, `services/academic_setup_service.py`
- Test: `tests/test_large_scheduler.py`
- Existing tests: `tests/test_scheduler_core.py`, `tests/test_workflow.py`

**Interfaces:**
- Consumes: synthetic population, generated semester offerings, teaching rooms, Monday–Friday 10-period model.
- Produces: a generated daily teaching timetable version with zero hard violations.

- [ ] **Step 1: Run the existing large-scheduler test before changing scheduler code**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_large_scheduler -v
```

Expected: either PASS immediately or a specific reproducible scheduler/validator failure.

- [ ] **Step 2: If it fails, write/adjust the smallest regression test that isolates the proven scheduler cause**

Do not change scheduler code until the failing test identifies the actual cause.

- [ ] **Step 3: Make the minimal scheduler/validator change required by that test**

Do not add exam sessions, exam dates, or exam-room logic.

- [ ] **Step 4: Run scheduler/workflow tests**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_large_scheduler tests.test_scheduler_core tests.test_workflow -v
```

Expected: PASS and the large test asserts `validate_version(...).total == 0`.

- [ ] **Step 5: Commit**

```bash
git add scheduler services/academic_setup_service.py tests/test_large_scheduler.py tests/test_scheduler_core.py tests/test_workflow.py
git commit -m "test: verify synthetic daily timetable scheduling"
```

### Task 6: Preserve Desktop Launch, Exports, and Run Full Acceptance Verification

**Files:**
- Preserve from FIXED build: `desktop_app.py`
- Preserve from FIXED build: `INSTALL_DESKTOP_APP.bat`
- Preserve from FIXED build: `TNU Timetable System.vbs`
- Modify: `final_check.py`
- Modify: `requirements.txt` only if merged imports require a dependency already present in one source build
- Add: `tests/test_exports_synthetic.py`
- Existing: full `tests/` suite

**Interfaces:**
- Consumes: merged Flask app, synthetic database, published timetable.
- Produces: desktop-startable merged project, PDF/XLSX exports, deterministic verification report.

- [ ] **Step 1: Write a failing export regression test**

`tests/test_exports_synthetic.py` generates a synthetic timetable in a temporary database, publishes it, calls the PDF and XLSX export services, and asserts both files exist and are non-empty.

- [ ] **Step 2: Run export test**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_exports_synthetic -v
```

Fix only proven export integration failures.

- [ ] **Step 3: Update `final_check.py`**

The check must report actual values read from the merged database:
- student count;
- lecturer count;
- registration count;
- teaching-room count;
- module/offering/scheduled-part counts;
- hard violations;
- sample Admin, Student, Lecturer login verification;
- role-scoped timetable checks;
- workflow state;
- export results.

Do not hard-code expected counts as proof.

- [ ] **Step 4: Run the entire automated suite**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: zero failures and zero errors.

- [ ] **Step 5: Run the final verification script**

```powershell
.\.venv\Scripts\python.exe final_check.py
```

Expected:
- fresh/merged database can be initialized;
- actual synthetic counts are printed;
- Admin, sample Student, and sample Lecturer authentication checks pass;
- scheduler completes;
- validator reports `0` hard violations;
- exports succeed;
- final status is PASS.

- [ ] **Step 6: Desktop smoke test on Windows**

From the merged project folder:
1. run `INSTALL_DESKTOP_APP.bat` once if needed;
2. double-click `TNU Timetable System.vbs`;
3. verify the dedicated desktop window opens to `/login` without typing a localhost URL;
4. manually sign in as Admin, one generated Student, and one generated Lecturer using accounts reported by `final_check.py`.

If the environment used for automated implementation is not Windows/GUI-capable, record this step as **requires user-side Windows smoke test** rather than falsely marking it passed.

- [ ] **Step 7: Build the separate merged ZIP**

Name the deliverable:

```text
campus_timetable_optimizer_SYNTHETIC_MERGED.zip
```

Exclude `.venv`, caches, and temporary test databases. Include the source CSVs, setup files, desktop launchers, tests, and verification notes.

- [ ] **Step 8: Commit**

```bash
git add final_check.py requirements.txt tests/test_exports_synthetic.py desktop_app.py INSTALL_DESKTOP_APP.bat "TNU Timetable System.vbs"
git commit -m "chore: verify merged synthetic desktop build"
```
