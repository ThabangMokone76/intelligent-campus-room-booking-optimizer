import unittest
from pathlib import Path


class ReviewCentreUISmokeTests(unittest.TestCase):
    def test_navigation_exposes_review_centre_to_admin_and_reviewer(self):
        base = Path("templates/base.html").read_text(encoding="utf-8")
        self.assertIn("Review Centre", base)
        self.assertIn("current_user.role == 'REVIEWER'", base)
        self.assertIn("url_for('review_centre')", base)

    def test_review_centre_contains_feedback_and_decision_actions(self):
        page = Path("templates/review_centre.html").read_text(encoding="utf-8")
        for text in ("Review Centre", "Add General Comment", "Add Class Comment", "Approve", "Request Changes", "Review history", "Edit class"):
            self.assertIn(text, page)

    def test_review_routes_use_role_specific_guards(self):
        source = Path("app.py").read_text(encoding="utf-8")
        self.assertIn('def review_centre():', source)
        self.assertIn('@role_required("ADMIN", "REVIEWER")', source)
        self.assertIn('def review_add_comment(', source)
        self.assertIn('def review_approve(', source)
        self.assertIn('def review_request_changes(', source)
        self.assertIn('def admin_resubmit_review(', source)
        self.assertIn('def admin_publish_approved(', source)

    def test_admin_feedback_has_direct_edit_class_link(self):
        page = Path("templates/review_centre.html").read_text(encoding="utf-8")
        self.assertIn("edit_entry=comment.entry_id", page)
        self.assertIn("Resolve feedback", page)


if __name__ == "__main__":
    unittest.main()
