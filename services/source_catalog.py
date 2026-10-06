from __future__ import annotations
import csv
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class ExamModuleRow:
    source_group_id: str; programme_code: str; module_code: str; module_name: str; source_students: int; faculty_code: str
@dataclass(frozen=True)
class TeachingRoomRow:
    room_code: str; room_name: str; building_code: str; capacity: int; room_type: str; faculty_code: str|None; is_shared: bool
@dataclass(frozen=True)
class ProgrammeMapRow:
    programme_code: str; programme_name: str; faculty_code: str; department_code: str; department_name: str; duration_years: int
@dataclass
class SourceValidationReport:
    errors: list[str]; exam_rows: list[ExamModuleRow]; rooms: list[TeachingRoomRow]

def _read(path):
    with open(path, newline='', encoding='utf-8-sig') as f: return list(csv.DictReader(f))
def load_exam_modules(path):
    return [ExamModuleRow(r['source_group_id'],r['programme_code'],r['module_code'],r['module_name'],int(r['source_students']),r['faculty_code']) for r in _read(path)]
def load_teaching_rooms(path):
    return [TeachingRoomRow(r['room_code'],r['room_name'],r['building_code'],int(r['capacity']),r['room_type'],r['faculty_code'] or None,r['is_shared'].strip() in {'1','true','True'}) for r in _read(path)]
def load_programme_map(path):
    rows=[ProgrammeMapRow(r['programme_code'],r['programme_name'],r['faculty_code'],r['department_code'],r['department_name'],int(r['duration_years'])) for r in _read(path)]
    return {r.programme_code:r for r in rows}
def load_module_year_map(path): return _read(path)
def validate_source_catalogs(data_dir: Path):
    data_dir=Path(data_dir); exam=load_exam_modules(data_dir/'source_exam_modules.csv'); rooms=load_teaching_rooms(data_dir/'source_teaching_rooms.csv'); pmap=load_programme_map(data_dir/'programme_faculty_map.csv'); errors=[]
    for r in exam:
        if r.programme_code not in pmap: errors.append(f'Unmapped programme: {r.programme_code}')
        if r.source_students<=0: errors.append(f'Invalid count: {r.module_code}')
    seen=set()
    for r in rooms:
        if r.room_code in seen: errors.append(f'Duplicate room code: {r.room_code}')
        seen.add(r.room_code)
        if r.capacity<=0: errors.append(f'Invalid room capacity: {r.room_code}')
    return SourceValidationReport(errors,exam,rooms)
