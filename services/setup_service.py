from scheduler.policy import split_eligible


def create_offering(
    conn,
    module_id,
    semester_id,
    expected_students,
    group_ids,
    staff_ids,
    session_type,
    sessions_per_week,
    duration_slots,
    required_room_type,
    can_split_duration=False,
    equipment_ids=None,
):
    group_ids = [int(x) for x in group_ids]
    staff_ids = [int(x) for x in staff_ids]
    equipment_ids = [int(x) for x in (equipment_ids or [])]
    if not group_ids:
        raise ValueError("At least one student group is required.")
    if not staff_ids:
        raise ValueError("At least one lecturer/staff member is required.")
    expected_students = int(expected_students)
    sessions_per_week = int(sessions_per_week)
    duration_slots = int(duration_slots)
    if expected_students <= 0 or sessions_per_week <= 0 or duration_slots not in (1, 2):
        raise ValueError("Invalid expected_students, sessions_per_week or duration_slots.")
    existing = conn.execute(
        "SELECT 1 FROM module_offerings WHERE module_id=? AND semester_id=?",
        (module_id, semester_id),
    ).fetchone()
    if existing:
        raise ValueError("That module already has an offering in the selected semester.")

    cur = conn.execute(
        "INSERT INTO module_offerings(module_id, semester_id, expected_students) VALUES (?, ?, ?)",
        (module_id, semester_id, expected_students),
    )
    offering_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO offering_groups(offering_id, group_id) VALUES (?, ?)",
        [(offering_id, gid) for gid in group_ids],
    )
    conn.executemany(
        "INSERT INTO offering_staff(offering_id, staff_id) VALUES (?, ?)",
        [(offering_id, sid) for sid in staff_ids],
    )

    if str(session_type).strip().lower() in {"practical", "laboratory", "lab"}:
        can_split_duration = False
        duration_slots = 2
    template_id = conn.execute(
        """INSERT INTO session_templates(
               offering_id, session_type, sessions_per_week, preferred_duration,
               minimum_duration, required_room_type, can_split_duration
           ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            offering_id,
            session_type,
            sessions_per_week,
            duration_slots,
            1 if str(session_type).strip().lower() == "lecture" else duration_slots,
            required_room_type,
            1 if can_split_duration else 0,
        ),
    ).lastrowid
    conn.executemany(
        "INSERT INTO session_requirements(session_template_id, equipment_id, quantity_required) VALUES (?, ?, 1)",
        [(template_id, eid) for eid in equipment_ids],
    )
    for number in range(1, sessions_per_week + 1):
        session_id = conn.execute(
            "INSERT INTO class_sessions(session_template_id, session_number, duration_slots) VALUES (?, ?, ?)",
            (template_id, number, duration_slots),
        ).lastrowid
        conn.execute(
            """INSERT INTO session_parts(
                   session_id, representation_type, part_number, duration_slots, is_split_part
               ) VALUES (?, 'CONTINUOUS', 1, ?, 0)""",
            (session_id, duration_slots),
        )
    return offering_id
