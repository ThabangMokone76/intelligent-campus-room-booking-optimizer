import unittest
from pathlib import Path


class ValidationTemplateTests(unittest.TestCase):
    def test_validation_uses_dict_key_access(self):
        source = Path('templates/validation.html').read_text(encoding='utf-8')
        self.assertIn("report['total']", source)
        self.assertIn("report['categories'].items()", source)
        self.assertIn("report['items']", source)
        self.assertNotIn('report.items', source)


if __name__ == '__main__': unittest.main()
