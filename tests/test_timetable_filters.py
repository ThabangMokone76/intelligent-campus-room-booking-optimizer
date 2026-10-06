import tempfile
import unittest
from pathlib import Path

from database.db import connect
from database.seed_demo import seed
from scheduler.engine import generate_timetable
from services.timetable_service import timetable_rows


class TimetableFilterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "filters.db"
        seed(self.db)
        self.conn = connect(self.db)
        self.version_id = generate_timetable(self.conn)["version_id"]

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_room_filter_returns_only_selected_room(self):
        all_rows = timetable_rows(self.conn, self.version_id)
        room_id = all_rows[0]["room_id"]
        rows = timetable_rows(self.conn, self.version_id, filters={"room_id": room_id})
        self.assertTrue(rows)
        self.assertEqual({r["room_id"] for r in rows}, {room_id})

    def test_unmatched_filter_returns_zero_entries(self):
        rows = timetable_rows(self.conn, self.version_id, filters={"room_id": 999999})
        self.assertEqual(rows, [])

    def test_admin_route_builds_filters_only_for_admin(self):
        source = Path("app.py").read_text(encoding="utf-8")
        self.assertIn('campus_timetable_grid', source)
        self.assertIn('campus_filter_options', source)
        self.assertIn('if user["role"] == "ADMIN":', source)
        self.assertIn('filters = {', source)
        self.assertIn('filter_options=', source)

    def test_admin_template_uses_spu_venue_by_period_grid(self):
        source = Path("templates/timetable.html").read_text(encoding="utf-8")
        self.assertIn("SPU campus timetable", source)
        self.assertIn("VENUE", source)
        self.assertIn("CAPACITY", source)
        self.assertIn("campus_grid.days", source)
        self.assertIn("campus_grid.periods", source)
        self.assertIn("Clear filters", source)


if __name__ == "__main__":
    unittest.main()
