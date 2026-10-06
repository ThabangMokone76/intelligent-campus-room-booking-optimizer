import tempfile
import unittest
from pathlib import Path

from database.db import connect
from database.seed_demo import seed

try:
    from services.faculty_style_service import FACULTY_STYLES, apply_canonical_faculty_colours, get_faculty_style
except ImportError:
    FACULTY_STYLES = None
    apply_canonical_faculty_colours = None
    get_faculty_style = None


class FacultyStyleTests(unittest.TestCase):
    def test_required_faculty_colours_are_canonical(self):
        self.assertIsNotNone(get_faculty_style)
        self.assertEqual(get_faculty_style("NAS")["background"], "#059669")
        self.assertEqual(get_faculty_style("EMS")["background"], "#7C3AED")
        self.assertEqual(get_faculty_style("EDU")["background"], "#F6B221")
        self.assertEqual(get_faculty_style("HUM")["background"], "#D97706")

    def test_unknown_faculty_uses_neutral_fallback(self):
        self.assertEqual(get_faculty_style("UNKNOWN")["background"], "#E5E7EB")

    def test_existing_database_colours_are_migrated(self):
        self.assertIsNotNone(apply_canonical_faculty_colours)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "db.sqlite"
            seed(path)
            conn = connect(path)
            try:
                conn.execute("UPDATE faculties SET colour_hex='#000000'")
                apply_canonical_faculty_colours(conn)
                rows = {r["faculty_code"]: r["colour_hex"] for r in conn.execute("SELECT faculty_code,colour_hex FROM faculties")}
                for code, expected in {"NAS":"#059669","EMS":"#7C3AED","EDU":"#F6B221","HUM":"#D97706"}.items():
                    if code in rows:
                        self.assertEqual(rows[code], expected)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
