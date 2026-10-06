import tempfile
import unittest
from pathlib import Path

from database.bootstrap import ensure_synthetic_ready
from database.db import connect
from database.security import check_password_hash


class SyntheticBootstrapTests(unittest.TestCase):
    def test_fresh_bootstrap_loads_accounts_and_registrations(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "synthetic.db"
            ensure_synthetic_ready(db)
            conn = connect(db)
            try:
                self.assertGreaterEqual(conn.execute("SELECT COUNT(*) FROM students").fetchone()[0], 3000)
                self.assertGreater(conn.execute("SELECT COUNT(*) FROM student_module_registrations").fetchone()[0], 0)
                admin = conn.execute("SELECT * FROM users WHERE username='admin'").fetchone()
                self.assertTrue(check_password_hash(admin['password_hash'], 'admin123'))
                student = conn.execute("SELECT u.*, s.student_number FROM users u JOIN students s ON s.student_id=u.student_id WHERE u.role='STUDENT' LIMIT 1").fetchone()
                self.assertTrue(check_password_hash(student['password_hash'], 'Tnu@' + student['student_number'][-4:]))
                lecturer = conn.execute("SELECT u.*, st.staff_number FROM users u JOIN staff st ON st.staff_id=u.staff_id WHERE u.role='LECTURER' LIMIT 1").fetchone()
                self.assertTrue(check_password_hash(lecturer['password_hash'], 'Tnu@' + lecturer['staff_number'][-4:]))
            finally:
                conn.close()

    def test_second_bootstrap_does_not_duplicate_population(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "synthetic.db"
            ensure_synthetic_ready(db)
            conn = connect(db)
            try:
                before = tuple(conn.execute(q).fetchone()[0] for q in [
                    "SELECT COUNT(*) FROM students",
                    "SELECT COUNT(*) FROM staff",
                    "SELECT COUNT(*) FROM student_module_registrations",
                    "SELECT COUNT(*) FROM users",
                ])
            finally:
                conn.close()
            ensure_synthetic_ready(db)
            conn = connect(db)
            try:
                after = tuple(conn.execute(q).fetchone()[0] for q in [
                    "SELECT COUNT(*) FROM students",
                    "SELECT COUNT(*) FROM staff",
                    "SELECT COUNT(*) FROM student_module_registrations",
                    "SELECT COUNT(*) FROM users",
                ])
            finally:
                conn.close()
            self.assertEqual(before, after)

    def test_wrong_password_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "synthetic.db"
            ensure_synthetic_ready(db)
            conn = connect(db)
            try:
                user = conn.execute("SELECT password_hash FROM users WHERE role='STUDENT' LIMIT 1").fetchone()
                self.assertFalse(check_password_hash(user['password_hash'], 'definitely-wrong'))
            finally:
                conn.close()


if __name__ == '__main__':
    unittest.main()
