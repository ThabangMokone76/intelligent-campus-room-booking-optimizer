import tempfile
import unittest
from pathlib import Path

from database.db import connect
from database.seed_demo import seed
from scheduler.engine import (
    generate_timetable,
    get_logical_sessions,
    prepare_representations,
    selected_parts,
    split_configurations,
)
from scheduler.validator import validate_version


class SchedulerCoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        seed(self.db_path)
        self.conn = connect(self.db_path)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_demo_generation_is_hard_constraint_valid(self):
        result = generate_timetable(self.conn)
        report = validate_version(self.conn, result["version_id"])
        self.assertEqual(report.total, 0, report.items)
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(result["split_session_ids"], [])

    def test_split_representation_is_additive_and_immutable(self):
        semester_id = self.conn.execute("SELECT semester_id FROM semesters WHERE status='ACTIVE'").fetchone()[0]
        sessions = get_logical_sessions(self.conn, semester_id)
        prepare_representations(self.conn, sessions)
        session = next(s for s in sessions if s["module_code"] == "CMP101")
        continuous_before = self.conn.execute(
            "SELECT part_id, duration_slots FROM session_parts WHERE session_id=? AND representation_type='CONTINUOUS'",
            (session["session_id"],),
        ).fetchone()
        split_parts = selected_parts(self.conn, [session], {session["session_id"]})
        continuous_after = self.conn.execute(
            "SELECT part_id, duration_slots FROM session_parts WHERE session_id=? AND representation_type='CONTINUOUS'",
            (session["session_id"],),
        ).fetchone()
        self.assertEqual(tuple(continuous_before), tuple(continuous_after))
        self.assertEqual(len(split_parts), 2)
        self.assertEqual([p["duration_slots"] for p in split_parts], [1, 1])

    def test_continuous_first_configuration_order(self):
        semester_id = self.conn.execute("SELECT semester_id FROM semesters WHERE status='ACTIVE'").fetchone()[0]
        sessions = get_logical_sessions(self.conn, semester_id)
        configs = split_configurations(sessions[:2], {})
        first = next(configs)
        second = next(configs)
        self.assertEqual(first, set())
        self.assertEqual(len(second), 1)

    def test_locked_part_is_preserved_during_regeneration(self):
        first = generate_timetable(self.conn)
        row = self.conn.execute(
            """SELECT te.entry_id, te.part_id, te.room_id, te.slot_id
               FROM timetable_entries te
               WHERE te.version_id=? ORDER BY te.entry_id LIMIT 1""",
            (first["version_id"],),
        ).fetchone()
        self.conn.execute("UPDATE timetable_entries SET is_locked=1 WHERE version_id=? AND part_id=?", (first["version_id"], row["part_id"]))
        self.conn.commit()
        second = generate_timetable(self.conn)
        copied = self.conn.execute(
            """SELECT part_id, room_id, slot_id, is_locked
               FROM timetable_entries
               WHERE version_id=? AND part_id=?""",
            (second["version_id"], row["part_id"]),
        ).fetchall()
        self.assertTrue(copied)
        self.assertTrue(all(r["is_locked"] == 1 for r in copied))
        self.assertEqual({r["room_id"] for r in copied}, {row["room_id"]})
        self.assertEqual({r["slot_id"] for r in copied}, {row["slot_id"]})
        self.assertEqual(validate_version(self.conn, second["version_id"]).total, 0)


if __name__ == "__main__":
    unittest.main()
