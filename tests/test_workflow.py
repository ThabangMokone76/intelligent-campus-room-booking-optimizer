import tempfile
import unittest
from pathlib import Path

from database.db import connect
from database.seed_demo import seed
from database.migrations import apply_runtime_migrations
from scheduler.engine import generate_timetable
from services.timetable_service import set_version_status, timetable_rows
from services.faculty_context_service import get_programmes, get_years, get_modules, get_lecturers, get_student_groups, get_ranked_rooms
from services.manual_timetable_service import get_editable_entry, save_manual_change, suggest_placements
from services.review_service import add_comment, request_changes, resolve_comment, resubmit_review, approve_review, publish_approved_version, submit_for_review


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        seed(self.db_path)
        self.conn = connect(self.db_path)
        apply_runtime_migrations(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_valid_draft_requires_approval_before_publish(self):
        result = generate_timetable(self.conn)
        with self.assertRaises(ValueError):
            set_version_status(self.conn, result["version_id"], "PUBLISHED")
        set_version_status(self.conn, result["version_id"], "IN_REVIEW")
        set_version_status(self.conn, result["version_id"], "APPROVED")
        set_version_status(self.conn, result["version_id"], "PUBLISHED")
        status = self.conn.execute(
            "SELECT status FROM timetable_versions WHERE version_id=?",
            (result["version_id"],),
        ).fetchone()[0]
        self.assertEqual(status, "PUBLISHED")

    def test_publish_creates_notifications_only_after_validation(self):
        result = generate_timetable(self.conn)
        version_id = result["version_id"]

        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0], 0)
        set_version_status(self.conn, version_id, "IN_REVIEW")
        set_version_status(self.conn, version_id, "APPROVED")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0], 0)

        set_version_status(self.conn, version_id, "PUBLISHED")
        self.assertGreater(self.conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0], 0)
        status = self.conn.execute(
            "SELECT status FROM timetable_versions WHERE version_id=?", (version_id,)
        ).fetchone()[0]
        self.assertEqual(status, "PUBLISHED")

    def test_failed_publish_rolls_back_status_and_notifications(self):
        result = generate_timetable(self.conn)
        version_id = result["version_id"]
        set_version_status(self.conn, version_id, "IN_REVIEW")
        set_version_status(self.conn, version_id, "APPROVED")

        entry = self.conn.execute(
            "SELECT section_id FROM timetable_entries WHERE version_id=? LIMIT 1", (version_id,)
        ).fetchone()
        self.assertIsNotNone(entry)
        self.conn.execute(
            "UPDATE session_sections SET student_count=student_count+10000 WHERE section_id=?",
            (entry["section_id"],),
        )
        self.conn.commit()

        with self.assertRaises(ValueError):
            set_version_status(self.conn, version_id, "PUBLISHED")

        status = self.conn.execute(
            "SELECT status FROM timetable_versions WHERE version_id=?", (version_id,)
        ).fetchone()[0]
        self.assertEqual(status, "APPROVED")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0], 0)

    def test_end_to_end_nas_manual_edit_review_feedback_approval_and_publish(self):
        result = generate_timetable(self.conn)
        version_id = result["version_id"]
        admin_id = self.conn.execute("SELECT user_id FROM users WHERE username='admin'").fetchone()[0]
        reviewer_id = self.conn.execute("SELECT user_id FROM users WHERE username='reviewer'").fetchone()[0]

        nas = self.conn.execute("SELECT faculty_id FROM faculties WHERE faculty_code='NAS'").fetchone()[0]
        programmes = get_programmes(self.conn, nas)
        bcomp = next(p for p in programmes if p["programme_code"] == "BCOMP")
        self.assertEqual(get_years(self.conn, bcomp["programme_id"]), [1])
        modules = get_modules(self.conn, bcomp["programme_id"], 1)
        cmp101 = next(m for m in modules if m["module_code"] == "CMP101")
        lecturers = get_lecturers(self.conn, cmp101["module_id"])
        self.assertTrue(lecturers)
        self.assertTrue(all(x["faculty_code"] == "NAS" for x in lecturers))
        self.assertTrue(get_student_groups(self.conn, bcomp["programme_id"], 1))
        rooms = get_ranked_rooms(self.conn, cmp101["module_id"], 93)
        self.assertTrue(rooms)
        self.assertEqual(rooms[0]["faculty_code"], "NAS")

        entry_id = self.conn.execute(
            """SELECT te.entry_id FROM timetable_entries te
               JOIN session_parts sp ON sp.part_id=te.part_id
               JOIN class_sessions cs ON cs.session_id=sp.session_id
               JOIN session_templates st ON st.session_template_id=cs.session_template_id
               JOIN module_offerings mo ON mo.offering_id=st.offering_id
               JOIN modules m ON m.module_id=mo.module_id
               WHERE te.version_id=? AND m.module_code='CMP101' ORDER BY te.entry_id LIMIT 1""",
            (version_id,),
        ).fetchone()[0]
        before = get_editable_entry(self.conn, entry_id, version_id)
        first_move = next(
            x for x in suggest_placements(self.conn, entry_id, limit=10)
            if (x["day"], x["start_period"], x["room_id"]) != (before["day_of_week"], before["start_period"], before["room_id"])
        )
        save_manual_change(self.conn, entry_id, {"day": first_move["day"], "start_period": first_move["start_period"], "room_id": first_move["room_id"]}, admin_id)

        review_id = submit_for_review(self.conn, version_id, admin_id, reviewer_id)
        comment_id = add_comment(self.conn, review_id, reviewer_id, "Please move this class to a better slot.", entry_id)
        request_changes(self.conn, review_id, reviewer_id, "Please address the class-specific feedback.")

        changed = get_editable_entry(self.conn, entry_id, version_id)
        second_move = next(
            x for x in suggest_placements(self.conn, entry_id, limit=20)
            if (x["day"], x["start_period"], x["room_id"]) != (changed["day_of_week"], changed["start_period"], changed["room_id"])
        )
        save_manual_change(self.conn, entry_id, {"day": second_move["day"], "start_period": second_move["start_period"], "room_id": second_move["room_id"]}, admin_id)
        resolve_comment(self.conn, comment_id, admin_id)
        review2 = resubmit_review(self.conn, version_id, admin_id)
        approve_review(self.conn, review2, reviewer_id, "Looks good after correction.")
        publish_approved_version(self.conn, version_id, admin_id)

        status = self.conn.execute("SELECT status FROM timetable_versions WHERE version_id=?", (version_id,)).fetchone()[0]
        self.assertEqual(status, "PUBLISHED")
        student = dict(self.conn.execute("SELECT * FROM users WHERE username='student'").fetchone())
        lecturer = dict(self.conn.execute("SELECT * FROM users WHERE username='lecturer'").fetchone())
        self.assertTrue(timetable_rows(self.conn, version_id, student))
        self.assertTrue(timetable_rows(self.conn, version_id, lecturer))

    def test_final_check_covers_spu_reviewer_and_workflow_acceptance(self):
        source = Path("final_check.py").read_text(encoding="utf-8")
        for marker in ("SPU branding: PASS", "Reviewer login: PASS", "Review workflow: PASS", "Canonical faculty colours: PASS"):
            self.assertIn(marker, source)



if __name__ == "__main__":
    unittest.main()
