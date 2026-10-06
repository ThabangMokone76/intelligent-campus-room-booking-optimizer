import sqlite3
import tempfile
import unittest
from pathlib import Path

from database.db import init_database


class SyntheticSchemaTests(unittest.TestCase):
    def test_fresh_database_contains_synthetic_tables_and_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "schema.db"
            init_database(path)
            conn = sqlite3.connect(path)
            try:
                tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                for name in {
                    "students", "programme_modules", "student_group_members",
                    "student_module_registrations", "section_student_assignments",
                }:
                    self.assertIn(name, tables)
                faculty_cols = {r[1] for r in conn.execute("PRAGMA table_info(faculties)")}
                group_cols = {r[1] for r in conn.execute("PRAGMA table_info(student_groups)")}
                user_cols = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
                self.assertIn("colour_hex", faculty_cols)
                self.assertIn("section_code", group_cols)
                self.assertIn("student_id", user_cols)
                self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
