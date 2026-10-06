from __future__ import annotations
import argparse, shutil, time
from pathlib import Path
from database.db import DATABASE_PATH, connect, init_database
from database.migrations import apply_runtime_migrations
from services.synthetic_population import generate_population
from services.synthetic_load_service import load_population, write_generated_csvs
from services.academic_setup_service import build_semester_offerings
from services.source_catalog import validate_source_catalogs

ROOT=Path(__file__).resolve().parent.parent; DATA=ROOT/'data'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--dry-run',action='store_true'); ap.add_argument('--generate',action='store_true'); ap.add_argument('--load',action='store_true'); ap.add_argument('--reset',action='store_true')
    args=ap.parse_args()
    rep=validate_source_catalogs(DATA)
    if rep.errors: raise SystemExit('Source validation failed: '+'; '.join(rep.errors))
    bundle=generate_population(DATA)
    if args.dry_run or not (args.generate or args.load or args.reset):
        print(f'Source relationships: {len(rep.exam_rows)}'); print(f'Teaching rooms: {len(rep.rooms)}'); print(f'Synthetic students: {len(bundle.students)}'); print(f'Synthetic lecturers: {len(bundle.lecturers)}'); print(f'Registrations: {len(bundle.registrations)}')
    if args.generate or args.load or args.reset:
        paths=write_generated_csvs(bundle,DATA); print('Generated CSVs:',', '.join(paths))
    if args.load or args.reset:
        if DATABASE_PATH.exists():
            backup=DATABASE_PATH.with_name(f'campus_timetable_before_synthetic_{int(time.time())}.db'); shutil.copy2(DATABASE_PATH,backup); print('Backup:',backup.name); DATABASE_PATH.unlink()
        init_database(); conn=connect()
        try:
            summary=load_population(conn,bundle,DATA)
            semester=conn.execute("SELECT semester_id FROM semesters WHERE status='ACTIVE'").fetchone()[0]
            setup=build_semester_offerings(conn,semester,DATA,bundle.module_lecturer)
            apply_runtime_migrations(conn)
            print('Loaded:',summary); print('Offerings:',setup.offerings,'Sessions:',setup.sessions)
        finally: conn.close()

if __name__=='__main__': main()
