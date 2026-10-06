import tempfile
import unittest
from pathlib import Path

from database.db import connect
from database.seed_demo import seed
from database.security import generate_password_hash
from scheduler.engine import generate_timetable
from services.review_service import (
    add_comment,
    approve_review,
    can_publish,
    request_changes,
    resolve_comment,
    resubmit_review,
    submit_for_review,
)


class ReviewWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "review.db"
        seed(self.db)
        self.conn = connect(self.db)
        self.version_id = generate_timetable(self.conn)["version_id"]
        self.admin_id = self.conn.execute("SELECT user_id FROM users WHERE role='ADMIN'").fetchone()[0]
        self.reviewer_id = self.conn.execute(
            "INSERT INTO users(username,password_hash,role) VALUES (?,?, 'REVIEWER')",
            ("reviewer-test", generate_password_hash("Reviewer@123")),
        ).lastrowid
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _status(self):
        return self.conn.execute("SELECT status FROM timetable_versions WHERE version_id=?", (self.version_id,)).fetchone()[0]

    def test_admin_submits_draft_to_named_reviewer(self):
        review_id = submit_for_review(self.conn, self.version_id, self.admin_id, self.reviewer_id)
        self.assertEqual(self._status(), "IN_REVIEW")
        review = self.conn.execute("SELECT * FROM timetable_reviews WHERE review_id=?", (review_id,)).fetchone()
        self.assertEqual(review["assigned_reviewer_user_id"], self.reviewer_id)
        self.assertEqual(review["status"], "IN_REVIEW")

    def test_non_admin_cannot_submit(self):
        with self.assertRaises(PermissionError):
            submit_for_review(self.conn, self.version_id, self.reviewer_id, self.reviewer_id)

    def test_reviewer_can_request_changes_and_admin_resubmit_preserving_history(self):
        first = submit_for_review(self.conn, self.version_id, self.admin_id, self.reviewer_id)
        request_changes(self.conn, first, self.reviewer_id, "Please move the NAS clash-risk class.")
        self.assertEqual(self._status(), "CHANGES_REQUESTED")
        second = resubmit_review(self.conn, self.version_id, self.admin_id)
        self.assertNotEqual(first, second)
        self.assertEqual(self._status(), "IN_REVIEW")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM timetable_reviews WHERE version_id=?", (self.version_id,)).fetchone()[0], 2)

    def test_unresolved_feedback_blocks_approval_until_resolved(self):
        review_id = submit_for_review(self.conn, self.version_id, self.admin_id, self.reviewer_id)
        entry_id = self.conn.execute("SELECT entry_id FROM timetable_entries WHERE version_id=? LIMIT 1", (self.version_id,)).fetchone()[0]
        comment_id = add_comment(self.conn, review_id, self.reviewer_id, "Check this venue.", entry_id)
        with self.assertRaisesRegex(ValueError, "unresolved"):
            approve_review(self.conn, review_id, self.reviewer_id)
        resolve_comment(self.conn, comment_id, self.admin_id)
        approve_review(self.conn, review_id, self.reviewer_id, "All corrections verified.")
        self.assertEqual(self._status(), "APPROVED")
        row = self.conn.execute("SELECT is_resolved,resolved_by_user_id FROM review_comments WHERE comment_id=?", (comment_id,)).fetchone()
        self.assertEqual((row[0], row[1]), (1, self.admin_id))

    def test_can_publish_requires_approved_unchanged_valid_content(self):
        review_id = submit_for_review(self.conn, self.version_id, self.admin_id, self.reviewer_id)
        approve_review(self.conn, review_id, self.reviewer_id)
        allowed, reasons = can_publish(self.conn, self.version_id)
        self.assertTrue(allowed, reasons)
        entry = self.conn.execute("SELECT entry_id,room_id FROM timetable_entries WHERE version_id=? LIMIT 1", (self.version_id,)).fetchone()
        other_room = self.conn.execute("SELECT room_id FROM rooms WHERE room_id<>? ORDER BY room_id LIMIT 1", (entry["room_id"],)).fetchone()[0]
        self.conn.execute("UPDATE timetable_entries SET room_id=? WHERE entry_id=?", (other_room, entry["entry_id"]))
        self.conn.commit()
        allowed, reasons = can_publish(self.conn, self.version_id)
        self.assertFalse(allowed)
        self.assertTrue(any("changed" in reason.lower() for reason in reasons))

    def test_class_comment_must_target_entry_in_reviewed_version(self):
        review_id = submit_for_review(self.conn, self.version_id, self.admin_id, self.reviewer_id)
        with self.assertRaises(ValueError):
            add_comment(self.conn, review_id, self.reviewer_id, "Wrong target", 999999)

    def test_faculty_restricted_reviewer_cannot_review_whole_campus_version(self):
        nas_id = self.conn.execute("SELECT faculty_id FROM faculties WHERE faculty_code='NAS'").fetchone()[0]
        self.conn.execute("INSERT INTO reviewer_faculties(user_id,faculty_id) VALUES (?,?)", (self.reviewer_id, nas_id))
        self.conn.commit()
        with self.assertRaisesRegex(PermissionError, "scope"):
            submit_for_review(self.conn, self.version_id, self.admin_id, self.reviewer_id)


if __name__ == "__main__":
    unittest.main()
