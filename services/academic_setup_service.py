from __future__ import annotations
import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

@dataclass
class AcademicSetupSummary:
    offerings:int; sessions:int; groups_linked:int

def _year_map(data_dir):
    with open(Path(data_dir)/'module_year_map.csv',newline='',encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def build_semester_offerings(conn, semester_id:int, data_dir:Path, module_lecturer:dict[str,str]|None=None):
    rows=_year_map(data_dir)
    by_module=defaultdict(list)
    for r in rows: by_module[r['module_code']].append(r)
    modules=conn.execute('''SELECT m.module_id,m.module_code,m.department_id,f.faculty_code
                            FROM modules m JOIN departments d ON d.department_id=m.department_id
                            JOIN faculties f ON f.faculty_id=d.faculty_id ORDER BY m.module_code''').fetchall()
    fac_staff=defaultdict(list)
    for r in conn.execute('''SELECT s.staff_id,s.staff_number,f.faculty_code FROM staff s
                             JOIN departments d ON d.department_id=s.department_id JOIN faculties f ON f.faculty_id=d.faculty_id
                             ORDER BY s.staff_id'''):
        fac_staff[r['faculty_code']].append((r['staff_id'],r['staff_number']))
    fac_idx=defaultdict(int); offerings=0; sessions=0; links=0
    for m in modules:
        count=conn.execute('SELECT COUNT(DISTINCT student_id) FROM student_module_registrations WHERE module_id=? AND semester_id=?',(m['module_id'],semester_id)).fetchone()[0]
        if not count: continue
        oid=conn.execute('INSERT INTO module_offerings(module_id,semester_id,expected_students) VALUES (?,?,?)',(m['module_id'],semester_id,count)).lastrowid
        offerings+=1
        gids=[r[0] for r in conn.execute('''SELECT DISTINCT sgm.group_id FROM student_module_registrations smr
                    JOIN student_group_members sgm ON sgm.student_id=smr.student_id
                    WHERE smr.module_id=? AND smr.semester_id=? ORDER BY sgm.group_id''',(m['module_id'],semester_id))]
        for gid in gids: conn.execute('INSERT INTO offering_groups(offering_id,group_id) VALUES (?,?)',(oid,gid)); links+=1
        staff_id=None
        if module_lecturer and m['module_code'] in module_lecturer:
            row=conn.execute('''SELECT s.staff_id,f.faculty_code FROM staff s
                                JOIN departments d ON d.department_id=s.department_id
                                JOIN faculties f ON f.faculty_id=d.faculty_id
                                WHERE s.staff_number=?''',(module_lecturer[m['module_code']],)).fetchone()
            if row and row['faculty_code'] != m['faculty_code']:
                raise ValueError(
                    f"Lecturer {module_lecturer[m['module_code']]} belongs to {row['faculty_code']} "
                    f"but module {m['module_code']} belongs to {m['faculty_code']}."
                )
            staff_id=row['staff_id'] if row else None
        if staff_id is None:
            pool=fac_staff[m['faculty_code']]; staff_id=pool[fac_idx[m['faculty_code']]%len(pool)][0]; fac_idx[m['faculty_code']]+=1
        conn.execute('INSERT INTO offering_staff(offering_id,staff_id) VALUES (?,?)',(oid,staff_id))
        spec=by_module.get(m['module_code'],[{}])[0]
        stype=spec.get('session_type','Lecture'); rtype=spec.get('required_room_type','Lecture Room'); spw=int(spec.get('sessions_per_week') or 1)
        practical=stype.lower() in {'practical','lab','laboratory'}
        template=conn.execute('''INSERT INTO session_templates(offering_id,session_type,sessions_per_week,preferred_duration,minimum_duration,required_room_type,can_split_duration)
                                 VALUES (?,?,?,?,?,?,?)''',(oid,stype,spw,2,2 if practical else 1,rtype,0 if practical else 1)).lastrowid
        for n in range(1,spw+1):
            sid=conn.execute('INSERT INTO class_sessions(session_template_id,session_number,duration_slots) VALUES (?,?,2)',(template,n)).lastrowid
            conn.execute("INSERT INTO session_parts(session_id,representation_type,part_number,duration_slots,is_split_part) VALUES (?,'CONTINUOUS',1,2,0)",(sid,)); sessions+=1
    conn.commit(); return AcademicSetupSummary(offerings,sessions,links)
