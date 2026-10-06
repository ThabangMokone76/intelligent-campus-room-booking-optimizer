import shutil
import tempfile
import unittest
from pathlib import Path

from services.source_catalog import validate_source_catalogs
from services.synthetic_population import generate_population

DATA = Path(__file__).resolve().parent.parent / 'data'


class SyntheticPopulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = generate_population(DATA)

    def test_source_catalogs_valid(self):
        self.assertEqual(validate_source_catalogs(DATA).errors, [])

    def test_population_size_and_credentials(self):
        s = self.bundle.students
        self.assertGreaterEqual(len(s), 3000)
        self.assertLessEqual(len(s), 5000)
        self.assertEqual(len(s), len({x.student_number for x in s}))
        self.assertEqual(len(s), len({x.email for x in s}))
        for x in s[:100]:
            self.assertEqual(x.email, f'{x.student_number}@tnu.ac.za')
            self.assertEqual(x.password, 'Tnu@' + x.student_number[-4:])

    def test_all_students_receive_modules(self):
        registered = {r.student_number for r in self.bundle.registrations}
        self.assertEqual(len(registered), len(self.bundle.students))

    def test_lecturer_credentials(self):
        ls = self.bundle.lecturers
        self.assertEqual(len(ls), len({x.staff_number for x in ls}))
        self.assertEqual(len(ls), len({x.email for x in ls}))
        for x in ls:
            self.assertTrue(x.email.endswith('@tnu.ac.za'))
            self.assertEqual(x.password, 'Tnu@' + x.staff_number[-4:])

    def test_generated_module_lecturer_mapping_stays_inside_faculty(self):
        lecturer_faculty = {x.staff_number: x.faculty_code for x in self.bundle.lecturers}
        module_faculty = {}
        with open(DATA / 'source_exam_modules.csv', encoding='utf-8-sig') as handle:
            import csv
            for row in csv.DictReader(handle):
                module_faculty.setdefault(row['module_code'], row['faculty_code'])
        for module_code, staff_number in self.bundle.module_lecturer.items():
            self.assertEqual(lecturer_faculty[staff_number], module_faculty[module_code])


class LecturerFacultyIntegrityTests(unittest.TestCase):
    def test_loaded_offering_faculty_audit_is_clean(self):
        from database.db import connect
        from services.synthetic_load_service import faculty_assignment_mismatches

        conn = connect()
        try:
            self.assertEqual(faculty_assignment_mismatches(conn), [])
        finally:
            conn.close()

    def test_faculty_audit_reports_intentional_wrong_faculty_assignment(self):
        from database.db import connect
        from services.synthetic_load_service import faculty_assignment_mismatches

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'audit.db'
            shutil.copy2(Path('database/campus_timetable.db'), path)
            conn = connect(path)
            try:
                offering = conn.execute(
                    '''SELECT mo.offering_id, md.faculty_id
                       FROM module_offerings mo
                       JOIN modules m ON m.module_id=mo.module_id
                       JOIN departments md ON md.department_id=m.department_id
                       LIMIT 1'''
                ).fetchone()
                wrong = conn.execute(
                    '''SELECT s.staff_id FROM staff s
                       JOIN departments d ON d.department_id=s.department_id
                       WHERE d.faculty_id<>? LIMIT 1''',
                    (offering['faculty_id'],),
                ).fetchone()
                self.assertIsNotNone(wrong)
                conn.execute('DELETE FROM offering_staff WHERE offering_id=?', (offering['offering_id'],))
                conn.execute(
                    'INSERT INTO offering_staff(offering_id,staff_id) VALUES (?,?)',
                    (offering['offering_id'], wrong['staff_id']),
                )
                conn.commit()
                mismatches = faculty_assignment_mismatches(conn)
                self.assertEqual(len(mismatches), 1)
                self.assertNotEqual(mismatches[0]['module_faculty'], mismatches[0]['staff_faculty'])
            finally:
                conn.close()


if __name__ == '__main__':
    unittest.main()
