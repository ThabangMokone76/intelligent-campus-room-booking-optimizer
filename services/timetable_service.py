from scheduler.engine import latest_version
from scheduler.validator import validate_version
from services.notification_service import create_publish_notifications

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


def visible_version(conn, semester_id, role):
    if role == "ADMIN":
        return latest_version(conn, semester_id)
    row = conn.execute(
        "SELECT * FROM timetable_versions WHERE semester_id=? AND status='PUBLISHED' ORDER BY version_number DESC LIMIT 1",
        (semester_id,),
    ).fetchone()
    return None if row is None else dict(row)


def _lecturer_names(conn, offering_id):
    rows = conn.execute(
        """SELECT s.first_name || ' ' || s.last_name AS name
           FROM offering_staff os JOIN staff s ON s.staff_id=os.staff_id
           WHERE os.offering_id=? ORDER BY s.last_name,s.first_name""",
        (offering_id,),
    ).fetchall()
    return ", ".join(r[0] for r in rows)


def timetable_rows(conn, version_id, user=None, filters=None):
    conditions = ["te.version_id=?"]
    params = [version_id]
    if user and user.get("role") == "LECTURER" and user.get("staff_id"):
        conditions.append("EXISTS (SELECT 1 FROM offering_staff os WHERE os.offering_id=st.offering_id AND os.staff_id=?)")
        params.append(user["staff_id"])
    if user and user.get("role") == "STUDENT" and user.get("student_id"):
        conditions.append("EXISTS (SELECT 1 FROM section_student_assignments ssa WHERE ssa.section_id=te.section_id AND ssa.student_id=?)")
        params.append(user["student_id"])
    elif user and user.get("role") == "STUDENT" and user.get("group_id"):
        conditions.append("EXISTS (SELECT 1 FROM offering_groups og WHERE og.offering_id=st.offering_id AND og.group_id=?)")
        params.append(user["group_id"])
    filters = filters or {}
    if filters.get("faculty_id"):
        conditions.append("f.faculty_id=?")
        params.append(int(filters["faculty_id"]))
    if filters.get("programme_id"):
        conditions.append("EXISTS (SELECT 1 FROM offering_groups fog JOIN student_groups fsg ON fsg.group_id=fog.group_id WHERE fog.offering_id=st.offering_id AND fsg.programme_id=?)")
        params.append(int(filters["programme_id"]))
    if filters.get("year_level"):
        conditions.append("EXISTS (SELECT 1 FROM offering_groups yog JOIN student_groups ysg ON ysg.group_id=yog.group_id WHERE yog.offering_id=st.offering_id AND ysg.year_level=?)")
        params.append(int(filters["year_level"]))
    if filters.get("group_id"):
        conditions.append("EXISTS (SELECT 1 FROM offering_groups gog WHERE gog.offering_id=st.offering_id AND gog.group_id=?)")
        params.append(int(filters["group_id"]))
    if filters.get("module_id"):
        conditions.append("m.module_id=?")
        params.append(int(filters["module_id"]))
    if filters.get("staff_id"):
        conditions.append("EXISTS (SELECT 1 FROM offering_staff fos WHERE fos.offering_id=st.offering_id AND fos.staff_id=?)")
        params.append(int(filters["staff_id"]))
    if filters.get("room_id"):
        conditions.append("r.room_id=?")
        params.append(int(filters["room_id"]))
    if filters.get("day"):
        conditions.append("ts.day_of_week=?")
        params.append(str(filters["day"]))
    rows = conn.execute(
        f"""
        SELECT te.entry_id, te.part_id, te.is_locked, te.duration_slots,
               ts.day_of_week, ts.period_number, ts.start_time, ts.end_time,
               r.room_id, r.room_name, r.room_code, r.capacity,
               ss.section_id, ss.section_name, ss.student_count,
               sp.representation_type, sp.part_number,
               cs.session_number,
               mo.offering_id,
               m.module_id, m.module_code, m.module_name,
               st.session_type,
               f.faculty_code, f.faculty_name, f.colour_hex
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
        WHERE {' AND '.join(conditions)}
        ORDER BY CASE ts.day_of_week
            WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3
            WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 END,
            ts.period_number, m.module_code, ss.section_name
        """,
        params,
    ).fetchall()
    result=[]
    for row in rows:
        item=dict(row); item['lecturers']=_lecturer_names(conn,item['offering_id']); result.append(item)
    return result


def timetable_grid(rows):
    grid={day:{period:[] for period in range(1,11)} for day in DAYS}
    for row in rows:
        grid[row['day_of_week']][row['period_number']].append(row)
    return grid


def _version(conn, version_id):
    row=conn.execute("SELECT * FROM timetable_versions WHERE version_id=?",(version_id,)).fetchone()
    if row is None: raise ValueError("Timetable version not found.")
    return dict(row)


def set_version_status(conn, version_id, status):
    # REVIEW is retained as a short-lived compatibility alias for older UI forms.
    if status == "REVIEW":
        status = "IN_REVIEW"
    if status not in {"IN_REVIEW", "APPROVED", "PUBLISHED"}:
        raise ValueError("Invalid timetable status transition.")
    version = _version(conn, version_id)
    current = version["status"]
    allowed = {
        ("DRAFT", "IN_REVIEW"),
        ("CHANGES_REQUESTED", "IN_REVIEW"),
        ("IN_REVIEW", "APPROVED"),
        ("APPROVED", "PUBLISHED"),
    }
    if (current, status) not in allowed:
        raise ValueError(f"Invalid timetable status transition: {current} -> {status}.")

    try:
        if status == "PUBLISHED":
            report = validate_version(conn, version_id)
            if report.total:
                raise ValueError(f"Cannot publish: {report.total} hard violation(s).")

            previous = conn.execute(
                """SELECT version_id FROM timetable_versions
                   WHERE semester_id=? AND status='PUBLISHED' AND version_id<>?
                   ORDER BY version_number DESC LIMIT 1""",
                (version["semester_id"], version_id),
            ).fetchone()
            previous_version_id = previous["version_id"] if previous else None

            conn.execute(
                "UPDATE timetable_versions SET status='APPROVED' WHERE semester_id=? AND status='PUBLISHED'",
                (version["semester_id"],),
            )
            conn.execute(
                "UPDATE timetable_versions SET status='PUBLISHED', published_at=CURRENT_TIMESTAMP WHERE version_id=?",
                (version_id,),
            )
            create_publish_notifications(conn, version_id, previous_version_id)
        else:
            conn.execute(
                "UPDATE timetable_versions SET status=?, published_at=NULL WHERE version_id=?",
                (status, version_id),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _require_draft(conn, version_id):
    if _version(conn,version_id)['status']!='DRAFT': raise ValueError('Only DRAFT timetables can be edited.')


def set_part_lock(conn, version_id, part_id, locked):
    _require_draft(conn,version_id)
    conn.execute("UPDATE timetable_entries SET is_locked=? WHERE version_id=? AND part_id=?",(1 if locked else 0,version_id,part_id)); conn.commit()


def move_part(conn, version_id, part_id, day, start_period, room_id=None):
    _require_draft(conn,version_id)
    rows=conn.execute("""SELECT te.*, sp.duration_slots, ss.student_count FROM timetable_entries te
        JOIN session_parts sp ON sp.part_id=te.part_id JOIN session_sections ss ON ss.section_id=te.section_id
        WHERE te.version_id=? AND te.part_id=? ORDER BY te.entry_id""",(version_id,part_id)).fetchall()
    if not rows: raise ValueError("Part not found in this timetable version.")
    duration=rows[0]['duration_slots']
    if start_period<1 or start_period+duration-1>10: raise ValueError("The move would extend outside the timetable day.")
    slot=conn.execute("SELECT slot_id FROM time_slots WHERE day_of_week=? AND period_number=?",(day,start_period)).fetchone()
    if slot is None: raise ValueError("Invalid day/period.")
    if room_id is not None and len(rows)!=1: raise ValueError("Room replacement is only supported for single-room parts.")
    try:
        for row in rows:
            new_room=int(room_id) if room_id is not None else row['room_id']
            conn.execute("UPDATE timetable_entries SET slot_id=?,room_id=? WHERE entry_id=?",(slot['slot_id'],new_room,row['entry_id']))
        report=validate_version(conn,version_id)
        if report.total: raise ValueError("Move rejected by hard-constraint validation: "+"; ".join(item['message'] for item in report.items[:5]))
        conn.commit()
    except Exception:
        conn.rollback(); raise
