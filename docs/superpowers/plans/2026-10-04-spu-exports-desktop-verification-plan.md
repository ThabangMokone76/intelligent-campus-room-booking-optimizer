# SPU Exports, Desktop Integration, and Final Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PDF/Excel exports reproduce the SPU venue-by-period timetable, keep PyWebView downloads working, preserve Validation Centre rendering, and complete full automated/manual acceptance verification.

**Architecture:** Reuse the campus timetable view model from the UI plan as the single source for on-screen and exported grid structure. Keep ReportLab and openpyxl; do not introduce new export dependencies. Preserve the local Flask + PyWebView desktop architecture and enable downloads explicitly.

**Tech Stack:** Python 3.12, ReportLab, openpyxl, Flask `send_file`, PyWebView, unittest.

**Spec:** `docs/superpowers/specs/2026-10-04-spu-system-upgrade-design.md`

## Global Constraints

- Campus PDF/Excel exports must use generated timetable data, not a screenshot/static copy of the supplied timetable.
- Exports must use separate day-by-day venue/capacity/P1–P10 sections and exact Period 6 `12:45–13:20`.
- Faculty colours and repeated multi-period module cells should match the on-screen SPU grid conventions.
- Personal exports may remain simplified and role-specific if existing behavior requires it.
- PyWebView must explicitly permit downloads.
- Validation Centre must use safe dictionary-key access and render both zero and non-zero violation reports.
- No success claim until `final_check.py` and manual desktop download checks are completed.

## Review Focus

- **Long module text:** Excel/PDF cells must wrap rather than overflow unreadably; pinned in Task 1/2.
- **Many active venues:** PDF must paginate without dropping column headers/day identity; pinned in Task 2.
- **Faculty colour missing/null:** export must fall back to a neutral fill rather than crash; pinned in Task 1/2.
- **Personal export scoping:** Student/Lecturer downloads must contain only their own published rows; pinned in Task 3.
- **Desktop download setting absent:** manual export click must be treated as failed acceptance even if backend test passes; pinned in Task 4.
- **Validation report dictionary key `items`:** must not resolve to Python dict method; pinned in Task 4.

---

### Task 1: Rebuild Excel Export as SPU Venue-by-Period Timetable

**Files:**
- Modify: `services/export_service.py`
- Test: `tests/test_exports_spu_grid.py`

**Interfaces:**
- Consumes: `campus_timetable_grid(conn, timetable_rows(conn, version_id))` from the UI plan.
- Produces: `export_excel(conn, version_id, output_path) -> Path` with one worksheet per weekday named Monday–Friday.

- [ ] **Step 1: Write failing workbook-structure tests**

Assert workbook has Monday–Friday sheets, `VENUE` and `CAPACITY` columns, P1–P10 headers, Period 6 header containing `12:45–13:20`, module codes in expected occupied cells, wrapped text, borders, and neutral fallback when faculty colour is missing.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_exports_spu_grid -v
```

Expected: FAIL because current export is a flat list.

- [ ] **Step 3: Implement SPU workbook layout**

Use day worksheets, merged title rows, SPU title/version/semester metadata, venue/capacity columns, P1–P10 period headers, black borders, wrap alignment, sensible widths/heights, and faculty fill colours from timetable cells.

- [ ] **Step 4: Run Excel export tests**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/export_service.py tests/test_exports_spu_grid.py
git commit -m "feat: export SPU-style Excel timetable"
```

### Task 2: Rebuild PDF Export as SPU Day-by-Day Timetable

**Files:**
- Modify: `services/export_service.py`
- Test: `tests/test_exports_spu_grid.py`

**Interfaces:**
- Consumes: the same campus grid as Task 1.
- Produces: `export_pdf(conn, version_id, output_path) -> Path` using landscape pages and repeated day/header context across pagination.

- [ ] **Step 1: Add failing PDF content tests**

Assert generated PDF bytes contain the timetable title/day labels and period header text where extractable; assert file is non-trivial in size and generation succeeds with long module codes/names and a null faculty colour.

- [ ] **Step 2: Run PDF tests and verify they fail against flat-list output expectations**

Expected: FAIL on SPU layout/content assertions.

- [ ] **Step 3: Implement ReportLab SPU grids**

Build one day section at a time with `VENUE`, `CAPACITY`, P1–P10, exact time row, faculty cell backgrounds, black grid, compact fonts, wrapped `Paragraph` module text, and page breaks as needed. Include SPU name/logo if the static asset is available; failure to load the image must fall back to text branding rather than abort export.

- [ ] **Step 4: Run all export tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_exports_spu_grid tests.test_exports_synthetic -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/export_service.py tests/test_exports_spu_grid.py tests/test_exports_synthetic.py
git commit -m "feat: export SPU-style PDF timetable"
```


### Task 3: Add Role-Scoped Personal Timetable Downloads

**Files:**
- Modify: `services/export_service.py`
- Modify: `app.py`
- Modify: `templates/personal_timetable.html`
- Test: `tests/test_personal_exports.py`

**Interfaces:**
- Produces: `export_personal_excel(conn, version_id: int, user: dict, output_path) -> Path`.
- Produces: `export_personal_pdf(conn, version_id: int, user: dict, output_path) -> Path`.
- Produces: `GET /my-timetable/export/<fmt>` for authenticated Student/Lecturer users using only the currently visible PUBLISHED version.

- [ ] **Step 1: Write failing personal export tests**

Assert Student export rows all belong to the student's `section_student_assignments`, Lecturer export rows all belong to `offering_staff`, a DRAFT version is never exported to non-admin users, and unsupported formats do not create a file.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_personal_exports -v
```

Expected: FAIL because personal export helpers/routes do not exist.

- [ ] **Step 3: Implement role-scoped personal export helpers**

Build simplified SPU-branded weekly personal PDF/Excel from `timetable_rows(conn, version_id, user)`. Keep campus export signatures unchanged.

- [ ] **Step 4: Add personal export route and buttons**

Resolve the user's visible PUBLISHED version server-side; do not accept an arbitrary version id from Student/Lecturer requests. Add PDF and Excel download actions to `personal_timetable.html`.

- [ ] **Step 5: Run personal export and visibility tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_personal_exports tests.test_personal_timetable -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/export_service.py app.py templates/personal_timetable.html tests/test_personal_exports.py
git commit -m "feat: add personal timetable downloads"
```

### Task 4: Preserve Desktop Downloads and Validation Centre Fix

**Files:**
- Modify: `desktop_app.py`
- Modify: `templates/validation.html`
- Test: `tests/test_desktop_config.py`
- Test: `tests/test_validation_template.py`

**Interfaces:**
- Produces: PyWebView title `Sol Plaatje University Timetable Optimizer` and `webview.settings['ALLOW_DOWNLOADS'] = True` before window start.
- Produces: validation template using bracket-key access for `report` dictionary.

- [ ] **Step 1: Write failing config/template tests**

Assert desktop launcher source/config enables downloads and uses SPU title. Render validation template with `{'total': 0, 'categories': {}, 'items': []}` and with one violation; both must render without exception.

- [ ] **Step 2: Run tests and verify current failures**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_desktop_config tests.test_validation_template -v
```

Expected: FAIL because current desktop launcher does not enable downloads and current template uses attribute-style dictionary access.

- [ ] **Step 3: Apply desktop download setting and title**

Set `webview.settings['ALLOW_DOWNLOADS'] = True` immediately after importing `webview` and before `create_window`/`start`.

- [ ] **Step 4: Apply validation bracket notation**

Use `report['total']`, `report['categories'].items()`, and `report['items']` explicitly.

- [ ] **Step 5: Run config/template tests**

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add desktop_app.py templates/validation.html tests/test_desktop_config.py tests/test_validation_template.py
git commit -m "fix: preserve desktop downloads and validation rendering"
```

### Task 5: Full Automated Regression Verification

**Files:**
- Modify: `final_check.py` only if new notification/SPU-grid checks are absent
- Test: all `tests/`

**Interfaces:**
- Consumes: every preceding upgrade plan.
- Produces: one repeatable verification path for the finished system.

- [ ] **Step 1: Run complete unittest discovery**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all tests PASS.

- [ ] **Step 2: Run full final check**

Run:

```powershell
.\.venv\Scripts\python.exe final_check.py
```

Expected: verified synthetic counts remain populated, all three role logins PASS, personal visibility PASS, exports PASS, hard violations are `0`, and `FINAL CHECK: PASS`.

- [ ] **Step 3: Add final-check assertions only for stable upgrade invariants if missing**

Add checks for Period 6 `12:45`, notification table availability, and successful SPU-style PDF/XLSX file generation; do not duplicate every unit test.

- [ ] **Step 4: Re-run final check after any edits**

Expected: `FINAL CHECK: PASS`.

- [ ] **Step 5: Commit**

```bash
git add final_check.py
git commit -m "test: verify complete SPU system upgrade"
```

### Task 6: Manual Desktop Acceptance

**Files:**
- No code changes unless a reproducible defect is found.

**Interfaces:**
- Produces: manual acceptance evidence for the exact visual and desktop-only requirements that automated tests cannot prove.

- [ ] **Step 1: Launch desktop application**

Run:

```powershell
.\.venv\Scripts\python.exe desktop_app.py
```

Expected: SPU-branded login opens in a native window.

- [ ] **Step 2: Verify Admin experience**

Log in as Admin; confirm SPU shell, campus timetable day grids, venue/capacity columns, Periods 1–10, Period 6 `12:45–13:20`, filters, lock visibility, validation zero-state, and grouped workflow controls.

- [ ] **Step 3: Compare timetable visually with supplied SPU source**

Check yellow/orange header treatment, black grid borders, white empty cells, faculty colours, venue/capacity left columns, repeated module codes across consecutive occupied periods, and separate day sections. Generated module placements may differ; structure/style must match.

- [ ] **Step 4: Verify Student and Lecturer experiences**

Confirm each role sees only personal published classes, role-specific dashboard cards, personal timetable, and notifications.

- [ ] **Step 5: Verify desktop PDF and Excel downloads**

Click both exports from the PyWebView app and confirm files are actually saved/openable; backend unit-test success alone is not enough.

- [ ] **Step 6: Verify notifications**

Publish a changed review version in a disposable test database or controlled demo copy; confirm affected Student/Lecturer bell count and messages update, then mark read.

- [ ] **Step 7: Record defects before any success claim**

If any manual check fails, reproduce it, add a failing test where practical, fix, rerun automated tests, and repeat the affected manual check.
