# Guided Manual Timetabling & Review Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the current SPU-branded timetable optimizer so administrators can edit and manually timetable classes through faculty-aware guided controls, while adding a real reviewer/feedback/approval workflow without replacing the approved SPU timetable UI.

**Architecture:** Extend the current Flask + SQLite application in place. Keep the existing SPU logo, SPU-branded navigation, timetable presentation, student/lecturer views, CSP engine, validation, locking, PDF export, and Excel export; add focused services for faculty context, manual editing, review workflow, and centralized faculty styling, then expose them through small Flask routes and dedicated templates.

**Tech Stack:** Python, Flask, SQLite, Jinja2, pytest, existing CSP scheduler/validator, existing PDF/Excel export stack, PyWebView desktop wrapper where already used.

**Spec:** `docs/superpowers/specs/2026-10-04-guided-manual-timetabling-review-workflow-design.md`

## Global Constraints

- The **current SPU-branded upgraded system is the base**. Preserve the existing SPU logo, branding, layout, navigation style, and approved timetable presentation.
- Do not fall back to the older TNU-looking UI when merging this work.
- Keep existing student and lecturer timetable views read-only and PUBLISHED-only.
- Preserve current CSP generation, validator, locking, exports, and synthetic dataset behaviour unless a task below explicitly changes an interface.
- Faculty colours must be centralized and consistent: NAS = Green, EMS = Purple, Education = Gold/Yellow, Humanities = Orange.
- Normal module lecturer eligibility requires matching faculty; cross-faculty teaching must be explicit.
- Valid workflow statuses are `DRAFT`, `IN_REVIEW`, `CHANGES_REQUESTED`, `APPROVED`, `PUBLISHED`.
- Publication requires APPROVED status and zero hard violations.
- Any structural timetable edit after approval invalidates approval and returns the version to DRAFT while preserving review history.
- Never destroy the last known-good database. Schema upgrades must be additive/migratable and tested on a copy first.
- Do not replace the existing approved timetable visual design with drag-and-drop.

## Review Focus

- **Stale dependent selection:** changing EMS → NAS must clear programme/year/module/lecturer/group values that no longer belong to the active context.
- **Legacy wrong-faculty assignment:** an existing invalid lecturer remains visible as a warning on that class but cannot be silently re-saved as valid.
- **Concurrent manual move:** room/lecturer/group availability must be revalidated at save time, not only when suggestions are first shown.
- **Post-approval edit:** changing room, time, lecturer, duration, or group after approval must invalidate the prior approval before publication.
- **Reviewer scope:** a faculty-restricted reviewer must never approve or comment on a timetable outside their authorized faculty scope.

---

## File Structure Map

Existing files to preserve and extend:

- `app.py` — Flask routes, auth guards, page wiring.
- `database/schema.sql` — canonical schema for fresh databases.
- `database/upgrade_existing.py` — additive migration path for existing databases.
- `database/db.py` — existing DB connection helper.
- `services/timetable_service.py` — existing timetable/version workflow integration.
- `scheduler/validator.py` — existing hard-constraint validation source of truth.
- `scheduler/engine.py` — existing CSP candidate-generation/search logic.
- `services/export_service.py` — PDF/Excel export integration.
- `templates/base.html` — keep SPU logo/branding and add navigation links only.
- `templates/timetable.html` — preserve approved timetable design; add direct Edit hooks.
- `templates/admin.html` / `templates/dashboard.html` — surface workflow status/notifications where appropriate.
- `static/style.css` — extend existing SPU-branded style system, do not replace it.
- `tests/test_workflow.py` — extend workflow/publication tests.
- `tests/test_scheduler_core.py` — preserve constraint regression coverage.

New focused files:

- `services/faculty_context_service.py` — cascading faculty/programme/year/module/lecturer/group/room queries.
- `services/manual_timetable_service.py` — editable class model, candidate placements, save/lock operations.
- `services/review_service.py` — submit/review/comment/approve/request-changes/resubmit/history.
- `services/faculty_style_service.py` — single faculty colour mapping.
- `templates/manual_timetabling.html` — guided manual workspace.
- `templates/review_centre.html` — reviewer/admin review UI.
- `tests/test_faculty_context.py`
- `tests/test_manual_timetabling.py`
- `tests/test_review_workflow.py`
- `tests/test_faculty_style.py`

---

### Task 1: Freeze the SPU-branded baseline and add regression guards

**Files:**
- Modify: `tests/test_workflow.py`
- Create: `tests/test_spu_branding_regression.py`

**Interfaces:**
- Consumes: current SPU-branded templates and routes.
- Produces: regression tests that prevent removal of the SPU logo/brand shell and approved timetable route during later tasks.

- [ ] Write tests that pin the current SPU logo/header, admin timetable route, and student/lecturer published timetable routes.
- [ ] Run `pytest tests/test_spu_branding_regression.py tests/test_workflow.py -v`.
- [ ] Confirm the current SPU baseline passes before changing implementation.
- [ ] Commit with `test: protect SPU branded timetable baseline`.

---

### Task 2: Centralize faculty colours and ownership helpers

**Files:**
- Create: `services/faculty_style_service.py`
- Create: `tests/test_faculty_style.py`
- Modify: `templates/timetable.html`
- Modify: `templates/personal_timetable.html`
- Modify: `static/style.css`
- Modify: `services/export_service.py`

**Interfaces:**
- Produces: `get_faculty_style(faculty_code: str) -> dict[str, str]`.

- [ ] Write failing tests for NAS green, EMS purple, Education gold/yellow, Humanities orange, plus unknown-faculty fallback.
- [ ] Run `pytest tests/test_faculty_style.py -v` and verify failure.
- [ ] Implement one central faculty-style mapping.
- [ ] Replace page/export-local colour decisions with the central service without changing SPU layout.
- [ ] Run faculty-style and branding regression tests.
- [ ] Commit with `feat: centralize faculty styling`.

---

### Task 3: Add schema migration for reviewer workflow and cross-faculty teaching

**Files:**
- Modify: `database/schema.sql`
- Modify: `database/upgrade_existing.py`
- Create: `tests/test_review_workflow.py`

**Interfaces:**
- Produces DB entities: `reviewer_faculties`, `timetable_reviews`, `review_comments`.
- Extends user role support with `REVIEWER`.

- [ ] Write migration tests for reviewer tables, role support, timetable-level/class-level comments, and explicit cross-faculty eligibility.
- [ ] Run tests and verify failure.
- [ ] Extend fresh schema.
- [ ] Add additive migration for existing SPU database.
- [ ] Test migration on a copied database and verify no timetable/student/lecturer data loss.
- [ ] Commit with `feat: add timetable review schema`.

---

### Task 4: Implement faculty-context cascading queries

**Files:**
- Create: `services/faculty_context_service.py`
- Create: `tests/test_faculty_context.py`
- Modify: `app.py`

**Interfaces:**
- `get_programmes(faculty_id: int) -> list[dict]`
- `get_years(programme_id: int) -> list[int]`
- `get_modules(programme_id: int, year_level: int) -> list[dict]`
- `get_lecturers(module_id: int, slot_ids: list[int] | None = None) -> list[dict]`
- `get_student_groups(programme_id: int, year_level: int) -> list[dict]`
- `get_ranked_rooms(module_id: int, expected_students: int, slot_ids: list[int] | None = None) -> list[dict]`

- [ ] Write tests covering NAS-only results, year/module narrowing, wrong-faculty lecturer exclusion, cross-faculty exception, inactive staff, and stale selections.
- [ ] Run tests and verify failure.
- [ ] Implement service using existing faculty/department/programme/module/staff links.
- [ ] Add small authenticated admin JSON endpoints in `app.py`.
- [ ] Run context + workflow tests.
- [ ] Commit with `feat: add faculty aware timetable context`.

---

### Task 5: Audit and repair synthetic lecturer/module faculty mismatches

**Files:**
- Modify: `services/synthetic_load_service.py`
- Modify: `services/synthetic_population.py`
- Modify: `final_check.py`
- Modify: `tests/test_synthetic_population.py`

- [ ] Add tests that generated normal-module assignments never cross faculty.
- [ ] Add a test that imported/real mismatches are warned about instead of silently rewritten.
- [ ] Update synthetic generation/loading so generated demo data is repaired safely.
- [ ] Extend `final_check.py` with faculty-assignment audit.
- [ ] Run `pytest tests/test_synthetic_population.py -v && python final_check.py`.
- [ ] Commit with `fix: enforce lecturer faculty ownership`.

---

### Task 6: Add manual timetable service with explainable validation

**Files:**
- Create: `services/manual_timetable_service.py`
- Create: `tests/test_manual_timetabling.py`
- Modify: `services/timetable_service.py`
- Modify: `scheduler/validator.py`

**Interfaces:**
- `get_editable_entry(entry_id: int, version_id: int) -> dict`
- `validate_manual_change(entry_id: int, proposal: dict) -> dict`
- `save_manual_change(entry_id: int, proposal: dict, actor_user_id: int) -> dict`
- `set_entry_lock(entry_id: int, locked: bool, actor_user_id: int) -> None`

Validation result:
`{valid: bool, errors: list[str], warnings: list[str], alternatives: list[dict]}`

- [ ] Write failing tests for lecturer clash, student clash, room clash, capacity, room type/equipment, practical continuity, locked entry, wrong faculty, and stale room availability.
- [ ] Run tests and verify failure.
- [ ] Implement manual service using the existing validator as source of truth.
- [ ] Add human-readable validation explanations.
- [ ] Invalidate APPROVED status on structural save and preserve review history.
- [ ] Run manual + scheduler + workflow regression tests.
- [ ] Commit with `feat: add validated manual timetable editing`.

---

### Task 7: Reuse CSP logic for smart placement suggestions

**Files:**
- Modify: `services/manual_timetable_service.py`
- Modify: `scheduler/engine.py`
- Modify: `tests/test_manual_timetabling.py`

**Interfaces:**
- `suggest_placements(entry_id: int, limit: int = 5) -> list[dict]`

- [ ] Add tests ensuring suggestions satisfy all hard constraints.
- [ ] Add tests that same-faculty rooms and better capacity fit rank ahead of weaker valid fallbacks.
- [ ] Expose a non-destructive candidate-ranking helper from the existing CSP engine.
- [ ] Implement `suggest_placements()`.
- [ ] Run manual + scheduler + large-scheduler tests.
- [ ] Commit with `feat: add CSP based manual placement suggestions`.

---

### Task 8: Build the SPU-branded Manual Timetabling workspace

**Files:**
- Create: `templates/manual_timetabling.html`
- Modify: `templates/base.html`
- Modify: `static/style.css`
- Modify: `app.py`
- Modify: `tests/test_manual_timetabling.py`

**Route:** `/manual-timetabling`

- [ ] Add tests for admin access, non-admin denial, NAS filtering, stale-child clearing, faculty context badge, and preserved SPU logo/header.
- [ ] Add Manual Timetabling navigation to existing SPU `base.html` without replacing the header/logo.
- [ ] Build context bar, class list, Smart Placement panel, and current timetable area.
- [ ] Add cascading client behaviour using Task 4 endpoints.
- [ ] Run manual + SPU branding regression tests.
- [ ] Commit with `feat: add guided manual timetabling workspace`.

---

### Task 9: Add direct Edit action to timetable class blocks

**Files:**
- Modify: `templates/timetable.html`
- Modify: `static/style.css`
- Modify: `app.py`
- Modify: `tests/test_manual_timetabling.py`

- [ ] Add tests that editable DRAFT classes expose Edit while published/student/lecturer views remain read-only.
- [ ] Add obvious Edit action without changing the approved timetable block design.
- [ ] Add side panel/modal for lecturer, room, day/time, duration/session type, lock state, Smart Suggestions, Save, Cancel.
- [ ] Preserve user-entered values after validation failure.
- [ ] Show human-readable validation reasons inline.
- [ ] Run manual + branding tests.
- [ ] Commit with `feat: add direct timetable class editing`.

---

### Task 10: Implement ReviewService and the five-status lifecycle

**Files:**
- Create: `services/review_service.py`
- Modify: `services/timetable_service.py`
- Modify: `tests/test_review_workflow.py`
- Modify: `tests/test_workflow.py`

**Interfaces:**
- `submit_for_review(version_id: int, admin_user_id: int, reviewer_user_id: int | None = None) -> int`
- `add_comment(review_id: int, author_user_id: int, text: str, entry_id: int | None = None) -> int`
- `resolve_comment(comment_id: int, user_id: int) -> None`
- `request_changes(review_id: int, reviewer_user_id: int, summary: str) -> None`
- `approve_review(review_id: int, reviewer_user_id: int, summary: str | None = None) -> None`
- `resubmit_review(version_id: int, admin_user_id: int) -> int`
- `can_publish(version_id: int) -> tuple[bool, list[str]]`

- [ ] Write tests for every valid/invalid status transition and reviewer scope.
- [ ] Implement ReviewService.
- [ ] Replace old REVIEW shortcut with DRAFT / IN_REVIEW / CHANGES_REQUESTED / APPROVED / PUBLISHED.
- [ ] Enforce APPROVED + zero hard violations + unchanged approved content before publish.
- [ ] Run review + workflow tests.
- [ ] Commit with `feat: add timetable review lifecycle`.

---

### Task 11: Build Review Centre for reviewer and administrator

**Files:**
- Create: `templates/review_centre.html`
- Modify: `templates/base.html`
- Modify: `static/style.css`
- Modify: `app.py`
- Modify: `tests/test_review_workflow.py`

- [ ] Add tests for reviewer scope, timetable/class comments, unresolved feedback count, direct Edit links, approve/request changes, and admin resubmit.
- [ ] Add Review Centre navigation while preserving SPU branding.
- [ ] Implement reviewer and admin modes.
- [ ] Add review history and unresolved-comment presentation.
- [ ] Run review + SPU branding tests.
- [ ] Commit with `feat: add timetable review centre`.

---

### Task 12: Add reviewer demo account and role-aware navigation

**Files:**
- Modify: `database/seed_synthetic.py`
- Modify: `SAMPLE_LOGINS.txt`
- Modify: `templates/base.html`
- Modify: `tests/test_review_workflow.py`

- [ ] Add tests for fictional REVIEWER demo account, hashed password, and minimal reviewer navigation.
- [ ] Seed reviewer account without using a real SPU staff identity.
- [ ] Add role-aware navigation.
- [ ] Run review tests.
- [ ] Commit with `feat: add demo timetable reviewer role`.

---

### Task 13: Update exports and status presentation

**Files:**
- Modify: `services/export_service.py`
- Modify: `templates/timetable.html`
- Modify: `templates/dashboard.html`
- Modify: `tests/test_workflow.py`
- Modify: `tests/test_faculty_style.py`

- [ ] Add tests for five-status labels and export faculty-colour consistency.
- [ ] Update status badges/actions.
- [ ] Update PDF/Excel faculty colour/status logic where supported.
- [ ] Run workflow + faculty-style tests.
- [ ] Commit with `feat: align exports with faculty and review workflow`.

---

### Task 14: Full end-to-end and regression verification

**Files:**
- Modify: `final_check.py`
- Modify: `README.md`
- Modify: `tests/test_workflow.py`
- Modify: `tests/test_large_scheduler.py`

- [ ] Extend `final_check.py` to verify SPU branding, faculty ownership, zero hard violations, reviewer schema/account, workflow integrity, and export generation.
- [ ] Add end-to-end flow: Admin selects NAS → narrows programme/year/module → gets valid lecturers/rooms → edits → submits → reviewer comments/request changes → admin fixes/resubmits → reviewer approves → admin publishes → student/lecturer see published timetable.
- [ ] Run `pytest -v`.
- [ ] Run `python final_check.py`.
- [ ] Smoke-test UI and confirm the SPU logo/current upgraded design remain unchanged.
- [ ] Update README for manual editing and reviewer workflow.
- [ ] Commit with `test: verify guided timetabling and review workflow`.

---

## Final Acceptance Gate

The implementation is ready only when all are true:

1. The upgraded **SPU-branded UI and logo are still present**.
2. The approved timetable display has not been replaced.
3. NAS selection restricts programme, year, module, lecturer, group, and room choices appropriately.
4. Wrong-faculty normal lecturer assignments are blocked and explained.
5. Manual editing is accessible directly from timetable class blocks.
6. Manual Timetabling offers only hard-valid smart placement suggestions.
7. Validation errors explain exactly what clashes or fails.
8. Faculty colours are consistent: NAS green, EMS purple, Education gold/yellow, Humanities orange.
9. REVIEWER role and Review Centre exist.
10. General and class-specific feedback works.
11. Admin can fix feedback and resubmit.
12. Reviewer can approve/request changes only within allowed scope.
13. Post-approval structural edits invalidate approval.
14. Publish requires APPROVED + zero hard violations.
15. Student and lecturer views remain published-only.
16. PDF and Excel exports still work.
17. Existing scheduler tests still pass at campus-scale synthetic data.
18. `python final_check.py` passes on the final demo database.
