import tempfile
import unittest
from pathlib import Path

from database.bootstrap import ensure_synthetic_ready
from database.db import connect
from services.timetable_service import timetable_rows


class RoleDashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "role-dashboard.db"
        ensure_synthetic_ready(self.db)
        self.conn = connect(self.db)
        self.version = dict(self.conn.execute(
            "SELECT * FROM timetable_versions WHERE status='PUBLISHED' ORDER BY version_number DESC LIMIT 1"
        ).fetchone())

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _context(self):
        try:
            from services.dashboard_service import personal_dashboard_context
        except ImportError:
            self.fail("services.dashboard_service.personal_dashboard_context does not exist")
        return personal_dashboard_context

    def test_student_context_contains_only_student_classes_modules_and_venues(self):
        user = dict(self.conn.execute(
            "SELECT * FROM users WHERE role='STUDENT' AND student_id IS NOT NULL ORDER BY user_id LIMIT 1"
        ).fetchone())
        expected = timetable_rows(self.conn, self.version["version_id"], user)
        self.assertTrue(expected)
        today = expected[0]["day_of_week"]
        ctx = self._context()(self.conn, self.version["version_id"], user, today=today, now_time="00:00")
        self.assertTrue(ctx["today_classes"])
        self.assertIsNotNone(ctx["next_class"])
        self.assertEqual({r["entry_id"] for r in ctx["classes"]}, {r["entry_id"] for r in expected})
        self.assertEqual({m["module_id"] for m in ctx["modules"]}, {r["module_id"] for r in expected})
        self.assertEqual({v["room_id"] for v in ctx["venues"]}, {r["room_id"] for r in expected})

    def test_lecturer_context_contains_only_assigned_offerings(self):
        user = dict(self.conn.execute(
            "SELECT * FROM users WHERE role='LECTURER' AND staff_id IS NOT NULL ORDER BY user_id LIMIT 1"
        ).fetchone())
        expected = timetable_rows(self.conn, self.version["version_id"], user)
        self.assertTrue(expected)
        today = expected[0]["day_of_week"]
        ctx = self._context()(self.conn, self.version["version_id"], user, today=today, now_time="00:00")
        self.assertEqual({r["entry_id"] for r in ctx["classes"]}, {r["entry_id"] for r in expected})
        self.assertTrue(ctx["groups"])
        for row in ctx["classes"]:
            assigned = self.conn.execute(
                "SELECT 1 FROM offering_staff WHERE offering_id=? AND staff_id=?",
                (row["offering_id"], user["staff_id"]),
            ).fetchone()
            self.assertIsNotNone(assigned)

    def test_non_admin_context_refuses_direct_draft_version(self):
        user = dict(self.conn.execute(
            "SELECT * FROM users WHERE role='STUDENT' AND student_id IS NOT NULL ORDER BY user_id LIMIT 1"
        ).fetchone())
        draft_id = self.conn.execute(
            "INSERT INTO timetable_versions(semester_id,version_number,status) VALUES (?,?,?)",
            (self.version["semester_id"], 999, "DRAFT"),
        ).lastrowid
        self.conn.commit()
        ctx = self._context()(self.conn, draft_id, user, today="Monday", now_time="00:00")
        self.assertEqual(ctx["classes"], [])
        self.assertFalse(ctx["is_visible"])

    def test_dashboard_template_has_role_specific_sections(self):
        source = Path("templates/dashboard.html").read_text(encoding="utf-8")
        self.assertIn("Today's Classes", source)
        self.assertIn("Today's Teaching", source)
        self.assertIn("Next Class", source)
        self.assertIn("Next Teaching Session", source)


if __name__ == "__main__":
    unittest.main()
