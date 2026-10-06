"""Small idempotent runtime migrations for existing project databases."""
from __future__ import annotations

from services.faculty_style_service import apply_canonical_faculty_colours
from database.security import generate_password_hash


def _table_sql(conn, table: str) -> str:
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return (row[0] or "") if row else ""


def _rebuild_users_if_needed(conn) -> None:
    sql = _table_sql(conn, "users")
    if "REVIEWER" in sql:
        return
    conn.execute("""CREATE TABLE users_new (
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
    )""")
    conn.execute("""INSERT INTO users_new(user_id,username,password_hash,role,staff_id,group_id,student_id,is_active)
                    SELECT user_id,username,password_hash,role,staff_id,group_id,student_id,is_active FROM users""")
    conn.execute("DROP TABLE users")
    conn.execute("ALTER TABLE users_new RENAME TO users")


def _rebuild_versions_if_needed(conn) -> None:
    sql = _table_sql(conn, "timetable_versions")
    if "CHANGES_REQUESTED" in sql and "APPROVED" in sql:
        return
    conn.execute("""CREATE TABLE timetable_versions_new (
        version_id INTEGER PRIMARY KEY AUTOINCREMENT,
        semester_id INTEGER NOT NULL,
        version_number INTEGER NOT NULL CHECK (version_number > 0),
        status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','IN_REVIEW','CHANGES_REQUESTED','APPROVED','PUBLISHED')),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        published_at TEXT,
        FOREIGN KEY (semester_id) REFERENCES semesters(semester_id) ON UPDATE CASCADE ON DELETE RESTRICT,
        UNIQUE (semester_id, version_number)
    )""")
    conn.execute("""INSERT INTO timetable_versions_new(version_id,semester_id,version_number,status,created_at,published_at)
                    SELECT version_id,semester_id,version_number,
                           CASE WHEN status='REVIEW' THEN 'IN_REVIEW' ELSE status END,
                           created_at,published_at
                    FROM timetable_versions""")
    conn.execute("DROP TABLE timetable_versions")
    conn.execute("ALTER TABLE timetable_versions_new RENAME TO timetable_versions")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_timetable_versions_semester ON timetable_versions(semester_id)")


def _create_review_tables(conn) -> None:
    conn.executescript("""
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
    CREATE INDEX IF NOT EXISTS idx_reviewer_faculties_user ON reviewer_faculties(user_id);
    CREATE INDEX IF NOT EXISTS idx_reviews_version ON timetable_reviews(version_id);
    CREATE INDEX IF NOT EXISTS idx_reviews_reviewer ON timetable_reviews(assigned_reviewer_user_id, status);
    CREATE INDEX IF NOT EXISTS idx_review_comments_review ON review_comments(review_id, is_resolved);
    CREATE INDEX IF NOT EXISTS idx_cross_faculty_staff ON cross_faculty_teaching_permissions(staff_id);
    """)


def _ensure_review_columns(conn) -> None:
    review_columns = {row[1] for row in conn.execute("PRAGMA table_info(timetable_reviews)")}
    if "approved_fingerprint" not in review_columns:
        conn.execute("ALTER TABLE timetable_reviews ADD COLUMN approved_fingerprint TEXT")
    comment_columns = {row[1] for row in conn.execute("PRAGMA table_info(review_comments)")}
    if "resolved_by_user_id" not in comment_columns:
        conn.execute("ALTER TABLE review_comments ADD COLUMN resolved_by_user_id INTEGER")


def _ensure_demo_reviewer(conn) -> None:
    row = conn.execute("SELECT user_id,role FROM users WHERE username='reviewer'").fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO users(username,password_hash,role) VALUES (?,?, 'REVIEWER')",
            ("reviewer", generate_password_hash("reviewer123")),
        )
    elif row["role"] != "REVIEWER":
        # Never silently repurpose an existing non-reviewer username.
        raise RuntimeError("The reserved demo username 'reviewer' already belongs to another role.")


def apply_runtime_migrations(conn) -> None:
    """Align existing databases with current runtime invariants without data loss."""
    # Table CHECK constraints in the earlier build require a table rebuild.  Do it
    # with FK enforcement temporarily disabled, then validate before returning.
    conn.commit()
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("BEGIN")
        _rebuild_users_if_needed(conn)
        _rebuild_versions_if_needed(conn)
        _create_review_tables(conn)
        _ensure_review_columns(conn)
        _ensure_demo_reviewer(conn)
        conn.execute("UPDATE time_slots SET start_time='12:45', end_time='13:20' WHERE period_number=6")
        apply_canonical_faculty_colours(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")
    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(f"Foreign key validation failed after runtime migration: {violations[:5]}")
