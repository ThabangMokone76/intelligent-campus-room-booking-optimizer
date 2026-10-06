from __future__ import annotations
import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from database.security import generate_password_hash
from services.source_catalog import load_exam_modules, load_programme_map, load_teaching_rooms, load_module_year_map, validate_source_catalogs

FACULTIES={'EDU':('Faculty of Education','#F6B221'),'EMS':('Faculty of Economic and Management Sciences','#7C3AED'),'HUM':('Faculty of Humanities','#D97706'),'NAS':('Faculty of Natural and Applied Sciences','#059669')}
@dataclass
class LoadSummary:
    students:int; lecturers:int; registrations:int; groups:int; modules:int; rooms:int

def write_generated_csvs(bundle,data_dir):
    data_dir=Path(data_dir); data_dir.mkdir(parents=True,exist_ok=True)
    specs={
      'generated_students.csv':(['student_number','first_name','last_name','email','programme_code','year_level','section_code'],[[s.student_number,s.first_name,s.last_name,s.email,s.programme_code,s.year_level,s.section_code] for s in bundle.students]),
      'generated_lecturers.csv':(['staff_number','first_name','last_name','email','faculty_code','department_code'],[[x.staff_number,x.first_name,x.last_name,x.email,x.faculty_code,x.department_code] for x in bundle.lecturers]),
      'generated_registrations.csv':(['student_number','module_code'],[[r.student_number,r.module_code] for r in bundle.registrations]),
      'generated_credentials.csv':(['role','display_name','username','email','initial_password','programme_or_department'],[['STUDENT',f'{s.first_name} {s.last_name}',s.student_number,s.email,s.password,s.programme_code] for s in bundle.students]+[['LECTURER',f'{x.first_name} {x.last_name}',x.staff_number,x.email,x.password,x.department_code] for x in bundle.lecturers]),
      'generation_report.csv':(['module_code','source_students','generated_students','absolute_difference','percentage_difference','programmes'],[[r[k] for k in ['module_code','source_students','generated_students','absolute_difference','percentage_difference','programmes']] for r in bundle.report_rows])}
    out={}
    for name,(headers,rows) in specs.items():
        p=data_dir/name
        with open(p,'w',newline='',encoding='utf-8') as f: w=csv.writer(f); w.writerow(headers); w.writerows(rows)
        out[name]=p
    return out

def load_population(conn,bundle,data_dir):
    data_dir=Path(data_dir); report=validate_source_catalogs(data_dir)
    if report.errors: raise ValueError('; '.join(report.errors))
    pmap=load_programme_map(data_dir/'programme_faculty_map.csv'); exam=load_exam_modules(data_dir/'source_exam_modules.csv'); rooms=load_teaching_rooms(data_dir/'source_teaching_rooms.csv'); my=load_module_year_map(data_dir/'module_year_map.csv')
    try:
        conn.execute('BEGIN')
        # clean synthetic academic rows but keep schema
        for table in ['section_student_assignments','timetable_entries','generation_metrics','timetable_versions','session_sections','session_parts','class_sessions','session_requirements','session_templates','offering_staff','offering_groups','module_offerings','student_module_registrations','student_group_members','users','students','staff','programme_modules','modules','rooms','buildings','student_groups','programmes','departments','faculties','semesters','equipment']:
            conn.execute(f'DELETE FROM {table}')
        facids={}
        for code,(name,col) in FACULTIES.items(): facids[code]=conn.execute('INSERT INTO faculties(faculty_code,faculty_name,colour_hex) VALUES (?,?,?)',(code,name,col)).lastrowid
        deptids={}
        for r in pmap.values():
            if r.department_code not in deptids: deptids[r.department_code]=conn.execute('INSERT INTO departments(faculty_id,department_code,department_name) VALUES (?,?,?)',(facids[r.faculty_code],r.department_code,r.department_name)).lastrowid
        progids={}
        for r in pmap.values(): progids[r.programme_code]=conn.execute('INSERT INTO programmes(department_id,programme_code,programme_name,duration_years) VALUES (?,?,?,?)',(deptids[r.department_code],r.programme_code,r.programme_name,r.duration_years)).lastrowid
        # buildings
        bids={}
        for code,name,fac,shared in [('EDU_MAIN','Education Teaching Buildings','EDU',0),('EMS_MAIN','EMS Teaching Buildings','EMS',0),('HUM_MAIN','Humanities Teaching Buildings','HUM',0),('NAS_MAIN','Natural and Applied Sciences Buildings','NAS',0),('SHARED','Shared Teaching Venues',None,1)]:
            bids[code]=conn.execute('INSERT INTO buildings(faculty_id,building_code,building_name,is_shared) VALUES (?,?,?,?)',(facids.get(fac),code,name,shared)).lastrowid
        for r in rooms: conn.execute('INSERT INTO rooms(building_id,room_code,room_name,capacity,room_type) VALUES (?,?,?,?,?)',(bids.get(r.building_code,bids['SHARED']),r.room_code,r.room_name,r.capacity,r.room_type))
        # modules & programme relationships
        module_info={}
        for r in exam: module_info.setdefault(r.module_code,(r.module_name,r.faculty_code))
        moduleids={}
        for code,(name,fac) in sorted(module_info.items()):
            dept={'EDU':'EDU','EMS':'BUS','HUM':'HUM','NAS':'SCI'}[fac]
            moduleids[code]=conn.execute('INSERT INTO modules(department_id,module_code,module_name,credits) VALUES (?,?,?,?)',(deptids[dept],code,name,16)).lastrowid
        ym={(r['programme_code'],r['module_code']):r for r in my}
        for r in exam:
            key=(r.programme_code,r.module_code); mr=ym.get(key); year=int(mr['year_level']) if mr else 1
            conn.execute('INSERT OR IGNORE INTO programme_modules(programme_id,module_id,year_level,is_elective,source_students) VALUES (?,?,?,?,?)',(progids[r.programme_code],moduleids[r.module_code],year,0,r.source_students))
        semester=conn.execute("INSERT INTO semesters(academic_year,semester_number,status) VALUES (2026,2,'ACTIVE')").lastrowid
        # groups based on generated student cohorts
        gcounts=defaultdict(int)
        for s in bundle.students: gcounts[(s.programme_code,s.year_level,s.section_code)]+=1
        gids={}
        for (p,y,sec),n in sorted(gcounts.items()): gids[(p,y,sec)]=conn.execute('INSERT INTO student_groups(programme_id,year_level,number_of_students,section_code) VALUES (?,?,?,?)',(progids[p],y,n,sec)).lastrowid
        sids={}
        for s in bundle.students:
            sid=conn.execute('INSERT INTO students(programme_id,student_number,first_name,last_name,email,year_level) VALUES (?,?,?,?,?,?)',(progids[s.programme_code],s.student_number,s.first_name,s.last_name,s.email,s.year_level)).lastrowid; sids[s.student_number]=sid
            conn.execute('INSERT INTO student_group_members(group_id,student_id) VALUES (?,?)',(gids[(s.programme_code,s.year_level,s.section_code)],sid))
            conn.execute('INSERT INTO users(username,password_hash,role,group_id,student_id) VALUES (?,?,?,?,?)',(s.student_number,generate_password_hash(s.password),'STUDENT',gids[(s.programme_code,s.year_level,s.section_code)],sid))
        # lecturers/users
        staffids={}
        for x in bundle.lecturers:
            st=conn.execute('INSERT INTO staff(department_id,staff_number,first_name,last_name,email) VALUES (?,?,?,?,?)',(deptids[x.department_code],x.staff_number,x.first_name,x.last_name,x.email)).lastrowid; staffids[x.staff_number]=st
            conn.execute('INSERT INTO users(username,password_hash,role,staff_id) VALUES (?,?,\'LECTURER\',?)',(x.staff_number,generate_password_hash(x.password),st))
        conn.execute("INSERT INTO users(username,password_hash,role) VALUES ('admin',?,'ADMIN')",(generate_password_hash('admin123'),))
        # regs
        for r in bundle.registrations: conn.execute('INSERT INTO student_module_registrations(student_id,module_id,semester_id) VALUES (?,?,?)',(sids[r.student_number],moduleids[r.module_code],semester))
        # equipment and time slots
        for e in ['Projector','Computer','Laboratory Workstation']: conn.execute('INSERT INTO equipment(equipment_name) VALUES (?)',(e,))
        periods=[('08:00','08:45'),('08:55','09:40'),('09:50','10:35'),('10:45','11:30'),('11:40','12:25'),('12:45','13:20'),('13:30','14:15'),('14:25','15:10'),('15:20','16:05'),('16:15','17:00')]
        for day in ['Monday','Tuesday','Wednesday','Thursday','Friday']:
            for i,(a,b) in enumerate(periods,1): conn.execute('INSERT INTO time_slots(day_of_week,period_number,start_time,end_time) VALUES (?,?,?,?)',(day,i,a,b))
        if conn.execute('PRAGMA foreign_key_check').fetchall(): raise RuntimeError('Foreign key validation failed')
        conn.commit()
        return LoadSummary(len(bundle.students),len(bundle.lecturers),len(bundle.registrations),len(gids),len(moduleids),len(rooms))
    except Exception:
        conn.rollback(); raise


def faculty_assignment_mismatches(conn) -> list[dict]:
    """Return module/staff assignments whose owning faculties disagree.

    Explicit cross-faculty permissions are treated as valid exceptions when
    the upgraded permission table exists. Legacy database copies can still be
    audited before their runtime migration has run.
    """
    has_permissions = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cross_faculty_teaching_permissions'"
    ).fetchone() is not None
    permission_clause = ""
    if has_permissions:
        permission_clause = """
             AND NOT EXISTS (
                 SELECT 1 FROM cross_faculty_teaching_permissions cfp
                 WHERE cfp.module_id=m.module_id AND cfp.staff_id=s.staff_id
             )
        """
    rows = conn.execute(
        f"""SELECT mo.offering_id,m.module_id,m.module_code,
                  mf.faculty_code AS module_faculty,
                  s.staff_id,s.staff_number,s.first_name,s.last_name,
                  sf.faculty_code AS staff_faculty
           FROM offering_staff os
           JOIN module_offerings mo ON mo.offering_id=os.offering_id
           JOIN modules m ON m.module_id=mo.module_id
           JOIN departments md ON md.department_id=m.department_id
           JOIN faculties mf ON mf.faculty_id=md.faculty_id
           JOIN staff s ON s.staff_id=os.staff_id
           JOIN departments sd ON sd.department_id=s.department_id
           JOIN faculties sf ON sf.faculty_id=sd.faculty_id
           WHERE mf.faculty_id<>sf.faculty_id
           {permission_clause}
           ORDER BY m.module_code,s.staff_number"""
    ).fetchall()
    return [dict(r) for r in rows]
