import tempfile
import unittest
from pathlib import Path

from database.db import connect
from database.migrations import apply_runtime_migrations
from database.seed_demo import seed
from database.security import check_password_hash


class ReviewerSeedTests(unittest.TestCase):
    def test_runtime_migration_provisions_fictional_demo_reviewer(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "reviewer.db"
            seed(path)
            conn = connect(path)
            try:
                apply_runtime_migrations(conn)
                row = conn.execute("SELECT username,password_hash,role FROM users WHERE username='reviewer'").fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row["role"], "REVIEWER")
                self.assertTrue(check_password_hash(row["password_hash"], "reviewer123"))
                self.assertNotEqual(row["password_hash"], "reviewer123")
            finally:
                conn.close()

    def test_sample_logins_documents_reviewer(self):
        text = Path("SAMPLE_LOGINS.txt").read_text(encoding="utf-8")
        self.assertIn("REVIEWER", text)
        self.assertIn("Username: reviewer", text)
        self.assertIn("Password: reviewer123", text)

    def test_reviewer_navigation_is_review_focused(self):
        source = Path("templates/base.html").read_text(encoding="utf-8")
        start = source.index("current_user.role == 'REVIEWER'")
        end = source.index("current_user.role == 'LECTURER'", start)
        branch = source[start:end]
        self.assertIn("Review Centre", branch)
        self.assertNotIn("Manual Timetabling", branch)
        self.assertNotIn("Synthetic Data", branch)


if __name__ == "__main__":
    unittest.main()
