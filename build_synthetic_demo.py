from __future__ import annotations
import subprocess, sys
from pathlib import Path
from database.db import connect
from scheduler.engine import generate_timetable
from scheduler.validator import validate_version
from services.timetable_service import set_version_status
from services.export_service import export_excel, export_pdf

ROOT=Path(__file__).resolve().parent

def main():
    print('1/5 Rebuilding synthetic undergraduate data...')
    subprocess.run([sys.executable,'-m','database.seed_synthetic','--reset'],cwd=ROOT,check=True)
    print('2/5 Generating daily timetable...')
    c=connect()
    try:
        result=generate_timetable(c)
        print('3/5 Validating hard constraints...')
        report=validate_version(c,result['version_id'])
        if report.total:
            raise SystemExit(f'Validation failed with {report.total} hard violation(s): {report.items[:5]}')
        print('4/5 Publishing valid timetable...')
        set_version_status(c,result['version_id'],'REVIEW'); set_version_status(c,result['version_id'],'PUBLISHED')
        print('5/5 Creating PDF and Excel exports...')
        export_excel(c,result['version_id'],ROOT/'exports'/'final_synthetic_timetable.xlsx')
        export_pdf(c,result['version_id'],ROOT/'exports'/'final_synthetic_timetable.pdf')
        students=c.execute('''SELECT s.student_number,s.first_name,s.last_name,p.programme_code,COUNT(smr.module_id)n
            FROM students s JOIN programmes p ON p.programme_id=s.programme_id
            JOIN student_module_registrations smr ON smr.student_id=s.student_id
            GROUP BY s.student_id ORDER BY n DESC LIMIT 4''').fetchall()
        lecturer=c.execute("SELECT staff_number,first_name,last_name FROM staff ORDER BY staff_id LIMIT 1").fetchone()
        print('\nBUILD COMPLETE')
        print(f"Students: {c.execute('SELECT COUNT(*) FROM students').fetchone()[0]}")
        print(f"Lecturers: {c.execute('SELECT COUNT(*) FROM staff').fetchone()[0]}")
        print(f"Registrations: {c.execute('SELECT COUNT(*) FROM student_module_registrations').fetchone()[0]}")
        print(f"Scheduled parts: {result['scheduled_parts']}")
        print('Hard violations: 0')
        print('\nAdmin: admin / admin123')
        for s in students:
            print(f"Student: {s['student_number']} / Tnu@{s['student_number'][-4:]} ({s['programme_code']})")
        print(f"Lecturer: {lecturer['staff_number']} / Tnu@{lecturer['staff_number'][-4:]}")
        print('\nRun: .\\.venv\\Scripts\\python.exe app.py')
        print('Open: http://127.0.0.1:5000/login')
    finally:
        c.close()

if __name__=='__main__': main()
