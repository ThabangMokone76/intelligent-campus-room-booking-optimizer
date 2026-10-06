# SPU Branding, Timetable, and Role UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the SPU-branded desktop/web UI, exact SPU-style campus timetable presentation, Period 6 alignment, filters, and improved Student/Lecturer dashboards without changing scheduling feasibility logic.

**Architecture:** Keep Flask/Jinja/PyWebView and the existing role model. Add a focused timetable presentation service that transforms scheduled entries into day → venue → period cells, while keeping the existing personal weekly grid. Apply additive runtime migration for Period 6 and reusable SPU design tokens/assets across templates.

**Tech Stack:** Python 3.12, Flask, Jinja2, SQLite, HTML/CSS, PyWebView, unittest.

**Spec:** `docs/superpowers/specs/2026-10-04-spu-system-upgrade-design.md`

## Global Constraints

- The campus output is a Monday–Friday academic teaching timetable, never an exam timetable.
- Admin campus timetable must use separate day grids with `VENUE`, `CAPACITY`, and Periods `1`–`10` horizontally.
- Period 6 must be exactly `12:45–13:20` in seed data, synthetic loading, migrated existing databases, views, and exports.
- Consecutive two-period sessions must repeat the module code in both occupied cells in the campus timetable.
- Student and Lecturer users continue to see only PUBLISHED timetable data relevant to them.
- SPU red/orange/white branding must not weaken text contrast or timetable readability.
- Existing scheduler hard constraints and database population are not redesigned in this plan.
- Use the user-supplied SPU logo image as the branding source; do not substitute a third-party logo.

## Review Focus

- **Existing populated database with old Period 6:** startup must update only the time definition without deleting timetable/user data; pinned in Task 1 migration test.
- **Two-period class at Period 9:** campus grid must occupy P9 and P10, never P11; pinned in Task 2 grid test.
- **Multi-room synchronized section:** each room row must receive the module in the same periods rather than collapsing rooms together; pinned in Task 2 grid test.
- **Admin filter with no matches:** page must render an empty timetable state, not crash or fall back to all data; pinned in Task 3 filter test.
- **Student/Lecturer direct access to non-published version:** role isolation must remain enforced; pinned in Task 5 regression test.

---

### Task 1: Align Period 6 Safely in Fresh and Existing Databases

**Files:**
- Create: `database/migrations.py`
- Modify: `database/seed_demo.py`
- Modify: `services/synthetic_load_service.py`
- Modify: `database/bootstrap.py`
- Test: `tests/test_time_slot_migration.py`

**Interfaces:**
- Consumes: `database.db.connect(path=None)`, `database.db.init_database(path=None)`.
- Produces: `apply_runtime_migrations(conn) -> None` and a stable Period 6 value of `12:45`–`13:20` for all five weekdays.

- [ ] **Step 1: Write the failing Period 6 tests**

Add tests named `test_fresh_demo_uses_spu_period_6_time()` and `test_runtime_migration_updates_old_period_6_without_deleting_data()` asserting all five Period 6 rows equal `('12:45','13:20')` and a sentinel user/timetable row survives migration.

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_time_slot_migration -v
```

Expected: FAIL because the current demo/synthetic definitions use `12:35`.

- [ ] **Step 3: Implement runtime migration and update seed sources**

Create `database/migrations.py` with `apply_runtime_migrations(conn) -> None`, performing one transactional `UPDATE time_slots SET start_time='12:45', end_time='13:20' WHERE period_number=6`, followed by `PRAGMA foreign_key_check`. Update `database/seed_demo.py` and `services/synthetic_load_service.py` to seed `12:45`.

- [ ] **Step 4: Call the migration from bootstrap paths**

Update `ensure_synthetic_ready(path=None)` and `ensure_demo_ready(path=None)` so migration runs after schema initialization/restoration and before returning.

- [ ] **Step 5: Run migration tests and bootstrap regressions**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_time_slot_migration tests.test_synthetic_bootstrap tests.test_auth_bootstrap -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add database/migrations.py database/seed_demo.py services/synthetic_load_service.py database/bootstrap.py tests/test_time_slot_migration.py
git commit -m "fix: align period six with SPU timetable"
```

### Task 2: Add an SPU Campus Timetable View Model

**Files:**
- Create: `services/timetable_view_service.py`
- Modify: `services/timetable_service.py`
- Test: `tests/test_spu_timetable_grid.py`

**Interfaces:**
- Consumes: `timetable_rows(conn, version_id, user=None, filters=None) -> list[dict]`.
- Produces: `campus_timetable_grid(conn, rows: list[dict]) -> dict`, returning ordered day sections with active room metadata and cell lists for periods 1–10.
- Produces: `campus_filter_options(conn, semester_id: int) -> dict[str, list[dict]]`.

- [ ] **Step 1: Write failing grid tests**

Add tests for `test_grid_is_day_then_venue_then_period()`, `test_two_period_session_repeats_in_both_cells()`, `test_period_nine_duration_two_stops_at_period_ten()`, and `test_multi_room_part_appears_in_each_room_row()`.

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_spu_timetable_grid -v
```

Expected: FAIL because the service does not exist.

- [ ] **Step 3: Extend `timetable_rows` for optional admin filters**

Change signature to `timetable_rows(conn, version_id, user=None, filters=None)` and support keys `faculty_id`, `programme_id`, `year_level`, `module_id`, `staff_id`, `room_id`, and `day`, using parameterized SQL and `EXISTS` joins for programme/year/staff filters.

- [ ] **Step 4: Implement campus grid transformation**

Implement `campus_timetable_grid(conn, rows)` so every active room is available as a venue row, room capacity is attached, and each timetable row is copied into every occupied period from `period_number` through `period_number + duration_slots - 1`.

- [ ] **Step 5: Implement filter option lookup**

Implement `campus_filter_options(conn, semester_id)` returning only values relevant to the active semester, sorted for UI display.

- [ ] **Step 6: Run grid and personal timetable regressions**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_spu_timetable_grid tests.test_personal_timetable -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add services/timetable_view_service.py services/timetable_service.py tests/test_spu_timetable_grid.py
git commit -m "feat: add SPU campus timetable grid model"
```

### Task 3: Add Admin Timetable Filters Without Changing Timetable Data

**Files:**
- Modify: `app.py`
- Modify: `templates/timetable.html`
- Test: `tests/test_timetable_filters.py`

**Interfaces:**
- Consumes: `campus_filter_options(conn, semester_id)` and `campus_timetable_grid(conn, rows)` from Task 2.
- Produces: `/timetable` GET query filters and an SPU campus grid context for Admin; personal roles continue using the existing weekly grid.

- [ ] **Step 1: Write failing route/filter tests**

Add tests proving a valid `room_id` filter returns only that venue's scheduled entries, an unmatched filter returns zero entries without an exception, and a Student cannot use query filters to reveal another student's classes.

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_timetable_filters -v
```

Expected: FAIL because Admin filters are not supported.

- [ ] **Step 3: Parse and validate Admin-only query filters in `/timetable`**

Build a `filters` dict only for Admin users and pass it to `timetable_rows`; ignore campus filter parameters for non-admin users.

- [ ] **Step 4: Render the SPU venue-by-period timetable**

Replace the current flat Admin timetable table with separate Monday–Friday day sections containing title/day strip, `VENUE`, `CAPACITY`, P1–P10 headers, exact period times, black borders, white empty cells, faculty colour fills, and repeated multi-period module codes. Keep Admin move/lock controls accessible through a compact selected-cell/detail area rather than adding controls to every grid cell.

- [ ] **Step 5: Add filter form and clear-filter action**

Render Faculty, Programme, Year, Module, Lecturer, Room, and Day selectors using Task 2 options and preserve `version_id` while filtering.

- [ ] **Step 6: Run filter and workflow tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_timetable_filters tests.test_workflow tests.test_personal_timetable -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app.py templates/timetable.html tests/test_timetable_filters.py
git commit -m "feat: render filterable SPU campus timetable"
```

### Task 4: Apply SPU Branding to Login and Application Shell

**Files:**
- Create: `static/images/spu-logo.png`
- Create: `static/images/spu-crest.png`
- Modify: `templates/base.html`
- Modify: `templates/login.html`
- Modify: `static/style.css`
- Test: `tests/test_spu_branding.py`

**Interfaces:**
- Consumes: the user-supplied SPU logo image.
- Produces: reusable `.spu-*` CSS design tokens/classes and static logo paths referenced by Jinja templates.

- [ ] **Step 1: Write failing branding smoke tests**

Add route tests asserting `/login` contains `Sol Plaatje University Timetable Optimizer`, the SPU logo static path, and the authenticated shell renders role-aware navigation.

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_spu_branding -v
```

Expected: FAIL because the current UI is generic.

- [ ] **Step 3: Create the two approved SPU assets**

Create `spu-logo.png` for the login view and `spu-crest.png` for the compact shell from the supplied image; keep transparent/white surroundings clean and do not fetch a replacement logo from the web.

- [ ] **Step 4: Rebuild login and shell styling**

Use CSS variables for SPU red, orange, white, charcoal, success green, and error red. Add the full logo to login, compact crest inside, product title/subtitle, role-aware sidebar/header, responsive content width, readable focus/hover states, and restrained watermark treatment.

- [ ] **Step 5: Run branding tests and manual contrast check**

Run the branding tests and inspect login plus one authenticated page in the desktop shell.

Expected: PASS; no text becomes unreadable over the logo/watermark.

- [ ] **Step 6: Commit**

```bash
git add static/images/spu-logo.png static/images/spu-crest.png templates/base.html templates/login.html static/style.css tests/test_spu_branding.py
git commit -m "feat: apply Sol Plaatje University branding"
```

### Task 5: Upgrade Role-Specific Dashboards and Personal Timetable Presentation

**Files:**
- Create: `services/dashboard_service.py`
- Modify: `app.py`
- Modify: `templates/dashboard.html`
- Modify: `templates/personal_timetable.html`
- Test: `tests/test_role_dashboards.py`
- Test: `tests/test_personal_timetable.py`

**Interfaces:**
- Produces: `personal_dashboard_context(conn, version_id: int | None, user: dict, today: str | None = None, now_time: str | None = None) -> dict`.
- Consumes: `timetable_rows` for role-scoped classes.

- [ ] **Step 1: Write failing Student/Lecturer dashboard tests**

Assert Student context exposes only their classes/modules/venues, Lecturer context exposes only assigned offerings, `today` and `next_class` derive from role-scoped rows, and neither role can reveal a DRAFT timetable by direct `version_id` query.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_role_dashboards tests.test_personal_timetable -v
```

Expected: FAIL because role-specific dashboard context does not exist.

- [ ] **Step 3: Implement role dashboard context**

Implement `personal_dashboard_context` with injectable day/time for deterministic tests; return `today_classes`, `next_class`, unique modules, and unique venues.

- [ ] **Step 4: Update dashboard and personal timetable templates**

Admin retains campus metrics/actions. Student gets Today's Classes, Next Class, My Timetable, Modules, Venues. Lecturer gets Today's Teaching, Next Teaching Session, Assigned Modules, Groups, Venues. Keep the personal Monday–Friday grid because it is more readable than the full campus venue grid.

- [ ] **Step 5: Run role, auth, and personal timetable regressions**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_role_dashboards tests.test_personal_timetable tests.test_auth_synthetic -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/dashboard_service.py app.py templates/dashboard.html templates/personal_timetable.html tests/test_role_dashboards.py tests/test_personal_timetable.py
git commit -m "feat: upgrade student and lecturer experience"
```
