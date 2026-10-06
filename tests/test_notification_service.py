import tempfile
import unittest
from pathlib import Path

from database.db import connect
from database.seed_demo import seed
from scheduler.engine import generate_timetable


class NotificationServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "notifications-service.db"
        seed(self.db)
        self.conn = connect(self.db)
        result = generate_timetable(self.conn)
        self.old_version = result["version_id"]
        self.conn.execute("UPDATE timetable_versions SET status='PUBLISHED' WHERE version_id=?", (self.old_version,))
        # Choose a Computer Science entry so the demo lecturer user is assigned to its offering.
        chosen = self.conn.execute(
            """SELECT te.entry_id,te.section_id,te.part_id,st.offering_id
               FROM timetable_entries te
               JOIN session_parts sp ON sp.part_id=te.part_id
               JOIN class_sessions cs ON cs.session_id=sp.session_id
               JOIN session_templates st ON st.session_template_id=cs.session_template_id
               JOIN offering_staff os ON os.offering_id=st.offering_id
               JOIN users u ON u.staff_id=os.staff_id AND u.username='lecturer'
               WHERE te.version_id=? ORDER BY te.entry_id LIMIT 1""",
            (self.old_version,),
        ).fetchone()
        self.assertIsNotNone(chosen)
        self.section_id = chosen["section_id"]
        self.part_id = chosen["part_id"]
        self.offering_id = chosen["offering_id"]
        programme_id = self.conn.execute("SELECT programme_id FROM programmes ORDER BY programme_id LIMIT 1").fetchone()[0]
        student_id = self.conn.execute(
            "INSERT INTO students(programme_id,student_number,first_name,last_name,email,year_level) VALUES (?,?,?,?,?,?)",
            (programme_id, "TEST9001", "Test", "Student", "notifstudent@example.test", 1),
        ).lastrowid
        self.student_user_id = self.conn.execute(
            "INSERT INTO users(username,password_hash,role,student_id) VALUES (?,?,?,?)",
            ("notifstudent", "x", "STUDENT", student_id),
        ).lastrowid
        self.conn.execute(
            "INSERT INTO section_student_assignments(section_id,student_id) VALUES (?,?)",
            (self.section_id, student_id),
        )
        self.lecturer_user_id = self.conn.execute("SELECT user_id FROM users WHERE username='lecturer'").fetchone()[0]
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _service(self):
        try:
            import services.notification_service as service
        except ImportError:
            self.fail("services.notification_service does not exist")
        return service

    def _clone_version(self):
        sem = self.conn.execute("SELECT semester_id FROM timetable_versions WHERE version_id=?", (self.old_version,)).fetchone()[0]
        num = self.conn.execute("SELECT MAX(version_number)+1 FROM timetable_versions WHERE semester_id=?", (sem,)).fetchone()[0]
        new_id = self.conn.execute(
            "INSERT INTO timetable_versions(semester_id,version_number,status) VALUES (?,?,?)", (sem, num, "APPROVED")
        ).lastrowid
        self.conn.execute(
            """INSERT INTO timetable_entries(version_id,section_id,room_id,slot_id,duration_slots,is_locked,part_id)
               SELECT ?,section_id,room_id,slot_id,duration_slots,is_locked,part_id
               FROM timetable_entries WHERE version_id=?""",
            (new_id, self.old_version),
        )
        self.conn.commit()
        return new_id

    def test_unread_count_and_mark_read_are_owner_scoped(self):
        svc = self._service()
        self.conn.execute(
            "INSERT INTO notifications(recipient_user_id,notification_type,title,message,version_id) VALUES (?,?,?,?,?)",
            (self.student_user_id, "TEST", "Student note", "One", self.old_version),
        )
        other_id = self.conn.execute(
            "INSERT INTO notifications(recipient_user_id,notification_type,title,message,version_id) VALUES (?,?,?,?,?)",
            (self.lecturer_user_id, "TEST", "Lecturer note", "Two", self.old_version),
        ).lastrowid
        self.conn.commit()
        self.assertEqual(svc.unread_count(self.conn, self.student_user_id), 1)
        self.assertFalse(svc.mark_read(self.conn, self.student_user_id, other_id))
        self.assertEqual(svc.unread_count(self.conn, self.student_user_id), 1)
        own = svc.list_notifications(self.conn, self.student_user_id)[0]
        self.assertTrue(svc.mark_read(self.conn, self.student_user_id, own["notification_id"]))
        self.assertEqual(svc.unread_count(self.conn, self.student_user_id), 0)

    def test_first_publish_creates_publish_notification_for_assigned_users(self):
        svc = self._service()
        self.conn.execute("DELETE FROM notifications")
        created = svc.create_publish_notifications(self.conn, self.old_version, None)
        self.assertGreaterEqual(created, 2)
        recipients = {r[0] for r in self.conn.execute("SELECT recipient_user_id FROM notifications")}
        self.assertIn(self.student_user_id, recipients)
        self.assertIn(self.lecturer_user_id, recipients)
        types = {r[0] for r in self.conn.execute("SELECT notification_type FROM notifications")}
        self.assertEqual(types, {"TIMETABLE_PUBLISHED"})

    def test_replacement_publish_time_change_notifies_only_affected_users(self):
        svc = self._service()
        new_id = self._clone_version()
        target = self.conn.execute(
            "SELECT entry_id,slot_id FROM timetable_entries WHERE version_id=? AND part_id=? AND section_id=? LIMIT 1",
            (new_id, self.part_id, self.section_id),
        ).fetchone()
        current = self.conn.execute("SELECT day_of_week,period_number FROM time_slots WHERE slot_id=?", (target["slot_id"],)).fetchone()
        replacement = self.conn.execute(
            "SELECT slot_id FROM time_slots WHERE day_of_week<>? AND period_number=? ORDER BY slot_id LIMIT 1",
            (current["day_of_week"], current["period_number"]),
        ).fetchone()[0]
        self.conn.execute("UPDATE timetable_entries SET slot_id=? WHERE version_id=? AND part_id=? AND section_id=?", (replacement, new_id, self.part_id, self.section_id))
        self.conn.execute("DELETE FROM notifications")
        created = svc.create_publish_notifications(self.conn, new_id, self.old_version)
        self.assertGreaterEqual(created, 2)
        notes = [dict(r) for r in self.conn.execute("SELECT * FROM notifications")]
        self.assertEqual({n["recipient_user_id"] for n in notes}, {self.student_user_id, self.lecturer_user_id})
        self.assertEqual({n["notification_type"] for n in notes}, {"TIME_CHANGED"})

    def test_replacement_publish_venue_change_classifies_venue_change(self):
        svc = self._service()
        new_id = self._clone_version()
        target = self.conn.execute(
            "SELECT entry_id,room_id FROM timetable_entries WHERE version_id=? AND part_id=? AND section_id=? LIMIT 1",
            (new_id, self.part_id, self.section_id),
        ).fetchone()
        replacement_room = self.conn.execute("SELECT room_id FROM rooms WHERE room_id<>? ORDER BY room_id LIMIT 1", (target["room_id"],)).fetchone()[0]
        self.conn.execute("UPDATE timetable_entries SET room_id=? WHERE entry_id=?", (replacement_room, target["entry_id"]))
        self.conn.execute("DELETE FROM notifications")
        svc.create_publish_notifications(self.conn, new_id, self.old_version)
        notes = [dict(r) for r in self.conn.execute("SELECT * FROM notifications")]
        self.assertEqual({n["notification_type"] for n in notes}, {"VENUE_CHANGED"})

    def test_mark_all_read_updates_only_requested_user(self):
        svc = self._service()
        for uid in (self.student_user_id, self.student_user_id, self.lecturer_user_id):
            self.conn.execute(
                "INSERT INTO notifications(recipient_user_id,notification_type,title,message,version_id) VALUES (?,?,?,?,?)",
                (uid, "TEST", "Note", "Message", self.old_version),
            )
        self.conn.commit()
        self.assertEqual(svc.mark_all_read(self.conn, self.student_user_id), 2)
        self.assertEqual(svc.unread_count(self.conn, self.student_user_id), 0)
        self.assertEqual(svc.unread_count(self.conn, self.lecturer_user_id), 1)


if __name__ == "__main__":
    unittest.main()
