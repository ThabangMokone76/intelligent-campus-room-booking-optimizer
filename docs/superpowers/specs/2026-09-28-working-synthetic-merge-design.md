# Working + Synthetic Timetable Project Merge — Design Specification

Date: 2026-09-28  
Project: Intelligent Campus-Wide Academic Timetable and Room Allocation Optimizer

## 1. Goal

Create one stable project that combines the verified desktop/login fixes from the current working build with the large synthetic undergraduate dataset and personal-timetable features from the synthetic build.

The result remains a **daily Monday–Friday academic teaching timetable system**. It is **not an exam timetable generator**.

## 2. Source Builds

### Working/FIXED build contributes

- Desktop launcher (`desktop_app.py`, `TNU Timetable System.vbs`)
- One-click setup (`INSTALL_DESKTOP_APP.bat`)
- Authentication bootstrap that guarantees usable demo/admin accounts on a fresh database
- Existing scheduler, validation, workflow and exports
- Known-good login baseline

### Synthetic build contributes

- `generated_students.csv`
- `generated_lecturers.csv`
- `generated_registrations.csv`
- `generated_credentials.csv`
- `programme_faculty_map.csv`
- `module_year_map.csv`
- `source_exam_modules.csv`
- `source_teaching_rooms.csv`
- `generation_report.csv`
- `database/seed_synthetic.py`
- `services/synthetic_population.py`
- `services/synthetic_load_service.py`
- `services/academic_setup_service.py`
- individual-student database tables and relationships
- personal student/lecturer timetable views
- synthetic-data admin page and credential export
- large-scheduler and synthetic-population tests

## 3. Correct Role of the Exam Timetable

The exam timetable is used only as a **source/reference dataset** for:

- undergraduate programme codes
- module codes and names
- approximate module enrolment targets
- programme-to-module relationships
- realistic cohort overlap

The application does **not** generate:

- exam dates
- exam sessions
- exam seating plans
- invigilation schedules
- exam venues as daily teaching rooms unless those venues independently exist in the teaching-room catalogue

The actual output is the normal daily teaching timetable using the project's Monday–Friday period model and teaching-room catalogue.

## 4. Merge Strategy

Use the working/FIXED build as the operational base, then add the synthetic schema and services deliberately rather than copying whole folders over each other.

### Authentication

- Preserve the fixed startup/bootstrap behavior so a fresh extraction can always authenticate.
- Admin remains `admin / admin123` for demo use.
- Each synthetic student receives an individual account:
  - username = student number
  - password = `Tnu@` + final four digits of student number
- Each synthetic lecturer receives an individual account:
  - username = staff number
  - password = `Tnu@` + final four numeric digits of staff number
- Store password hashes in SQLite, not plaintext passwords.
- Credential CSV exists for demonstration/testing only.

### Database

Extend the working schema with the synthetic build's required fields/tables:

- faculty colour
- student-group section code
- `students`
- `programme_modules`
- `student_group_members`
- `student_module_registrations`
- `section_student_assignments`
- `users.student_id`
- relevant indexes

Fresh database creation must load the correct schema and then load synthetic data in a deterministic order.

### Synthetic Population

Load the approved synthetic files as the source of truth for the demonstration dataset. Preserve their existing deterministic IDs and relationships where practical.

Target characteristics from the existing synthetic package include roughly:

- 4,000+ synthetic students
- 50+ synthetic lecturers
- 12,000+ student-module registrations
- 160+ scheduled teaching parts/modules depending on normalized offering structure
- 80+ teaching rooms

Exact counts must be reported from the merged build after seeding; they must not be hard-coded as proof of success.

### Timetable Visibility

- Admin: campus-wide timetable and synthetic-data administration
- Lecturer: only timetable entries assigned to that lecturer
- Student: only timetable entries for modules/sections assigned to that student
- Unpublished versions remain hidden from lecturer/student roles

### Scheduler

Retain the existing daily teaching scheduler and hard-constraint validation.

Synthetic data must feed the same scheduler model; no separate exam scheduler is introduced.

Hard constraints continue to include at minimum:

- no room double-booking
- no lecturer double-booking
- no student/group collision for required teaching
- room capacity/type/equipment compatibility
- practical/lab continuity rules
- shared-module synchronization where configured
- locked entries preserved during regeneration

## 5. Startup and Desktop Behavior

The merged project must work after extraction with this flow:

1. User creates/has `.venv` and installs `requirements.txt` once.
2. `INSTALL_DESKTOP_APP.bat` completes the desktop dependency setup.
3. User double-clicks `TNU Timetable System.vbs`.
4. Flask runs privately on loopback inside the desktop shell.
5. A dedicated desktop window opens to the login page.
6. No manual browser URL is required.

A fresh database must not result in an empty `users` table.

## 6. Data Safety

The user's existing `BACKUP` and `WORKING` folders are not modified.

The merged build is produced separately and is intended for the user's `campus_timetable_optimizer_SYNTHETIC` copy or as a new downloadable ZIP.

Database seeding must be idempotent enough to avoid silently duplicating the synthetic population when the app is launched more than once.

## 7. Acceptance Tests

The merged build is not considered complete until fresh verification proves all of the following:

1. Fresh database initialization completes.
2. Admin login succeeds with `admin / admin123`.
3. At least one real row from `generated_students.csv` can log in with the documented `Tnu@last4` rule.
4. At least one real row from `generated_lecturers.csv` can log in with the documented `Tnu@last4` rule.
5. Incorrect passwords are rejected.
6. Student sees only their own registered teaching timetable.
7. Lecturer sees only their assigned teaching timetable.
8. Admin sees the campus-wide timetable and synthetic-data counts.
9. Synthetic population counts match the loaded files/database and registrations contain no duplicate `(student,module,semester)` rows.
10. Scheduler generation completes for the synthetic dataset.
11. Validator reports zero hard violations for the published demonstration timetable, or the build is explicitly reported as not ready.
12. Draft → Review → Published workflow still works.
13. Excel and PDF export still work.
14. Desktop launcher opens the application without requiring the user to type a localhost URL.
15. Full automated test suite passes with zero failures.

## 8. Non-Goals

This merge does not add:

- exam scheduling
- machine learning
- live university SIS integration
- real student or lecturer personal data
- cloud deployment
- production-grade password reset/email delivery

## 9. Deliverable

The deliverable will be a new merged ZIP, separate from the user's untouched BACKUP and current WORKING copy, plus a short verification summary containing the exact tested accounts, dataset counts, test results and any remaining limitations.
