import tempfile
import unittest
from pathlib import Path

from database.bootstrap import ensure_synthetic_ready
from database.db import connect
from database.security import check_password_hash


class SyntheticAuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'auth.db'
        ensure_synthetic_ready(self.db)
        self.conn = connect(self.db)

    def tearDown(self):
        self.conn.close(); self.tmp.cleanup()

    def test_admin_student_and_lecturer_credentials(self):
        admin = self.conn.execute("SELECT * FROM users WHERE username='admin'").fetchone()
        self.assertTrue(check_password_hash(admin['password_hash'], 'admin123'))
        student = self.conn.execute("SELECT u.*,s.student_number FROM users u JOIN students s ON s.student_id=u.student_id WHERE u.role='STUDENT' ORDER BY u.user_id LIMIT 1").fetchone()
        self.assertTrue(check_password_hash(student['password_hash'], 'Tnu@' + student['student_number'][-4:]))
        lecturer = self.conn.execute("SELECT u.*,st.staff_number FROM users u JOIN staff st ON st.staff_id=u.staff_id WHERE u.role='LECTURER' ORDER BY u.user_id LIMIT 1").fetchone()
        self.assertTrue(check_password_hash(lecturer['password_hash'], 'Tnu@' + lecturer['staff_number'][-4:]))
        self.assertFalse(check_password_hash(student['password_hash'], 'wrong-password'))


if __name__ == '__main__': unittest.main()
