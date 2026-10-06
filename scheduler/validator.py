from collections import defaultdict

from scheduler.engine import _equipment_requirements, _group_ids, _staff_ids, periods
from scheduler.policy import SPLIT, split_eligible


class ValidationReport:
    def __init__(self):
        self.items = []

    def add(self, category, message):
        self.items.append({"category": category, "message": message})

    @property
    def total(self):
        return len(self.items)

    def count(self, category):
        return sum(1 for item in self.items if item["category"] == category)

    def as_dict(self):
        categories = defaultdict(int)
        for item in self.items:
            categories[item["category"]] += 1
        return {"total": self.total, "categories": dict(categories), "items": self.items}


def _rows(conn, version_id):
    return conn.execute(
        """
        SELECT
            te.entry_id, te.version_id, te.room_id, te.slot_id, te.duration_slots,
            te.is_locked, te.part_id,
            ss.section_id, ss.session_id AS section_session_id, ss.section_name, ss.student_count,
            r.room_name, r.room_type, r.capacity,
            ts.day_of_week, ts.period_number,
            sp.session_id AS part_session_id, sp.representation_type, sp.part_number,
            sp.duration_slots AS part_duration, sp.is_split_part,
            cs.duration_slots AS logical_duration,
            st.session_template_id, st.offering_id, st.session_type,
            st.required_room_type, st.can_split_duration,
            mo.expected_students,
            m.module_code, m.module_name
        FROM timetable_entries te
        JOIN session_sections ss ON ss.section_id=te.section_id
        JOIN rooms r ON r.room_id=te.room_id
        JOIN time_slots ts ON ts.slot_id=te.slot_id
        JOIN session_parts sp ON sp.part_id=te.part_id
        JOIN class_sessions cs ON cs.session_id=sp.session_id
        JOIN session_templates st ON st.session_template_id=cs.session_template_id
        JOIN module_offerings mo ON mo.offering_id=st.offering_id
        JOIN modules m ON m.module_id=mo.module_id
        WHERE te.version_id=?
        ORDER BY ts.day_of_week, ts.period_number, te.entry_id
        """,
        (version_id,),
    ).fetchall()


def validate_version(conn, version_id):
    report = ValidationReport()
    rows = _rows(conn, version_id)
    if not rows:
        report.add("missing", "Timetable version contains no entries.")
        return report

    # Basic row integrity, capacity, room type and equipment.
    for row in rows:
        if row["part_id"] is None:
            report.add("representation", f"Entry {row['entry_id']} has no part_id.")
            continue
        if row["section_session_id"] != row["part_session_id"]:
            report.add("representation", f"Entry {row['entry_id']} part/session parent mismatch.")
        if row["duration_slots"] != row["part_duration"]:
            report.add("duration", f"Entry {row['entry_id']} duration does not match its immutable part.")
        if row["student_count"] > row["capacity"]:
            report.add("capacity", f"{row['module_code']} section exceeds room capacity in {row['room_name']}.")

        required = row["required_room_type"]
        actual = row["room_type"]
        from scheduler.engine import room_type_compatible
        if not room_type_compatible(required, actual):
            report.add("room_type", f"{row['module_code']} requires {required} but uses {actual}.")

        reqs = _equipment_requirements(conn, row["session_template_id"])
        inventory = {
            r[0]: r[1]
            for r in conn.execute(
                "SELECT equipment_id, quantity FROM room_equipment WHERE room_id=?",
                (row["room_id"],),
            )
        }
        for equipment_id, needed in reqs.items():
            if inventory.get(equipment_id, 0) < needed:
                report.add("equipment", f"{row['module_code']} uses {row['room_name']} without enough required equipment.")

    # Distinct part facts; multiple room sections of one part must be synchronized.
    by_part = defaultdict(list)
    for row in rows:
        by_part[row["part_id"]].append(row)
    for part_id, group in by_part.items():
        signature = {(r["day_of_week"], r["period_number"], r["duration_slots"]) for r in group}
        if len(signature) != 1:
            report.add("synchronization", f"Part {part_id} room sections are not simultaneous.")
        total_students = sum(r["student_count"] for r in group)
        if total_students != group[0]["expected_students"]:
            report.add(
                "capacity",
                f"{group[0]['module_code']} part {part_id} allocates {total_students} students; expected {group[0]['expected_students']}.",
            )

    # Representation / contact-time rules per logical session.
    by_session = defaultdict(dict)
    for part_id, group in by_part.items():
        first = group[0]
        by_session[first["part_session_id"]][part_id] = first

    for session_id, parts in by_session.items():
        values = list(parts.values())
        representations = {r["representation_type"] for r in values}
        if len(representations) != 1:
            report.add("representation", f"Session {session_id} mixes CONTINUOUS and SPLIT representations.")
            continue
        representation = next(iter(representations))
        first = values[0]
        session = {
            "session_type": first["session_type"],
            "duration_slots": first["logical_duration"],
            "can_split_duration": first["can_split_duration"],
        }
        distinct_duration = sum(r["part_duration"] for r in values)
        if distinct_duration != first["logical_duration"]:
            report.add("contact_time", f"Session {session_id} schedules {distinct_duration} slots; requires {first['logical_duration']}.")

        stype = str(first["session_type"]).strip().lower()
        if representation == SPLIT:
            if not split_eligible(session):
                report.add("representation", f"Session {session_id} is not legally splittable.")
            if len(values) != 2 or sorted(r["part_number"] for r in values) != [1, 2]:
                report.add("representation", f"Session {session_id} SPLIT representation is incomplete.")
            days = {r["day_of_week"] for r in values}
            if len(days) != len(values):
                report.add("representation", f"Session {session_id} split siblings occur on the same day.")
        else:
            if len(values) != 1 or values[0]["part_number"] != 1:
                report.add("representation", f"Session {session_id} CONTINUOUS representation is invalid.")

        if stype in {"practical", "laboratory", "lab"} and representation == SPLIT:
            report.add("duration_policy", f"{first['module_code']} {first['session_type']} may not be split.")

    # Time conflicts across distinct parts.
    part_items = []
    for part_id, group in by_part.items():
        first = group[0]
        part_items.append(
            {
                "part_id": part_id,
                "session_id": first["part_session_id"],
                "day": first["day_of_week"],
                "start_period": first["period_number"],
                "duration_slots": first["duration_slots"],
                "room_ids": {r["room_id"] for r in group},
                "group_ids": _group_ids(conn, first["offering_id"]),
                "staff_ids": _staff_ids(conn, first["offering_id"]),
                "module_code": first["module_code"],
            }
        )
    for i, a in enumerate(part_items):
        for b in part_items[i + 1 :]:
            if a["day"] != b["day"]:
                continue
            pa = {"start_period": a["start_period"]}
            pb = {"start_period": b["start_period"]}
            if not periods(a, pa) & periods(b, pb):
                continue
            if a["room_ids"] & b["room_ids"]:
                report.add("room_clash", f"Room clash: {a['module_code']} and {b['module_code']}.")
            if a["group_ids"] & b["group_ids"]:
                report.add("student_clash", f"Student clash: {a['module_code']} and {b['module_code']}.")
            if a["staff_ids"] & b["staff_ids"]:
                report.add("lecturer_clash", f"Lecturer clash: {a['module_code']} and {b['module_code']}.")

    return report


def latest_version_for_semester(conn, semester_id):
    row = conn.execute(
        "SELECT version_id FROM timetable_versions WHERE semester_id=? ORDER BY version_number DESC LIMIT 1",
        (semester_id,),
    ).fetchone()
    return None if row is None else row["version_id"]
