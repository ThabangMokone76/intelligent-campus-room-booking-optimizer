from database.db import connect
from scheduler.engine import generate_timetable
from scheduler.validator import validate_version

if __name__ == "__main__":
    conn = connect()
    try:
        result = generate_timetable(conn)
        report = validate_version(conn, result["version_id"])
        conn.execute(
            "UPDATE generation_metrics SET hard_violations=? WHERE version_id=?",
            (report.total, result["version_id"]),
        )
        conn.commit()
        print("Generation complete")
        print(result)
        print(f"TOTAL HARD VIOLATIONS: {report.total}")
        if report.total:
            for item in report.items:
                print(f"- [{item['category']}] {item['message']}")
        else:
            print("VALID TIMETABLE")
    finally:
        conn.close()
