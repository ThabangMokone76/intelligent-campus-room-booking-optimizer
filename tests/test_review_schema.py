import shutil
import tempfile
import unittest
from pathlib import Path

from database.db import connect, init_database
from database.migrations import apply_runtime_migrations
from database.security import generate_password_hash


class ReviewSchemaTests(unittest.TestCase):
    def test_fresh_schema_supports_reviewer_and_review_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fresh.db"
            init_database(path)
            conn = connect(path)
            try:
                uid = conn.execute(
                    "INSERT INTO users(username,password_hash,role) VALUES (?,?,?)",
                    ("reviewer", generate_password_hash("x"), "REVIEWER"),
                ).lastrowid
                self.assertGreater(uid, 0)
                for table in ("reviewer_faculties", "timetable_reviews", "review_comments", "cross_faculty_teaching_permissions"):
                    self.assertIsNotNone(conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone())
            finally:
                conn.close()

    def test_runtime_migration_preserves_existing_population_and_enables_new_statuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "legacy.db"
            shutil.copy2(Path("database/synthetic_seed.db"), path)
            conn = connect(path)
            try:
                before_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                before_entries = conn.execute("SELECT COUNT(*) FROM timetable_entries").fetchone()[0]
                apply_runtime_migrations(conn)
                conn.commit()
                conn.execute(
                    "INSERT INTO users(username,password_hash,role) VALUES (?,?,?)",
                    ("schema-reviewer", generate_password_hash("x"), "REVIEWER"),
                )
                version = conn.execute("SELECT version_id FROM timetable_versions ORDER BY version_id LIMIT 1").fetchone()
                if version:
                    conn.execute("UPDATE timetable_versions SET status='IN_REVIEW' WHERE version_id=?", (version[0],))
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0], before_users + 2)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM timetable_entries").fetchone()[0], before_entries)
                self.assertFalse(conn.execute("PRAGMA foreign_key_check").fetchall())
            finally:
                conn.close()

    def test_review_comment_can_target_specific_entry_or_whole_timetable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fresh.db"
            init_database(path)
            conn = connect(path)
            try:
                conn.execute("INSERT INTO semesters(academic_year,semester_number,status) VALUES (2026,2,'ACTIVE')")
                sid = conn.execute("SELECT semester_id FROM semesters").fetchone()[0]
                conn.execute("INSERT INTO timetable_versions(semester_id,version_number,status) VALUES (?,1,'IN_REVIEW')", (sid,))
                vid = conn.execute("SELECT version_id FROM timetable_versions").fetchone()[0]
                admin = conn.execute("INSERT INTO users(username,password_hash,role) VALUES ('a','x','ADMIN')").lastrowid
                reviewer = conn.execute("INSERT INTO users(username,password_hash,role) VALUES ('r','x','REVIEWER')").lastrowid
                review_id = conn.execute(
                    "INSERT INTO timetable_reviews(version_id,submitted_by_user_id,assigned_reviewer_user_id,status) VALUES (?,?,?,'IN_REVIEW')",
                    (vid, admin, reviewer),
                ).lastrowid
                cid = conn.execute(
                    "INSERT INTO review_comments(review_id,author_user_id,comment_text,entry_id) VALUES (?,?,?,NULL)",
                    (review_id, reviewer, "General feedback"),
                ).lastrowid
                self.assertGreater(cid, 0)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
