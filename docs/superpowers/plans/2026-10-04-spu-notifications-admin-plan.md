# SPU Notifications and Admin Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reliable in-app timetable notifications and improve Admin workflow controls while preserving Draft → Review → Published safety and role isolation.

**Architecture:** Add one notification table plus a focused notification service. Notification creation is tied to publication and recipient assignment data, while reading/marking notifications is exposed through small Flask routes. Existing `set_version_status`, `move_part`, and `set_part_lock` remain the source of timetable workflow truth.

**Tech Stack:** Python 3.12, Flask, SQLite, Jinja2, unittest.

**Spec:** `docs/superpowers/specs/2026-10-04-spu-system-upgrade-design.md`

## Global Constraints

- Notifications are in-app only in this upgrade; email remains deferred.
- Notification recipients must be scoped from actual Student section assignments and Lecturer offering assignments.
- Student/Lecturer users must never receive another user's class details.
- Workflow remains strictly `DRAFT → REVIEW → PUBLISHED`.
- Publish remains blocked whenever independent validation reports any hard violation.
- Manual move and lock actions remain DRAFT-only.
- Notification writes must be transactional with publication or visibly reported if executed as a controlled follow-up; they must not fail silently.

## Review Focus

- **First-ever publish with no previous published version:** assigned users should get a publish notification; pinned in Task 2.
- **Replacement publish with one changed class:** only affected students/lecturers receive class-change details; pinned in Task 2.
- **User with zero notifications:** bell count and page render zero cleanly; pinned in Task 3.
- **User attempts to mark another user's notification as read:** no row changes; pinned in Task 3.
- **Publish with hard violations:** status and notifications must both remain unchanged; pinned in Task 4.

---

### Task 1: Add Notification Schema

**Files:**
- Modify: `database/schema.sql`
- Test: `tests/test_notifications_schema.py`

**Interfaces:**
- Produces: `notifications(notification_id, recipient_user_id, notification_type, title, message, version_id, entry_id, created_at, read_at)` plus indexes on recipient/read state and version.

- [ ] **Step 1: Write failing schema test**

Assert a fresh database has the `notifications` table, foreign keys to `users`, `timetable_versions`, and optionally `timetable_entries`, plus recipient/read and version indexes.

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_notifications_schema -v
```

Expected: FAIL because the table does not exist.

- [ ] **Step 3: Add the additive schema objects**

Add the notification table with `ON DELETE CASCADE` for recipient user, `ON DELETE CASCADE` for version, `ON DELETE SET NULL` for entry, and nullable `read_at`.

- [ ] **Step 4: Run schema and foreign-key tests**

Expected: PASS with empty `PRAGMA foreign_key_check`.

- [ ] **Step 5: Commit**

```bash
git add database/schema.sql tests/test_notifications_schema.py
git commit -m "feat: add in-app notification schema"
```

### Task 2: Implement Notification Service and Publication Diffing

**Files:**
- Create: `services/notification_service.py`
- Test: `tests/test_notification_service.py`

**Interfaces:**
- Produces: `unread_count(conn, user_id: int) -> int`.
- Produces: `list_notifications(conn, user_id: int, limit: int = 100) -> list[dict]`.
- Produces: `mark_read(conn, user_id: int, notification_id: int) -> bool`.
- Produces: `mark_all_read(conn, user_id: int) -> int`.
- Produces: `create_publish_notifications(conn, new_version_id: int, previous_version_id: int | None) -> int`, with no internal commit.

- [ ] **Step 1: Write failing service tests**

Cover unread count, mark-read ownership, first publish recipient creation, replacement publish time change, venue change, and unrelated-user exclusion.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_notification_service -v
```

Expected: FAIL because the service does not exist.

- [ ] **Step 3: Implement read/list helpers**

All notification reads and updates must require `recipient_user_id=?` in SQL.

- [ ] **Step 4: Implement publication diffing**

Compare old/new entry signatures by `(part_id, section_id)` and classify changed day/period as `TIME_CHANGED`, changed room as `VENUE_CHANGED`, combined changes as `CLASS_MOVED`, and initial publication as `TIMETABLE_PUBLISHED`. Resolve recipients from `section_student_assignments → users.student_id` and `session template offering → offering_staff → users.staff_id`.

- [ ] **Step 5: Run service tests**

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/notification_service.py tests/test_notification_service.py
git commit -m "feat: add timetable notification service"
```

### Task 3: Add Notification Routes, Bell, and Page

**Files:**
- Modify: `app.py`
- Modify: `templates/base.html`
- Create: `templates/notifications.html`
- Modify: `static/style.css`
- Test: `tests/test_notifications_routes.py`

**Interfaces:**
- Consumes: Task 2 notification service.
- Produces: `GET /notifications`, `POST /notifications/<int:notification_id>/read`, `POST /notifications/read-all`.
- Produces: `unread_notifications` global template value for authenticated users.

- [ ] **Step 1: Write failing route tests**

Assert authenticated users can list their own notifications, unread count renders zero cleanly, mark-read changes only owned rows, and anonymous users are redirected to login.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_notifications_routes -v
```

Expected: FAIL because routes/template do not exist.

- [ ] **Step 3: Extend `inject_globals()` safely**

Fetch current user once, and if authenticated add `unread_notifications=unread_count(...)`; do not query notifications for anonymous requests.

- [ ] **Step 4: Add notification routes and template**

Render newest-first items with type badge, title, message, created time, read/unread state, individual mark-read, and mark-all-read.

- [ ] **Step 5: Add bell to authenticated shell**

Show `Notifications`/bell plus unread count badge in role-aware navigation.

- [ ] **Step 6: Run route/auth regressions**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_notifications_routes tests.test_auth_synthetic -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app.py templates/base.html templates/notifications.html static/style.css tests/test_notifications_routes.py
git commit -m "feat: add in-app notification UI"
```

### Task 4: Integrate Notifications with Safe Publication

**Files:**
- Modify: `services/timetable_service.py`
- Test: `tests/test_workflow.py`
- Test: `tests/test_notification_service.py`

**Interfaces:**
- Consumes: `create_publish_notifications` from Task 2.
- Produces: `set_version_status(conn, version_id, status)` that atomically validates, identifies previous published version, updates statuses, creates notifications, and commits once for PUBLISHED transitions.

- [ ] **Step 1: Add failing workflow tests**

Add `test_publish_creates_notifications_only_after_validation()` and `test_failed_publish_rolls_back_status_and_notifications()`.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_workflow tests.test_notification_service -v
```

Expected: FAIL because publication does not create notifications.

- [ ] **Step 3: Make publication transactional**

For `PUBLISHED`: validate first; read current published version before status changes; update old/new statuses; call `create_publish_notifications` on the same connection; commit once. On any exception, rollback and re-raise.

- [ ] **Step 4: Keep REVIEW transition unchanged except for explicit transaction safety**

No notifications are created for REVIEW.

- [ ] **Step 5: Run workflow and notification tests**

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/timetable_service.py tests/test_workflow.py tests/test_notification_service.py
git commit -m "feat: notify affected users on publication"
```

### Task 5: Improve Admin Workflow Controls and Rejection Feedback

**Files:**
- Modify: `app.py`
- Modify: `templates/dashboard.html`
- Modify: `templates/timetable.html`
- Modify: `templates/admin.html`
- Modify: `templates/validation.html`
- Modify: `static/style.css`
- Test: `tests/test_admin_workflow_ui.py`

**Interfaces:**
- Consumes: existing Admin POST routes and validation report.
- Produces: grouped Generate/Validate, Edit/Move/Lock, Workflow, Import/Export controls with confirmation prompts on regenerate/publish.
- Produces: Admin dashboard `recent_activity` showing latest timetable publications/changes without exposing duplicate per-recipient notification rows.

- [ ] **Step 1: Write failing Admin UI smoke tests**

Assert publish/regenerate forms include confirmation behavior, status badges render, locked rows/cells expose a visible lock state, validation zero state says the timetable is publishable, and Admin dashboard renders a concise recent timetable activity section.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_admin_workflow_ui -v
```

Expected: FAIL on missing grouped/confirmation markup.

- [ ] **Step 3: Group controls and add confirmations**

Use simple browser `confirm()` on high-impact forms; do not add a JavaScript framework.

- [ ] **Step 4: Add concise recent timetable activity to the Admin dashboard**

Query recent timetable versions/publication timestamps plus distinct recent change summaries for display; avoid listing the same event once per notification recipient.

- [ ] **Step 5: Preserve safe validation rendering**

Use bracket notation for dictionary keys in `validation.html` (`report['items']`, `report['total']`, `report['categories']`) so Jinja never resolves `dict.items` as a method.

- [ ] **Step 6: Run Admin/workflow tests**

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app.py templates/dashboard.html templates/timetable.html templates/admin.html templates/validation.html static/style.css tests/test_admin_workflow_ui.py
git commit -m "feat: improve admin timetable workflow controls"
```
