import tempfile
import unittest
from pathlib import Path

from database.bootstrap import ensure_synthetic_ready
from database.db import connect
from services.export_service import export_excel, export_pdf


class SyntheticExportTests(unittest.TestCase):
    def test_published_synthetic_timetable_exports_pdf_and_xlsx(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'export.db'; ensure_synthetic_ready(db); conn=connect(db)
            try:
                version=conn.execute("SELECT version_id FROM timetable_versions WHERE status='PUBLISHED' ORDER BY version_number DESC LIMIT 1").fetchone()
                self.assertIsNotNone(version)
                xlsx=export_excel(conn,version['version_id'],Path(tmp)/'timetable.xlsx')
                pdf=export_pdf(conn,version['version_id'],Path(tmp)/'timetable.pdf')
                self.assertTrue(Path(xlsx).exists()); self.assertGreater(Path(xlsx).stat().st_size,1000)
                self.assertTrue(Path(pdf).exists()); self.assertGreater(Path(pdf).stat().st_size,1000)
            finally:
                conn.close()


if __name__=='__main__': unittest.main()
