from __future__ import annotations

import hashlib
import json

from scheduler.validator import validate_version
from services.timetable_service import set_version_status


def _user(conn, user_id: int) -> dict:
    row = conn.execute("SELECT * FROM users WHERE user_id=? AND is_active=1", (user_id,)).fetchone()
    if row is None:
        raise PermissionError("Active user account required.")
    return dict(row)


def _require_role(conn, user_id: int, role: str) -> dict:
    user = _user(conn, user_id)
    if user["role"] != role:
        raise PermissionError(f"Only a {role.lower()} can perform this review action.")
    return user


def _version(conn, version_id: int) -> dict:
    row = conn.execute("SELECT * FROM timetable_versions WHERE version_id=?", (version_id,)).fetchone()
    if row is None:
        raise ValueError("Timetable version not found.")
    return dict(row)


def _review(conn, review_id: int) -> dict:
    row = conn.execute("SELECT * FROM timetable_reviews WHERE review_id=?", (review_id,)).fetchone()
    if row is None:
        raise ValueError("Timetable review not found.")
    return dict(row)


def version_faculty_ids(conn, version_id: int) -> set[int]:
    rows = conn.execute(
        """SELECT DISTINCT f.faculty_id
           FROM timetable_entries te
           JOIN session_parts sp ON sp.part_id=te.part_id
           JOIN class_sessions cs ON cs.session_id=sp.session_id
           JOIN session_templates st ON st.session_template_id=cs.session_template_id
           JOIN module_offerings mo ON mo.offering_id=st.offering_id
           JOIN modules m ON m.module_id=mo.module_id
           JOIN departments d ON d.department_id=m.department_id
           JOIN faculties f ON f.faculty_id=d.faculty_id
           WHERE te.version_id=?""",
        (version_id,),
    ).fetchall()
    return {int(row[0]) for row in rows}


def reviewer_can_access_version(conn, reviewer_user_id: int, version_id: int) -> bool:
    user = _user(conn, reviewer_user_id)
    if user["role"] != "REVIEWER":
        return False
    scope = {int(row[0]) for row in conn.execute("SELECT faculty_id FROM reviewer_faculties WHERE user_id=?", (reviewer_user_id,))}
    if not scope:
        return True
    faculties = version_faculty_ids(conn, version_id)
    return bool(faculties) and faculties.issubset(scope)


def _eligible_reviewer(conn, version_id: int, reviewer_user_id: int | None) -> int:
    if reviewer_user_id is not None:
        _require_role(conn, reviewer_user_id, "REVIEWER")
        if not reviewer_can_access_version(conn, reviewer_user_id, version_id):
            raise PermissionError("Reviewer faculty scope does not cover this timetable version.")
        return int(reviewer_user_id)
    for row in conn.execute("SELECT user_id FROM users WHERE role='REVIEWER' AND is_active=1 ORDER BY user_id"):
        if reviewer_can_access_version(conn, row[0], version_id):
            return int(row[0])
    raise ValueError("No eligible timetable reviewer is configured. Add or assign a reviewer first.")


def timetable_fingerprint(conn, version_id: int) -> str:
    entries = [
        tuple(row)
        for row in conn.execute(
            """SELECT te.part_id,te.section_id,te.room_id,te.slot_id,te.duration_slots,te.is_locked
               FROM timetable_entries te WHERE te.version_id=?
               ORDER BY te.part_id,te.section_id,te.entry_id""",
            (version_id,),
        )
    ]
    offering_ids = [
        row[0]
        for row in conn.execute(
            """SELECT DISTINCT st.offering_id
               FROM timetable_entries te
               JOIN session_parts sp ON sp.part_id=te.part_id
               JOIN class_sessions cs ON cs.session_id=sp.session_id
               JOIN session_templates st ON st.session_template_id=cs.session_template_id
               WHERE te.version_id=? ORDER BY st.offering_id""",
            (version_id,),
        )
    ]
    staff = []
    for offering_id in offering_ids:
        staff.extend(
            (int(offering_id), int(row[0]), str(row[1]))
            for row in conn.execute(
                "SELECT staff_id,role FROM offering_staff WHERE offering_id=? ORDER BY staff_id,role",
                (offering_id,),
            )
        )
    payload = json.dumps({"entries": entries, "staff": staff}, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def submit_for_review(conn, version_id: int, admin_user_id: int, reviewer_user_id: int | None = None) -> int:
    _require_role(conn, admin_user_id, "ADMIN")
    version = _version(conn, version_id)
    if version["status"] not in {"DRAFT", "CHANGES_REQUESTED"}:
        raise ValueError("Only a DRAFT or CHANGES_REQUESTED timetable can be submitted for review.")
    report = validate_version(conn, version_id)
    if report.total:
        raise ValueError(f"Cannot submit for review: {report.total} hard violation(s) must be fixed first.")
    reviewer_id = _eligible_reviewer(conn, version_id, reviewer_user_id)
    try:
        review_id = conn.execute(
            """INSERT INTO timetable_reviews(version_id,submitted_by_user_id,assigned_reviewer_user_id,status)
               VALUES (?,?,?,'IN_REVIEW')""",
            (version_id, admin_user_id, reviewer_id),
        ).lastrowid
        conn.execute("UPDATE timetable_versions SET status='IN_REVIEW',published_at=NULL WHERE version_id=?", (version_id,))
        conn.commit()
        return int(review_id)
    except Exception:
        conn.rollback()
        raise


def _require_assigned_reviewer(conn, review: dict, reviewer_user_id: int) -> None:
    _require_role(conn, reviewer_user_id, "REVIEWER")
    if review["assigned_reviewer_user_id"] != reviewer_user_id:
        raise PermissionError("This review is assigned to another reviewer.")
    if not reviewer_can_access_version(conn, reviewer_user_id, review["version_id"]):
        raise PermissionError("Reviewer faculty scope does not cover this timetable version.")


def add_comment(conn, review_id: int, author_user_id: int, text: str, entry_id: int | None = None) -> int:
    review = _review(conn, review_id)
    _require_assigned_reviewer(conn, review, author_user_id)
    text = (text or "").strip()
    if not text:
        raise ValueError("Feedback comment cannot be empty.")
    if entry_id is not None:
        row = conn.execute(
            "SELECT 1 FROM timetable_entries WHERE entry_id=? AND version_id=?", (entry_id, review["version_id"])
        ).fetchone()
        if row is None:
            raise ValueError("Class comment must target an entry in the reviewed timetable version.")
    comment_id = conn.execute(
        "INSERT INTO review_comments(review_id,entry_id,author_user_id,comment_text) VALUES (?,?,?,?)",
        (review_id, entry_id, author_user_id, text),
    ).lastrowid
    conn.commit()
    return int(comment_id)


def resolve_comment(conn, comment_id: int, user_id: int) -> None:
    user = _user(conn, user_id)
    row = conn.execute(
        """SELECT rc.*,tr.assigned_reviewer_user_id FROM review_comments rc
           JOIN timetable_reviews tr ON tr.review_id=rc.review_id WHERE rc.comment_id=?""",
        (comment_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Review comment not found.")
    if user["role"] == "REVIEWER" and row["assigned_reviewer_user_id"] != user_id:
        raise PermissionError("Only the assigned reviewer or an administrator can resolve this comment.")
    if user["role"] not in {"ADMIN", "REVIEWER"}:
        raise PermissionError("Only an administrator or reviewer can resolve review feedback.")
    conn.execute(
        "UPDATE review_comments SET is_resolved=1,resolved_at=CURRENT_TIMESTAMP,resolved_by_user_id=? WHERE comment_id=?",
        (user_id, comment_id),
    )
    conn.commit()


def request_changes(conn, review_id: int, reviewer_user_id: int, summary: str) -> None:
    review = _review(conn, review_id)
    _require_assigned_reviewer(conn, review, reviewer_user_id)
    if review["status"] != "IN_REVIEW":
        raise ValueError("Only an IN_REVIEW timetable can have changes requested.")
    summary = (summary or "").strip()
    if not summary:
        raise ValueError("A change-request summary is required.")
    try:
        conn.execute(
            "UPDATE timetable_reviews SET status='CHANGES_REQUESTED',decided_at=CURRENT_TIMESTAMP,decision_summary=? WHERE review_id=?",
            (summary, review_id),
        )
        conn.execute("UPDATE timetable_versions SET status='CHANGES_REQUESTED' WHERE version_id=?", (review["version_id"],))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def approve_review(conn, review_id: int, reviewer_user_id: int, summary: str | None = None) -> None:
    review = _review(conn, review_id)
    _require_assigned_reviewer(conn, review, reviewer_user_id)
    if review["status"] != "IN_REVIEW":
        raise ValueError("Only an IN_REVIEW timetable can be approved.")
    unresolved = conn.execute(
        "SELECT COUNT(*) FROM review_comments WHERE review_id=? AND is_resolved=0", (review_id,)
    ).fetchone()[0]
    if unresolved:
        raise ValueError(f"Cannot approve while {unresolved} unresolved feedback comment(s) remain.")
    report = validate_version(conn, review["version_id"])
    if report.total:
        raise ValueError(f"Cannot approve: validator reports {report.total} hard violation(s).")
    fingerprint = timetable_fingerprint(conn, review["version_id"])
    try:
        conn.execute(
            """UPDATE timetable_reviews
               SET status='APPROVED',decided_at=CURRENT_TIMESTAMP,decision_summary=?,approved_fingerprint=?
               WHERE review_id=?""",
            ((summary or "").strip() or None, fingerprint, review_id),
        )
        conn.execute("UPDATE timetable_versions SET status='APPROVED' WHERE version_id=?", (review["version_id"],))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def resubmit_review(conn, version_id: int, admin_user_id: int) -> int:
    _require_role(conn, admin_user_id, "ADMIN")
    version = _version(conn, version_id)
    if version["status"] != "CHANGES_REQUESTED":
        raise ValueError("Only a CHANGES_REQUESTED timetable can be resubmitted.")
    previous = conn.execute(
        "SELECT * FROM timetable_reviews WHERE version_id=? ORDER BY review_id DESC LIMIT 1", (version_id,)
    ).fetchone()
    if previous is None:
        raise ValueError("No previous review exists for this timetable.")
    return submit_for_review(conn, version_id, admin_user_id, previous["assigned_reviewer_user_id"])


def can_publish(conn, version_id: int) -> tuple[bool, list[str]]:
    reasons = []
    version = _version(conn, version_id)
    if version["status"] != "APPROVED":
        reasons.append("Timetable must be APPROVED before publication.")
    review = conn.execute(
        "SELECT * FROM timetable_reviews WHERE version_id=? ORDER BY review_id DESC LIMIT 1", (version_id,)
    ).fetchone()
    if review is None or review["status"] != "APPROVED":
        reasons.append("Latest timetable review is not approved.")
    elif not review["approved_fingerprint"] or review["approved_fingerprint"] != timetable_fingerprint(conn, version_id):
        reasons.append("Timetable content changed after reviewer approval; submit it for review again.")
    report = validate_version(conn, version_id)
    if report.total:
        reasons.append(f"Validator reports {report.total} hard violation(s).")
    return (not reasons, reasons)


def publish_approved_version(conn, version_id: int, admin_user_id: int) -> None:
    _require_role(conn, admin_user_id, "ADMIN")
    allowed, reasons = can_publish(conn, version_id)
    if not allowed:
        raise ValueError("Cannot publish: " + " ".join(reasons))
    set_version_status(conn, version_id, "PUBLISHED")


def list_reviews_for_user(conn, user: dict) -> list[dict]:
    role = user.get("role")
    params = []
    where = ""
    if role == "REVIEWER":
        where = "WHERE tr.assigned_reviewer_user_id=?"
        params.append(user["user_id"])
    elif role != "ADMIN":
        return []
    rows = conn.execute(
        f"""SELECT tr.*,tv.version_number,tv.status AS version_status,s.academic_year,s.semester_number,
                   submitter.username AS submitted_by,reviewer.username AS reviewer_username,
                   (SELECT COUNT(*) FROM review_comments rc WHERE rc.review_id=tr.review_id AND rc.is_resolved=0) AS unresolved_comments
            FROM timetable_reviews tr
            JOIN timetable_versions tv ON tv.version_id=tr.version_id
            JOIN semesters s ON s.semester_id=tv.semester_id
            JOIN users submitter ON submitter.user_id=tr.submitted_by_user_id
            LEFT JOIN users reviewer ON reviewer.user_id=tr.assigned_reviewer_user_id
            {where}
            ORDER BY tr.review_id DESC""",
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def review_detail_for_user(conn, review_id: int, user: dict) -> dict:
    review = _review(conn, review_id)
    if user.get("role") == "REVIEWER":
        if review["assigned_reviewer_user_id"] != user.get("user_id") or not reviewer_can_access_version(conn, user["user_id"], review["version_id"]):
            raise PermissionError("This review is not available to your reviewer account.")
    elif user.get("role") != "ADMIN":
        raise PermissionError("Review Centre is available only to administrators and reviewers.")
    details = conn.execute(
        """SELECT tr.*,tv.version_number,tv.status AS version_status,s.academic_year,s.semester_number,
                  submitter.username AS submitted_by,reviewer.username AS reviewer_username
           FROM timetable_reviews tr
           JOIN timetable_versions tv ON tv.version_id=tr.version_id
           JOIN semesters s ON s.semester_id=tv.semester_id
           JOIN users submitter ON submitter.user_id=tr.submitted_by_user_id
           LEFT JOIN users reviewer ON reviewer.user_id=tr.assigned_reviewer_user_id
           WHERE tr.review_id=?""",
        (review_id,),
    ).fetchone()
    comments = conn.execute(
        """SELECT rc.*,u.username AS author_username,
                  m.module_code,ts.day_of_week,ts.period_number,r.room_name
           FROM review_comments rc
           JOIN users u ON u.user_id=rc.author_user_id
           LEFT JOIN timetable_entries te ON te.entry_id=rc.entry_id
           LEFT JOIN time_slots ts ON ts.slot_id=te.slot_id
           LEFT JOIN rooms r ON r.room_id=te.room_id
           LEFT JOIN session_parts sp ON sp.part_id=te.part_id
           LEFT JOIN class_sessions cs ON cs.session_id=sp.session_id
           LEFT JOIN session_templates st ON st.session_template_id=cs.session_template_id
           LEFT JOIN module_offerings mo ON mo.offering_id=st.offering_id
           LEFT JOIN modules m ON m.module_id=mo.module_id
           WHERE rc.review_id=? ORDER BY rc.is_resolved,rc.created_at,rc.comment_id""",
        (review_id,),
    ).fetchall()
    item = dict(details)
    item["comments"] = [dict(row) for row in comments]
    item["unresolved_comments"] = sum(1 for row in item["comments"] if not row["is_resolved"])
    return item
