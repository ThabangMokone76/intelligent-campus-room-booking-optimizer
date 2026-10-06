# SPU System Upgrade Master Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Coordinate the approved SPU timetable optimizer upgrade through four independently testable implementation plans while keeping the verified base safe.

**Architecture:** Execute the UI/data-presentation foundation first, then notifications/Admin workflow, then scheduler quality, and finally exports/desktop/final verification. Each sub-plan has its own TDD cycle and commits; later plans consume only explicit interfaces established by earlier plans.

**Tech Stack:** Python 3.12, Flask, Jinja2, SQLite, PyWebView, ReportLab, openpyxl, unittest.

**Spec:** `docs/superpowers/specs/2026-10-04-spu-system-upgrade-design.md`

## Global Constraints

- Work only in the upgrade copy, never the frozen `FINAL_WORKING` safety copy.
- Preserve the current verified synthetic population, role authentication, CSP foundation, validation rules, and Draft → Review → Published workflow.
- Do not add exam timetable generation, ML prediction, mobile, cloud, finance, HR, LMS, or multi-campus scope.
- The Admin campus timetable must reproduce the supplied SPU venue-by-period layout and visual conventions.
- Period 6 must become `12:45–13:20` everywhere.
- Completion requires zero hard violations and `final_check.py` PASS plus manual desktop export verification.

## Review Focus

- **Cross-plan interface drift:** export plan must consume the exact campus grid interface produced by the UI plan.
- **Database migration on verified synthetic DB:** additive changes must preserve users, registrations, versions, and timetable entries.
- **Role privacy after notifications/filters:** Student/Lecturer data must remain scoped to assignments.
- **Soft optimization regression:** scheduler quality changes must never weaken validator-enforced hard constraints.
- **Visual fidelity mistaken for static copying:** UI/export must use generated data while matching the supplied SPU timetable structure/style.

---

### Task 1: Execute SPU Branding, Timetable, and Role UI Plan

**Files:**
- Plan: `docs/superpowers/plans/2026-10-04-spu-branding-timetable-ui-plan.md`

**Interfaces:**
- Produces the runtime Period 6 migration, SPU campus timetable grid, Admin filters, branding shell, and role dashboards used by all later plans.

- [ ] Execute every task in the referenced plan using TDD and its listed verification commands.
- [ ] Run the referenced plan's final regression commands before proceeding.

### Task 2: Execute Notifications and Admin Workflow Plan

**Files:**
- Plan: `docs/superpowers/plans/2026-10-04-spu-notifications-admin-plan.md`

**Interfaces:**
- Produces notification schema/service/routes/UI and publication integration.

- [ ] Execute every task in the referenced plan.
- [ ] Confirm workflow and notification tests pass before scheduler changes.

### Task 3: Execute Scheduler Quality Plan

**Files:**
- Plan: `docs/superpowers/plans/2026-10-04-spu-scheduler-quality-plan.md`

**Interfaces:**
- Produces improved soft scoring while retaining existing CSP/hard-constraint behavior.

- [ ] Execute every task in the referenced plan.
- [ ] Confirm core and large synthetic scheduler tests pass with zero hard violations.

### Task 4: Execute Exports, Desktop, and Final Verification Plan

**Files:**
- Plan: `docs/superpowers/plans/2026-10-04-spu-exports-desktop-verification-plan.md`

**Interfaces:**
- Consumes all previous interfaces and produces final export/desktop/verification evidence.

- [ ] Execute every task in the referenced plan.
- [ ] Run full unittest discovery and `final_check.py`.
- [ ] Complete manual SPU visual comparison and desktop PDF/XLSX download checks before declaring completion.
