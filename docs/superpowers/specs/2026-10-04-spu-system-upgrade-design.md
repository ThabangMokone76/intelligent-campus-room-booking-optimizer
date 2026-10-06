# Sol Plaatje University Timetable Optimizer Upgrade — Design Specification

**Date:** 2026-10-04  
**Status:** Approved design, awaiting implementation-plan approval  
**Base application:** `campus_timetable_optimizer_SYNTHETIC_MERGED`

## 1. Purpose

Upgrade the existing working campus timetable optimizer into a professional Sol Plaatje University (SPU)-branded desktop application without replacing the proven scheduling, authentication, validation, synthetic-data, and publication foundations.

The upgrade covers five requested areas:

1. SPU-branded user interface.
2. Scheduler quality and search improvements.
3. Admin workflow and control improvements.
4. Student and lecturer experience improvements.
5. In-app timetable-change notifications, with email integration left as a later extension.

The timetable presentation is a hard requirement: the campus timetable view and exported timetable must closely reproduce the structure and visual language of the supplied **2026 Semester Two Timetable (Draft 1)**, using generated optimizer data rather than copied timetable contents.

## 2. Existing foundation to preserve

The current application already provides:

- Python/Flask backend.
- SQLite relational database.
- PyWebView desktop shell.
- Admin, lecturer, and student authentication.
- Role-based timetable visibility.
- Draft → Review → Published workflow.
- Hybrid scheduler using greedy scheduling plus CSP/backtracking.
- MRV, Degree, LCV, and forward checking.
- Independent hard-constraint validation.
- Manual move and lock support.
- Synthetic campus dataset.
- PDF and Excel exports.
- Automated tests and `final_check.py`.

These working components remain the foundation. The upgrade must not turn the project into an ML system and must not introduce exam timetable generation.

## 3. Branding and application shell

### 3.1 Visual identity

The application will use Sol Plaatje University branding:

- SPU deep red/crimson as the primary application colour.
- SPU orange as the secondary/accent colour.
- White/light neutral content surfaces.
- Dark charcoal text for readability.
- Green only for successful/valid/published states.
- Red alert treatments only for errors and hard violations.

### 3.2 Login screen

The login screen will be the strongest branded view:

- Full SPU logo displayed prominently.
- Soft/faded SPU logo background treatment where it does not reduce readability.
- White login card.
- SPU red primary sign-in button.
- Orange accent details.
- Product title: **Sol Plaatje University Timetable Optimizer**.
- Subtitle: **Campus Academic Timetable and Room Allocation System**.

### 3.3 Logged-in layout

The authenticated application shell will use:

- Compact SPU crest/logo in the header/sidebar.
- Clear current-user identity and role.
- Notification bell with unread count.
- Role-specific navigation.
- Consistent status badges for DRAFT, REVIEW, PUBLISHED, VALID, and ERROR.
- Responsive desktop layout suitable for the existing PyWebView shell.

The logo will be prominent on login but restrained inside the application to keep timetable content readable.

## 4. Role-specific experience

### 4.1 Admin

The Admin dashboard will act as the control centre and show:

- Active semester.
- Current timetable version and workflow status.
- Students, lecturers, rooms, modules, registrations, and scheduled-session counts.
- Hard violations.
- Student gaps.
- Lecturer gaps.
- Room utilisation.
- Weekly balance score.
- Recent timetable activity/changes.

Admin actions will be grouped by purpose rather than scattered across the page:

- **Generate / Validate**
- **Edit / Move / Lock**
- **Workflow: Review / Publish**
- **Import / Export**

Potentially destructive or high-impact actions such as regeneration and publishing will require confirmation in the interface.

### 4.2 Student

A student will see only published timetable information relevant to that student's assigned sections. The dashboard will surface:

- Today's classes.
- Next class.
- My weekly timetable.
- My modules.
- Venues.
- Notifications.
- Personal timetable download.

No admin controls will appear.

### 4.3 Lecturer

A lecturer will see only published timetable information for assigned offerings. The dashboard will surface:

- Today's teaching.
- Next teaching session.
- My weekly teaching timetable.
- Assigned modules.
- Student groups.
- Venues.
- Notifications.
- Personal timetable download.

No admin-only actions will appear.

## 5. SPU timetable reproduction

### 5.1 Hard visual requirement

The campus timetable must reproduce the supplied SPU teaching timetable's main layout rather than using a generic Monday-to-Friday calendar.

Each day will have its own timetable grid with:

- Timetable title at the top.
- Day label strip.
- `VENUE` column on the left.
- `CAPACITY` column next.
- Period columns `1` through `10` horizontally.
- Period start/end times beneath or within the period headers.
- Black grid borders.
- White empty cells.
- Module codes placed in the relevant room/period cells.
- Faculty-based colour coding consistent with the supplied timetable's visual style.
- Adjacent multi-period classes shown by repeating the module code across the occupied period cells, matching the supplied timetable convention.

The output must remain generated from the application's current timetable entries. It is not a static image of the source timetable.

### 5.2 Period definitions

The upgraded system will align the displayed and seeded times with the supplied SPU timetable:

| Period | Time |
|---|---|
| 1 | 08:00–08:45 |
| 2 | 08:55–09:40 |
| 3 | 09:50–10:35 |
| 4 | 10:45–11:30 |
| 5 | 11:40–12:25 |
| 6 | 12:45–13:20 |
| 7 | 13:30–14:15 |
| 8 | 14:25–15:10 |
| 9 | 15:20–16:05 |
| 10 | 16:15–17:00 |

This changes Period 6 from the current project value of `12:35–13:20` to `12:45–13:20` so the system matches the supplied SPU timetable.

### 5.3 Campus and personal timetable views

The **Admin/campus** timetable will use the venue-by-period SPU grid because it is intended to represent the whole campus timetable.

The **Student** and **Lecturer** timetable views may use a more readable personal weekly layout while keeping the same SPU branding and class colours. Personal users do not need to scan every campus venue.

### 5.4 Filters

The Admin timetable will support filtering by:

- Faculty.
- Programme.
- Year level.
- Module.
- Lecturer.
- Room/venue.
- Day.

Filtering changes only presentation; it must not change timetable data.

## 6. Scheduler improvements

### 6.1 Hard constraints remain dominant

The scheduler must continue to reject solutions that violate mandatory rules, including:

- Room clashes.
- Lecturer clashes.
- Student/group clashes.
- Room capacity.
- Room type.
- Required equipment.
- Session duration/contact time.
- Practical/lab continuity.
- Split-lecture rules.
- Synchronized multi-room sections.

A timetable is publishable only when the independent validator reports zero hard violations.

### 6.2 Soft-quality improvements

The scheduler will improve preference scoring without changing feasibility rules. The score will more strongly prefer:

- Fewer student gaps.
- Fewer lecturer gaps.
- Better room-capacity fit.
- Better weekly workload balance.
- Better spacing of repeated module meetings.
- Suitable faculty rooms.
- Avoidance of excessive first/last-period usage.
- Avoidance of overloaded group days.

Lower soft score remains better.

### 6.3 Search strategy

The hybrid strategy remains:

1. Build legal room/time domains.
2. Build conflict graph.
3. Try greedy scheduling first.
4. If greedy fails, use CSP backtracking.
5. Use MRV to select the most constrained variable.
6. Use Degree as a tie breaker.
7. Use larger class size as an additional priority.
8. Use LCV to order values.
9. Use forward checking to prune domains.
10. If necessary, try legal lecture-splitting configurations.
11. Validate independently before workflow progression.

The upgrade may improve candidate ranking and soft scoring, but it will not claim mathematical global optimality.

## 7. Admin editing and workflow upgrades

### 7.1 Manual moves

Manual moves remain limited to DRAFT versions. A proposed move will:

1. Apply temporarily.
2. Run hard-constraint validation.
3. Commit if valid.
4. Roll back if invalid.

The UI will provide clearer rejection messages and keep the existing transactional safety.

### 7.2 Locks

Locked classes remain fixed during regeneration. The UI will make lock state visibly obvious and provide clear lock/unlock actions.

### 7.3 Publication

Workflow remains:

`DRAFT → REVIEW → PUBLISHED`

Publishing must be blocked when hard violations are greater than zero.

## 8. Notification architecture

### 8.1 Scope now

Notifications are in-app only in this upgrade. Email is deliberately deferred.

Supported notification types include:

- Timetable published.
- Class moved.
- Venue changed.
- Time changed.
- Relevant timetable version updated.

### 8.2 Data model

Add a notification subsystem with records containing at least:

- notification id.
- recipient user id.
- notification type.
- title.
- message.
- related timetable version/entry where applicable.
- created timestamp.
- read timestamp or read flag.

### 8.3 Delivery flow

When timetable workflow or editing changes affect a published timetable:

1. Determine affected users.
2. Create notification records.
3. Show unread count in the application shell.
4. Allow users to open notifications.
5. Allow mark-as-read and mark-all-as-read.

The notification service should expose a clean interface so a future email adapter can consume the same events without redesigning timetable logic.

## 9. Export upgrades

### 9.1 PDF

The campus PDF export will reproduce the SPU-style timetable grid rather than a flat row list. It will include:

- SPU logo/name.
- Semester and version information.
- Day-by-day venue/capacity/period grids.
- Period times.
- Faculty colour legend.
- Module codes in scheduled cells.
- Print-friendly page sizing/orientation.

### 9.2 Excel

The Excel export will use the same venue-by-period concept:

- SPU title.
- Day sections or worksheets.
- Venue and capacity columns.
- Period 1–10 columns.
- Period times.
- Borders.
- Wrapped module text.
- Faculty colours.
- Sensible row heights and column widths.

Personal exports may remain simplified and user-specific, but must use SPU branding.

## 10. Desktop integration

The PyWebView desktop shell remains the desktop delivery method.

The upgrade must retain the download-enabling configuration required for PDF/Excel downloads inside PyWebView. The desktop window title will become **Sol Plaatje University Timetable Optimizer**.

## 11. Database migration strategy

Schema changes must be additive and backward-compatible with the existing synthetic database wherever practical.

Required migration work includes:

- Add notification tables/indexes.
- Update Period 6 time definition from `12:35` to `12:45` in seed/bootstrap/migration logic.
- Avoid deleting existing users, registrations, timetable versions, or synthetic data.

Database upgrades must run transactionally, with foreign-key checks after migration.

## 12. Error handling

The upgrade will preserve clear failure boundaries:

- Scheduler failure → show `NoSolutionError` without corrupting existing versions.
- Invalid manual move → rollback and show reason.
- Validation failure → keep timetable from publishing.
- Import failure → rollback the import transaction.
- Notification creation failure must not silently publish corrupt timetable data; notification side effects should occur after a successful timetable transaction or in a controlled follow-up transaction.
- Export failure → user-friendly error without changing timetable state.

## 13. Testing strategy

Implementation follows test-driven development for behaviour changes.

### 13.1 Existing regression checks

The existing tests and final check must continue to pass, subject only to intentionally updated expectations such as Period 6 start time.

Important regression commands:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_scheduler_core -v
.\.venv\Scripts\python.exe -m unittest tests.test_large_scheduler -v
.\.venv\Scripts\python.exe final_check.py
```

### 13.2 New automated tests

Add tests for:

- SPU Period 6 time definition.
- Campus timetable grid transformation by day/venue/period.
- Consecutive duration rendering across each occupied period.
- Admin filter behaviour.
- Notifications created for relevant timetable events.
- Notification recipient scoping.
- Mark-as-read behaviour.
- Student/lecturer role isolation.
- Improved soft-score behaviour for gaps, capacity fit, and balance.
- PDF/Excel exports containing day/venue/period structure.
- Existing Draft → Review → Published validation rule.

### 13.3 Visual/manual acceptance checks

Before calling the upgrade complete:

- Compare the campus timetable against the supplied SPU timetable visually.
- Verify day title, venue/capacity columns, period columns, times, faculty colours, borders, and repeated multi-period module cells.
- Verify login branding with SPU logo.
- Verify Admin, Student, and Lecturer dashboards.
- Verify notification bell/unread flow.
- Verify desktop PDF and Excel downloads manually after the PyWebView download setting is included.

## 14. Implementation boundaries

This upgrade does **not** add:

- Exam timetable generation.
- Student online registration.
- Attendance management.
- Finance/payments.
- HR/payroll.
- LMS features.
- Mobile app.
- Multi-campus scheduling.
- Cloud deployment.
- Machine-learning timetable prediction.
- CNN/image models or Grad-CAM.

## 15. Acceptance criteria

The upgrade is complete only when all of the following are true:

1. Login and internal UI visibly use SPU branding.
2. Admin, Student, and Lecturer roles still authenticate correctly.
3. Role visibility remains correct.
4. Campus timetable matches the supplied SPU venue-by-period layout and visual conventions.
5. Period 6 displays `12:45–13:20` consistently.
6. Generated timetable retains zero hard violations in the verified synthetic scenario.
7. Scheduler quality scoring is improved without weakening hard constraints.
8. Admin manual moves, locks, validation, review, and publishing still work.
9. In-app notifications work for timetable changes/publication events.
10. PDF and Excel campus exports use the SPU-style timetable structure.
11. Existing regression tests pass after intentional expectation updates.
12. New feature tests pass.
13. `final_check.py` passes.
14. Manual desktop checks confirm the Validation Centre and PDF/Excel download workflow.

## 16. Implementation sequence

The planned implementation order is:

1. Establish upgrade branch/working copy and regression baseline.
2. Add SPU assets and design tokens.
3. Upgrade login and application shell.
4. Add timetable-grid view model and SPU campus timetable screen.
5. Add role-specific dashboard improvements.
6. Add notification schema/service/routes/UI.
7. Improve Admin timetable controls and filters.
8. Improve scheduler soft scoring/search ordering with tests.
9. Rebuild PDF/Excel exports in SPU timetable format.
10. Carry forward/fix desktop download configuration and Validation Centre rendering.
11. Run full automated and manual verification.

