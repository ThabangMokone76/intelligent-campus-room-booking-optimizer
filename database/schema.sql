PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS faculties (
    faculty_id INTEGER PRIMARY KEY AUTOINCREMENT,
    faculty_code TEXT NOT NULL UNIQUE,
    faculty_name TEXT NOT NULL UNIQUE,
    colour_hex TEXT NOT NULL DEFAULT '#64748B'
);

CREATE TABLE IF NOT EXISTS departments (
    department_id INTEGER PRIMARY KEY AUTOINCREMENT,
    faculty_id INTEGER NOT NULL,
    department_code TEXT NOT NULL,
    department_name TEXT NOT NULL,
    FOREIGN KEY (faculty_id) REFERENCES faculties(faculty_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    UNIQUE (faculty_id, department_code)
);

CREATE TABLE IF NOT EXISTS programmes (
    programme_id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL,
    programme_code TEXT NOT NULL UNIQUE,
    programme_name TEXT NOT NULL,
    duration_years INTEGER NOT NULL CHECK (duration_years > 0),
    FOREIGN KEY (department_id) REFERENCES departments(department_id) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS buildings (
    building_id INTEGER PRIMARY KEY AUTOINCREMENT,
    faculty_id INTEGER,
    building_code TEXT NOT NULL UNIQUE,
    building_name TEXT NOT NULL,
    is_shared INTEGER NOT NULL DEFAULT 0 CHECK (is_shared IN (0,1)),
    FOREIGN KEY (faculty_id) REFERENCES faculties(faculty_id) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS student_groups (
    group_id INTEGER PRIMARY KEY AUTOINCREMENT,
    programme_id INTEGER NOT NULL,
    year_level INTEGER NOT NULL CHECK (year_level > 0),
    number_of_students INTEGER NOT NULL CHECK (number_of_students > 0),
    section_code TEXT NOT NULL DEFAULT 'A',
    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    UNIQUE (programme_id, year_level, section_code)
);


CREATE TABLE IF NOT EXISTS students (
    student_id INTEGER PRIMARY KEY AUTOINCREMENT,
    programme_id INTEGER NOT NULL,
    student_number TEXT NOT NULL UNIQUE,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    year_level INTEGER NOT NULL CHECK (year_level > 0),
    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS programme_modules (
    programme_id INTEGER NOT NULL,
    module_id INTEGER NOT NULL,
    year_level INTEGER NOT NULL CHECK (year_level > 0),
    is_elective INTEGER NOT NULL DEFAULT 0 CHECK (is_elective IN (0,1)),
    source_students INTEGER NOT NULL CHECK (source_students > 0),
    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (module_id) REFERENCES modules(module_id) ON UPDATE CASCADE ON DELETE CASCADE,
    PRIMARY KEY (programme_id, module_id)
);

CREATE TABLE IF NOT EXISTS student_group_members (
    group_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL UNIQUE,
    FOREIGN KEY (group_id) REFERENCES student_groups(group_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON UPDATE CASCADE ON DELETE CASCADE,
    PRIMARY KEY (group_id, student_id)
);

CREATE TABLE IF NOT EXISTS rooms (
    room_id INTEGER PRIMARY KEY AUTOINCREMENT,
    building_id INTEGER NOT NULL,
    room_code TEXT NOT NULL UNIQUE,
    room_name TEXT NOT NULL,
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    room_type TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    FOREIGN KEY (building_id) REFERENCES buildings(building_id) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS staff (
    staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL,
    staff_number TEXT NOT NULL UNIQUE,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT,
    staff_type TEXT NOT NULL DEFAULT 'Lecturer',
    FOREIGN KEY (department_id) REFERENCES departments(department_id) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS modules (
    module_id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL,
    module_code TEXT NOT NULL UNIQUE,
    module_name TEXT NOT NULL,
    module_type TEXT NOT NULL DEFAULT 'Compulsory',
    credits INTEGER CHECK (credits IS NULL OR credits > 0),
    is_elective INTEGER NOT NULL DEFAULT 0 CHECK (is_elective IN (0,1)),
    FOREIGN KEY (department_id) REFERENCES departments(department_id) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS semesters (
    semester_id INTEGER PRIMARY KEY AUTOINCREMENT,
    academic_year INTEGER NOT NULL,
    semester_number INTEGER NOT NULL CHECK (semester_number IN (1,2)),
    status TEXT NOT NULL DEFAULT 'INACTIVE' CHECK (status IN ('INACTIVE','ACTIVE','COMPLETED')),
    UNIQUE (academic_year, semester_number)
);

CREATE TABLE IF NOT EXISTS student_module_registrations (
    student_id INTEGER NOT NULL,
    module_id INTEGER NOT NULL,
    semester_id INTEGER NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (module_id) REFERENCES modules(module_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (semester_id) REFERENCES semesters(semester_id) ON UPDATE CASCADE ON DELETE CASCADE,
    PRIMARY KEY (student_id, module_id, semester_id)
);

CREATE TABLE IF NOT EXISTS module_offerings (
    offering_id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id INTEGER NOT NULL,
    semester_id INTEGER NOT NULL,
    expected_students INTEGER NOT NULL CHECK (expected_students > 0),
    FOREIGN KEY (module_id) REFERENCES modules(module_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (semester_id) REFERENCES semesters(semester_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    UNIQUE (module_id, semester_id)
);

CREATE TABLE IF NOT EXISTS offering_groups (
    offering_id INTEGER NOT NULL,
    group_id INTEGER NOT NULL,
    FOREIGN KEY (offering_id) REFERENCES module_offerings(offering_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES student_groups(group_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    PRIMARY KEY (offering_id, group_id)
);

CREATE TABLE IF NOT EXISTS offering_staff (
    offering_id INTEGER NOT NULL,
    staff_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'Lecturer',
    FOREIGN KEY (offering_id) REFERENCES module_offerings(offering_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    PRIMARY KEY (offering_id, staff_id)
);

CREATE TABLE IF NOT EXISTS equipment (
    equipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS room_equipment (
    room_id INTEGER NOT NULL,
    equipment_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    FOREIGN KEY (room_id) REFERENCES rooms(room_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (equipment_id) REFERENCES equipment(equipment_id) ON UPDATE CASCADE ON DELETE CASCADE,
    PRIMARY KEY (room_id, equipment_id)
);

CREATE TABLE IF NOT EXISTS session_templates (
    session_template_id INTEGER PRIMARY KEY AUTOINCREMENT,
    offering_id INTEGER NOT NULL,
    session_type TEXT NOT NULL,
    sessions_per_week INTEGER NOT NULL CHECK (sessions_per_week > 0),
    preferred_duration INTEGER NOT NULL CHECK (preferred_duration IN (1,2)),
    minimum_duration INTEGER NOT NULL CHECK (minimum_duration IN (1,2)),
    required_room_type TEXT NOT NULL,
    can_split_duration INTEGER NOT NULL DEFAULT 0 CHECK (can_split_duration IN (0,1)),
    FOREIGN KEY (offering_id) REFERENCES module_offerings(offering_id) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS session_requirements (
    session_template_id INTEGER NOT NULL,
    equipment_id INTEGER NOT NULL,
    quantity_required INTEGER NOT NULL DEFAULT 1 CHECK (quantity_required > 0),
    FOREIGN KEY (session_template_id) REFERENCES session_templates(session_template_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (equipment_id) REFERENCES equipment(equipment_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    PRIMARY KEY (session_template_id, equipment_id)
);

CREATE TABLE IF NOT EXISTS time_slots (
    slot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    day_of_week TEXT NOT NULL CHECK (day_of_week IN ('Monday','Tuesday','Wednesday','Thursday','Friday')),
    period_number INTEGER NOT NULL CHECK (period_number BETWEEN 1 AND 10),
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    UNIQUE (day_of_week, period_number)
);

CREATE TABLE IF NOT EXISTS class_sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_template_id INTEGER NOT NULL,
    session_number INTEGER NOT NULL CHECK (session_number > 0),
    duration_slots INTEGER NOT NULL CHECK (duration_slots IN (1,2)),
    status TEXT NOT NULL DEFAULT 'UNSCHEDULED' CHECK (status IN ('UNSCHEDULED','SCHEDULED')),
    FOREIGN KEY (session_template_id) REFERENCES session_templates(session_template_id) ON UPDATE CASCADE ON DELETE CASCADE,
    UNIQUE (session_template_id, session_number)
);

CREATE TABLE IF NOT EXISTS session_parts (
    part_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    representation_type TEXT NOT NULL DEFAULT 'CONTINUOUS' CHECK (representation_type IN ('CONTINUOUS','SPLIT')),
    part_number INTEGER NOT NULL CHECK (part_number > 0),
    duration_slots INTEGER NOT NULL CHECK (duration_slots IN (1,2)),
    is_split_part INTEGER NOT NULL DEFAULT 0 CHECK (is_split_part IN (0,1)),
    FOREIGN KEY (session_id) REFERENCES class_sessions(session_id) ON UPDATE CASCADE ON DELETE CASCADE,
    UNIQUE (session_id, representation_type, part_number)
);

CREATE TABLE IF NOT EXISTS session_sections (
    section_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    section_name TEXT NOT NULL,
    student_count INTEGER NOT NULL CHECK (student_count > 0),
    FOREIGN KEY (session_id) REFERENCES class_sessions(session_id) ON UPDATE CASCADE ON DELETE CASCADE,
    UNIQUE (session_id, section_name)
);

CREATE TABLE IF NOT EXISTS section_student_assignments (
    section_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    FOREIGN KEY (section_id) REFERENCES session_sections(section_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON UPDATE CASCADE ON DELETE CASCADE,
    PRIMARY KEY (section_id, student_id)
);

CREATE TABLE IF NOT EXISTS timetable_versions (
    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
    semester_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','IN_REVIEW','CHANGES_REQUESTED','APPROVED','PUBLISHED')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    published_at TEXT,
    FOREIGN KEY (semester_id) REFERENCES semesters(semester_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    UNIQUE (semester_id, version_number)
);

CREATE TABLE IF NOT EXISTS timetable_entries (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id INTEGER NOT NULL,
    section_id INTEGER NOT NULL,
    room_id INTEGER NOT NULL,
    slot_id INTEGER NOT NULL,
    duration_slots INTEGER NOT NULL CHECK (duration_slots IN (1,2)),
    is_locked INTEGER NOT NULL DEFAULT 0 CHECK (is_locked IN (0,1)),
    part_id INTEGER NOT NULL,
    FOREIGN KEY (version_id) REFERENCES timetable_versions(version_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (section_id) REFERENCES session_sections(section_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (room_id) REFERENCES rooms(room_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (slot_id) REFERENCES time_slots(slot_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (part_id) REFERENCES session_parts(part_id) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('ADMIN','REVIEWER','LECTURER','STUDENT')),
    staff_id INTEGER,
    group_id INTEGER,
    student_id INTEGER UNIQUE,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON UPDATE CASCADE ON DELETE SET NULL,
    FOREIGN KEY (group_id) REFERENCES student_groups(group_id) ON UPDATE CASCADE ON DELETE SET NULL,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient_user_id INTEGER NOT NULL,
    notification_type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    version_id INTEGER NOT NULL,
    entry_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    read_at TEXT,
    FOREIGN KEY (recipient_user_id) REFERENCES users(user_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (version_id) REFERENCES timetable_versions(version_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (entry_id) REFERENCES timetable_entries(entry_id) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS reviewer_faculties (
    user_id INTEGER NOT NULL,
    faculty_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (faculty_id) REFERENCES faculties(faculty_id) ON UPDATE CASCADE ON DELETE CASCADE,
    PRIMARY KEY (user_id, faculty_id)
);

CREATE TABLE IF NOT EXISTS cross_faculty_teaching_permissions (
    module_id INTEGER NOT NULL,
    staff_id INTEGER NOT NULL,
    approved_by_user_id INTEGER,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (module_id) REFERENCES modules(module_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (approved_by_user_id) REFERENCES users(user_id) ON UPDATE CASCADE ON DELETE SET NULL,
    PRIMARY KEY (module_id, staff_id)
);

CREATE TABLE IF NOT EXISTS timetable_reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id INTEGER NOT NULL,
    submitted_by_user_id INTEGER NOT NULL,
    assigned_reviewer_user_id INTEGER,
    status TEXT NOT NULL DEFAULT 'IN_REVIEW' CHECK (status IN ('IN_REVIEW','CHANGES_REQUESTED','APPROVED')),
    submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_at TEXT,
    decision_summary TEXT,
    approved_fingerprint TEXT,
    FOREIGN KEY (version_id) REFERENCES timetable_versions(version_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (submitted_by_user_id) REFERENCES users(user_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (assigned_reviewer_user_id) REFERENCES users(user_id) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS review_comments (
    comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER NOT NULL,
    entry_id INTEGER,
    author_user_id INTEGER NOT NULL,
    comment_text TEXT NOT NULL,
    is_resolved INTEGER NOT NULL DEFAULT 0 CHECK (is_resolved IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT,
    resolved_by_user_id INTEGER,
    FOREIGN KEY (review_id) REFERENCES timetable_reviews(review_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (entry_id) REFERENCES timetable_entries(entry_id) ON UPDATE CASCADE ON DELETE SET NULL,
    FOREIGN KEY (author_user_id) REFERENCES users(user_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (resolved_by_user_id) REFERENCES users(user_id) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS generation_metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id INTEGER NOT NULL UNIQUE,
    hard_violations INTEGER NOT NULL DEFAULT 0,
    student_gaps INTEGER NOT NULL DEFAULT 0,
    lecturer_gaps INTEGER NOT NULL DEFAULT 0,
    room_utilization REAL NOT NULL DEFAULT 0,
    balance_score REAL NOT NULL DEFAULT 0,
    soft_score REAL NOT NULL DEFAULT 0,
    FOREIGN KEY (version_id) REFERENCES timetable_versions(version_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_departments_faculty ON departments(faculty_id);
CREATE INDEX IF NOT EXISTS idx_programmes_department ON programmes(department_id);
CREATE INDEX IF NOT EXISTS idx_buildings_faculty ON buildings(faculty_id);
CREATE INDEX IF NOT EXISTS idx_student_groups_programme ON student_groups(programme_id);
CREATE INDEX IF NOT EXISTS idx_rooms_building ON rooms(building_id);
CREATE INDEX IF NOT EXISTS idx_staff_department ON staff(department_id);
CREATE INDEX IF NOT EXISTS idx_modules_department ON modules(department_id);
CREATE INDEX IF NOT EXISTS idx_module_offerings_module ON module_offerings(module_id);
CREATE INDEX IF NOT EXISTS idx_module_offerings_semester ON module_offerings(semester_id);
CREATE INDEX IF NOT EXISTS idx_session_templates_offering ON session_templates(offering_id);
CREATE INDEX IF NOT EXISTS idx_class_sessions_template ON class_sessions(session_template_id);
CREATE INDEX IF NOT EXISTS idx_session_parts_session ON session_parts(session_id);
CREATE INDEX IF NOT EXISTS idx_session_sections_session ON session_sections(session_id);
CREATE INDEX IF NOT EXISTS idx_timetable_versions_semester ON timetable_versions(semester_id);
CREATE INDEX IF NOT EXISTS idx_timetable_entries_version ON timetable_entries(version_id);
CREATE INDEX IF NOT EXISTS idx_timetable_entries_section ON timetable_entries(section_id);
CREATE INDEX IF NOT EXISTS idx_timetable_entries_room ON timetable_entries(room_id);
CREATE INDEX IF NOT EXISTS idx_timetable_entries_slot ON timetable_entries(slot_id);
CREATE INDEX IF NOT EXISTS idx_timetable_entries_part ON timetable_entries(part_id);

CREATE INDEX IF NOT EXISTS idx_notifications_recipient_read ON notifications(recipient_user_id, read_at);
CREATE INDEX IF NOT EXISTS idx_notifications_version ON notifications(version_id);
CREATE INDEX IF NOT EXISTS idx_students_programme ON students(programme_id);
CREATE INDEX IF NOT EXISTS idx_registrations_student ON student_module_registrations(student_id, semester_id);
CREATE INDEX IF NOT EXISTS idx_registrations_module ON student_module_registrations(module_id, semester_id);
CREATE INDEX IF NOT EXISTS idx_group_members_group ON student_group_members(group_id);
CREATE INDEX IF NOT EXISTS idx_section_assign_student ON section_student_assignments(student_id);

CREATE INDEX IF NOT EXISTS idx_reviewer_faculties_user ON reviewer_faculties(user_id);
CREATE INDEX IF NOT EXISTS idx_reviews_version ON timetable_reviews(version_id);
CREATE INDEX IF NOT EXISTS idx_reviews_reviewer ON timetable_reviews(assigned_reviewer_user_id, status);
CREATE INDEX IF NOT EXISTS idx_review_comments_review ON review_comments(review_id, is_resolved);
CREATE INDEX IF NOT EXISTS idx_cross_faculty_staff ON cross_faculty_teaching_permissions(staff_id);
