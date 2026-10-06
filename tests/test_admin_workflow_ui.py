import unittest
from pathlib import Path


class AdminWorkflowUISmokeTests(unittest.TestCase):
    def test_generate_and_publish_require_confirmation(self):
        dashboard = Path("templates/dashboard.html").read_text(encoding="utf-8")
        admin = Path("templates/admin.html").read_text(encoding="utf-8")
        timetable = Path("templates/timetable.html").read_text(encoding="utf-8")
        self.assertIn("confirm(", dashboard)
        self.assertIn("confirm(", admin)
        self.assertIn("confirm(", timetable)
        self.assertIn("Publish", timetable)

    def test_admin_controls_are_grouped_and_lock_state_is_visible(self):
        timetable = Path("templates/timetable.html").read_text(encoding="utf-8")
        for heading in ("Generate & Validate", "Edit & Lock", "Workflow", "Export"):
            self.assertIn(heading, timetable)
        self.assertIn("Locked", timetable)
        self.assertIn("is-locked", timetable)

    def test_validation_uses_safe_dictionary_key_access_and_publishable_zero_state(self):
        validation = Path("templates/validation.html").read_text(encoding="utf-8")
        self.assertIn("report['total']", validation)
        self.assertIn("report['categories']", validation)
        self.assertIn("report['items']", validation)
        self.assertNotIn("report.items", validation)
        self.assertIn("publishable", validation.lower())

    def test_admin_dashboard_receives_and_renders_recent_activity(self):
        app_source = Path("app.py").read_text(encoding="utf-8")
        dashboard = Path("templates/dashboard.html").read_text(encoding="utf-8")
        self.assertIn("recent_activity", app_source)
        self.assertIn("recent_activity", dashboard)
        self.assertIn("Recent timetable activity", dashboard)
        self.assertIn("GROUP BY", app_source)

    def test_status_badges_remain_visible(self):
        for path in ("templates/admin.html", "templates/timetable.html", "templates/dashboard.html"):
            source = Path(path).read_text(encoding="utf-8")
            self.assertIn("badge", source)


    def test_legacy_advanced_move_controls_only_render_for_draft_versions(self):
        timetable = Path("templates/timetable.html").read_text(encoding="utf-8")
        self.assertIn("{% if version and rows and version.status == 'DRAFT' %}", timetable)

    def test_new_review_statuses_and_review_centre_actions_are_rendered(self):
        timetable = Path("templates/timetable.html").read_text(encoding="utf-8")
        dashboard = Path("templates/dashboard.html").read_text(encoding="utf-8")
        combined = timetable + dashboard
        for status in ("DRAFT", "IN_REVIEW", "CHANGES_REQUESTED", "APPROVED", "PUBLISHED"):
            self.assertIn(status, combined)
        self.assertNotIn('value="REVIEW"', timetable)
        self.assertIn("Review Centre", timetable)


if __name__ == "__main__":
    unittest.main()
