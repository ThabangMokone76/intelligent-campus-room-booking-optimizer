from database.security import generate_password_hash

from database.db import connect, init_database

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
PERIODS = [
    (1, "08:00", "08:45"),
    (2, "08:55", "09:40"),
    (3, "09:50", "10:35"),
    (4, "10:45", "11:30"),
    (5, "11:40", "12:25"),
    (6, "12:45", "13:20"),
    (7, "13:30", "14:15"),
    (8, "14:25", "15:10"),
    (9, "15:20", "16:05"),
    (10, "16:15", "17:00"),
]


def insert_id(conn, sql, params):
    return conn.execute(sql, params).lastrowid


def seed(path=None):
    init_database(path)
    conn = connect(path)
    try:
        if conn.execute("SELECT COUNT(*) FROM faculties").fetchone()[0] > 0:
            print("Demo data already present; seed skipped.")
            return

        faculties = {}
        for code, name in [
            ("EMS", "Economic and Management Sciences"),
            ("EDU", "Education"),
            ("HUM", "Humanities"),
            ("NAS", "Natural and Applied Sciences"),
        ]:
            faculties[code] = insert_id(
                conn,
                "INSERT INTO faculties(faculty_code, faculty_name) VALUES (?, ?)",
                (code, name),
            )

        departments = {}
        dept_rows = [
            ("CS", "Computer Science", "NAS"),
            ("MATH", "Mathematics", "NAS"),
            ("STAT", "Statistics", "NAS"),
            ("ACC", "Accounting", "EMS"),
            ("ED", "Education Studies", "EDU"),
            ("HIST", "History", "HUM"),
        ]
        for code, name, fcode in dept_rows:
            departments[code] = insert_id(
                conn,
                "INSERT INTO departments(faculty_id, department_code, department_name) VALUES (?, ?, ?)",
                (faculties[fcode], code, name),
            )

        programmes = {}
        programme_rows = [
            ("BCOMP", "BSc Computer Science", "CS", 3),
            ("BMATH", "BSc Mathematics", "MATH", 3),
            ("BSTAT", "BSc Statistics", "STAT", 3),
            ("BACC", "BCom Accounting", "ACC", 3),
            ("BED", "Bachelor of Education", "ED", 4),
            ("BHIST", "BA History", "HIST", 3),
        ]
        for code, name, dcode, years in programme_rows:
            programmes[code] = insert_id(
                conn,
                "INSERT INTO programmes(department_id, programme_code, programme_name, duration_years) VALUES (?, ?, ?, ?)",
                (departments[dcode], code, name, years),
            )

        groups = {}
        group_rows = [
            ("BCOMP", 1, 93),
            ("BMATH", 1, 70),
            ("BSTAT", 1, 65),
            ("BACC", 1, 82),
            ("BED", 1, 120),
            ("BHIST", 1, 58),
        ]
        for pcode, year, size in group_rows:
            groups[(pcode, year)] = insert_id(
                conn,
                "INSERT INTO student_groups(programme_id, year_level, number_of_students) VALUES (?, ?, ?)",
                (programmes[pcode], year, size),
            )

        buildings = {}
        for code, name, fcode, shared in [
            ("NAS_MAIN", "Natural Sciences Building", "NAS", 0),
            ("EMS_MAIN", "EMS Building", "EMS", 0),
            ("EDU_MAIN", "Education Building", "EDU", 0),
            ("HUM_MAIN", "Humanities Building", "HUM", 0),
            ("SHARED", "Shared Teaching Centre", None, 1),
        ]:
            buildings[code] = insert_id(
                conn,
                "INSERT INTO buildings(faculty_id, building_code, building_name, is_shared) VALUES (?, ?, ?, ?)",
                (faculties.get(fcode), code, name, shared),
            )

        room_rows = [
            ("N-LH1", "NAS Lecture Hall 1", "NAS_MAIN", 160, "Lecture Hall"),
            ("N-LH2", "NAS Lecture Hall 2", "NAS_MAIN", 120, "Lecture Hall"),
            ("N-CR1", "NAS Classroom 1", "NAS_MAIN", 80, "Classroom"),
            ("N-CL1", "Computer Lab 1", "NAS_MAIN", 60, "Computer Lab"),
            ("E-LH1", "EMS Lecture Hall", "EMS_MAIN", 120, "Lecture Hall"),
            ("D-LH1", "Education Lecture Hall", "EDU_MAIN", 150, "Lecture Hall"),
            ("H-LH1", "Humanities Lecture Hall", "HUM_MAIN", 100, "Lecture Hall"),
            ("S-AUD", "Shared Auditorium", "SHARED", 320, "Auditorium"),
            ("S-EXAM", "Shared Exam Hall", "SHARED", 300, "Exam Hall"),
            ("S-CR1", "Shared Classroom 1", "SHARED", 100, "Classroom"),
            ("S-CR2", "Shared Classroom 2", "SHARED", 80, "Classroom"),
            ("S-LAB", "Shared Teaching Lab", "SHARED", 80, "Teaching Lab"),
        ]
        rooms = {}
        for code, name, bcode, capacity, rtype in room_rows:
            rooms[code] = insert_id(
                conn,
                "INSERT INTO rooms(building_id, room_code, room_name, capacity, room_type) VALUES (?, ?, ?, ?, ?)",
                (buildings[bcode], code, name, capacity, rtype),
            )

        equipment = {}
        for name in ["Projector", "Computer", "Laboratory Workstation"]:
            equipment[name] = insert_id(conn, "INSERT INTO equipment(equipment_name) VALUES (?)", (name,))

        for code, room_id in rooms.items():
            if code not in {"S-LAB"}:
                conn.execute(
                    "INSERT INTO room_equipment(room_id, equipment_id, quantity) VALUES (?, ?, 1)",
                    (room_id, equipment["Projector"]),
                )
        conn.execute(
            "INSERT INTO room_equipment(room_id, equipment_id, quantity) VALUES (?, ?, 60)",
            (rooms["N-CL1"], equipment["Computer"]),
        )
        conn.execute(
            "INSERT INTO room_equipment(room_id, equipment_id, quantity) VALUES (?, ?, 80)",
            (rooms["S-LAB"], equipment["Laboratory Workstation"]),
        )

        staff = {}
        staff_rows = [
            ("CS001", "Ada", "Mokoena", "CS", "ada@example.edu"),
            ("MA001", "Grace", "Ndlovu", "MATH", "grace@example.edu"),
            ("ST001", "Ronald", "Dube", "STAT", "ronald@example.edu"),
            ("AC001", "Lerato", "Khumalo", "ACC", "lerato@example.edu"),
            ("ED001", "Thandi", "Molefe", "ED", "thandi@example.edu"),
            ("HI001", "Sipho", "Mahlangu", "HIST", "sipho@example.edu"),
        ]
        for number, first, last, dcode, email in staff_rows:
            staff[number] = insert_id(
                conn,
                "INSERT INTO staff(department_id, staff_number, first_name, last_name, email) VALUES (?, ?, ?, ?, ?)",
                (departments[dcode], number, first, last, email),
            )

        modules = {}
        module_rows = [
            ("CMP101", "Introduction to Computing", "CS", 16),
            ("MAT101", "Calculus I", "MATH", 16),
            ("STA101", "Statistics I", "STAT", 16),
            ("ACC101", "Financial Accounting I", "ACC", 16),
            ("EDU101", "Foundations of Education", "ED", 16),
            ("HIS101", "Introduction to History", "HIST", 16),
        ]
        for code, name, dcode, credits in module_rows:
            modules[code] = insert_id(
                conn,
                "INSERT INTO modules(department_id, module_code, module_name, credits) VALUES (?, ?, ?, ?)",
                (departments[dcode], code, name, credits),
            )

        semester = insert_id(
            conn,
            "INSERT INTO semesters(academic_year, semester_number, status) VALUES (2026, 2, 'ACTIVE')",
            (),
        )

        offering_specs = [
            ("CMP101", 93, [("BCOMP", 1)], "CS001", "Lecture", 2, 2, 1, "Lecture Room", ["Projector"]),
            ("MAT101", 70, [("BMATH", 1)], "MA001", "Lecture", 2, 2, 1, "Lecture Room", ["Projector"]),
            ("STA101", 228, [("BCOMP", 1), ("BMATH", 1), ("BSTAT", 1)], "ST001", "Lecture", 2, 2, 1, "Lecture Room", ["Projector"]),
            ("ACC101", 82, [("BACC", 1)], "AC001", "Lecture", 2, 2, 1, "Lecture Room", ["Projector"]),
            ("EDU101", 120, [("BED", 1)], "ED001", "Lecture", 2, 2, 1, "Lecture Room", ["Projector"]),
            ("HIS101", 58, [("BHIST", 1)], "HI001", "Lecture", 2, 2, 1, "Lecture Room", ["Projector"]),
        ]

        for mcode, expected, group_specs, staff_no, stype, sessions_per_week, duration, can_split, room_type, reqs in offering_specs:
            offering = insert_id(
                conn,
                "INSERT INTO module_offerings(module_id, semester_id, expected_students) VALUES (?, ?, ?)",
                (modules[mcode], semester, expected),
            )
            for group_key in group_specs:
                conn.execute("INSERT INTO offering_groups(offering_id, group_id) VALUES (?, ?)", (offering, groups[group_key]))
            conn.execute("INSERT INTO offering_staff(offering_id, staff_id) VALUES (?, ?)", (offering, staff[staff_no]))
            template = insert_id(
                conn,
                """INSERT INTO session_templates(
                    offering_id, session_type, sessions_per_week, preferred_duration,
                    minimum_duration, required_room_type, can_split_duration
                ) VALUES (?, ?, ?, ?, 1, ?, ?)""",
                (offering, stype, sessions_per_week, duration, room_type, can_split),
            )
            for req in reqs:
                conn.execute(
                    "INSERT INTO session_requirements(session_template_id, equipment_id, quantity_required) VALUES (?, ?, 1)",
                    (template, equipment[req]),
                )
            for n in range(1, sessions_per_week + 1):
                session_id = insert_id(
                    conn,
                    "INSERT INTO class_sessions(session_template_id, session_number, duration_slots) VALUES (?, ?, ?)",
                    (template, n, duration),
                )
                conn.execute(
                    "INSERT INTO session_parts(session_id, representation_type, part_number, duration_slots, is_split_part) VALUES (?, 'CONTINUOUS', 1, ?, 0)",
                    (session_id, duration),
                )

        for day in DAYS:
            for period, start, end in PERIODS:
                conn.execute(
                    "INSERT INTO time_slots(day_of_week, period_number, start_time, end_time) VALUES (?, ?, ?, ?)",
                    (day, period, start, end),
                )

        admin_hash = generate_password_hash("admin123")
        lecturer_hash = generate_password_hash("lecturer123")
        student_hash = generate_password_hash("student123")
        conn.execute("INSERT INTO users(username, password_hash, role) VALUES ('admin', ?, 'ADMIN')", (admin_hash,))
        conn.execute(
            "INSERT INTO users(username, password_hash, role, staff_id) VALUES ('lecturer', ?, 'LECTURER', ?)",
            (lecturer_hash, staff["CS001"]),
        )
        conn.execute(
            "INSERT INTO users(username, password_hash, role, group_id) VALUES ('student', ?, 'STUDENT', ?)",
            (student_hash, groups[("BCOMP", 1)]),
        )

        conn.commit()
        print("Demo data seeded.")
        print("Admin: admin / admin123")
        print("Lecturer: lecturer / lecturer123")
        print("Student: student / student123")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
