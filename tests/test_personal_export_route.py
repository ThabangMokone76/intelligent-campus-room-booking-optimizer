import unittest
from pathlib import Path


class PersonalExportRouteSourceTests(unittest.TestCase):
    def test_personal_export_route_is_role_scoped_and_supports_pdf_xlsx(self):
        source = Path('app.py').read_text(encoding='utf-8')
        self.assertIn('@app.route("/my-timetable/export/<fmt>")', source)
        self.assertIn('export_personal_excel', source)
        self.assertIn('export_personal_pdf', source)
        self.assertIn('visible_version(conn, semester["semester_id"], user["role"])', source)

    def test_personal_template_has_download_actions(self):
        source = Path('templates/personal_timetable.html').read_text(encoding='utf-8')
        self.assertIn("my_timetable_export", source)
        self.assertIn("PDF", source)
        self.assertIn("Excel", source)


if __name__ == '__main__': unittest.main()
