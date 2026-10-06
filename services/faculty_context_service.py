"""Faculty-aware cascading choices for manual timetabling."""
from __future__ import annotations

from scheduler.engine import compatible_rooms, faculty_priority, get_rooms


def get_programmes(conn, faculty_id: int) -> list[dict]:
    rows = conn.execute(
        """SELECT p.programme_id,p.programme_code,p.programme_name,p.duration_years,
                  d.department_id,d.department_code
           FROM programmes p
           JOIN departments d ON d.department_id=p.department_id
           WHERE d.faculty_id=?
           ORDER BY p.programme_name,p.programme_code""",
        (int(faculty_id),),
    ).fetchall()
    return [dict(r) for r in rows]


def get_years(conn, programme_id: int) -> list[int]:
    rows = conn.execute(
        """SELECT DISTINCT year_level FROM (
               SELECT year_level FROM programme_modules WHERE programme_id=?
               UNION
               SELECT year_level FROM student_groups WHERE programme_id=?
           ) ORDER BY year_level""",
        (int(programme_id), int(programme_id)),
    ).fetchall()
    return [int(r[0]) for r in rows]


def get_modules(conn, programme_id: int, year_level: int) -> list[dict]:
    # Prefer the explicit curriculum map, but include modules already connected
    # to this programme/year through live offering groups.  Older/demo databases
    # may not yet have programme_modules populated even though the relationship
    # is unambiguous from student_groups -> offering_groups.
    rows = conn.execute(
        """WITH relevant_modules AS (
               SELECT pm.module_id,pm.year_level
               FROM programme_modules pm
               WHERE pm.programme_id=? AND pm.year_level=?
               UNION
               SELECT mo.module_id,sg.year_level
               FROM student_groups sg
               JOIN offering_groups og ON og.group_id=sg.group_id
               JOIN module_offerings mo ON mo.offering_id=og.offering_id
               WHERE sg.programme_id=? AND sg.year_level=?
           )
           SELECT DISTINCT m.module_id,m.module_code,m.module_name,m.module_type,
                  rm.year_level,d.department_id,d.department_code,
                  f.faculty_id,f.faculty_code,f.faculty_name
           FROM relevant_modules rm
           JOIN modules m ON m.module_id=rm.module_id
           JOIN departments d ON d.department_id=m.department_id
           JOIN faculties f ON f.faculty_id=d.faculty_id
           ORDER BY m.module_code""",
        (int(programme_id), int(year_level), int(programme_id), int(year_level)),
    ).fetchall()
    return [dict(r) for r in rows]


def get_student_groups(conn, programme_id: int, year_level: int) -> list[dict]:
    rows = conn.execute(
        """SELECT sg.group_id,sg.year_level,sg.number_of_students,sg.section_code,
                  p.programme_id,p.programme_code,p.programme_name
           FROM student_groups sg
           JOIN programmes p ON p.programme_id=sg.programme_id
           WHERE sg.programme_id=? AND sg.year_level=?
           ORDER BY sg.section_code,sg.group_id""",
        (int(programme_id), int(year_level)),
    ).fetchall()
    return [dict(r) for r in rows]


def _module_owner(conn, module_id: int):
    row = conn.execute(
        """SELECT m.module_id,m.department_id,d.faculty_id,d.department_code,
                  f.faculty_code,f.faculty_name
           FROM modules m
           JOIN departments d ON d.department_id=m.department_id
           JOIN faculties f ON f.faculty_id=d.faculty_id
           WHERE m.module_id=?""",
        (int(module_id),),
    ).fetchone()
    if row is None:
        raise ValueError("Module not found.")
    return dict(row)


def get_lecturers(conn, module_id: int, slot_ids: list[int] | None = None) -> list[dict]:
    owner = _module_owner(conn, module_id)
    rows = conn.execute(
        """SELECT s.staff_id,s.staff_number,s.first_name,s.last_name,s.email,s.staff_type,
                  d.department_id,d.department_code,d.faculty_id,
                  f.faculty_code,f.faculty_name,
                  CASE WHEN d.department_id=? THEN 0
                       WHEN d.faculty_id=? THEN 1
                       ELSE 2 END AS eligibility_rank,
                  CASE WHEN d.faculty_id=? THEN 0 ELSE 1 END AS cross_faculty
           FROM staff s
           JOIN departments d ON d.department_id=s.department_id
           JOIN faculties f ON f.faculty_id=d.faculty_id
           WHERE s.staff_type='Lecturer'
             AND (
                 d.faculty_id=?
                 OR EXISTS (
                     SELECT 1 FROM cross_faculty_teaching_permissions cfp
                     WHERE cfp.module_id=? AND cfp.staff_id=s.staff_id
                 )
             )
           ORDER BY eligibility_rank,s.last_name,s.first_name,s.staff_id""",
        (
            owner["department_id"], owner["faculty_id"], owner["faculty_id"],
            owner["faculty_id"], int(module_id),
        ),
    ).fetchall()
    result = [dict(r) for r in rows]
    # Optional slot filtering is intentionally conservative: if a staff member is
    # already teaching in any requested slot, remove them from the choices.
    if slot_ids:
        requested = {int(x) for x in slot_ids}
        filtered = []
        for item in result:
            busy = conn.execute(
                f"""SELECT 1
                    FROM timetable_entries te
                    JOIN session_parts sp ON sp.part_id=te.part_id
                    JOIN class_sessions cs ON cs.session_id=sp.session_id
                    JOIN session_templates st ON st.session_template_id=cs.session_template_id
                    JOIN offering_staff os ON os.offering_id=st.offering_id
                    WHERE os.staff_id=? AND te.slot_id IN ({','.join('?' for _ in requested)})
                    LIMIT 1""",
                [item["staff_id"], *sorted(requested)],
            ).fetchone()
            if not busy:
                filtered.append(item)
        result = filtered
    return result


def _module_room_requirements(conn, module_id: int, expected_students: int) -> dict:
    owner = _module_owner(conn, module_id)
    template = conn.execute(
        """SELECT st.session_template_id,st.required_room_type
           FROM session_templates st
           JOIN module_offerings mo ON mo.offering_id=st.offering_id
           WHERE mo.module_id=?
           ORDER BY mo.semester_id DESC,st.session_template_id
           LIMIT 1""",
        (int(module_id),),
    ).fetchone()
    required_room_type = template["required_room_type"] if template else None
    equipment = {}
    if template:
        equipment = {
            int(r["equipment_id"]): int(r["quantity_required"])
            for r in conn.execute(
                "SELECT equipment_id,quantity_required FROM session_requirements WHERE session_template_id=?",
                (template["session_template_id"],),
            )
        }
    return {
        "faculty_id": owner["faculty_id"],
        "expected_students": int(expected_students),
        "required_room_type": required_room_type,
        "equipment_requirements": equipment,
    }


def get_ranked_rooms(conn, module_id: int, expected_students: int, slot_ids: list[int] | None = None) -> list[dict]:
    part = _module_room_requirements(conn, module_id, expected_students)
    rooms = [r for r in compatible_rooms(part, get_rooms(conn)) if int(r["capacity"]) >= int(expected_students)]
    if slot_ids:
        requested = {int(x) for x in slot_ids}
        rooms = [
            r for r in rooms
            if not conn.execute(
                f"SELECT 1 FROM timetable_entries WHERE room_id=? AND slot_id IN ({','.join('?' for _ in requested)}) LIMIT 1",
                [r["room_id"], *sorted(requested)],
            ).fetchone()
        ]
    rooms.sort(
        key=lambda r: (
            faculty_priority(part, r),
            int(r["capacity"]) - int(expected_students),
            r["room_name"],
        )
    )
    faculty_codes = {int(r["faculty_id"]): r["faculty_code"] for r in conn.execute("SELECT faculty_id,faculty_code FROM faculties")}
    result = []
    for room in rooms:
        item = dict(room)
        item["faculty_priority"] = faculty_priority(part, room)
        item["capacity_waste"] = int(room["capacity"]) - int(expected_students)
        item["faculty_code"] = faculty_codes.get(item.get("faculty_id"), "SHARED")
        result.append(item)
    return result
