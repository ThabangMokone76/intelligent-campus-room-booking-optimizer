import unittest
from pathlib import Path


class ManualTimetablingUISmokeTests(unittest.TestCase):
    def test_admin_navigation_exposes_manual_timetabling(self):
        base = Path("templates/base.html").read_text(encoding="utf-8")
        self.assertIn("Manual Timetabling", base)
        self.assertIn("url_for('manual_timetabling')", base)

    def test_manual_workspace_has_guided_context_and_smart_placement(self):
        page = Path("templates/manual_timetabling.html").read_text(encoding="utf-8")
        for text in ("Working in:", "Faculty", "Programme", "Year", "Module", "Smart Placement", "Current timetable"):
            self.assertIn(text, page)
        for field_id in ("faculty_id", "programme_id", "year_level", "module_id", "staff_id", "group_id", "room_id"):
            self.assertIn(field_id, page)

    def test_parent_context_changes_clear_dependent_choices(self):
        page = Path("templates/manual_timetabling.html").read_text(encoding="utf-8")
        self.assertIn("clearSelect", page)
        self.assertIn("/api/context/programmes", page)
        self.assertIn("/api/context/years", page)
        self.assertIn("/api/context/modules", page)
        self.assertIn("/api/context/lecturers", page)
        self.assertIn("/api/context/groups", page)
        self.assertIn("/api/context/rooms", page)

    def test_manual_route_is_admin_only(self):
        source = Path("app.py").read_text(encoding="utf-8")
        marker = 'def manual_timetabling():'
        self.assertIn(marker, source)
        prefix = source[:source.index(marker)]
        self.assertIn('@role_required("ADMIN")', prefix[-200:])

    def test_spu_branding_is_inherited_not_replaced(self):
        page = Path("templates/manual_timetabling.html").read_text(encoding="utf-8")
        self.assertIn("{% extends 'base.html' %}", page)
        base = Path("templates/base.html").read_text(encoding="utf-8")
        self.assertIn("images/spu-crest.png", base)

    def test_admin_timetable_class_cells_expose_direct_edit_drawer(self):
        page = Path("templates/timetable.html").read_text(encoding="utf-8")
        self.assertIn("Edit class", page)
        self.assertIn("edit_entry", page)
        self.assertIn("timetable-edit-drawer", page)
        self.assertIn("Smart Suggestions", page)
        self.assertIn("admin_edit_entry", page)
        self.assertIn("admin_entry_lock", page)

    def test_direct_editor_keeps_published_views_read_only(self):
        page = Path("templates/timetable.html").read_text(encoding="utf-8")
        self.assertIn("version.status in ['DRAFT','CHANGES_REQUESTED','APPROVED']", page)
        self.assertIn("read-only", page.lower())


if __name__ == "__main__":
    unittest.main()
