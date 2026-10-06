import tempfile
import unittest
from pathlib import Path

from database.db import connect
from database.seed_demo import seed


class TimeSlotMigrationTests(unittest.TestCase):
    def test_fresh_demo_uses_spu_period_6_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "demo.db"
            seed(db)
            conn = connect(db)
            try:
                rows = conn.execute(
                    "SELECT day_of_week,start_time,end_time FROM time_slots WHERE period_number=6 ORDER BY slot_id"
                ).fetchall()
                self.assertEqual(len(rows), 5)
                self.assertTrue(all((r["start_time"], r["end_time"]) == ("12:45", "13:20") for r in rows))
            finally:
                conn.close()

    def test_runtime_migration_updates_old_period_6_without_deleting_data(self):
        try:
            from database.migrations import apply_runtime_migrations
        except ImportError:
            self.fail("database.migrations.apply_runtime_migrations does not exist")

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "old.db"
            seed(db)
            conn = connect(db)
            try:
                conn.execute("UPDATE time_slots SET start_time='12:35', end_time='13:20' WHERE period_number=6")
                semester_id = conn.execute("SELECT semester_id FROM semesters LIMIT 1").fetchone()[0]
                version_id = conn.execute(
                    "INSERT INTO timetable_versions(semester_id,version_number,status) VALUES (?,?,?)",
                    (semester_id, 99, "DRAFT"),
                ).lastrowid
                session_id = conn.execute("SELECT session_id FROM class_sessions LIMIT 1").fetchone()[0]
                part_id = conn.execute("SELECT part_id FROM session_parts WHERE session_id=? LIMIT 1", (session_id,)).fetchone()[0]
                section_id = conn.execute(
                    "INSERT INTO session_sections(session_id,section_name,student_count) VALUES (?,?,?)",
                    (session_id, "Migration Sentinel", 1),
                ).lastrowid
                room_id = conn.execute("SELECT room_id FROM rooms LIMIT 1").fetchone()[0]
                slot_id = conn.execute(
                    "SELECT slot_id FROM time_slots WHERE day_of_week='Monday' AND period_number=1"
                ).fetchone()[0]
                entry_id = conn.execute(
                    "INSERT INTO timetable_entries(version_id,section_id,room_id,slot_id,duration_slots,part_id) VALUES (?,?,?,?,?,?)",
                    (version_id, section_id, room_id, slot_id, 1, part_id),
                ).lastrowid
                user_id = conn.execute(
                    "INSERT INTO users(username,password_hash,role) VALUES ('migration_sentinel','x','ADMIN')"
                ).lastrowid
                conn.commit()

                apply_runtime_migrations(conn)

                rows = conn.execute(
                    "SELECT start_time,end_time FROM time_slots WHERE period_number=6"
                ).fetchall()
                self.assertEqual(len(rows), 5)
                self.assertTrue(all(tuple(r) == ("12:45", "13:20") for r in rows))
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM users WHERE user_id=?", (user_id,)).fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM timetable_entries WHERE entry_id=?", (entry_id,)).fetchone()[0], 1)
                self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
