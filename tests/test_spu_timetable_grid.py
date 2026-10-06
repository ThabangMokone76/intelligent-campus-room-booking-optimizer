import tempfile
import unittest
from pathlib import Path

from database.db import connect
from database.seed_demo import seed


class SPUTimetableGridTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "grid.db"
        seed(self.db)
        self.conn = connect(self.db)
        rooms = self.conn.execute(
            "SELECT room_id, room_code, room_name, capacity FROM rooms WHERE is_active=1 ORDER BY room_id LIMIT 2"
        ).fetchall()
        self.room1 = dict(rooms[0])
        self.room2 = dict(rooms[1])

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _row(self, room, period=3, duration=1, module="CMP101", part=10):
        return {
            "entry_id": part * 10 + room["room_id"],
            "part_id": part,
            "is_locked": 0,
            "duration_slots": duration,
            "day_of_week": "Monday",
            "period_number": period,
            "start_time": "09:50",
            "end_time": "10:35",
            "room_id": room["room_id"],
            "room_name": room["room_name"],
            "room_code": room["room_code"],
            "section_id": 1,
            "section_name": "A",
            "student_count": 40,
            "representation_type": "CONTINUOUS",
            "part_number": 1,
            "session_number": 1,
            "offering_id": 1,
            "module_id": 1,
            "module_code": module,
            "module_name": "Introduction to Computing",
            "session_type": "LECTURE",
            "faculty_code": "NAS",
            "faculty_name": "Natural and Applied Sciences",
            "colour_hex": "#059669",
            "lecturers": "Ada Mokoena",
        }

    def _service(self):
        try:
            from services.timetable_view_service import campus_timetable_grid
        except ImportError:
            self.fail("services.timetable_view_service.campus_timetable_grid does not exist")
        return campus_timetable_grid

    def test_grid_is_day_then_venue_then_period(self):
        grid = self._service()(self.conn, [self._row(self.room1)])
        self.assertEqual([d["day"] for d in grid["days"]], ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
        monday = grid["days"][0]
        venue = next(v for v in monday["venues"] if v["room_id"] == self.room1["room_id"])
        self.assertEqual(venue["capacity"], self.room1["capacity"])
        self.assertEqual(venue["cells"][3][0]["module_code"], "CMP101")
        self.assertEqual(sorted(venue["cells"].keys()), list(range(1, 11)))

    def test_two_period_session_repeats_in_both_cells(self):
        grid = self._service()(self.conn, [self._row(self.room1, period=3, duration=2)])
        venue = next(v for v in grid["days"][0]["venues"] if v["room_id"] == self.room1["room_id"])
        self.assertEqual(venue["cells"][3][0]["module_code"], "CMP101")
        self.assertEqual(venue["cells"][4][0]["module_code"], "CMP101")

    def test_period_nine_duration_two_stops_at_period_ten(self):
        grid = self._service()(self.conn, [self._row(self.room1, period=9, duration=2)])
        venue = next(v for v in grid["days"][0]["venues"] if v["room_id"] == self.room1["room_id"])
        self.assertEqual(venue["cells"][9][0]["module_code"], "CMP101")
        self.assertEqual(venue["cells"][10][0]["module_code"], "CMP101")
        self.assertNotIn(11, venue["cells"])

    def test_multi_room_part_appears_in_each_room_row(self):
        rows = [self._row(self.room1, period=5, part=20), self._row(self.room2, period=5, part=20)]
        grid = self._service()(self.conn, rows)
        monday = grid["days"][0]
        by_room = {v["room_id"]: v for v in monday["venues"]}
        self.assertEqual(by_room[self.room1["room_id"]]["cells"][5][0]["part_id"], 20)
        self.assertEqual(by_room[self.room2["room_id"]]["cells"][5][0]["part_id"], 20)


if __name__ == "__main__":
    unittest.main()
