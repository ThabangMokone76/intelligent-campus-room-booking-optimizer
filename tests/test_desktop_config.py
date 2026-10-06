import unittest
from pathlib import Path


class DesktopConfigTests(unittest.TestCase):
    def test_downloads_enabled_and_spu_title_used(self):
        source = Path('desktop_app.py').read_text(encoding='utf-8')
        self.assertIn("webview.settings['ALLOW_DOWNLOADS'] = True", source)
        self.assertIn('Sol Plaatje University Timetable Optimizer', source)


if __name__ == '__main__': unittest.main()
