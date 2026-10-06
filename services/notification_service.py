"""In-app timetable notification helpers.

Write helpers deliberately do not commit so publication can keep status changes and
notifications in one transaction.
"""
from __future__ import annotations


def unread_count(conn, user_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE recipient_user_id=? AND read_at IS NULL",
        (user_id,),
    ).fetchone()[0]


def list_notifications(conn, user_id: int, limit: int = 100) -> list[dict]:
    rows = conn.execute(
        """SELECT notification_id,recipient_user_id,notification_type,title,message,
                  version_id,entry_id,created_at,read_at
           FROM notifications
           WHERE recipient_user_id=?
           ORDER BY created_at DESC, notification_id DESC
           LIMIT ?""",
        (user_id, int(limit)),
    ).fetchall()
    return [dict(r) for r in rows]


def mark_read(conn, user_id: int, notification_id: int) -> bool:
    cur = conn.execute(
        """UPDATE notifications
           SET read_at=COALESCE(read_at,CURRENT_TIMESTAMP)
           WHERE notification_id=? AND recipient_user_id=?""",
        (notification_id, user_id),
    )
    return cur.rowcount > 0


def mark_all_read(conn, user_id: int) -> int:
    cur = conn.execute(
        """UPDATE notifications SET read_at=CURRENT_TIMESTAMP
           WHERE recipient_user_id=? AND read_at IS NULL""",
        (user_id,),
    )
    return cur.rowcount


def _version_entries(conn, version_id: int) -> dict[tuple[int, int], dict]:
    rows = conn.execute(
        """SELECT te.entry_id,te.part_id,te.section_id,te.room_id,
                  ts.day_of_week,ts.period_number,
                  r.room_name,r.room_code,
                  st.offering_id,m.module_code,m.module_name
           FROM timetable_entries te
           JOIN time_slots ts ON ts.slot_id=te.slot_id
           JOIN rooms r ON r.room_id=te.room_id
           JOIN session_parts sp ON sp.part_id=te.part_id
           JOIN class_sessions cs ON cs.session_id=sp.session_id
           JOIN session_templates st ON st.session_template_id=cs.session_template_id
           JOIN module_offerings mo ON mo.offering_id=st.offering_id
           JOIN modules m ON m.module_id=mo.module_id
           WHERE te.version_id=?
           ORDER BY te.entry_id""",
        (version_id,),
    ).fetchall()
    result = {}
    for raw in rows:
        row = dict(raw)
        key = (row["part_id"], row["section_id"])
        item = result.setdefault(
            key,
            {
                "part_id": row["part_id"],
                "section_id": row["section_id"],
                "offering_id": row["offering_id"],
                "module_code": row["module_code"],
                "module_name": row["module_name"],
                "day_of_week": row["day_of_week"],
                "period_number": row["period_number"],
                "room_ids": set(),
                "room_names": set(),
                "entry_ids": [],
            },
        )
        item["room_ids"].add(row["room_id"])
        item["room_names"].add(row["room_name"])
        item["entry_ids"].append(row["entry_id"])
    return result


def _recipient_user_ids(conn, section_id: int, offering_id: int) -> set[int]:
    student_rows = conn.execute(
        """SELECT DISTINCT u.user_id
           FROM section_student_assignments ssa
           JOIN users u ON u.student_id=ssa.student_id
           WHERE ssa.section_id=? AND u.role='STUDENT' AND u.is_active=1""",
        (section_id,),
    ).fetchall()
    lecturer_rows = conn.execute(
        """SELECT DISTINCT u.user_id
           FROM offering_staff os
           JOIN users u ON u.staff_id=os.staff_id
           WHERE os.offering_id=? AND u.role='LECTURER' AND u.is_active=1""",
        (offering_id,),
    ).fetchall()
    return {r[0] for r in student_rows} | {r[0] for r in lecturer_rows}


def _insert_notification(conn, recipient_user_id: int, notification_type: str, title: str, message: str, version_id: int, entry_id=None) -> None:
    conn.execute(
        """INSERT INTO notifications(
               recipient_user_id,notification_type,title,message,version_id,entry_id
           ) VALUES (?,?,?,?,?,?)""",
        (recipient_user_id, notification_type, title, message, version_id, entry_id),
    )


def _rooms_text(item: dict) -> str:
    return ", ".join(sorted(item["room_names"])) or "venue to be confirmed"


def create_publish_notifications(conn, new_version_id: int, previous_version_id: int | None) -> int:
    """Create notifications for a publication without committing the transaction."""
    new_entries = _version_entries(conn, new_version_id)
    created = 0

    if previous_version_id is None:
        recipients = set()
        for item in new_entries.values():
            recipients.update(_recipient_user_ids(conn, item["section_id"], item["offering_id"]))
        for user_id in sorted(recipients):
            _insert_notification(
                conn,
                user_id,
                "TIMETABLE_PUBLISHED",
                "Timetable published",
                "A new Sol Plaatje University academic timetable has been published. Open My Timetable to view your classes.",
                new_version_id,
                None,
            )
            created += 1
        return created

    old_entries = _version_entries(conn, previous_version_id)
    for key, new_item in new_entries.items():
        old_item = old_entries.get(key)
        if old_item is None:
            notification_type = "TIMETABLE_PUBLISHED"
            title = "New class scheduled"
            message = (
                f"{new_item['module_code']} is scheduled for {new_item['day_of_week']} "
                f"Period {new_item['period_number']} in {_rooms_text(new_item)}."
            )
        else:
            time_changed = (
                old_item["day_of_week"] != new_item["day_of_week"]
                or old_item["period_number"] != new_item["period_number"]
            )
            venue_changed = old_item["room_ids"] != new_item["room_ids"]
            if not (time_changed or venue_changed):
                continue
            if time_changed and venue_changed:
                notification_type = "CLASS_MOVED"
                title = "Class moved"
            elif time_changed:
                notification_type = "TIME_CHANGED"
                title = "Class time changed"
            else:
                notification_type = "VENUE_CHANGED"
                title = "Venue changed"
            message = (
                f"{new_item['module_code']} changed from {old_item['day_of_week']} "
                f"Period {old_item['period_number']} ({_rooms_text(old_item)}) to "
                f"{new_item['day_of_week']} Period {new_item['period_number']} ({_rooms_text(new_item)})."
            )

        recipients = _recipient_user_ids(conn, new_item["section_id"], new_item["offering_id"])
        entry_id = min(new_item["entry_ids"]) if new_item["entry_ids"] else None
        for user_id in sorted(recipients):
            _insert_notification(
                conn, user_id, notification_type, title, message, new_version_id, entry_id
            )
            created += 1
    return created
