import csv
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class SyntheticAdminTests(unittest.TestCase):
    def test_admin_synthetic_routes_and_template_exist(self):
        app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        self.assertIn('@app.route("/admin/synthetic")', app_source)
        self.assertIn('@app.route("/admin/synthetic/credentials")', app_source)
        self.assertIn('@role_required("ADMIN")', app_source)
        self.assertTrue((ROOT / 'templates' / 'synthetic_data.html').exists())

    def test_generated_credentials_are_present_and_have_expected_roles(self):
        path = ROOT / 'data' / 'generated_credentials.csv'
        self.assertTrue(path.exists())
        with path.open(newline='', encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f))
        roles = {r['role'] for r in rows}
        self.assertEqual(roles, {'STUDENT', 'LECTURER'})
        self.assertGreater(len(rows), 4000)

    def test_no_exam_scheduling_route_is_added(self):
        app_source = (ROOT / 'app.py').read_text(encoding='utf-8').lower()
        self.assertNotIn('/admin/exam', app_source)
        self.assertNotIn('generate_exam', app_source)


if __name__ == '__main__': unittest.main()
