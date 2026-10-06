import tempfile
import unittest
from pathlib import Path

from database.db import connect
from database.seed_demo import seed
from services.import_service import preview_import


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        seed(self.db_path)
        self.conn = connect(self.db_path)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_unknown_room_building_is_rejected(self):
        data = b"room_code,room_name,building_code,capacity,room_type\nX1,Room X,NO_SUCH,50,Lecture Room\n"
        preview = preview_import(self.conn, "rooms", "rooms.csv", data)
        self.assertFalse(preview["valid"])
        self.assertTrue(any("unknown building" in e for e in preview["errors"]))

    def test_duplicate_module_is_rejected(self):
        data = b"module_code,module_name,department_code,credits\nCMP101,Duplicate,CS,16\n"
        preview = preview_import(self.conn, "modules", "modules.csv", data)
        self.assertFalse(preview["valid"])
        self.assertTrue(any("duplicate module" in e for e in preview["errors"]))


if __name__ == "__main__":
    unittest.main()
