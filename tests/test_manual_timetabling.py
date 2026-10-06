import tempfile
import unittest
from pathlib import Path

from database.db import connect
from database.seed_demo import seed
from scheduler.engine import generate_timetable
from services.manual_timetable_service import (
    get_editable_entry,
    save_manual_change,
    set_entry_lock,
    suggest_placements,
    validate_manual_change,
)


class ManualTimetablingServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "manual.db"
        seed(self.db_path)
        self.conn = connect(self.db_path)
        self.result = generate_timetable(self.conn)
        self.version_id = self.result["version_id"]
        self.admin_id = self.conn.execute("SELECT user_id FROM users WHERE role='ADMIN'").fetchone()[0]

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _entry(self, module_code):
        return self.conn.execute(
            """SELECT te.entry_id FROM timetable_entries te
               JOIN session_parts sp ON sp.part_id=te.part_id
               JOIN class_sessions cs ON cs.session_id=sp.session_id
               JOIN session_templates st ON st.session_template_id=cs.session_template_id
               JOIN module_offerings mo ON mo.offering_id=st.offering_id
               JOIN modules m ON m.module_id=mo.module_id
               WHERE te.version_id=? AND m.module_code=? ORDER BY te.entry_id LIMIT 1""",
            (self.version_id, module_code),
        ).fetchone()[0]

    def test_editable_entry_contains_derived_faculty_module_placement_and_lecturer(self):
        entry_id = self._entry("CMP101")
        item = get_editable_entry(self.conn, entry_id, self.version_id)
        self.assertEqual(item["module_code"], "CMP101")
        self.assertEqual(item["faculty_code"], "NAS")
        self.assertEqual(item["day_of_week"], "Thursday")
        self.assertEqual(item["start_period"], 2)
        self.assertEqual(item["duration_slots"], 2)
        self.assertEqual(item["staff"][0]["faculty_code"], "NAS")
        self.assertTrue(item["groups"])

    def test_wrong_faculty_lecturer_is_rejected_with_clear_message(self):
        entry_id = self._entry("CMP101")
        ems_staff = self.conn.execute(
            """SELECT s.staff_id FROM staff s JOIN departments d ON d.department_id=s.department_id
               JOIN faculties f ON f.faculty_id=d.faculty_id WHERE f.faculty_code='EMS' LIMIT 1"""
        ).fetchone()[0]
        result = validate_manual_change(self.conn, entry_id, {"staff_id": ems_staff})
        self.assertFalse(result["valid"])
        self.assertTrue(any("faculty" in error.lower() and "NAS" in error for error in result["errors"]))

    def test_undersized_room_is_rejected_with_capacity_numbers(self):
        entry_id = self._entry("CMP101")
        small_room = self.conn.execute("SELECT room_id FROM rooms WHERE room_name='NAS Classroom 1'").fetchone()[0]
        result = validate_manual_change(self.conn, entry_id, {"room_id": small_room})
        self.assertFalse(result["valid"])
        text = " ".join(result["errors"])
        self.assertIn("capacity", text.lower())
        self.assertIn("80", text)
        self.assertIn("93", text)

    def test_room_clash_is_rejected_and_names_conflicting_module(self):
        target = self._entry("CMP101")
        acc = get_editable_entry(self.conn, self._entry("ACC101"), self.version_id)
        result = validate_manual_change(
            self.conn,
            target,
            {"day": acc["day_of_week"], "start_period": acc["start_period"], "room_id": acc["room_id"]},
        )
        self.assertFalse(result["valid"])
        self.assertTrue(any("clash" in e.lower() for e in result["errors"]))
        self.assertTrue(any("ACC101" in e or "CMP101" in e for e in result["errors"]))

    def test_locked_entry_cannot_be_structurally_changed(self):
        entry_id = self._entry("CMP101")
        set_entry_lock(self.conn, entry_id, True, self.admin_id)
        current = get_editable_entry(self.conn, entry_id, self.version_id)
        with self.assertRaisesRegex(ValueError, "locked"):
            save_manual_change(
                self.conn,
                entry_id,
                {"room_id": current["room_id"] + 1},
                self.admin_id,
            )

    def test_valid_room_change_saves_and_revalidates(self):
        entry_id = self._entry("CMP101")
        room1 = self.conn.execute("SELECT room_id FROM rooms WHERE room_name='NAS Lecture Hall 1'").fetchone()[0]
        result = save_manual_change(self.conn, entry_id, {"room_id": room1}, self.admin_id)
        self.assertTrue(result["valid"])
        saved = get_editable_entry(self.conn, entry_id, self.version_id)
        self.assertEqual(saved["room_id"], room1)

    def test_structural_edit_after_approval_returns_version_to_draft(self):
        entry_id = self._entry("CMP101")
        room1 = self.conn.execute("SELECT room_id FROM rooms WHERE room_name='NAS Lecture Hall 1'").fetchone()[0]
        self.conn.execute("UPDATE timetable_versions SET status='APPROVED' WHERE version_id=?", (self.version_id,))
        self.conn.commit()
        result = save_manual_change(self.conn, entry_id, {"room_id": room1}, self.admin_id)
        self.assertTrue(result["valid"])
        status = self.conn.execute("SELECT status FROM timetable_versions WHERE version_id=?", (self.version_id,)).fetchone()[0]
        self.assertEqual(status, "DRAFT")

    def test_smart_suggestions_are_hard_valid_and_rank_faculty_rooms_first(self):
        entry_id = self._entry("CMP101")
        suggestions = suggest_placements(self.conn, entry_id, limit=5)
        self.assertGreaterEqual(len(suggestions), 3)
        self.assertLessEqual(len(suggestions), 5)
        first = suggestions[0]
        self.assertTrue(first["faculty_preferred"])
        self.assertGreaterEqual(first["capacity"], first["students"])
        self.assertIn(first["quality"], {"Best option", "Good alternative", "Valid alternative"})
        for candidate in suggestions:
            checked = validate_manual_change(
                self.conn, entry_id,
                {"day": candidate["day"], "start_period": candidate["start_period"], "room_id": candidate["room_id"]},
            )
            self.assertTrue(checked["valid"], candidate)
            self.assertGreaterEqual(candidate["capacity"], candidate["students"])

    def test_smart_suggestions_do_not_offer_incompatible_or_undersized_rooms(self):
        entry_id = self._entry("CMP101")
        small_room = self.conn.execute("SELECT room_id FROM rooms WHERE room_name='NAS Classroom 1'").fetchone()[0]
        suggestions = suggest_placements(self.conn, entry_id, limit=20)
        self.assertNotIn(small_room, {item["room_id"] for item in suggestions})
        self.assertTrue(all(item["room_compatible"] for item in suggestions))



if __name__ == "__main__":
    unittest.main()
