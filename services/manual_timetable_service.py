from __future__ import annotations

from scheduler.engine import _equipment_requirements, get_rooms, room_equipment_ok, room_type_compatible
from scheduler.validator import validate_version
from services.faculty_context_service import get_lecturers

EDITABLE_STATUSES = {"DRAFT", "CHANGES_REQUESTED", "APPROVED"}


def _entry_context(conn, entry_id: int) -> dict:
    row = conn.execute(
        """SELECT te.entry_id,te.version_id,te.part_id,te.section_id,te.room_id,te.slot_id,
                  te.duration_slots,te.is_locked,ts.day_of_week,ts.period_number,
                  ts.start_time,ts.end_time,r.room_name,r.room_code,r.capacity,r.room_type,
                  ss.section_name,ss.student_count,cs.session_id,st.session_template_id,
                  st.offering_id,st.session_type,st.required_room_type,mo.expected_students,
                  m.module_id,m.module_code,m.module_name,
                  f.faculty_id,f.faculty_code,f.faculty_name
           FROM timetable_entries te
           JOIN time_slots ts ON ts.slot_id=te.slot_id
           JOIN rooms r ON r.room_id=te.room_id
           JOIN session_sections ss ON ss.section_id=te.section_id
           JOIN session_parts sp ON sp.part_id=te.part_id
           JOIN class_sessions cs ON cs.session_id=sp.session_id
           JOIN session_templates st ON st.session_template_id=cs.session_template_id
           JOIN module_offerings mo ON mo.offering_id=st.offering_id
           JOIN modules m ON m.module_id=mo.module_id
           JOIN departments d ON d.department_id=m.department_id
           JOIN faculties f ON f.faculty_id=d.faculty_id
           WHERE te.entry_id=?""",
        (entry_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Timetable class not found.")
    return dict(row)


def _version_status(conn, version_id: int) -> str:
    row = conn.execute("SELECT status FROM timetable_versions WHERE version_id=?", (version_id,)).fetchone()
    if row is None:
        raise ValueError("Timetable version not found.")
    return row[0]


def _require_editable(conn, version_id: int) -> str:
    status = _version_status(conn, version_id)
    if status not in EDITABLE_STATUSES:
        raise ValueError(f"Timetable cannot be edited while it is {status}.")
    return status


def _staff_rows(conn, offering_id: int) -> list[dict]:
    rows = conn.execute(
        """SELECT s.staff_id,s.staff_number,s.first_name,s.last_name,s.staff_type,os.role,
                  f.faculty_id,f.faculty_code,f.faculty_name,d.department_id,d.department_code
           FROM offering_staff os
           JOIN staff s ON s.staff_id=os.staff_id
           JOIN departments d ON d.department_id=s.department_id
           JOIN faculties f ON f.faculty_id=d.faculty_id
           WHERE os.offering_id=? ORDER BY os.role,s.last_name,s.first_name""",
        (offering_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _group_rows(conn, offering_id: int) -> list[dict]:
    rows = conn.execute(
        """SELECT sg.group_id,sg.year_level,sg.section_code,sg.number_of_students,
                  p.programme_id,p.programme_code,p.programme_name
           FROM offering_groups og
           JOIN student_groups sg ON sg.group_id=og.group_id
           JOIN programmes p ON p.programme_id=sg.programme_id
           WHERE og.offering_id=? ORDER BY p.programme_code,sg.year_level,sg.section_code""",
        (offering_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_editable_entry(conn, entry_id: int, version_id: int | None = None) -> dict:
    item = _entry_context(conn, entry_id)
    if version_id is not None and int(item["version_id"]) != int(version_id):
        raise ValueError("Timetable class does not belong to the selected version.")
    item["start_period"] = item["period_number"]
    item["staff"] = _staff_rows(conn, item["offering_id"])
    item["groups"] = _group_rows(conn, item["offering_id"])
    item["version_status"] = _version_status(conn, item["version_id"])
    return item


def _room_precheck(conn, item: dict, room_id: int) -> list[str]:
    room = next((room for room in get_rooms(conn) if int(room["room_id"]) == int(room_id)), None)
    if room is None:
        return ["Cannot use this room: it is missing or inactive."]
    errors = []
    students = int(item["student_count"])
    if int(room["capacity"]) < students:
        errors.append(
            f"Cannot use {room['room_name']}: capacity {room['capacity']} is below required {students}."
        )
    if not room_type_compatible(item["required_room_type"], room["room_type"]):
        errors.append(
            f"Cannot use {room['room_name']}: {item['required_room_type']} requirement is not satisfied by {room['room_type']}."
        )
    part = {
        "equipment_requirements": _equipment_requirements(conn, item["session_template_id"]),
    }
    if not room_equipment_ok(part, room):
        errors.append(f"Cannot use {room['room_name']}: required room equipment is not available.")
    return errors


def _staff_precheck(conn, item: dict, staff_id: int) -> list[str]:
    staff = conn.execute(
        """SELECT s.staff_id,s.staff_number,s.first_name,s.last_name,f.faculty_code,f.faculty_name
           FROM staff s JOIN departments d ON d.department_id=s.department_id
           JOIN faculties f ON f.faculty_id=d.faculty_id WHERE s.staff_id=?""",
        (staff_id,),
    ).fetchone()
    if staff is None:
        return ["Cannot assign lecturer: staff member was not found."]
    eligible = {int(x["staff_id"]) for x in get_lecturers(conn, item["module_id"])}
    if int(staff_id) not in eligible:
        return [
            f"Cannot assign {staff['staff_number']} ({staff['faculty_code']}): "
            f"{item['module_code']} belongs to faculty {item['faculty_code']} and no cross-faculty permission exists."
        ]
    return []


def _normalise_proposal(item: dict, proposal: dict) -> dict:
    result = {
        "day": proposal.get("day", item["day_of_week"]),
        "start_period": int(proposal.get("start_period", item["period_number"])),
        "room_id": int(proposal.get("room_id", item["room_id"])),
    }
    if proposal.get("staff_id") not in (None, ""):
        result["staff_id"] = int(proposal["staff_id"])
    return result


def _apply_proposal(conn, item: dict, proposal: dict) -> None:
    day = proposal["day"]
    start = int(proposal["start_period"])
    duration = int(item["duration_slots"])
    if day not in {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday"}:
        raise ValueError("Invalid timetable day.")
    if start < 1 or start + duration - 1 > 10:
        raise ValueError("The class would extend outside the timetable day.")
    slot = conn.execute(
        "SELECT slot_id FROM time_slots WHERE day_of_week=? AND period_number=?", (day, start)
    ).fetchone()
    if slot is None:
        raise ValueError("Invalid timetable day/period.")

    # Time changes belong to the logical part, so synchronized room sections move together.
    conn.execute(
        "UPDATE timetable_entries SET slot_id=? WHERE version_id=? AND part_id=?",
        (slot["slot_id"], item["version_id"], item["part_id"]),
    )
    # The selected room belongs only to the selected section/entry.
    conn.execute("UPDATE timetable_entries SET room_id=? WHERE entry_id=?", (proposal["room_id"], item["entry_id"]))

    if "staff_id" in proposal:
        conn.execute(
            "DELETE FROM offering_staff WHERE offering_id=? AND lower(role)='lecturer'",
            (item["offering_id"],),
        )
        conn.execute(
            "INSERT OR IGNORE INTO offering_staff(offering_id,staff_id,role) VALUES (?,?,'Lecturer')",
            (item["offering_id"], proposal["staff_id"]),
        )


def _evaluate(conn, entry_id: int, proposal: dict, persist: bool) -> dict:
    item = _entry_context(conn, entry_id)
    original_status = _require_editable(conn, item["version_id"])
    if item["is_locked"]:
        raise ValueError("This timetable class is locked. Unlock it before editing.")
    normalized = _normalise_proposal(item, proposal)

    errors = []
    errors.extend(_room_precheck(conn, item, normalized["room_id"]))
    if "staff_id" in normalized:
        errors.extend(_staff_precheck(conn, item, normalized["staff_id"]))
    if errors:
        return {"valid": False, "errors": errors, "warnings": [], "alternatives": []}

    conn.execute("SAVEPOINT manual_timetable_change")
    try:
        _apply_proposal(conn, item, normalized)
        report = validate_version(conn, item["version_id"])
        if report.total:
            errors = [entry["message"] for entry in report.items]
            conn.execute("ROLLBACK TO manual_timetable_change")
            conn.execute("RELEASE manual_timetable_change")
            return {"valid": False, "errors": errors, "warnings": [], "alternatives": []}
        if persist:
            if original_status == "APPROVED":
                conn.execute(
                    "UPDATE timetable_versions SET status='DRAFT',published_at=NULL WHERE version_id=?",
                    (item["version_id"],),
                )
            conn.execute("RELEASE manual_timetable_change")
            conn.commit()
        else:
            conn.execute("ROLLBACK TO manual_timetable_change")
            conn.execute("RELEASE manual_timetable_change")
        return {"valid": True, "errors": [], "warnings": [], "alternatives": []}
    except Exception:
        try:
            conn.execute("ROLLBACK TO manual_timetable_change")
            conn.execute("RELEASE manual_timetable_change")
        except Exception:
            pass
        if persist:
            conn.rollback()
        raise


def validate_manual_change(conn, entry_id: int, proposal: dict) -> dict:
    return _evaluate(conn, entry_id, proposal, persist=False)


def save_manual_change(conn, entry_id: int, proposal: dict, actor_user_id: int) -> dict:
    user = conn.execute("SELECT role FROM users WHERE user_id=? AND is_active=1", (actor_user_id,)).fetchone()
    if user is None or user["role"] != "ADMIN":
        raise PermissionError("Only an administrator can edit timetable classes.")
    result = _evaluate(conn, entry_id, proposal, persist=True)
    if not result["valid"]:
        raise ValueError("Change rejected: " + "; ".join(result["errors"][:5]))
    return result


def set_entry_lock(conn, entry_id: int, locked: bool, actor_user_id: int) -> None:
    user = conn.execute("SELECT role FROM users WHERE user_id=? AND is_active=1", (actor_user_id,)).fetchone()
    if user is None or user["role"] != "ADMIN":
        raise PermissionError("Only an administrator can lock timetable classes.")
    item = _entry_context(conn, entry_id)
    _require_editable(conn, item["version_id"])
    conn.execute(
        "UPDATE timetable_entries SET is_locked=? WHERE version_id=? AND part_id=?",
        (1 if locked else 0, item["version_id"], item["part_id"]),
    )
    conn.commit()


def suggest_placements(conn, entry_id: int, limit: int = 5) -> list[dict]:
    """Return explainable, hard-valid alternatives for one editable timetable entry."""
    from scheduler.engine import rank_manual_candidates

    item = _entry_context(conn, entry_id)
    _require_editable(conn, item["version_id"])
    part = {
        "duration_slots": int(item["duration_slots"]),
        "expected_students": int(item["student_count"]),
        "faculty_id": int(item["faculty_id"]),
        "required_room_type": item["required_room_type"],
        "equipment_requirements": _equipment_requirements(conn, item["session_template_id"]),
    }
    candidates = rank_manual_candidates(part, get_rooms(conn))
    suggestions = []
    seen = set()
    # Static ranking puts faculty/capacity fit first; full validator then removes live clashes.
    for candidate in candidates:
        if len(candidate["rooms"]) != 1:
            continue
        room = candidate["rooms"][0]
        key = (candidate["day"], candidate["start_period"], room["room_id"])
        if key in seen:
            continue
        seen.add(key)
        proposal = {
            "day": candidate["day"],
            "start_period": candidate["start_period"],
            "room_id": room["room_id"],
        }
        checked = validate_manual_change(conn, entry_id, proposal)
        if not checked["valid"]:
            continue
        rank = len(suggestions)
        suggestions.append(
            {
                "day": candidate["day"],
                "start_period": candidate["start_period"],
                "end_period": candidate["start_period"] + int(item["duration_slots"]) - 1,
                "room_id": room["room_id"],
                "room_name": room["room_name"],
                "room_code": room["room_code"],
                "capacity": int(room["capacity"]),
                "students": int(item["student_count"]),
                "faculty_preferred": room.get("faculty_id") == item["faculty_id"],
                "room_compatible": True,
                "lecturer_available": True,
                "student_group_available": True,
                "room_available": True,
                "score": float(candidate["base_score"]),
                "quality": "Best option" if rank == 0 else ("Good alternative" if rank < 3 else "Valid alternative"),
            }
        )
        if len(suggestions) >= max(1, int(limit)):
            break
    return suggestions
