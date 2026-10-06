import tempfile, unittest
from pathlib import Path
from database.db import connect, init_database
from services.synthetic_population import generate_population
from services.synthetic_load_service import load_population, faculty_assignment_mismatches
from services.academic_setup_service import build_semester_offerings
from scheduler.engine import generate_timetable
from scheduler.validator import validate_version

DATA=Path(__file__).resolve().parent.parent/'data'
class LargeSchedulerTests(unittest.TestCase):
    def test_synthetic_timetable_has_zero_hard_violations(self):
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/'large.db'; init_database(db); c=connect(db)
            try:
                b=generate_population(DATA); load_population(c,b,DATA); sem=c.execute("SELECT semester_id FROM semesters WHERE status='ACTIVE'").fetchone()[0]; build_semester_offerings(c,sem,DATA,b.module_lecturer)
                r=generate_timetable(c); rep=validate_version(c,r['version_id']); self.assertEqual(rep.total,0,rep.items[:10]); self.assertGreater(r['scheduled_parts'],100); self.assertEqual(faculty_assignment_mismatches(c), [])
            finally: c.close()
if __name__=='__main__': unittest.main()
