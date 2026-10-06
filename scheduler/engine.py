from __future__ import annotations

from itertools import combinations
from math import prod
from collections import defaultdict

from scheduler.policy import CONTINUOUS, SPLIT, split_eligible, split_sibling_day_conflict

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
MAX_SEARCH_NODES = 120000

ROOM_TYPE_COMPATIBILITY = {
    "Lecture Room": {"Lecture Room", "Classroom", "Lecture Hall", "Auditorium", "Exam Hall"},
    "Classroom": {"Classroom", "Lecture Room", "Lecture Hall", "Auditorium"},
    "Lecture Hall": {"Lecture Hall", "Auditorium", "Exam Hall"},
    "Tutorial Room": {"Tutorial Room", "Classroom"},
    "Teaching Lab": {"Teaching Lab"},
    "Computer Lab": {"Computer Lab"},
    "Chemistry Lab": {"Chemistry Lab"},
    "Physics Lab": {"Physics Lab"},
    "Biology Lab": {"Biology Lab"},
    "GIS Lab": {"GIS Lab"},
}


class NoSolutionError(RuntimeError):
    pass


def active_semester(conn):
    row = conn.execute(
        "SELECT * FROM semesters WHERE status='ACTIVE' ORDER BY academic_year DESC, semester_number DESC LIMIT 1"
    ).fetchone()
    if row is None:
        raise ValueError("No ACTIVE semester exists.")
    return dict(row)


def latest_version(conn, semester_id):
    row = conn.execute(
        "SELECT * FROM timetable_versions WHERE semester_id=? ORDER BY version_number DESC LIMIT 1",
        (semester_id,),
    ).fetchone()
    return None if row is None else dict(row)


def _group_ids(conn, offering_id):
    return {r[0] for r in conn.execute("SELECT group_id FROM offering_groups WHERE offering_id=?", (offering_id,))}


def _staff_ids(conn, offering_id):
    return {r[0] for r in conn.execute("SELECT staff_id FROM offering_staff WHERE offering_id=?", (offering_id,))}


def _equipment_requirements(conn, template_id):
    return {
        r[0]: r[1]
        for r in conn.execute(
            "SELECT equipment_id, quantity_required FROM session_requirements WHERE session_template_id=?",
            (template_id,),
        )
    }


def get_logical_sessions(conn, semester_id):
    rows = conn.execute(
        """
        SELECT
            cs.session_id, cs.session_number, cs.duration_slots,
            st.session_template_id, st.offering_id, st.session_type,
            st.required_room_type, st.can_split_duration,
            mo.expected_students,
            m.module_id, m.module_code, m.module_name,
            f.faculty_id, f.faculty_code, f.faculty_name
        FROM class_sessions cs
        JOIN session_templates st ON st.session_template_id=cs.session_template_id
        JOIN module_offerings mo ON mo.offering_id=st.offering_id
        JOIN modules m ON m.module_id=mo.module_id
        JOIN departments d ON d.department_id=m.department_id
        JOIN faculties f ON f.faculty_id=d.faculty_id
        WHERE mo.semester_id=?
        ORDER BY m.module_code, cs.session_number
        """,
        (semester_id,),
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["group_ids"] = _group_ids(conn, item["offering_id"])
        item["staff_ids"] = _staff_ids(conn, item["offering_id"])
        item["equipment_requirements"] = _equipment_requirements(conn, item["session_template_id"])
        result.append(item)
    return result


def ensure_continuous_part(conn, session):
    row = conn.execute(
        "SELECT part_id FROM session_parts WHERE session_id=? AND representation_type='CONTINUOUS' AND part_number=1",
        (session["session_id"],),
    ).fetchone()
    if row is None:
        conn.execute(
            """INSERT INTO session_parts(session_id, representation_type, part_number, duration_slots, is_split_part)
               VALUES (?, 'CONTINUOUS', 1, ?, 0)""",
            (session["session_id"], session["duration_slots"]),
        )


def ensure_split_parts(conn, session):
    if not split_eligible(session):
        raise ValueError(f"Session {session['session_id']} is not eligible for split duration.")
    for part_number in (1, 2):
        conn.execute(
            """INSERT OR IGNORE INTO session_parts(
                   session_id, representation_type, part_number, duration_slots, is_split_part
               ) VALUES (?, 'SPLIT', ?, 1, 1)""",
            (session["session_id"], part_number),
        )


def prepare_representations(conn, sessions):
    for session in sessions:
        ensure_continuous_part(conn, session)
        if split_eligible(session):
            ensure_split_parts(conn, session)
    conn.commit()


def selected_parts(conn, sessions, split_session_ids):
    split_session_ids = set(split_session_ids)
    result = []
    for session in sessions:
        representation = SPLIT if session["session_id"] in split_session_ids else CONTINUOUS
        if representation == SPLIT and not split_eligible(session):
            raise ValueError(f"Illegal SPLIT selection for session {session['session_id']}")
        rows = conn.execute(
            """SELECT part_id, session_id, representation_type, part_number, duration_slots, is_split_part
               FROM session_parts
               WHERE session_id=? AND representation_type=?
               ORDER BY part_number""",
            (session["session_id"], representation),
        ).fetchall()
        expected = 2 if representation == SPLIT else 1
        if len(rows) != expected:
            raise RuntimeError(f"Session {session['session_id']} has an incomplete {representation} representation.")
        for row in rows:
            part = dict(session)
            part["logical_duration_slots"] = session["duration_slots"]
            part.update(dict(row))
            result.append(part)
    return result


def get_rooms(conn):
    rows = conn.execute(
        """SELECT r.*, b.faculty_id, b.is_shared, b.building_name
           FROM rooms r JOIN buildings b ON b.building_id=r.building_id
           WHERE r.is_active=1"""
    ).fetchall()
    result = []
    for row in rows:
        room = dict(row)
        room["equipment_inventory"] = {
            er[0]: er[1]
            for er in conn.execute(
                "SELECT equipment_id, quantity FROM room_equipment WHERE room_id=?",
                (room["room_id"],),
            )
        }
        result.append(room)
    return result


def get_time_slots(conn):
    return {
        (r["day_of_week"], r["period_number"]): dict(r)
        for r in conn.execute("SELECT * FROM time_slots")
    }


def room_type_compatible(required, actual):
    if not required:
        return True
    return actual in ROOM_TYPE_COMPATIBILITY.get(required, {required})


def room_equipment_ok(part, room):
    for equipment_id, quantity in part.get("equipment_requirements", {}).items():
        if room["equipment_inventory"].get(equipment_id, 0) < quantity:
            return False
    return True


def faculty_priority(part, room):
    if room.get("faculty_id") == part.get("faculty_id"):
        return 0
    if room.get("is_shared") or room.get("faculty_id") is None:
        return 1
    return 2


def compatible_rooms(part, rooms):
    return [
        room
        for room in rooms
        if room_type_compatible(part.get("required_room_type"), room.get("room_type"))
        and room_equipment_ok(part, room)
    ]


def room_options(part, rooms):
    students = int(part.get("expected_students") or 0)
    candidates = compatible_rooms(part, rooms)
    singles = [r for r in candidates if r["capacity"] >= students]
    if singles:
        singles.sort(key=lambda r: (faculty_priority(part, r), r["capacity"] - students, r["capacity"]))
        return [[r] for r in singles[:10]]

    candidates.sort(key=lambda r: (-r["capacity"], faculty_priority(part, r)))
    candidates = candidates[:16]
    options = []
    for count in range(2, min(4, len(candidates)) + 1):
        for group in combinations(candidates, count):
            if sum(r["capacity"] for r in group) >= students:
                options.append(list(group))
        if options:
            break
    options.sort(
        key=lambda rs: (
            len(rs),
            sum(r["capacity"] for r in rs) - students,
            sum(faculty_priority(part, r) for r in rs),
        )
    )
    return options[:16]


def base_soft_score(part, rooms, day, start_period):
    students = int(part.get("expected_students") or 0)
    total_capacity = sum(r["capacity"] for r in rooms)
    score = sum(faculty_priority(part, r) * 20 for r in rooms)
    score += max(0, total_capacity - students) / 20
    score += max(0, len(rooms) - 1) * 60
    if start_period == 1:
        score += 5
    if start_period + int(part["duration_slots"]) - 1 == 10:
        score += 5
    return float(score)


def build_domain(part, rooms):
    options = room_options(part, rooms)
    if not options:
        return []
    values = []
    duration = int(part["duration_slots"])
    for day in DAYS:
        for start in range(1, 11 - duration + 1):
            for room_group in options:
                values.append(
                    {
                        "day": day,
                        "start_period": start,
                        "rooms": room_group,
                        "room_ids": {r["room_id"] for r in room_group},
                        "base_score": base_soft_score(part, room_group, day, start),
                    }
                )
    return values


def build_graph(parts):
    graph = {p["part_id"]: set() for p in parts}
    by_group = defaultdict(list)
    by_staff = defaultdict(list)
    by_id = {p["part_id"]: p for p in parts}
    for part in parts:
        for gid in part.get("group_ids", set()): by_group[gid].append(part["part_id"])
        for sid in part.get("staff_ids", set()): by_staff[sid].append(part["part_id"])
    for bucket in list(by_group.values()) + list(by_staff.values()):
        for i, a in enumerate(bucket):
            for b in bucket[i+1:]:
                if a != b and by_id[a]["session_id"] != by_id[b]["session_id"]:
                    graph[a].add(b); graph[b].add(a)
    return graph


def periods(part, placement):
    start = placement["start_period"]
    return set(range(start, start + int(part["duration_slots"])))


def placements_conflict(part_a, place_a, part_b, place_b, graph):
    if split_sibling_day_conflict(part_a, place_a, part_b, place_b):
        return True
    if place_a["day"] != place_b["day"]:
        return False
    if not periods(part_a, place_a) & periods(part_b, place_b):
        return False
    if place_a["room_ids"] & place_b["room_ids"]:
        return True
    if part_b["part_id"] in graph.get(part_a["part_id"], set()):
        return True
    return False


def get_locked_parts(conn, semester_id):
    version = latest_version(conn, semester_id)
    if version is None:
        return None, []
    rows = conn.execute(
        """
        SELECT te.*, sp.session_id, sp.representation_type, sp.part_number,
               ts.day_of_week, ts.period_number,
               st.offering_id
        FROM timetable_entries te
        JOIN session_parts sp ON sp.part_id=te.part_id
        JOIN session_sections ss ON ss.section_id=te.section_id
        JOIN time_slots ts ON ts.slot_id=te.slot_id
        JOIN class_sessions cs ON cs.session_id=sp.session_id
        JOIN session_templates st ON st.session_template_id=cs.session_template_id
        WHERE te.version_id=? AND te.is_locked=1
        ORDER BY te.part_id, te.entry_id
        """,
        (version["version_id"],),
    ).fetchall()
    grouped = {}
    for row in rows:
        pid = row["part_id"]
        item = grouped.setdefault(
            pid,
            {
                "part_id": pid,
                "session_id": row["session_id"],
                "representation_type": row["representation_type"],
                "part_number": row["part_number"],
                "day": row["day_of_week"],
                "start_period": row["period_number"],
                "duration_slots": row["duration_slots"],
                "room_ids": set(),
                "entry_ids": [],
                "offering_id": row["offering_id"],
            },
        )
        if item["day"] != row["day_of_week"] or item["start_period"] != row["period_number"]:
            raise RuntimeError("Locked room sections for the same part are not synchronized.")
        item["room_ids"].add(row["room_id"])
        item["entry_ids"].append(row["entry_id"])
    for item in grouped.values():
        item["group_ids"] = _group_ids(conn, item["offering_id"])
        item["staff_ids"] = _staff_ids(conn, item["offering_id"])
    return version, list(grouped.values())


def forced_representations(locked_parts):
    forced = {}
    for lock in locked_parts:
        current = forced.get(lock["session_id"])
        if current and current != lock["representation_type"]:
            raise RuntimeError("A logical session has locked parts from mixed representations.")
        forced[lock["session_id"]] = lock["representation_type"]
    return forced


def locked_conflict(part, placement, locked_parts):
    for lock in locked_parts:
        lock_part = {
            "part_id": lock["part_id"],
            "session_id": lock["session_id"],
            "representation_type": lock["representation_type"],
            "duration_slots": lock["duration_slots"],
            "group_ids": lock.get("group_ids", set()),
            "staff_ids": lock.get("staff_ids", set()),
        }
        lock_place = {
            "day": lock["day"],
            "start_period": lock["start_period"],
            "room_ids": lock["room_ids"],
        }
        if split_sibling_day_conflict(part, placement, lock_part, lock_place):
            return True
        if placement["day"] != lock["day"]:
            continue
        if not periods(part, placement) & periods(lock_part, lock_place):
            continue
        if placement["room_ids"] & lock["room_ids"]:
            return True
        if part.get("group_ids", set()) & lock.get("group_ids", set()):
            return True
        if part.get("staff_ids", set()) & lock.get("staff_ids", set()):
            return True
    return False


def projected_gap_penalty(part, placement, assignments, by_id, entity_key):
    """Return free periods trapped between classes for the candidate's groups/staff.

    The function is intentionally pure so candidate quality can be tested without a DB.
    """
    candidate_entities = set(part.get(entity_key, set()))
    if not candidate_entities:
        return 0.0
    candidate_periods = periods(part, placement)
    penalty = 0
    for entity_id in candidate_entities:
        occupied = set(candidate_periods)
        for other_id, other_place in assignments.items():
            other = by_id[other_id]
            if entity_id not in set(other.get(entity_key, set())):
                continue
            if other_place["day"] != placement["day"]:
                continue
            occupied.update(periods(other, other_place))
        if occupied:
            penalty += max(0, (max(occupied) - min(occupied) + 1) - len(occupied))
    return float(penalty)


def projected_daily_load_penalty(part, placement, assignments, by_id):
    """Penalize adding a fifth or later daily session for affected groups/staff."""
    penalty = 0.0
    for entity_key in ("group_ids", "staff_ids"):
        for entity_id in set(part.get(entity_key, set())):
            count = 1
            for other_id, other_place in assignments.items():
                if other_place["day"] != placement["day"]:
                    continue
                if entity_id in set(by_id[other_id].get(entity_key, set())):
                    count += 1
            excess = max(0, count - 4)
            penalty += float(excess * excess)
    return penalty


def projected_week_balance_penalty(part, placement, assignments, by_id):
    """Return weekday load variance for the candidate's affected groups/staff."""
    penalty = 0.0
    for entity_key in ("group_ids", "staff_ids"):
        for entity_id in set(part.get(entity_key, set())):
            counts = {day: 0 for day in DAYS}
            counts[placement["day"]] += 1
            for other_id, other_place in assignments.items():
                if entity_id in set(by_id[other_id].get(entity_key, set())):
                    counts[other_place["day"]] += 1
            mean = sum(counts.values()) / len(DAYS)
            penalty += sum((counts[day] - mean) ** 2 for day in DAYS)
    return float(penalty)


# Soft-quality weights are penalties: lower candidate scores are preferred.
# They never override hard-constraint consistency checks.
STUDENT_GAP_WEIGHT = 12.0
LECTURER_GAP_WEIGHT = 8.0
DAILY_OVERLOAD_WEIGHT = 35.0
WEEK_BALANCE_WEIGHT = 2.0
SAME_MODULE_SAME_DAY_PENALTY = 180.0
ADJACENT_MODULE_DAY_PENALTY = 20.0


def dynamic_soft_score(part, placement, assignments, by_id):
    score = float(placement["base_score"])

    # Compact student and lecturer days while allowing the hard constraints to decide feasibility.
    score += STUDENT_GAP_WEIGHT * projected_gap_penalty(
        part, placement, assignments, by_id, "group_ids"
    )
    score += LECTURER_GAP_WEIGHT * projected_gap_penalty(
        part, placement, assignments, by_id, "staff_ids"
    )
    score += DAILY_OVERLOAD_WEIGHT * projected_daily_load_penalty(
        part, placement, assignments, by_id
    )
    score += WEEK_BALANCE_WEIGHT * projected_week_balance_penalty(
        part, placement, assignments, by_id
    )

    day_index = DAYS.index(placement["day"])
    same_group_today = 0
    for other_id, other_place in assignments.items():
        other = by_id[other_id]
        if other.get("module_id") == part.get("module_id"):
            if other_place["day"] == placement["day"]:
                score += SAME_MODULE_SAME_DAY_PENALTY
            else:
                diff = abs(day_index - DAYS.index(other_place["day"]))
                if diff == 1:
                    score += ADJACENT_MODULE_DAY_PENALTY
        if (
            other_place["day"] == placement["day"]
            and other.get("group_ids", set()) & part.get("group_ids", set())
        ):
            same_group_today += 1

    # Preserve the original light daily-load preference, plus a strong penalty at five classes.
    score += same_group_today * 6
    if same_group_today >= 4:
        score += 100
    return float(score)


def select_variable(unassigned, domains, graph):
    return min(
        unassigned,
        key=lambda p: (
            len(domains[p["part_id"]]),
            -len(graph.get(p["part_id"], set())),
            -int(p.get("expected_students") or 0),
            p["part_id"],
        ),
    )


def consistent(part, placement, assignments, by_id, graph):
    for other_id, other_place in assignments.items():
        if placements_conflict(part, placement, by_id[other_id], other_place, graph):
            return False
    return True


def lcv_cost(part, placement, remaining, domains, graph):
    cost = 0
    for other in remaining:
        for value in domains[other["part_id"]]:
            if placements_conflict(part, placement, other, value, graph):
                cost += 1
    return cost


def prune_domains(part, placement, remaining, domains, graph):
    pruned = {}
    removed = 0
    for other in remaining:
        allowed = []
        for value in domains[other["part_id"]]:
            if placements_conflict(part, placement, other, value, graph):
                removed += 1
            else:
                allowed.append(value)
        if not allowed:
            return None, removed
        pruned[other["part_id"]] = allowed
    return pruned, removed


def backtrack(unassigned, domains, graph, assignments, by_id, stats):
    stats["nodes"] += 1
    if stats["nodes"] > MAX_SEARCH_NODES:
        return None
    if not unassigned:
        return dict(assignments)
    part = select_variable(unassigned, domains, graph)
    pid = part["part_id"]
    remaining = [p for p in unassigned if p["part_id"] != pid]
    values = []
    for value in domains[pid]:
        if consistent(part, value, assignments, by_id, graph):
            values.append(
                (
                    lcv_cost(part, value, remaining, domains, graph),
                    dynamic_soft_score(part, value, assignments, by_id),
                    value,
                )
            )
    values.sort(key=lambda x: (x[0], x[1]))
    for _, _, value in values:
        stats["values_tried"] += 1
        assignments[pid] = value
        new_domains, removed = prune_domains(part, value, remaining, domains, graph)
        stats["pruned"] += removed
        if new_domains is not None:
            result = backtrack(remaining, new_domains, graph, assignments, by_id, stats)
            if result is not None:
                return result
        assignments.pop(pid, None)
        stats["backtracks"] += 1
    return None


def greedy_schedule(unlocked, domains, graph, by_id):
    assignments = {}
    ordered = sorted(unlocked, key=lambda p: (len(domains[p["part_id"]]), -len(graph.get(p["part_id"], set())), -int(p.get("expected_students") or 0)))
    for part in ordered:
        vals = sorted(domains[part["part_id"]], key=lambda v: (dynamic_soft_score(part, v, assignments, by_id), v["day"], v["start_period"]))
        chosen = next((v for v in vals if consistent(part, v, assignments, by_id, graph)), None)
        if chosen is None: return None
        assignments[part["part_id"]] = chosen
    return assignments


def attempt_configuration(parts, rooms, locked_parts):
    unlocked = [p for p in parts if p["part_id"] not in {l["part_id"] for l in locked_parts}]
    graph = build_graph(unlocked)
    domains = {}
    for part in unlocked:
        domain = [v for v in build_domain(part, rooms) if not locked_conflict(part, v, locked_parts)]
        if not domain:
            return None
        domains[part["part_id"]] = domain
    by_id = {p["part_id"]: p for p in unlocked}
    stats = {"nodes": 0, "values_tried": 0, "pruned": 0, "backtracks": 0, "method": "greedy"}
    solution = greedy_schedule(unlocked, domains, graph, by_id)
    if solution is None:
        stats["method"] = "backtracking"
        solution = backtrack(unlocked, domains, graph, {}, by_id, stats)
    if solution is None:
        return None
    return {"solution": solution, "parts": parts, "stats": stats}


def split_configurations(sessions, forced):
    forced_split = {sid for sid, rep in forced.items() if rep == SPLIT}
    forced_cont = {sid for sid, rep in forced.items() if rep == CONTINUOUS}
    eligible = [s for s in sessions if split_eligible(s) and s["session_id"] not in forced_split | forced_cont]
    yield set(forced_split)
    ids = [s["session_id"] for s in eligible]
    for size in range(1, len(ids) + 1):
        for combo in combinations(ids, size):
            yield forced_split | set(combo)


def create_version(conn, semester_id):
    number = conn.execute(
        "SELECT COALESCE(MAX(version_number),0)+1 FROM timetable_versions WHERE semester_id=?",
        (semester_id,),
    ).fetchone()[0]
    cur = conn.execute(
        "INSERT INTO timetable_versions(semester_id, version_number, status) VALUES (?, ?, 'DRAFT')",
        (semester_id, number),
    )
    return cur.lastrowid, number


def copy_locked_entries(conn, source_version_id, target_version_id):
    if source_version_id is None:
        return 0
    rows = conn.execute(
        """SELECT section_id, room_id, slot_id, duration_slots, part_id
           FROM timetable_entries WHERE version_id=? AND is_locked=1""",
        (source_version_id,),
    ).fetchall()
    for row in rows:
        conn.execute(
            """INSERT INTO timetable_entries(
                   version_id, section_id, room_id, slot_id, duration_slots, is_locked, part_id
               ) VALUES (?, ?, ?, ?, ?, 1, ?)""",
            (target_version_id, row["section_id"], row["room_id"], row["slot_id"], row["duration_slots"], row["part_id"]),
        )
    return len(rows)


def section_for(conn, session_id, name, students):
    row = conn.execute(
        "SELECT section_id, student_count FROM session_sections WHERE session_id=? AND section_name=?",
        (session_id, name),
    ).fetchone()
    if row is not None and row["student_count"] == students:
        return row["section_id"]
    if row is not None:
        name = f"{name}-{students}"
        row2 = conn.execute(
            "SELECT section_id FROM session_sections WHERE session_id=? AND section_name=?",
            (session_id, name),
        ).fetchone()
        if row2 is not None:
            return row2["section_id"]
    return conn.execute(
        "INSERT INTO session_sections(session_id, section_name, student_count) VALUES (?, ?, ?)",
        (session_id, name, students),
    ).lastrowid


def save_part(conn, version_id, part, placement, time_slots):
    rooms = placement["rooms"]
    registered = [r[0] for r in conn.execute(
        "SELECT smr.student_id FROM student_module_registrations smr WHERE smr.module_id=? ORDER BY smr.student_id",
        (part["module_id"],),
    )]
    remaining = int(part["expected_students"])
    offset = 0
    for index, room in enumerate(rooms, start=1):
        students = min(remaining, int(room["capacity"]))
        remaining -= students
        name = "Main" if len(rooms) == 1 else f"P{part['part_id']}-Section-{index}"
        section_id = section_for(conn, part["session_id"], name, students)
        conn.execute("DELETE FROM section_student_assignments WHERE section_id=?", (section_id,))
        for sid in registered[offset:offset+students]:
            conn.execute("INSERT OR IGNORE INTO section_student_assignments(section_id,student_id) VALUES (?,?)", (section_id,sid))
        offset += students
        slot_id = time_slots[(placement["day"], placement["start_period"])]["slot_id"]
        conn.execute(
            """INSERT INTO timetable_entries(
                   version_id, section_id, room_id, slot_id, duration_slots, is_locked, part_id
               ) VALUES (?, ?, ?, ?, ?, 0, ?)""",
            (version_id, section_id, room["room_id"], slot_id, part["duration_slots"], part["part_id"]),
        )
    if remaining > 0:
        raise RuntimeError("Room allocation did not cover all students.")


def calculate_metrics(conn, version_id):
    rows = conn.execute(
        """SELECT te.*, ss.student_count, r.capacity, ts.day_of_week, ts.period_number,
                  sp.session_id, st.offering_id
           FROM timetable_entries te
           JOIN session_sections ss ON ss.section_id=te.section_id
           JOIN rooms r ON r.room_id=te.room_id
           JOIN time_slots ts ON ts.slot_id=te.slot_id
           JOIN session_parts sp ON sp.part_id=te.part_id
           JOIN class_sessions cs ON cs.session_id=sp.session_id
           JOIN session_templates st ON st.session_template_id=cs.session_template_id
           WHERE te.version_id=?""",
        (version_id,),
    ).fetchall()
    if not rows:
        return {"student_gaps": 0, "lecturer_gaps": 0, "room_utilization": 0.0, "balance_score": 0.0, "soft_score": 0.0}
    utilization = sum(r["student_count"] / r["capacity"] for r in rows) / len(rows) * 100
    # Compute day counts per student group and lecturer from distinct parts.
    distinct = {}
    for r in rows:
        distinct.setdefault(r["part_id"], r)
    group_days = {}
    staff_days = {}
    for r in distinct.values():
        gids = _group_ids(conn, r["offering_id"])
        sids = _staff_ids(conn, r["offering_id"])
        for gid in gids:
            group_days.setdefault((gid, r["day_of_week"]), []).append(r["period_number"])
        for sid in sids:
            staff_days.setdefault((sid, r["day_of_week"]), []).append(r["period_number"])

    def gaps(mapping):
        total = 0
        for periods_list in mapping.values():
            if len(periods_list) > 1:
                p = sorted(periods_list)
                total += sum(max(0, b - a - 1) for a, b in zip(p, p[1:]))
        return total

    student_gaps = gaps(group_days)
    lecturer_gaps = gaps(staff_days)
    day_counts = {day: 0 for day in DAYS}
    for r in distinct.values():
        day_counts[r["day_of_week"]] += 1
    avg = sum(day_counts.values()) / 5
    variance = sum((count - avg) ** 2 for count in day_counts.values()) / 5
    balance_score = max(0.0, 100.0 - variance * 5)
    soft_score = student_gaps * 5 + lecturer_gaps * 3 + (100 - utilization) + (100 - balance_score)
    return {
        "student_gaps": student_gaps,
        "lecturer_gaps": lecturer_gaps,
        "room_utilization": round(utilization, 2),
        "balance_score": round(balance_score, 2),
        "soft_score": round(soft_score, 2),
    }


def generate_timetable(conn, semester_id=None):
    semester = active_semester(conn) if semester_id is None else dict(conn.execute("SELECT * FROM semesters WHERE semester_id=?", (semester_id,)).fetchone())
    sessions = get_logical_sessions(conn, semester["semester_id"])
    if not sessions:
        raise ValueError("No class sessions exist for the semester.")
    prepare_representations(conn, sessions)
    rooms = get_rooms(conn)
    if not rooms:
        raise ValueError("No active rooms exist.")
    time_slots = get_time_slots(conn)
    source_version, locked = get_locked_parts(conn, semester["semester_id"])
    forced = forced_representations(locked)

    result = None
    chosen_split = None
    attempts = 0
    for split_ids in split_configurations(sessions, forced):
        attempts += 1
        parts = selected_parts(conn, sessions, split_ids)
        candidate = attempt_configuration(parts, rooms, locked)
        if candidate is not None:
            result = candidate
            chosen_split = split_ids
            break
    if result is None:
        raise NoSolutionError("No complete hard-constraint timetable could be found, even after legal lecture splitting.")

    version_id, version_number = create_version(conn, semester["semester_id"])
    copied_locked = copy_locked_entries(conn, None if source_version is None else source_version["version_id"], version_id)
    by_id = {p["part_id"]: p for p in result["parts"]}
    for part_id, placement in result["solution"].items():
        save_part(conn, version_id, by_id[part_id], placement, time_slots)
    session_ids = {p["session_id"] for p in result["parts"]}
    conn.executemany("UPDATE class_sessions SET status='SCHEDULED' WHERE session_id=?", [(sid,) for sid in session_ids])
    metrics = calculate_metrics(conn, version_id)
    conn.execute(
        """INSERT INTO generation_metrics(
               version_id, student_gaps, lecturer_gaps, room_utilization, balance_score, soft_score
           ) VALUES (?, ?, ?, ?, ?, ?)""",
        (
            version_id,
            metrics["student_gaps"],
            metrics["lecturer_gaps"],
            metrics["room_utilization"],
            metrics["balance_score"],
            metrics["soft_score"],
        ),
    )
    conn.commit()
    return {
        "version_id": version_id,
        "version_number": version_number,
        "split_session_ids": sorted(chosen_split or []),
        "attempts": attempts,
        "locked_rows_copied": copied_locked,
        "scheduled_parts": len(result["solution"]),
        "search": result["stats"],
        "metrics": metrics,
    }


def rank_manual_candidates(part, rooms):
    """Return CSP-compatible candidate placements ordered by static soft cost."""
    return sorted(
        build_domain(part, rooms),
        key=lambda value: (value["base_score"], DAYS.index(value["day"]), value["start_period"]),
    )
