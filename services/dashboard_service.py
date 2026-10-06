"""Role-scoped dashboard context for Student and Lecturer users."""
from __future__ import annotations

from datetime import datetime

from services.timetable_service import DAYS, timetable_rows


def _unique(rows, key, fields):
    seen = set()
    out = []
    for row in rows:
        value = row.get(key)
        if value in seen:
            continue
        seen.add(value)
        out.append({field: row.get(field) for field in fields})
    return out


def personal_dashboard_context(conn, version_id: int | None, user: dict, today: str | None = None, now_time: str | None = None) -> dict:
    """Build a privacy-safe personal dashboard from the user's published rows."""
    role = user.get("role")
    empty = {
        "is_visible": False,
        "classes": [],
        "today_classes": [],
        "next_class": None,
        "modules": [],
        "venues": [],
        "groups": [],
    }
    if role not in {"STUDENT", "LECTURER"} or not version_id:
        return empty
    version = conn.execute(
        "SELECT status FROM timetable_versions WHERE version_id=?", (version_id,)
    ).fetchone()
    if version is None or version["status"] != "PUBLISHED":
        return empty

    rows = timetable_rows(conn, version_id, user)
    today = today or datetime.now().strftime("%A")
    now_time = now_time or datetime.now().strftime("%H:%M")
    today_rows = sorted(
        [r for r in rows if r["day_of_week"] == today],
        key=lambda r: (r["period_number"], r["module_code"], r["room_name"]),
    )

    next_class = None
    for row in today_rows:
        if row["start_time"] >= now_time:
            next_class = row
            break
    if next_class is None and today in DAYS:
        today_index = DAYS.index(today)
        future = sorted(
            [r for r in rows if r["day_of_week"] in DAYS and DAYS.index(r["day_of_week"]) > today_index],
            key=lambda r: (DAYS.index(r["day_of_week"]), r["period_number"], r["module_code"]),
        )
        if future:
            next_class = future[0]

    modules = _unique(rows, "module_id", ("module_id", "module_code", "module_name"))
    modules.sort(key=lambda x: x["module_code"] or "")
    venues = _unique(rows, "room_id", ("room_id", "room_code", "room_name"))
    venues.sort(key=lambda x: x["room_name"] or "")
    groups = _unique(rows, "section_id", ("section_id", "section_name", "student_count"))
    groups.sort(key=lambda x: x["section_name"] or "")

    return {
        "is_visible": True,
        "classes": rows,
        "today_classes": today_rows,
        "next_class": next_class,
        "modules": modules,
        "venues": venues,
        "groups": groups,
        "today": today,
        "role": role,
    }
