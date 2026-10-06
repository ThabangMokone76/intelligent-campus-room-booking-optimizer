from pathlib import Path
import tempfile

from database.bootstrap import ensure_synthetic_ready
from database.db import connect
from database.security import check_password_hash
from scheduler.validator import validate_version
from services.export_service import export_excel, export_pdf
from services.source_catalog import validate_source_catalogs
from services.synthetic_load_service import faculty_assignment_mismatches
from services.faculty_style_service import get_faculty_style
from services.timetable_service import timetable_rows

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


def fail(message):
    print("FAIL:", message)
    raise SystemExit(1)


def main():
    print("=== SYNTHETIC MERGED FINAL CHECK ===")
    source_report = validate_source_catalogs(DATA)
    if source_report.errors:
        fail("source catalogs: " + "; ".join(source_report.errors))

    ensure_synthetic_ready()
    conn = connect()
    try:
        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        if fk:
            fail(f"foreign key errors: {fk[:5]}")

        students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        lecturers = conn.execute("SELECT COUNT(*) FROM staff WHERE staff_type='Lecturer'").fetchone()[0]
        registrations = conn.execute("SELECT COUNT(*) FROM student_module_registrations").fetchone()[0]
        rooms = conn.execute("SELECT COUNT(*) FROM rooms WHERE is_active=1").fetchone()[0]
        modules = conn.execute("SELECT COUNT(*) FROM modules").fetchone()[0]
        offerings = conn.execute("SELECT COUNT(*) FROM module_offerings").fetchone()[0]

        if not 3000 <= students <= 5000:
            fail(f"student population {students} outside approved range")
        if lecturers < 1 or registrations < 1 or rooms < 1 or modules < 1:
            fail("required synthetic academic data is missing")

        faculty_mismatches = faculty_assignment_mismatches(conn)
        if faculty_mismatches:
            sample = faculty_mismatches[0]
            fail(
                f"lecturer faculty mismatch: {sample['module_code']} is {sample['module_faculty']} "
                f"but {sample['staff_number']} is {sample['staff_faculty']}"
            )

        expected_colours = {"NAS": "#059669", "EMS": "#7C3AED", "EDU": "#F6B221", "HUM": "#D97706"}
        actual_colours = {r["faculty_code"]: r["colour_hex"] for r in conn.execute("SELECT faculty_code,colour_hex FROM faculties")}
        for code, colour in expected_colours.items():
            if code in actual_colours and actual_colours[code].upper() != colour:
                fail(f"faculty colour mismatch for {code}: {actual_colours[code]} != {colour}")
            if get_faculty_style(code)["background"].upper() != colour:
                fail(f"faculty style service mismatch for {code}")

        branding_files = [ROOT / "static" / "images" / "spu-logo.png", ROOT / "static" / "images" / "spu-crest.png"]
        if not all(path.exists() and path.stat().st_size > 0 for path in branding_files):
            fail("SPU branding assets are missing")
        base_source = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
        if "spu-crest.png" not in base_source or "Sol Plaatje University" not in base_source:
            fail("SPU branded application shell is missing")

        required_tables = {"reviewer_faculties", "timetable_reviews", "review_comments", "cross_faculty_teaching_permissions"}
        existing_tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not required_tables.issubset(existing_tables):
            fail("review workflow schema is incomplete")
        legacy_statuses = conn.execute("SELECT COUNT(*) FROM timetable_versions WHERE status='REVIEW'").fetchone()[0]
        if legacy_statuses:
            fail("legacy REVIEW timetable status still exists")
        if not (ROOT / "templates" / "review_centre.html").exists() or not (ROOT / "templates" / "manual_timetabling.html").exists():
            fail("manual timetabling or Review Centre template is missing")

        admin = conn.execute("SELECT * FROM users WHERE username='admin' AND role='ADMIN'").fetchone()
        if not admin or not check_password_hash(admin['password_hash'], 'admin123'):
            fail("admin / admin123 authentication check failed")

        reviewer = conn.execute("SELECT * FROM users WHERE username='reviewer' AND role='REVIEWER'").fetchone()
        if not reviewer or not check_password_hash(reviewer['password_hash'], 'reviewer123'):
            fail("reviewer / reviewer123 authentication check failed")

        student = conn.execute(
            """SELECT u.*,s.student_number,s.first_name,s.last_name
               FROM users u JOIN students s ON s.student_id=u.student_id
               WHERE u.role='STUDENT' ORDER BY CASE WHEN s.student_number='202611367' THEN 0 ELSE 1 END,u.user_id LIMIT 1"""
        ).fetchone()
        if not student or not check_password_hash(student['password_hash'], 'Tnu@' + student['student_number'][-4:]):
            fail("sample student authentication check failed")

        lecturer = conn.execute(
            """SELECT u.*,st.staff_number,st.first_name,st.last_name
               FROM users u JOIN staff st ON st.staff_id=u.staff_id
               WHERE u.role='LECTURER' ORDER BY CASE WHEN st.staff_number='TNU00001' THEN 0 ELSE 1 END,u.user_id LIMIT 1"""
        ).fetchone()
        if not lecturer or not check_password_hash(lecturer['password_hash'], 'Tnu@' + lecturer['staff_number'][-4:]):
            fail("sample lecturer authentication check failed")

        version = conn.execute(
            "SELECT * FROM timetable_versions WHERE status='PUBLISHED' ORDER BY version_number DESC LIMIT 1"
        ).fetchone()
        if not version:
            fail("no PUBLISHED daily teaching timetable")

        validation = validate_version(conn, version['version_id'])
        if validation.total:
            fail(f"published timetable has {validation.total} hard violation(s)")

        student_rows = timetable_rows(conn, version['version_id'], dict(student))
        lecturer_rows = timetable_rows(conn, version['version_id'], dict(lecturer))
        if not student_rows:
            fail("sample student has no personal timetable rows")
        if not lecturer_rows:
            fail("sample lecturer has no personal timetable rows")

        for row in student_rows:
            assigned = conn.execute(
                "SELECT 1 FROM section_student_assignments WHERE section_id=? AND student_id=?",
                (row['section_id'], student['student_id']),
            ).fetchone()
            if not assigned:
                fail("student personal timetable contains another student's section")

        for row in lecturer_rows:
            assigned = conn.execute(
                "SELECT 1 FROM offering_staff WHERE offering_id=? AND staff_id=?",
                (row['offering_id'], lecturer['staff_id']),
            ).fetchone()
            if not assigned:
                fail("lecturer personal timetable contains an unassigned offering")

        scheduled_parts = conn.execute(
            "SELECT COUNT(DISTINCT part_id) FROM timetable_entries WHERE version_id=?",
            (version['version_id'],),
        ).fetchone()[0]

        with tempfile.TemporaryDirectory() as tmp:
            xlsx = export_excel(conn, version['version_id'], Path(tmp) / 'check.xlsx')
            pdf = export_pdf(conn, version['version_id'], Path(tmp) / 'check.pdf')
            if not Path(xlsx).exists() or Path(xlsx).stat().st_size == 0:
                fail("XLSX export check failed")
            if not Path(pdf).exists() or Path(pdf).stat().st_size == 0:
                fail("PDF export check failed")

        print(f"Synthetic students: {students}")
        print(f"Synthetic lecturers: {lecturers}")
        print(f"Registrations: {registrations}")
        print(f"Teaching rooms: {rooms}")
        print(f"Modules: {modules}")
        print(f"Offerings: {offerings}")
        print(f"Scheduled parts: {scheduled_parts}")
        print("Hard violations: 0")
        print("Lecturer/faculty assignment audit: PASS")
        print("Canonical faculty colours: PASS")
        print("SPU branding: PASS")
        print("Review workflow: PASS")
        print(f"Admin login: PASS (admin / admin123)")
        print("Reviewer login: PASS (reviewer / reviewer123)")
        print(f"Student login: PASS ({student['student_number']} / Tnu@{student['student_number'][-4:]})")
        print(f"Lecturer login: PASS ({lecturer['staff_number']} / Tnu@{lecturer['staff_number'][-4:]})")
        print("Personal timetable visibility: PASS")
        print("PDF/XLSX exports: PASS")
        print("FINAL CHECK: PASS")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
