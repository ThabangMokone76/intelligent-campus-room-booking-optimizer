import tempfile
import unittest
from pathlib import Path

from database.bootstrap import ensure_synthetic_ready
from database.db import connect
from services.timetable_service import timetable_rows, visible_version


class PersonalTimetableTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.db=Path(self.tmp.name)/'personal.db'
        ensure_synthetic_ready(self.db); self.conn=connect(self.db)
        self.version=self.conn.execute("SELECT * FROM timetable_versions WHERE status='PUBLISHED' ORDER BY version_number DESC LIMIT 1").fetchone()

    def tearDown(self): self.conn.close(); self.tmp.cleanup()

    def test_student_rows_match_section_assignments(self):
        user=dict(self.conn.execute("SELECT * FROM users WHERE role='STUDENT' AND student_id IS NOT NULL ORDER BY user_id LIMIT 1").fetchone())
        rows=timetable_rows(self.conn,self.version['version_id'],user)
        self.assertTrue(rows)
        for row in rows:
            assigned=self.conn.execute("SELECT 1 FROM section_student_assignments WHERE section_id=? AND student_id=?",(row['section_id'],user['student_id'])).fetchone()
            self.assertIsNotNone(assigned)

    def test_lecturer_rows_match_offering_assignment(self):
        user=dict(self.conn.execute("SELECT * FROM users WHERE role='LECTURER' AND staff_id IS NOT NULL ORDER BY user_id LIMIT 1").fetchone())
        rows=timetable_rows(self.conn,self.version['version_id'],user)
        self.assertTrue(rows)
        for row in rows:
            assigned=self.conn.execute("SELECT 1 FROM offering_staff WHERE offering_id=? AND staff_id=?",(row['offering_id'],user['staff_id'])).fetchone()
            self.assertIsNotNone(assigned)

    def test_non_admin_visible_version_is_published(self):
        sem=self.version['semester_id']
        self.conn.execute("INSERT INTO timetable_versions(semester_id,version_number,status) VALUES (?,?,?)",(sem,999,'DRAFT'))
        self.conn.commit()
        v=visible_version(self.conn,sem,'STUDENT')
        self.assertEqual(v['status'],'PUBLISHED')


if __name__ == '__main__': unittest.main()
