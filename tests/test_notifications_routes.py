import unittest
from pathlib import Path


class NotificationRouteSmokeTests(unittest.TestCase):
    def test_notification_routes_are_login_protected(self):
        source = Path("app.py").read_text(encoding="utf-8")
        self.assertIn('@app.route("/notifications")', source)
        self.assertIn('@app.post("/notifications/<int:notification_id>/read")', source)
        self.assertIn('@app.post("/notifications/read-all")', source)
        # Each route is expected to use the existing login guard.
        for name in ("notifications_page", "notification_read", "notifications_read_all"):
            marker = f"def {name}"
            pos = source.index(marker)
            self.assertIn("@login_required", source[max(0, pos - 180):pos])

    def test_authenticated_shell_renders_notification_bell_and_zero_count(self):
        source = Path("templates/base.html").read_text(encoding="utf-8")
        self.assertIn("Notifications", source)
        self.assertIn("unread_notifications", source)
        self.assertIn("notification-badge", source)

    def test_notification_page_has_read_actions_and_empty_state(self):
        path = Path("templates/notifications.html")
        self.assertTrue(path.exists())
        source = path.read_text(encoding="utf-8")
        self.assertIn("Mark all as read", source)
        self.assertIn("Mark as read", source)
        self.assertIn("No notifications yet", source)

    def test_context_processor_queries_unread_only_for_authenticated_user(self):
        source = Path("app.py").read_text(encoding="utf-8")
        start = source.index("def inject_globals")
        end = source.index('@app.route("/login"', start)
        block = source[start:end]
        self.assertIn("user = current_user()", block)
        self.assertIn("if user", block)
        self.assertIn("unread_count", block)


if __name__ == "__main__":
    unittest.main()
