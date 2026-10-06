"""Presentation helpers for SPU-style campus timetables."""
from __future__ import annotations

from services.timetable_service import DAYS


DEFAULT_FACULTY_COLOUR = "#E5E7EB"


def _period_definitions(conn):
    rows = conn.execute(
        """SELECT period_number, MIN(start_time) AS start_time, MIN(end_time) AS end_time
           FROM time_slots GROUP BY period_number ORDER BY period_number"""
    ).fetchall()
    by_period = {int(r["period_number"]): {"period_number": int(r["period_number"]), "start_time": r["start_time"], "end_time": r["end_time"]} for r in rows}
    return [by_period.get(p, {"period_number": p, "start_time": "", "end_time": ""}) for p in range(1, 11)]


def campus_timetable_grid(conn, rows: list[dict]) -> dict:
    """Transform entry rows into day -> venue -> P1..P10 cells.

    All active teaching rooms are retained so the campus view has the same
    venue-first shape as the supplied SPU timetable. A multi-period class is
    deliberately repeated in each occupied period cell.
    """
    rooms = [dict(r) for r in conn.execute(
        """SELECT room_id,room_code,room_name,capacity,room_type
           FROM rooms WHERE is_active=1 ORDER BY room_name,room_code"""
    ).fetchall()]
    days = []
    for day in DAYS:
        venues = []
        for room in rooms:
            venue = dict(room)
            venue["cells"] = {p: [] for p in range(1, 11)}
            venues.append(venue)
        days.append({"day": day, "venues": venues})

    day_lookup = {d["day"]: d for d in days}
    venue_lookup = {
        (d["day"], v["room_id"]): v
        for d in days
        for v in d["venues"]
    }
    for source in rows:
        row = dict(source)
        day = row.get("day_of_week")
        room_id = row.get("room_id")
        if day not in day_lookup or (day, room_id) not in venue_lookup:
            continue
        start = int(row.get("period_number") or 0)
        duration = max(1, int(row.get("duration_slots") or 1))
        row["colour_hex"] = row.get("colour_hex") or DEFAULT_FACULTY_COLOUR
        for period in range(start, min(10, start + duration - 1) + 1):
            cell_row = dict(row)
            cell_row["display_period"] = period
            venue_lookup[(day, room_id)]["cells"][period].append(cell_row)

    return {
        "periods": _period_definitions(conn),
        "days": days,
        "entry_count": len(rows),
    }


def campus_filter_options(conn, semester_id: int) -> dict[str, list[dict]]:
    """Return sorted filter values that are relevant to one semester."""
    faculties = [dict(r) for r in conn.execute(
        """SELECT DISTINCT f.faculty_id,f.faculty_code,f.faculty_name
           FROM module_offerings mo
           JOIN modules m ON m.module_id=mo.module_id
           JOIN departments d ON d.department_id=m.department_id
           JOIN faculties f ON f.faculty_id=d.faculty_id
           WHERE mo.semester_id=? ORDER BY f.faculty_name""",
        (semester_id,),
    ).fetchall()]
    programmes = [dict(r) for r in conn.execute(
        """SELECT DISTINCT p.programme_id,p.programme_code,p.programme_name
           FROM module_offerings mo
           JOIN offering_groups og ON og.offering_id=mo.offering_id
           JOIN student_groups sg ON sg.group_id=og.group_id
           JOIN programmes p ON p.programme_id=sg.programme_id
           WHERE mo.semester_id=? ORDER BY p.programme_name""",
        (semester_id,),
    ).fetchall()]
    years = [dict(r) for r in conn.execute(
        """SELECT DISTINCT sg.year_level
           FROM module_offerings mo
           JOIN offering_groups og ON og.offering_id=mo.offering_id
           JOIN student_groups sg ON sg.group_id=og.group_id
           WHERE mo.semester_id=? ORDER BY sg.year_level""",
        (semester_id,),
    ).fetchall()]
    modules = [dict(r) for r in conn.execute(
        """SELECT DISTINCT m.module_id,m.module_code,m.module_name
           FROM module_offerings mo JOIN modules m ON m.module_id=mo.module_id
           WHERE mo.semester_id=? ORDER BY m.module_code""",
        (semester_id,),
    ).fetchall()]
    lecturers = [dict(r) for r in conn.execute(
        """SELECT DISTINCT s.staff_id,s.staff_number,s.first_name,s.last_name
           FROM module_offerings mo
           JOIN offering_staff os ON os.offering_id=mo.offering_id
           JOIN staff s ON s.staff_id=os.staff_id
           WHERE mo.semester_id=? ORDER BY s.last_name,s.first_name""",
        (semester_id,),
    ).fetchall()]
    rooms = [dict(r) for r in conn.execute(
        "SELECT room_id,room_code,room_name,capacity FROM rooms WHERE is_active=1 ORDER BY room_name,room_code"
    ).fetchall()]
    return {
        "faculties": faculties,
        "programmes": programmes,
        "years": years,
        "modules": modules,
        "lecturers": lecturers,
        "rooms": rooms,
        "days": [{"value": d, "label": d} for d in DAYS],
    }
