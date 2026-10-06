import tempfile
import unittest
from pathlib import Path

from database.db import connect
from database.security import check_password_hash
from database.bootstrap import ensure_demo_ready


class AuthBootstrapTests(unittest.TestCase):
    def test_fresh_database_gets_working_demo_accounts(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / 'demo.db'
            ensure_demo_ready(db_path)
            conn = connect(db_path)
            try:
                accounts = {
                    row['username']: row
                    for row in conn.execute(
                        "SELECT username, password_hash, role FROM users ORDER BY username"
                    ).fetchall()
                }
                self.assertEqual(accounts['admin']['role'], 'ADMIN')
                self.assertTrue(check_password_hash(accounts['admin']['password_hash'], 'admin123'))
                self.assertEqual(accounts['lecturer']['role'], 'LECTURER')
                self.assertTrue(check_password_hash(accounts['lecturer']['password_hash'], 'lecturer123'))
                self.assertEqual(accounts['student']['role'], 'STUDENT')
                self.assertTrue(check_password_hash(accounts['student']['password_hash'], 'student123'))
            finally:
                conn.close()


if __name__ == '__main__':
    unittest.main()
