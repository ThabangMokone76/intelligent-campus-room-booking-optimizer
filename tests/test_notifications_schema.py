import tempfile
import unittest
from pathlib import Path

from database.db import connect, init_database


class NotificationSchemaTests(unittest.TestCase):
    def test_fresh_database_has_notification_table_foreign_keys_and_indexes(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "notifications.db"
            init_database(db)
            conn = connect(db)
            try:
                table = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'"
                ).fetchone()
                self.assertIsNotNone(table)
                columns = {r["name"] for r in conn.execute("PRAGMA table_info(notifications)")}
                self.assertEqual(
                    columns,
                    {"notification_id", "recipient_user_id", "notification_type", "title", "message", "version_id", "entry_id", "created_at", "read_at"},
                )
                fks = conn.execute("PRAGMA foreign_key_list(notifications)").fetchall()
                by_from = {r["from"]: (r["table"], r["on_delete"]) for r in fks}
                self.assertEqual(by_from["recipient_user_id"], ("users", "CASCADE"))
                self.assertEqual(by_from["version_id"], ("timetable_versions", "CASCADE"))
                self.assertEqual(by_from["entry_id"], ("timetable_entries", "SET NULL"))
                indexes = {r["name"] for r in conn.execute("PRAGMA index_list(notifications)")}
                self.assertIn("idx_notifications_recipient_read", indexes)
                self.assertIn("idx_notifications_version", indexes)
                self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
