# Guided Manual Timetabling & Review Workflow — Design Specification

Date: 2026-10-04  
Project: Intelligent Campus Room Booking Optimizer  
Status: Approved design, awaiting implementation-plan approval

## 1. Purpose

Upgrade the existing timetable optimizer without replacing the current approved timetable display. The upgrade focuses on making manual timetable editing, faculty filtering, lecturer assignment, faculty colouring, validation feedback, and timetable review simple, intelligent, and user-friendly.

The system must guide administrators through valid choices instead of showing unrelated options. It must also support a real review/feedback lifecycle before publication.

## 2. Core UX Principle

The interface is context-driven.

When an administrator selects a faculty, every dependent control must be restricted to data relevant to that faculty unless a shared/cross-faculty exception applies.

Example:

Faculty = Natural and Applied Sciences (NAS)
→ departments = NAS only
→ programmes = NAS only
→ years = valid years for selected programme
→ modules = modules for selected programme/year
→ lecturers = valid lecturers for selected module/faculty
→ student groups = matching programme/year groups
→ rooms = suitable NAS rooms first, then valid shared/fallback rooms

The administrator should never have to search through unrelated faculties, lecturers, modules, or student groups.

## 3. Scope

### Included

- Keep the existing timetable presentation.
- Add guided manual timetabling.
- Add direct class editing from timetable entries.
- Add dependent/cascading faculty filters.
- Enforce faculty-correct lecturer assignment.
- Add faculty-aware room suggestions.
- Add smart placement suggestions using existing scheduling constraints.
- Show human-readable reasons when a move is invalid.
- Centralize faculty colours.
- Add a reviewer role.
- Add a Review Centre.
- Add timetable-level and class-level feedback.
- Add approve/request-changes/resubmit workflow.
- Add statuses DRAFT, IN_REVIEW, CHANGES_REQUESTED, APPROVED, PUBLISHED.
- Keep student and lecturer timetable views read-only and published-only.
- Preserve existing validation, locking, generation, export, and CSP logic.

### Excluded

- Drag-and-drop as the primary editing mechanism.
- Machine-learning-based timetable generation.
- Replacing the current timetable visual design.
- Lecturer preference submission in this upgrade.
- Real institutional staff identities for demo data.

## 4. Roles

### Administrator

Can:
- generate timetable drafts;
- open Manual Timetabling;
- edit classes;
- use smart placement suggestions;
- lock/unlock classes;
- validate timetable changes;
- send timetable to review;
- view reviewer feedback;
- make corrections;
- resubmit for review;
- publish only an approved, valid timetable.

### Timetable Reviewer

Can:
- view timetables sent for review;
- review timetable-wide information;
- inspect individual timetable entries;
- add comments to the timetable;
- add comments to specific classes;
- approve a timetable;
- request changes with feedback.

Reviewer access may be campus-wide or optionally restricted to assigned faculty/faculties.

### Lecturer

- read-only;
- sees only published classes assigned to the lecturer.

### Student

- read-only;
- sees only the published timetable applicable to the student/group/registrations.

## 5. Faculty and Ownership Rules

### Faculty Hierarchy

Campus → Faculty → Department → Programme → Module/Student Group

Lecturers belong to departments, and departments belong to faculties.

### Default Assignment Rule

For a normal module:

`module.faculty_id == lecturer.faculty_id`

A lecturer from another faculty must not appear in the normal lecturer dropdown for that module.

### Shared/Cross-Faculty Exception

A module may be explicitly marked shared/cross-faculty.

Only then may approved lecturers from another faculty be eligible.

Cross-faculty eligibility must be explicit, not inferred from a random prior assignment.

### Synthetic Data Cleanup

Generated/demo records that violate faculty ownership should be corrected or flagged during seed validation.

Imported/real records should not be silently rewritten. They should produce a clear data-integrity warning requiring admin action.

## 6. Faculty Colour System

One centralized colour configuration must be used everywhere.

Initial mapping:

- Natural and Applied Sciences (NAS): Green
- Economic and Management Sciences (EMS): Purple
- Education: Gold/Yellow
- Humanities: Orange

The same mapping must be reused in:
- admin timetable;
- manual timetable editor;
- student timetable;
- lecturer timetable;
- faculty badges;
- review centre;
- PDF/Excel exports where colour styling is supported.

Colour must never be the only identifier; faculty code/name must remain visible or available.

## 7. Manual Timetabling Workspace

Add a first-class admin navigation item:

`Manual Timetabling`

### Page Structure

Top context bar:
- Faculty
- Department (optional where useful)
- Programme
- Year
- Semester/version

A visible context badge should show, for example:

`Working in: Natural and Applied Sciences (NAS)`

### Left Panel — Classes

Shows classes/modules relevant to the current context.

Filters may include:
- scheduled;
- unscheduled;
- locked;
- conflicts;
- module code/search.

### Right Panel — Smart Placement

When a class is selected, show:
- module code/name;
- faculty;
- programme/year/group;
- expected class size;
- assigned lecturer;
- duration;
- room requirements;
- current placement if scheduled;
- recommended alternatives.

### Current Timetable Area

Shows the same approved timetable style, filtered to the active context.

## 8. Direct Class Editing

Every editable class block in an admin draft should expose an obvious `Edit` action.

Clicking a class opens a side panel or modal instead of sending the user to a large unrelated data table.

### Edit Panel Fields

- module (normally fixed for an existing session);
- faculty (displayed, normally derived rather than manually changed);
- programme/year/group;
- lecturer;
- room;
- day;
- starting period/time;
- duration/session type;
- lock toggle where permitted.

### Actions

- Save Changes
- Smart Suggestions
- Lock / Unlock
- Cancel

Saving must run full validation before persisting the change.

## 9. Cascading Filter Behaviour

Changing a parent selection clears invalid child selections.

Example:

If Faculty changes from EMS to NAS:
- any EMS programme selection is cleared;
- year list recalculates;
- module list recalculates;
- lecturer list recalculates;
- student-group list recalculates;
- room ranking recalculates.

The UI must never leave stale invalid combinations selected.

## 10. Lecturer Filtering Logic

Lecturer candidates are ranked/filtered using:

1. same faculty required by default;
2. same department preferred;
3. explicit lecturer-module assignment if present;
4. no timetable clash for selected slot;
5. active staff only;
6. allowed staff type for the teaching role;
7. cross-faculty lecturers only for modules explicitly configured to allow them.

The dropdown should not merely hide impossible lecturers; when editing an existing invalid legacy assignment, the UI should display a warning explaining why it is invalid.

## 11. Room Filtering and Ranking

Room suggestions must consider hard constraints first:

- active room;
- sufficient capacity;
- compatible room type;
- required equipment;
- no room clash;
- duration availability.

Then rank valid rooms by soft preferences:

1. faculty-owned room/building;
2. smallest reasonable capacity waste;
3. same building/faculty where practical;
4. suitable shared room;
5. cross-faculty fallback.

The system must never silently offer an undersized or incompatible room as valid.

## 12. Smart Placement Suggestions

Manual editing should reuse the existing CSP/constraint logic rather than use a separate weaker ruleset.

For a selected class, generate ranked candidate placements.

Each suggestion should show:

- day and time;
- room;
- capacity versus class size;
- lecturer availability;
- student-group availability;
- room availability;
- room suitability;
- faculty-room preference;
- concise quality indicator.

Example:

Best option
Wednesday, Periods 3–4
Lecture Hall 2
Capacity 160 / Students 118
✓ Lecturer available
✓ Student group available
✓ No room clash
✓ Correct room type
✓ Faculty-preferred room

Alternative placements should also be available.

## 13. Explainable Validation

Invalid edits must produce specific, human-readable reasons.

Examples:

- `Cannot place here: lecturer TNU00427 is already teaching NSTA732 during Period 3.`
- `Cannot use Lecture Hall 1: capacity 80 is below required 118.`
- `Cannot place here: BSc Computer Science Year 3 already has NMAT731.`
- `Cannot use room C205: computer-lab requirement is not satisfied.`
- `Cannot split this practical: practical sessions require a continuous two-period block.`

Where practical, the error message should also offer a valid alternative action or suggestion.

## 14. Timetable Review Workflow

### Status Model

Replace the simplified workflow with:

`DRAFT → IN_REVIEW → APPROVED → PUBLISHED`

or

`DRAFT → IN_REVIEW → CHANGES_REQUESTED → DRAFT/IN_REVIEW → APPROVED → PUBLISHED`

Recommended transition rules:

- DRAFT → IN_REVIEW: administrator only
- IN_REVIEW → APPROVED: reviewer only
- IN_REVIEW → CHANGES_REQUESTED: reviewer only
- CHANGES_REQUESTED → IN_REVIEW: administrator resubmission
- APPROVED → PUBLISHED: administrator only

Any structural timetable edit after approval should invalidate approval and return the version to DRAFT or CHANGES_REQUESTED according to implementation policy. Recommended behaviour: return to DRAFT and preserve the review history.

## 15. Review Centre

Add an admin/reviewer navigation item:

`Review Centre`

### Reviewer View

Shows:
- timetable/version;
- semester;
- submitted by;
- submitted date;
- validation summary;
- faculty scope;
- timetable preview;
- unresolved comments;
- review history.

Actions:
- Approve
- Request Changes
- Add General Comment
- Add Class Comment

### Administrator View

Shows:
- current review status;
- reviewer;
- general comments;
- class-specific comments;
- unresolved feedback count;
- direct `Edit class` links from comments;
- Resubmit for Review action.

## 16. Review Feedback Model

Feedback can target:

1. the whole timetable/version; or
2. a specific timetable entry/class.

Each comment should store:
- comment id;
- timetable version id;
- timetable entry id (nullable for general comments);
- author user id;
- comment text;
- created timestamp;
- resolution status;
- resolved timestamp;
- resolved by user id (nullable).

Comments should remain in history even after resolution.

## 17. Database Changes

Existing schema should be extended, not replaced.

### users

Extend role values to include:
- ADMIN
- REVIEWER
- LECTURER
- STUDENT

### reviewer_faculties (optional but recommended)

- reviewer_user_id (FK users)
- faculty_id (FK faculties)

If a reviewer has no faculty restriction and has campus-wide permission, they may review all faculties.

### timetable_reviews

Suggested fields:
- review_id (PK)
- version_id (FK timetable_versions)
- reviewer_user_id (FK users)
- submitted_by_user_id (FK users)
- submitted_at
- decision (PENDING/APPROVED/CHANGES_REQUESTED)
- decided_at
- decision_summary (nullable)

### review_comments

Suggested fields:
- comment_id (PK)
- review_id (FK timetable_reviews)
- entry_id (nullable FK timetable_entries)
- author_user_id (FK users)
- comment_text
- status (OPEN/RESOLVED)
- created_at
- resolved_at (nullable)
- resolved_by_user_id (nullable FK users)

### modules / module_offerings

Ensure ownership is derivable through department/faculty.

Optional explicit fields/tables for cross-faculty teaching:
- `is_cross_faculty`
- or a `module_allowed_faculties` / `module_allowed_staff` relation.

Do not duplicate faculty data unnecessarily when it can be reliably derived from department ownership.

## 18. Service / Backend Responsibilities

Use focused services rather than putting all logic in route handlers.

Recommended logical components:

### FacultyContextService

Responsibilities:
- return valid dependent choices;
- programme-by-faculty filtering;
- year-by-programme filtering;
- module-by-programme/year filtering;
- lecturer eligibility;
- student-group eligibility;
- room ranking inputs.

### ManualTimetableService

Responsibilities:
- load editable class details;
- calculate candidate placements;
- validate proposed edits;
- save valid changes;
- lock/unlock classes.

### ReviewService

Responsibilities:
- submit timetable for review;
- assign/resolve reviewer scope;
- store comments;
- request changes;
- approve;
- resubmit;
- keep audit/history.

### FacultyColourService / Central Configuration

Responsibilities:
- expose one faculty colour mapping to templates, exports and badges.

## 19. Validation Rules for Manual Editing

Before saving an edit, recheck all relevant hard constraints:

- lecturer clash;
- student/group clash;
- room clash;
- room capacity;
- room type;
- equipment;
- session duration;
- practical continuity;
- split-section synchronization;
- locked-entry rules;
- shared-module rules;
- faculty/lecturer ownership;
- active semester/version state.

A timetable must still have zero hard-constraint violations before approval/publication.

## 20. Publication Rules

Publish must be disabled unless all are true:

- version status is APPROVED;
- hard-constraint count is zero;
- required sessions are scheduled or explicitly handled according to project rules;
- no review state is pending;
- current timetable content has not changed since approval.

Students and lecturers must continue seeing only PUBLISHED timetable versions.

## 21. Navigation

Recommended admin navigation:

- Dashboard
- Timetable
- Manual Timetabling
- Validation Centre
- Review Centre
- Data Management
- Users
- Reports

Reviewer navigation should remain minimal:

- Review Centre
- Timetable Preview
- Account/Logout

## 22. User-Friendliness Requirements

- Never show hundreds of irrelevant options where a parent selection can narrow them.
- Clear invalid dependent selections automatically.
- Put Edit actions on the timetable itself.
- Use search within long dropdowns.
- Show faculty context prominently.
- Keep important actions consistently positioned.
- Show success/error feedback immediately after actions.
- Preserve entered values when validation fails.
- Use simple labels rather than database terminology.
- Make review comments clickable to the affected class.
- Use tooltips/help text only where the field is not self-explanatory.

## 23. Error Handling

### Data integrity error

Example: lecturer is attached to a module in the wrong faculty.

Behaviour:
- do not silently accept;
- show warning in admin audit;
- exclude invalid lecturer from future valid choices unless explicitly cross-faculty;
- allow synthetic-data repair tooling to fix generated demo inconsistencies.

### Review state error

Example: admin attempts to publish IN_REVIEW timetable.

Behaviour:
- block action;
- explain that reviewer approval is required.

### Concurrent/stale edit

If another change invalidates the selected room/time before save, revalidate at save time and reject with an updated explanation and alternatives.

## 24. Testing Strategy

### Unit Tests

- faculty → programme filtering;
- programme → year filtering;
- programme/year → module filtering;
- module → valid lecturer filtering;
- shared/cross-faculty lecturer exception;
- room capacity filtering;
- room type filtering;
- room faculty preference ranking;
- faculty colour mapping;
- status transition rules;
- review comment creation/resolution;
- approval invalidation after timetable edit.

### Constraint Tests

- lecturer clash rejected;
- student-group clash rejected;
- room clash rejected;
- capacity violation rejected;
- equipment mismatch rejected;
- practical split rejected;
- locked class protected;
- wrong-faculty lecturer rejected.

### Integration Tests

1. Admin selects NAS and only NAS context data appears.
2. Admin selects programme/year and module list narrows correctly.
3. Admin edits a class from timetable block.
4. Smart suggestions return only valid candidate placements.
5. Admin saves valid manual change.
6. Admin submits timetable for review.
7. Reviewer sees submitted timetable.
8. Reviewer comments on a specific class and requests changes.
9. Admin sees feedback and opens affected class directly.
10. Admin fixes and resubmits.
11. Reviewer approves.
12. Admin publishes.
13. Student and lecturer views receive the published timetable only.

### UI Tests

- no stale dropdown values after parent selection changes;
- correct faculty colours on all views;
- edit panel opens from timetable entry;
- validation messages are readable;
- review feedback is discoverable;
- publish button state reflects workflow correctly.

## 25. Acceptance Criteria

The upgrade is complete when:

1. Selecting NAS restricts all dependent choices to NAS-compatible data.
2. Normal modules cannot be assigned to lecturers from unrelated faculties.
3. Explicit cross-faculty modules can use approved cross-faculty lecturers.
4. Existing timetable classes can be edited directly from the timetable view.
5. Admin can use a dedicated Manual Timetabling workspace.
6. Smart placement suggestions satisfy hard constraints before being shown as valid.
7. Invalid manual placements explain exactly why they are invalid.
8. Faculty colours are consistent throughout the application and exports.
9. Reviewer role exists.
10. Review Centre exists.
11. Reviewer can approve or request changes.
12. Reviewer can comment on a timetable or individual class.
13. Admin can open/edit the class referenced by feedback.
14. Admin can resubmit after requested changes.
15. Only APPROVED, valid timetable versions can be published.
16. Any material post-approval timetable edit invalidates the prior approval.
17. Existing generation, locking, validation, student/lecturer viewing, PDF and Excel behaviour continue to work.
18. Automated tests cover cascading filters, faculty ownership, manual edit validation, reviewer workflow, and publication guards.

## 26. Implementation Boundaries

The upgrade should be implemented in small recoverable phases and tested after each phase:

1. centralize faculty colours and faculty ownership helpers;
2. repair/audit synthetic lecturer-module faculty relationships;
3. add cascading filter backend endpoints/services;
4. add guided Manual Timetabling UI;
5. add direct edit panel to timetable classes;
6. integrate smart candidate placement and explainable validation;
7. add reviewer role and database migration;
8. add Review Centre and feedback workflow;
9. enforce new status/publication rules;
10. update exports where needed;
11. add automated tests and regression checks;
12. perform full end-to-end demo verification.

No phase should destroy the last known-good database or remove the existing approved timetable display.

## 27. Design Decision Summary

Chosen approach: **Guided Manual Timetabling + Review Centre**.

Why:
- simpler for administrators than the current editing flow;
- easier and safer than a drag-and-drop-first editor;
- strongly aligned with the CSP nature of the project;
- reuses existing constraint logic rather than duplicating it;
- makes the system visibly “intelligent” during manual scheduling;
- creates a realistic approval process suitable for the final project demonstration.
