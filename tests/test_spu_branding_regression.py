import unittest
from pathlib import Path


class SPUBrandingRegressionTests(unittest.TestCase):
    def test_spu_shell_and_logo_assets_remain_present(self):
        base = Path("templates/base.html").read_text(encoding="utf-8")
        timetable = Path("templates/timetable.html").read_text(encoding="utf-8")
        self.assertIn("Sol Plaatje University", base)
        self.assertIn("images/spu-crest.png", base)
        self.assertTrue(Path("static/images/spu-logo.png").exists())
        self.assertTrue(Path("static/images/spu-crest.png").exists())
        self.assertIn("SPU campus timetable", timetable)
        self.assertIn("spu-campus-grid", timetable)

    def test_spu_period_six_definition_is_preserved(self):
        migration = Path("database/migrations.py").read_text(encoding="utf-8")
        self.assertIn("12:45", migration)
        self.assertIn("13:20", migration)

    def test_existing_student_and_lecturer_personal_view_is_preserved(self):
        source = Path("templates/personal_timetable.html").read_text(encoding="utf-8")
        self.assertIn("weekly-grid", source)
        self.assertIn("My Timetable", source)


if __name__ == "__main__":
    unittest.main()
