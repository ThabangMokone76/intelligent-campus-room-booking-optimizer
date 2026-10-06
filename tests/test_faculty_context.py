import tempfile
import unittest
from pathlib import Path

from database.db import connect, init_database

try:
    from services.faculty_context_service import (
        get_programmes, get_years, get_modules, get_lecturers,
        get_student_groups, get_ranked_rooms,
    )
except ImportError:
    get_programmes = get_years = get_modules = get_lecturers = get_student_groups = get_ranked_rooms = None


class FacultyContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "context.db"
        init_database(self.path)
        self.conn = connect(self.path)
        c = self.conn
        nas = c.execute("INSERT INTO faculties(faculty_code,faculty_name,colour_hex) VALUES ('NAS','Natural and Applied Sciences','#059669')").lastrowid
        edu = c.execute("INSERT INTO faculties(faculty_code,faculty_name,colour_hex) VALUES ('EDU','Education','#F6B221')").lastrowid
        dnas = c.execute("INSERT INTO departments(faculty_id,department_code,department_name) VALUES (?,?,?)", (nas,'SCI','Science')).lastrowid
        dedu = c.execute("INSERT INTO departments(faculty_id,department_code,department_name) VALUES (?,?,?)", (edu,'EDU','Education')).lastrowid
        pnas = c.execute("INSERT INTO programmes(department_id,programme_code,programme_name,duration_years) VALUES (?,?,?,3)", (dnas,'BSC700','BSc Computer Science')).lastrowid
        pedu = c.execute("INSERT INTO programmes(department_id,programme_code,programme_name,duration_years) VALUES (?,?,?,4)", (dedu,'EDU700','BEd')).lastrowid
        mnas = c.execute("INSERT INTO modules(department_id,module_code,module_name) VALUES (?,?,?)", (dnas,'NCOS734','Special Topics')).lastrowid
        medu = c.execute("INSERT INTO modules(department_id,module_code,module_name) VALUES (?,?,?)", (dedu,'EEDU734','Education Studies')).lastrowid
        c.execute("INSERT INTO programme_modules(programme_id,module_id,year_level,source_students) VALUES (?,?,3,60)", (pnas,mnas))
        c.execute("INSERT INTO programme_modules(programme_id,module_id,year_level,source_students) VALUES (?,?,4,40)", (pedu,medu))
        gnas = c.execute("INSERT INTO student_groups(programme_id,year_level,number_of_students,section_code) VALUES (?,3,60,'A')", (pnas,)).lastrowid
        gedu = c.execute("INSERT INTO student_groups(programme_id,year_level,number_of_students,section_code) VALUES (?,4,40,'A')", (pedu,)).lastrowid
        snas = c.execute("INSERT INTO staff(department_id,staff_number,first_name,last_name,email) VALUES (?,?,?,?,?)", (dnas,'SPU001','Neo','Mokoena','neo@spu.ac.za')).lastrowid
        sedu = c.execute("INSERT INTO staff(department_id,staff_number,first_name,last_name,email) VALUES (?,?,?,?,?)", (dedu,'SPU002','Lebo','Khumalo','lebo@spu.ac.za')).lastrowid
        bnas = c.execute("INSERT INTO buildings(faculty_id,building_code,building_name,is_shared) VALUES (?,?,?,0)", (nas,'C006','NAS Building')).lastrowid
        bedu = c.execute("INSERT INTO buildings(faculty_id,building_code,building_name,is_shared) VALUES (?,?,?,0)", (edu,'C008','Education Building')).lastrowid
        bshared = c.execute("INSERT INTO buildings(faculty_id,building_code,building_name,is_shared) VALUES (NULL,'GH','Great Hall',1)").lastrowid
        c.execute("INSERT INTO rooms(building_id,room_code,room_name,capacity,room_type) VALUES (?,?,?,?,?)", (bnas,'NAS100','NAS Lecture Hall',100,'Lecture Hall'))
        c.execute("INSERT INTO rooms(building_id,room_code,room_name,capacity,room_type) VALUES (?,?,?,?,?)", (bedu,'EDU100','Education Lecture Hall',100,'Lecture Hall'))
        c.execute("INSERT INTO rooms(building_id,room_code,room_name,capacity,room_type) VALUES (?,?,?,?,?)", (bshared,'GH1','Great Hall',500,'Lecture Hall'))
        c.execute("INSERT INTO semesters(academic_year,semester_number,status) VALUES (2026,2,'ACTIVE')")
        sid = c.execute("SELECT semester_id FROM semesters").fetchone()[0]
        offering = c.execute("INSERT INTO module_offerings(module_id,semester_id,expected_students) VALUES (?,?,60)", (mnas,sid)).lastrowid
        c.execute("INSERT INTO offering_groups(offering_id,group_id) VALUES (?,?)", (offering,gnas))
        c.execute("INSERT INTO offering_staff(offering_id,staff_id) VALUES (?,?)", (offering,snas))
        c.execute("INSERT INTO session_templates(offering_id,session_type,sessions_per_week,preferred_duration,minimum_duration,required_room_type,can_split_duration) VALUES (?,?,1,2,2,'Lecture Hall',0)", (offering,'Lecture'))
        c.commit()
        self.ids = dict(nas=nas, edu=edu, pnas=pnas, pedu=pedu, mnas=mnas, medu=medu, gnas=gnas, gedu=gedu, snas=snas, sedu=sedu)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_nas_context_only_returns_nas_programme_year_module_and_group(self):
        self.assertIsNotNone(get_programmes)
        self.assertEqual([x['programme_id'] for x in get_programmes(self.conn, self.ids['nas'])], [self.ids['pnas']])
        self.assertEqual(get_years(self.conn, self.ids['pnas']), [3])
        self.assertEqual([x['module_id'] for x in get_modules(self.conn, self.ids['pnas'], 3)], [self.ids['mnas']])
        self.assertEqual([x['group_id'] for x in get_student_groups(self.conn, self.ids['pnas'], 3)], [self.ids['gnas']])

    def test_normal_nas_module_excludes_education_lecturer(self):
        lecturers = get_lecturers(self.conn, self.ids['mnas'])
        ids = [x['staff_id'] for x in lecturers]
        self.assertIn(self.ids['snas'], ids)
        self.assertNotIn(self.ids['sedu'], ids)

    def test_explicit_cross_faculty_permission_allows_exception(self):
        self.conn.execute("INSERT INTO cross_faculty_teaching_permissions(module_id,staff_id,note) VALUES (?,?,?)", (self.ids['mnas'], self.ids['sedu'], 'Approved shared teaching'))
        self.conn.commit()
        ids = [x['staff_id'] for x in get_lecturers(self.conn, self.ids['mnas'])]
        self.assertIn(self.ids['sedu'], ids)

    def test_rooms_prefer_nas_then_shared_then_other_faculty(self):
        rooms = get_ranked_rooms(self.conn, self.ids['mnas'], 60)
        names = [r['room_name'] for r in rooms]
        self.assertEqual(names[0], 'NAS Lecture Hall')
        self.assertLess(names.index('Great Hall'), names.index('Education Lecture Hall'))


if __name__ == '__main__':
    unittest.main()
