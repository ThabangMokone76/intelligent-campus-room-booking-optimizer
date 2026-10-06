import unittest
from pathlib import Path


class SPUBrandingTests(unittest.TestCase):
    def test_login_contains_spu_identity_and_logo(self):
        source = Path("templates/login.html").read_text(encoding="utf-8")
        self.assertIn("Sol Plaatje University Timetable Optimizer", source)
        self.assertIn("Campus Academic Timetable and Room Allocation System", source)
        self.assertIn("images/spu-logo.png", source)

    def test_authenticated_shell_uses_compact_crest_and_role_navigation(self):
        source = Path("templates/base.html").read_text(encoding="utf-8")
        self.assertIn("images/spu-crest.png", source)
        self.assertIn("Sol Plaatje University", source)
        self.assertIn("current_user.role == 'ADMIN'", source)
        self.assertIn("current_user.role == 'LECTURER'", source)
        self.assertIn("current_user.role == 'STUDENT'", source)

    def test_spu_design_tokens_exist(self):
        css = Path("static/style.css").read_text(encoding="utf-8")
        for token in ("--spu-red", "--spu-orange", "--spu-charcoal", "--spu-cream"):
            self.assertIn(token, css)

    def test_supplied_logo_assets_are_present(self):
        self.assertTrue(Path("static/images/spu-logo.png").exists())
        self.assertTrue(Path("static/images/spu-crest.png").exists())


if __name__ == "__main__":
    unittest.main()
