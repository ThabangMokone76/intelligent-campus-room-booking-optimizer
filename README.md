# Sol Plaatje University Timetable Optimizer — Upgraded Demo Build

This is the SPU-branded desktop/web build of the Intelligent Campus Timetable and Room Allocation Optimizer. It generates the normal **Monday–Friday daily teaching timetable** and does **not** generate examination timetables.

## What is included

The verified synthetic campus build contains approximately 4,001 students, 56 lecturers, 166 modules/offerings, 85 teaching rooms, 12,681 registrations, and a published timetable with zero hard-constraint violations.

The upgraded system includes:

- Sol Plaatje University logo/theme and SPU timetable layout;
- faculty-aware colours: **NAS green, EMS purple, Education gold/yellow, Humanities orange**;
- faculty-first manual timetabling and cascading filters;
- lecturer filtering so normal modules use lecturers from the correct faculty, with explicit cross-faculty exceptions only;
- direct **Edit class** controls from the campus timetable;
- CSP-ranked Smart Suggestions for valid alternative room/time placements;
- human-readable clash, capacity, faculty and room-compatibility errors;
- a dedicated **Review Centre** with reviewer comments, request-changes, approval and resubmission;
- published-only Student and Lecturer timetable views;
- SPU-style PDF and Excel exports;
- in-app timetable notifications and independent hard-constraint validation.

## Demo logins

```text
Administrator
Username: admin
Password: admin123

Timetable Reviewer
Username: reviewer
Password: reviewer123
```

Synthetic student and lecturer credentials follow the existing demo rules. See `SAMPLE_LOGINS.txt` and `data/generated_credentials.csv` for examples.

## Intelligent manual timetabling

For manual work, use **Manual Timetabling** from the administrator navigation.

The intended flow is:

```text
Faculty → Programme → Year → Module → Lecturer → Student Group → Room
```

Choosing NAS restricts the downstream choices to NAS programmes/modules/groups and NAS-valid lecturers. Rooms are ranked with suitable faculty rooms first, then valid shared/fallback rooms. Changing a parent filter clears stale child selections.

For an existing class, open the campus timetable and choose **Edit class**. The edit drawer lets the administrator change the lecturer, venue, day/period, lock state, or use Smart Suggestions. Every save is revalidated before it is committed.

## Review workflow

The formal workflow is:

```text
DRAFT → IN_REVIEW → APPROVED → PUBLISHED
                   ↘ CHANGES_REQUESTED → IN_REVIEW
```

1. Admin validates the draft and selects **Send to review**.
2. The timetable is assigned to the Reviewer account.
3. Reviewer opens **Review Centre** and can add general or class-specific feedback.
4. Reviewer either **Request Changes** or **Approve**.
5. Class feedback includes a direct **Edit class** link for the administrator.
6. Admin resolves corrections and **Resubmit for Review**.
7. Reviewer approves after feedback is resolved.
8. Admin publishes the approved timetable. Student/Lecturer views then update.

A structural edit after approval invalidates approval and requires another review.

## Windows setup

Create the Python environment once:

```powershell
py -3.12 -m venv .venv
```

Then double-click `INSTALL_DESKTOP_APP.bat`. After setup, launch the desktop app with the supplied `.vbs` launcher. The application starts Flask locally and opens in PyWebView.

## Verification

Run the final acceptance check:

```powershell
.\.venv\Scripts\python.exe final_check.py
```

The final line must be:

```text
FINAL CHECK: PASS
```

Run the complete automated suite with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Important folders

```text
data/       synthetic source/generated CSVs
database/   schema, migrations, database and seed/restore tools
scheduler/  hybrid CSP scheduler and independent validator
services/   timetable, manual editing, review, exports and data services
templates/  SPU Admin/Reviewer/Student/Lecturer views
static/     SPU branding assets and CSS
tests/      automated verification
```
