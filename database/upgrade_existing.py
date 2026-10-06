import shutil
from pathlib import Path

from database.db import DATABASE_PATH, SCHEMA_PATH, connect
from database.security import generate_password_hash

BACKUP_PATH = DATABASE_PATH.with_name("campus_timetable_before_final_upgrade.db")


def columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def migrate_session_parts_if_needed(conn):
    if "representation_type" in columns(conn, "session_parts"):
        return False
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.commit()
    try:
        conn.execute("BEGIN")
        conn.execute(
            """CREATE TABLE session_parts_new (
                part_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                representation_type TEXT NOT NULL DEFAULT 'CONTINUOUS' CHECK (representation_type IN ('CONTINUOUS','SPLIT')),
                part_number INTEGER NOT NULL CHECK (part_number > 0),
                duration_slots INTEGER NOT NULL CHECK (duration_slots IN (1,2)),
                is_split_part INTEGER NOT NULL DEFAULT 0 CHECK (is_split_part IN (0,1)),
                FOREIGN KEY (session_id) REFERENCES class_sessions(session_id) ON UPDATE CASCADE ON DELETE CASCADE,
                UNIQUE (session_id, representation_type, part_number)
            )"""
        )
        conn.execute(
            """INSERT INTO session_parts_new(part_id, session_id, representation_type, part_number, duration_slots, is_split_part)
               SELECT part_id, session_id, 'CONTINUOUS', part_number, duration_slots, is_split_part FROM session_parts"""
        )
        conn.execute("DROP TABLE session_parts")
        conn.execute("ALTER TABLE session_parts_new RENAME TO session_parts")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_session_parts_session ON session_parts(session_id)")
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def ensure_users(conn):
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
        return
    staff = conn.execute("SELECT staff_id FROM staff ORDER BY staff_id LIMIT 1").fetchone()
    group = conn.execute("SELECT group_id FROM student_groups ORDER BY group_id LIMIT 1").fetchone()
    conn.execute(
        "INSERT INTO users(username, password_hash, role) VALUES ('admin', ?, 'ADMIN')",
        (generate_password_hash("admin123"),),
    )
    if staff:
        conn.execute(
            "INSERT INTO users(username, password_hash, role, staff_id) VALUES ('lecturer', ?, 'LECTURER', ?)",
            (generate_password_hash("lecturer123"), staff[0]),
        )
    if group:
        conn.execute(
            "INSERT INTO users(username, password_hash, role, group_id) VALUES ('student', ?, 'STUDENT', ?)",
            (generate_password_hash("student123"), group[0]),
        )


def upgrade():
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")
    if not BACKUP_PATH.exists():
        shutil.copy2(DATABASE_PATH, BACKUP_PATH)
        print(f"Backup created: {BACKUP_PATH.name}")
    conn = connect()
    try:
        migrate_session_parts_if_needed(conn)
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        ensure_users(conn)
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(f"Foreign key violations after upgrade: {violations}")
        conn.commit()
        print("Existing database upgraded successfully.")
        print("Demo login if users were newly created: admin / admin123")
    finally:
        conn.close()


if __name__ == "__main__":
    upgrade()
