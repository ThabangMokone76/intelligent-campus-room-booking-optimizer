# SPU Scheduler Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve timetable quality for gaps, room fit, weekly balance, repeated-session spacing, and first/last-period usage while preserving the existing hybrid CSP search and zero-hard-violation requirement.

**Architecture:** Keep the current domain generation, conflict graph, greedy-first strategy, MRV/Degree/class-size selection, LCV, forward checking, backtracking, splitting fallback, and validator. Refactor soft scoring into small pure helpers that can be tested deterministically, then use the same score in greedy and backtracking value ordering.

**Tech Stack:** Python 3.12, SQLite, unittest; existing scheduler modules only.

**Spec:** `docs/superpowers/specs/2026-10-04-spu-system-upgrade-design.md`

## Global Constraints

- Hard constraints always dominate soft preferences.
- `MAX_SEARCH_NODES = 120000` remains the search safety limit unless a failing performance test proves a change is necessary.
- Greedy remains the first scheduling attempt; CSP backtracking remains fallback.
- MRV, Degree, larger class size, LCV, and forward checking remain in use.
- Labs/practicals remain continuous; eligible lecture splitting remains fallback-only.
- No claim of global mathematical optimality.
- Verified synthetic generation must finish with zero hard violations.

## Review Focus

- **Gap calculation with a two-period class:** occupied periods must be treated as contiguous, not counted as an internal gap; pinned in Task 1.
- **Two unrelated groups on the same day:** one group's placement must not change the other's gap penalty; pinned in Task 1.
- **Room fit tie:** smaller legal room should beat a much larger legal room while faculty priority still matters; pinned in Task 2.
- **Repeated module meetings:** same-day placement must remain worse than properly spaced placement; pinned in Task 2.
- **Quality improvement accidentally breaks feasibility:** core, large, and validator tests must remain zero-hard-violation; pinned in Task 3.

---

### Task 1: Add Deterministic Gap and Balance Penalty Helpers

**Files:**
- Modify: `scheduler/engine.py`
- Test: `tests/test_scheduler_soft_scoring.py`

**Interfaces:**
- Produces: `projected_gap_penalty(part, placement, assignments, by_id, entity_key: str) -> float`, where `entity_key` is `group_ids` or `staff_ids`.
- Produces: `projected_daily_load_penalty(part, placement, assignments, by_id) -> float`.
- Produces: `projected_week_balance_penalty(part, placement, assignments, by_id) -> float`.

- [ ] **Step 1: Write failing pure scoring tests**

Add tests asserting a placement adjacent to an existing group/lecturer class scores lower than one separated by several free periods, a two-period class has no internal gap, unrelated entities do not influence each other, and adding to an already overloaded day scores worse than placing on a lighter day.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_scheduler_soft_scoring -v
```

Expected: FAIL because helpers do not exist.

- [ ] **Step 3: Implement helpers as pure functions**

Base them only on `part`, candidate `placement`, current `assignments`, and `by_id`; do not query SQLite inside scoring helpers.

- [ ] **Step 4: Run pure scoring tests**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scheduler/engine.py tests/test_scheduler_soft_scoring.py
git commit -m "feat: add gap and balance scheduler scoring"
```

### Task 2: Integrate Improved Soft Scoring into Candidate Ranking

**Files:**
- Modify: `scheduler/engine.py`
- Test: `tests/test_scheduler_soft_scoring.py`
- Test: `tests/test_scheduler_core.py`

**Interfaces:**
- Consumes: Task 1 helpers.
- Produces: updated `base_soft_score(...)` and `dynamic_soft_score(...)` with lower-is-better ordering.

- [ ] **Step 1: Add failing ranking tests**

Assert: legal 50-seat room beats legal 200-seat room for a 40-student class when faculty priority is equal; same-faculty room beats cross-faculty room when capacities are comparable; same-day repeated module is worse than Wednesday spacing after Monday; Period 1/10 penalties remain positive.

- [ ] **Step 2: Run ranking tests and verify intended failures**

Expected: at least gap/balance tests fail against current scoring.

- [ ] **Step 3: Update score composition**

Keep existing faculty/capacity/multi-room/edge-period penalties, then add student gap, lecturer gap, projected daily overload, weekly balance, and repeated-meeting spacing penalties. Document constants beside the score code so they are explainable in the viva.

- [ ] **Step 4: Ensure both search paths use the same improved score**

Keep greedy ordering by `dynamic_soft_score`; keep backtracking ordering by `(lcv_cost, dynamic_soft_score)` so LCV remains primary in CSP fallback.

- [ ] **Step 5: Run scoring and core scheduler tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_scheduler_soft_scoring tests.test_scheduler_core -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scheduler/engine.py tests/test_scheduler_soft_scoring.py tests/test_scheduler_core.py
git commit -m "feat: improve scheduler candidate quality ranking"
```

### Task 3: Verify Large Synthetic Feasibility and Metrics

**Files:**
- Modify: `tests/test_large_scheduler.py` only if new quality assertions are absent
- Modify: `final_check.py` only if it does not surface the required metrics

**Interfaces:**
- Consumes: existing `generate_timetable`, `validate_version`, and `generation_metrics`.
- Produces: regression evidence that improved scoring keeps hard violations at zero and records gap/utilization/balance metrics.

- [ ] **Step 1: Add/confirm large-data quality assertions**

Assert generated synthetic version has `hard_violations == 0`, non-null student gaps, lecturer gaps, room utilization, balance score, and soft score. Do not assert brittle exact metric values unless the synthetic seed makes them deterministic and stable.

- [ ] **Step 2: Run large scheduler test**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_large_scheduler -v
```

Expected: PASS within the current practical runtime envelope.

- [ ] **Step 3: Run core scheduler and workflow suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_scheduler_core tests.test_workflow -v
```

Expected: PASS with zero hard violations.

- [ ] **Step 4: Run full project check**

Run:

```powershell
.\.venv\Scripts\python.exe final_check.py
```

Expected: `FINAL CHECK: PASS`.

- [ ] **Step 5: Commit any test/reporting-only changes**

```bash
git add tests/test_large_scheduler.py final_check.py
git commit -m "test: verify upgraded scheduler quality"
```
