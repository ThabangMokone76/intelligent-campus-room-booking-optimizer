import json
import os
from functools import wraps
from pathlib import Path

from flask import Flask, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from database.security import check_password_hash

from database.db import connect
from database.bootstrap import ensure_synthetic_ready
from scheduler.engine import active_semester, generate_timetable, NoSolutionError
from scheduler.validator import validate_version
from services.export_service import export_excel, export_pdf, export_personal_excel, export_personal_pdf
from services.import_service import preview_import, commit_import
from services.setup_service import create_offering
from services.dashboard_service import personal_dashboard_context
from services.faculty_context_service import (
    get_programmes, get_years, get_modules, get_lecturers, get_student_groups, get_ranked_rooms,
)
from services.manual_timetable_service import (
    get_editable_entry, save_manual_change, set_entry_lock, suggest_placements,
)
from services.notification_service import (
    list_notifications,
    mark_all_read,
    mark_read,
    unread_count,
)
from services.review_service import (
    add_comment, approve_review, list_reviews_for_user, publish_approved_version,
    request_changes, resolve_comment, resubmit_review, review_detail_for_user, submit_for_review,
)
from services.timetable_view_service import campus_filter_options, campus_timetable_grid
from services.timetable_service import (
    move_part,
    set_part_lock,
    set_version_status,
    timetable_rows,
    timetable_grid,
    visible_version,
)

BASE_DIR = Path(__file__).resolve().parent
EXPORT_DIR = BASE_DIR / "exports"

app = Flask(__name__)
app.secret_key = os.environ.get("TIMETABLE_SECRET_KEY", "change-this-secret-before-production")
ensure_synthetic_ready()


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM users WHERE user_id=? AND is_active=1", (user_id,)).fetchone()
        return None if row is None else dict(row)
    finally:
        conn.close()


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


def role_required(*roles):
    def decorate(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                return redirect(url_for("login"))
            if user["role"] not in roles:
                flash("You do not have permission to open that page.", "error")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapper
    return decorate


@app.context_processor
def inject_globals():
    user = current_user()
    unread = 0
    if user:
        conn = connect()
        try:
            unread = unread_count(conn, user["user_id"])
        finally:
            conn.close()
    return {"current_user": user, "unread_notifications": unread}


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = connect()
        try:
            row = conn.execute("SELECT * FROM users WHERE username=? AND is_active=1", (username,)).fetchone()
        finally:
            conn.close()
        if row and check_password_hash(row["password_hash"], password):
            session.clear()
            session["user_id"] = row["user_id"]
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))




@app.route("/notifications")
@login_required
def notifications_page():
    user = current_user()
    conn = connect()
    try:
        items = list_notifications(conn, user["user_id"])
        return render_template("notifications.html", notifications=items)
    finally:
        conn.close()


@app.post("/notifications/<int:notification_id>/read")
@login_required
def notification_read(notification_id):
    user = current_user()
    conn = connect()
    try:
        mark_read(conn, user["user_id"], notification_id)
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for("notifications_page"))


@app.post("/notifications/read-all")
@login_required
def notifications_read_all():
    user = current_user()
    conn = connect()
    try:
        mark_all_read(conn, user["user_id"])
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for("notifications_page"))


@app.route("/")
@login_required
def dashboard():
    user = current_user()
    if user["role"] == "REVIEWER":
        return redirect(url_for("review_centre"))
    conn = connect()
    try:
        semester = active_semester(conn)
        version = visible_version(conn, semester["semester_id"], user["role"])
        counts = {}
        metrics = None
        personal_context = None
        recent_activity = []
        if user["role"] == "ADMIN":
            counts = {
                "rooms": conn.execute("SELECT COUNT(*) FROM rooms WHERE is_active=1").fetchone()[0],
                "modules": conn.execute("SELECT COUNT(*) FROM modules").fetchone()[0],
                "groups": conn.execute("SELECT COUNT(*) FROM student_groups").fetchone()[0],
                "students": conn.execute("SELECT COUNT(*) FROM students").fetchone()[0],
                "lecturers": conn.execute("SELECT COUNT(*) FROM staff WHERE staff_type='Lecturer'").fetchone()[0],
                "registrations": conn.execute("SELECT COUNT(*) FROM student_module_registrations").fetchone()[0],
                "sessions": conn.execute(
                    """SELECT COUNT(*) FROM class_sessions cs
                       JOIN session_templates st ON st.session_template_id=cs.session_template_id
                       JOIN module_offerings mo ON mo.offering_id=st.offering_id
                       WHERE mo.semester_id=?""",
                    (semester["semester_id"],),
                ).fetchone()[0],
            }
            if version:
                row = conn.execute("SELECT * FROM generation_metrics WHERE version_id=?", (version["version_id"],)).fetchone()
                metrics = None if row is None else dict(row)
            version_activity = [dict(r) for r in conn.execute(
                """SELECT version_id, 'VERSION' AS activity_type,
                          'Timetable V' || version_number || ' · ' || status AS title,
                          COALESCE(published_at, created_at) AS activity_at,
                          0 AS recipients
                   FROM timetable_versions
                   WHERE semester_id=?
                   ORDER BY COALESCE(published_at, created_at) DESC
                   LIMIT 5""",
                (semester["semester_id"],),
            )]
            change_activity = [dict(r) for r in conn.execute(
                """SELECT version_id, notification_type AS activity_type, title,
                          MAX(created_at) AS activity_at,
                          COUNT(DISTINCT recipient_user_id) AS recipients
                   FROM notifications
                   GROUP BY version_id, notification_type, title, message
                   ORDER BY MAX(created_at) DESC
                   LIMIT 5"""
            )]
            recent_activity = sorted(
                version_activity + change_activity,
                key=lambda item: item.get("activity_at") or "",
                reverse=True,
            )[:6]
        else:
            personal_context = personal_dashboard_context(
                conn, version["version_id"] if version else None, user
            )
        return render_template(
            "dashboard.html", semester=semester, version=version, counts=counts,
            metrics=metrics, personal_context=personal_context, recent_activity=recent_activity,
        )
    finally:
        conn.close()


@app.route("/review-centre")
@role_required("ADMIN", "REVIEWER")
def review_centre():
    user = current_user()
    conn = connect()
    try:
        reviews = list_reviews_for_user(conn, user)
        review_id = request.args.get("review_id", type=int)
        if review_id is None and reviews:
            review_id = reviews[0]["review_id"]
        selected_review = None
        review_rows = []
        review_grid = None
        validation = None
        if review_id:
            try:
                selected_review = review_detail_for_user(conn, review_id, user)
                review_rows = timetable_rows(conn, selected_review["version_id"], {"role": "ADMIN"})
                review_grid = campus_timetable_grid(conn, review_rows)
                validation = validate_version(conn, selected_review["version_id"]).as_dict()
            except PermissionError as exc:
                flash(str(exc), "error")
        return render_template(
            "review_centre.html", reviews=reviews, review=selected_review, review_rows=review_rows,
            review_grid=review_grid, validation=validation,
        )
    finally:
        conn.close()


@app.post("/admin/version/<int:version_id>/submit-review")
@role_required("ADMIN")
def admin_submit_review(version_id):
    user = current_user()
    reviewer_id = request.form.get("reviewer_user_id", type=int)
    conn = connect()
    try:
        try:
            review_id = submit_for_review(conn, version_id, user["user_id"], reviewer_id)
            flash("Timetable sent to its assigned reviewer.", "success")
            return redirect(url_for("review_centre", review_id=review_id))
        except (ValueError, PermissionError) as exc:
            flash(str(exc), "error")
    finally:
        conn.close()
    return redirect(url_for("timetable", version_id=version_id))


@app.post("/reviews/<int:review_id>/comment")
@role_required("REVIEWER")
def review_add_comment(review_id):
    user = current_user()
    entry_id = request.form.get("entry_id", type=int)
    conn = connect()
    try:
        try:
            add_comment(conn, review_id, user["user_id"], request.form.get("comment_text", ""), entry_id)
            flash("Review feedback added.", "success")
        except (ValueError, PermissionError) as exc:
            flash(str(exc), "error")
    finally:
        conn.close()
    return redirect(url_for("review_centre", review_id=review_id))


@app.post("/reviews/comments/<int:comment_id>/resolve")
@role_required("ADMIN", "REVIEWER")
def review_resolve_comment(comment_id):
    user = current_user()
    review_id = request.form.get("review_id", type=int)
    conn = connect()
    try:
        try:
            resolve_comment(conn, comment_id, user["user_id"])
            flash("Feedback marked resolved.", "success")
        except (ValueError, PermissionError) as exc:
            flash(str(exc), "error")
    finally:
        conn.close()
    return redirect(url_for("review_centre", review_id=review_id))


@app.post("/reviews/<int:review_id>/request-changes")
@role_required("REVIEWER")
def review_request_changes(review_id):
    user = current_user()
    conn = connect()
    try:
        try:
            request_changes(conn, review_id, user["user_id"], request.form.get("summary", ""))
            flash("Changes requested. The administrator can now edit and resubmit the timetable.", "success")
        except (ValueError, PermissionError) as exc:
            flash(str(exc), "error")
    finally:
        conn.close()
    return redirect(url_for("review_centre", review_id=review_id))


@app.post("/reviews/<int:review_id>/approve")
@role_required("REVIEWER")
def review_approve(review_id):
    user = current_user()
    conn = connect()
    try:
        try:
            approve_review(conn, review_id, user["user_id"], request.form.get("summary"))
            flash("Timetable approved. It is now ready for administrator publication.", "success")
        except (ValueError, PermissionError) as exc:
            flash(str(exc), "error")
    finally:
        conn.close()
    return redirect(url_for("review_centre", review_id=review_id))


@app.post("/admin/version/<int:version_id>/resubmit-review")
@role_required("ADMIN")
def admin_resubmit_review(version_id):
    user = current_user()
    conn = connect()
    try:
        try:
            review_id = resubmit_review(conn, version_id, user["user_id"])
            flash("Corrected timetable resubmitted for review.", "success")
            return redirect(url_for("review_centre", review_id=review_id))
        except (ValueError, PermissionError) as exc:
            flash(str(exc), "error")
    finally:
        conn.close()
    return redirect(url_for("review_centre"))


@app.post("/admin/version/<int:version_id>/publish-approved")
@role_required("ADMIN")
def admin_publish_approved(version_id):
    user = current_user()
    conn = connect()
    try:
        try:
            publish_approved_version(conn, version_id, user["user_id"])
            flash("Approved timetable published. Students and lecturers have been notified.", "success")
        except (ValueError, PermissionError) as exc:
            flash(str(exc), "error")
    finally:
        conn.close()
    return redirect(url_for("timetable", version_id=version_id))


@app.route("/timetable")
@login_required
def timetable():
    user = current_user()
    conn = connect()
    try:
        semester = active_semester(conn)
        version_id = request.args.get("version_id", type=int)
        if version_id:
            version_row = conn.execute("SELECT * FROM timetable_versions WHERE version_id=?", (version_id,)).fetchone()
            version = None if version_row is None else dict(version_row)
            if user["role"] != "ADMIN" and version and version["status"] != "PUBLISHED":
                version = None
        else:
            version = visible_version(conn, semester["semester_id"], user["role"])

        versions = []
        filters = {}
        filter_options = {}
        campus_grid = None
        edit_entry = None
        edit_suggestions = []
        edit_lecturers = []
        edit_rooms = []
        if user["role"] == "ADMIN":
            versions = [dict(r) for r in conn.execute(
                "SELECT * FROM timetable_versions WHERE semester_id=? ORDER BY version_number DESC",
                (semester["semester_id"],),
            )]
            for key in ("faculty_id", "programme_id", "year_level", "module_id", "staff_id", "group_id", "room_id"):
                value = request.args.get(key, type=int)
                if value is not None:
                    filters[key] = value
            day = request.args.get("day", "").strip()
            if day in {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday"}:
                filters["day"] = day
            rows = timetable_rows(conn, version["version_id"], user, filters=filters) if version else []
            campus_grid = campus_timetable_grid(conn, rows)
            if filters.get("room_id"):
                for day_section in campus_grid["days"]:
                    day_section["venues"] = [v for v in day_section["venues"] if v["room_id"] == filters["room_id"]]
            if filters.get("day"):
                campus_grid["days"] = [d for d in campus_grid["days"] if d["day"] == filters["day"]]
            filter_options = campus_filter_options(conn, semester["semester_id"])
            edit_entry_id = request.args.get("edit_entry", type=int)
            if edit_entry_id and version:
                try:
                    edit_entry = get_editable_entry(conn, edit_entry_id, version["version_id"])
                    edit_lecturers = get_lecturers(conn, edit_entry["module_id"])
                    edit_rooms = get_ranked_rooms(conn, edit_entry["module_id"], edit_entry["student_count"])
                    if version["status"] in {"DRAFT", "CHANGES_REQUESTED", "APPROVED"} and not edit_entry["is_locked"]:
                        edit_suggestions = suggest_placements(conn, edit_entry_id, limit=5)
                except ValueError:
                    edit_entry = None
        else:
            rows = timetable_rows(conn, version["version_id"], user) if version else []

        rooms = [dict(r) for r in conn.execute(
            "SELECT room_id, room_name FROM rooms WHERE is_active=1 ORDER BY room_name"
        )]
        template = "timetable.html" if user["role"] == "ADMIN" else "personal_timetable.html"
        return render_template(
            template, semester=semester, version=version, versions=versions, rows=rows,
            grid=timetable_grid(rows), rooms=rooms, campus_grid=campus_grid,
            filters=filters, filter_options=filter_options, edit_entry=edit_entry,
            edit_suggestions=edit_suggestions, edit_lecturers=edit_lecturers, edit_rooms=edit_rooms,
        )
    finally:
        conn.close()


@app.route("/manual-timetabling")
@role_required("ADMIN")
def manual_timetabling():
    conn = connect()
    try:
        semester = active_semester(conn)
        version_id = request.args.get("version_id", type=int)
        if version_id:
            row = conn.execute("SELECT * FROM timetable_versions WHERE version_id=? AND semester_id=?", (version_id, semester["semester_id"])).fetchone()
            version = dict(row) if row else None
        else:
            version = visible_version(conn, semester["semester_id"], "ADMIN")
        versions = [dict(r) for r in conn.execute(
            "SELECT * FROM timetable_versions WHERE semester_id=? ORDER BY version_number DESC",
            (semester["semester_id"],),
        )]
        faculties = [dict(r) for r in conn.execute("SELECT * FROM faculties ORDER BY faculty_name")]
        faculty_id = request.args.get("faculty_id", type=int)
        programme_id = request.args.get("programme_id", type=int)
        year_level = request.args.get("year_level", type=int)
        module_id = request.args.get("module_id", type=int)
        staff_id = request.args.get("staff_id", type=int)
        group_id = request.args.get("group_id", type=int)
        room_id = request.args.get("room_id", type=int)

        programmes = get_programmes(conn, faculty_id) if faculty_id else []
        years = get_years(conn, programme_id) if programme_id else []
        modules = get_modules(conn, programme_id, year_level) if programme_id and year_level else []
        lecturers = get_lecturers(conn, module_id) if module_id else []
        groups = get_student_groups(conn, programme_id, year_level) if programme_id and year_level else []
        ranked_rooms = get_ranked_rooms(conn, module_id, 0) if module_id else []
        faculty = next((f for f in faculties if f["faculty_id"] == faculty_id), None)

        filters = {}
        for key, value in (("faculty_id", faculty_id), ("programme_id", programme_id), ("year_level", year_level),
                           ("module_id", module_id), ("staff_id", staff_id), ("group_id", group_id), ("room_id", room_id)):
            if value is not None:
                filters[key] = value
        rows = timetable_rows(conn, version["version_id"], {"role": "ADMIN"}, filters=filters) if version else []

        selected_entry = None
        suggestions = []
        entry_id = request.args.get("entry_id", type=int)
        if entry_id and version:
            try:
                selected_entry = get_editable_entry(conn, entry_id, version["version_id"])
                if selected_entry["version_status"] in {"DRAFT", "CHANGES_REQUESTED", "APPROVED"} and not selected_entry["is_locked"]:
                    suggestions = suggest_placements(conn, entry_id, limit=5)
            except ValueError:
                selected_entry = None

        return render_template(
            "manual_timetabling.html", semester=semester, version=version, versions=versions, faculties=faculties,
            faculty=faculty, programmes=programmes, years=years, modules=modules, lecturers=lecturers, groups=groups,
            ranked_rooms=ranked_rooms, rows=rows, selected_entry=selected_entry, suggestions=suggestions,
            selected={"faculty_id": faculty_id, "programme_id": programme_id, "year_level": year_level,
                      "module_id": module_id, "staff_id": staff_id, "group_id": group_id, "room_id": room_id},
        )
    finally:
        conn.close()


@app.post("/admin/entry/<int:entry_id>/edit")
@role_required("ADMIN")
def admin_edit_entry(entry_id):
    user = current_user()
    proposal = {
        "day": request.form.get("day", ""),
        "start_period": request.form.get("start_period", type=int),
        "room_id": request.form.get("room_id", type=int),
        "staff_id": request.form.get("staff_id", type=int),
    }
    proposal = {k: v for k, v in proposal.items() if v not in (None, "")}
    conn = connect()
    try:
        try:
            save_manual_change(conn, entry_id, proposal, user["user_id"])
            flash("Class updated successfully. Full hard-constraint validation passed.", "success")
        except (ValueError, PermissionError) as exc:
            flash(str(exc), "error")
    finally:
        conn.close()
    next_url = request.form.get("next", "")
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = url_for("timetable")
    return redirect(next_url)


@app.post("/admin/entry/<int:entry_id>/lock")
@role_required("ADMIN")
def admin_entry_lock(entry_id):
    user = current_user()
    locked = request.form.get("locked") == "1"
    conn = connect()
    try:
        try:
            set_entry_lock(conn, entry_id, locked, user["user_id"])
            flash("Class lock updated.", "success")
        except (ValueError, PermissionError) as exc:
            flash(str(exc), "error")
    finally:
        conn.close()
    next_url = request.form.get("next", "")
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = url_for("timetable")
    return redirect(next_url)


@app.get("/api/context/programmes")
@role_required("ADMIN")
def api_context_programmes():
    faculty_id = request.args.get("faculty_id", type=int)
    if not faculty_id:
        return jsonify([])
    conn = connect()
    try:
        return jsonify(get_programmes(conn, faculty_id))
    finally:
        conn.close()


@app.get("/api/context/years")
@role_required("ADMIN")
def api_context_years():
    programme_id = request.args.get("programme_id", type=int)
    if not programme_id:
        return jsonify([])
    conn = connect()
    try:
        return jsonify(get_years(conn, programme_id))
    finally:
        conn.close()


@app.get("/api/context/modules")
@role_required("ADMIN")
def api_context_modules():
    programme_id = request.args.get("programme_id", type=int)
    year_level = request.args.get("year_level", type=int)
    if not programme_id or not year_level:
        return jsonify([])
    conn = connect()
    try:
        return jsonify(get_modules(conn, programme_id, year_level))
    finally:
        conn.close()


@app.get("/api/context/lecturers")
@role_required("ADMIN")
def api_context_lecturers():
    module_id = request.args.get("module_id", type=int)
    if not module_id:
        return jsonify([])
    conn = connect()
    try:
        return jsonify(get_lecturers(conn, module_id))
    finally:
        conn.close()


@app.get("/api/context/groups")
@role_required("ADMIN")
def api_context_groups():
    programme_id = request.args.get("programme_id", type=int)
    year_level = request.args.get("year_level", type=int)
    if not programme_id or not year_level:
        return jsonify([])
    conn = connect()
    try:
        return jsonify(get_student_groups(conn, programme_id, year_level))
    finally:
        conn.close()


@app.get("/api/context/rooms")
@role_required("ADMIN")
def api_context_rooms():
    module_id = request.args.get("module_id", type=int)
    expected_students = request.args.get("expected_students", default=1, type=int)
    if not module_id:
        return jsonify([])
    conn = connect()
    try:
        rooms = get_ranked_rooms(conn, module_id, max(1, expected_students or 1))
        # equipment inventory is internal data and not JSON-friendly; choices need only these fields
        return jsonify([{k:v for k,v in r.items() if k != "equipment_inventory"} for r in rooms])
    finally:
        conn.close()


@app.route("/admin")
@role_required("ADMIN")
def admin():
    conn = connect()
    try:
        semester = active_semester(conn)
        versions = [dict(r) for r in conn.execute("SELECT * FROM timetable_versions WHERE semester_id=? ORDER BY version_number DESC", (semester["semester_id"],))]
        return render_template("admin.html", semester=semester, versions=versions)
    finally:
        conn.close()


@app.post("/admin/generate")
@role_required("ADMIN")
def admin_generate():
    conn = connect()
    try:
        try:
            result = generate_timetable(conn)
            report = validate_version(conn, result["version_id"])
            conn.execute("UPDATE generation_metrics SET hard_violations=? WHERE version_id=?", (report.total, result["version_id"]))
            conn.commit()
            if report.total:
                flash(f"Draft generated, but validator found {report.total} hard violation(s).", "error")
            else:
                flash(
                    f"Draft version {result['version_number']} generated successfully. "
                    f"Split sessions: {len(result['split_session_ids'])}. Hard violations: 0.",
                    "success",
                )
            return redirect(url_for("timetable", version_id=result["version_id"]))
        except NoSolutionError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin"))
    finally:
        conn.close()


@app.route("/admin/validate/<int:version_id>")
@role_required("ADMIN")
def admin_validate(version_id):
    conn = connect()
    try:
        report = validate_version(conn, version_id)
        conn.execute(
            "INSERT INTO generation_metrics(version_id, hard_violations) VALUES (?, ?) ON CONFLICT(version_id) DO UPDATE SET hard_violations=excluded.hard_violations",
            (version_id, report.total),
        )
        conn.commit()
        return render_template("validation.html", version_id=version_id, report=report.as_dict())
    finally:
        conn.close()


@app.post("/admin/version/<int:version_id>/status")
@role_required("ADMIN")
def admin_status(version_id):
    status = request.form.get("status", "")
    conn = connect()
    try:
        try:
            set_version_status(conn, version_id, status)
            flash(f"Timetable status changed to {status}.", "success")
        except ValueError as exc:
            flash(str(exc), "error")
    finally:
        conn.close()
    return redirect(url_for("timetable", version_id=version_id))


@app.post("/admin/part/<int:part_id>/lock")
@role_required("ADMIN")
def admin_lock(part_id):
    version_id = int(request.form["version_id"])
    locked = request.form.get("locked") == "1"
    conn = connect()
    try:
        set_part_lock(conn, version_id, part_id, locked)
    finally:
        conn.close()
    flash("Part lock updated.", "success")
    return redirect(url_for("timetable", version_id=version_id))


@app.post("/admin/part/<int:part_id>/move")
@role_required("ADMIN")
def admin_move(part_id):
    version_id = int(request.form["version_id"])
    day = request.form["day"]
    period = int(request.form["period"])
    room_value = request.form.get("room_id", "").strip()
    room_id = int(room_value) if room_value else None
    conn = connect()
    try:
        try:
            move_part(conn, version_id, part_id, day, period, room_id)
            flash("Manual move accepted by hard-constraint validation.", "success")
        except ValueError as exc:
            flash(str(exc), "error")
    finally:
        conn.close()
    return redirect(url_for("timetable", version_id=version_id))


@app.route("/admin/data", methods=["GET", "POST"])
@role_required("ADMIN")
def admin_data():
    conn = connect()
    try:
        if request.method == "POST":
            kind = request.form["kind"]
            try:
                if kind == "room":
                    conn.execute(
                        "INSERT INTO rooms(building_id, room_code, room_name, capacity, room_type) VALUES (?, ?, ?, ?, ?)",
                        (int(request.form["building_id"]), request.form["room_code"].strip(), request.form["room_name"].strip(), int(request.form["capacity"]), request.form["room_type"].strip()),
                    )
                elif kind == "module":
                    conn.execute(
                        "INSERT INTO modules(department_id, module_code, module_name, credits) VALUES (?, ?, ?, ?)",
                        (int(request.form["department_id"]), request.form["module_code"].strip(), request.form["module_name"].strip(), int(request.form["credits"])),
                    )
                elif kind == "staff":
                    conn.execute(
                        "INSERT INTO staff(department_id, staff_number, first_name, last_name, email) VALUES (?, ?, ?, ?, ?)",
                        (int(request.form["department_id"]), request.form["staff_number"].strip(), request.form["first_name"].strip(), request.form["last_name"].strip(), request.form["email"].strip()),
                    )
                elif kind == "group":
                    conn.execute(
                        "INSERT INTO student_groups(programme_id, year_level, number_of_students) VALUES (?, ?, ?)",
                        (int(request.form["programme_id"]), int(request.form["year_level"]), int(request.form["number_of_students"])),
                    )
                elif kind == "offering":
                    semester_id = active_semester(conn)["semester_id"]
                    create_offering(
                        conn=conn,
                        module_id=int(request.form["module_id"]),
                        semester_id=semester_id,
                        expected_students=int(request.form["expected_students"]),
                        group_ids=request.form.getlist("group_ids"),
                        staff_ids=request.form.getlist("staff_ids"),
                        session_type=request.form["session_type"],
                        sessions_per_week=int(request.form["sessions_per_week"]),
                        duration_slots=int(request.form["duration_slots"]),
                        required_room_type=request.form["required_room_type"],
                        can_split_duration=request.form.get("can_split_duration") == "1",
                        equipment_ids=request.form.getlist("equipment_ids"),
                    )
                else:
                    raise ValueError("Unknown manual data type.")
                conn.commit()
                flash("Record created.", "success")
            except Exception as exc:
                conn.rollback()
                flash(f"Could not create record: {exc}", "error")
            return redirect(url_for("admin_data"))

        context = {
            "buildings": [dict(r) for r in conn.execute("SELECT * FROM buildings ORDER BY building_name")],
            "departments": [dict(r) for r in conn.execute("SELECT * FROM departments ORDER BY department_name")],
            "programmes": [dict(r) for r in conn.execute("SELECT * FROM programmes ORDER BY programme_name")],
            "rooms": [dict(r) for r in conn.execute("SELECT r.*, b.building_name FROM rooms r JOIN buildings b ON b.building_id=r.building_id ORDER BY r.room_name")],
            "modules": [dict(r) for r in conn.execute("SELECT m.*, d.department_code FROM modules m JOIN departments d ON d.department_id=m.department_id ORDER BY m.module_code")],
            "staff": [dict(r) for r in conn.execute("SELECT s.*, d.department_code FROM staff s JOIN departments d ON d.department_id=s.department_id ORDER BY s.last_name")],
            "groups": [dict(r) for r in conn.execute("SELECT g.*, p.programme_code, p.programme_name FROM student_groups g JOIN programmes p ON p.programme_id=g.programme_id ORDER BY p.programme_code, g.year_level")],
            "equipment": [dict(r) for r in conn.execute("SELECT * FROM equipment ORDER BY equipment_name")],
        }
        return render_template("data.html", **context)
    finally:
        conn.close()


@app.route("/admin/synthetic")
@role_required("ADMIN")
def admin_synthetic():
    conn = connect()
    try:
        stats = {
            "students": conn.execute("SELECT COUNT(*) FROM students").fetchone()[0],
            "lecturers": conn.execute("SELECT COUNT(*) FROM staff WHERE staff_type='Lecturer'").fetchone()[0],
            "registrations": conn.execute("SELECT COUNT(*) FROM student_module_registrations").fetchone()[0],
            "programmes": conn.execute("SELECT COUNT(*) FROM programmes").fetchone()[0],
            "modules": conn.execute("SELECT COUNT(*) FROM modules").fetchone()[0],
            "rooms": conn.execute("SELECT COUNT(*) FROM rooms WHERE is_active=1").fetchone()[0],
        }
        students = [dict(r) for r in conn.execute("""SELECT s.student_number,s.first_name,s.last_name,s.email,p.programme_code,s.year_level,COUNT(smr.module_id) AS module_count
            FROM students s JOIN programmes p ON p.programme_id=s.programme_id
            JOIN student_module_registrations smr ON smr.student_id=s.student_id
            GROUP BY s.student_id ORDER BY module_count DESC, s.student_id LIMIT 12""")]
        lecturers = [dict(r) for r in conn.execute("""SELECT s.staff_number,s.first_name,s.last_name,s.email,f.faculty_code
            FROM staff s JOIN departments d ON d.department_id=s.department_id JOIN faculties f ON f.faculty_id=d.faculty_id
            ORDER BY s.staff_id LIMIT 12""")]
        return render_template("synthetic_data.html", stats=stats, students=students, lecturers=lecturers)
    finally:
        conn.close()

@app.route("/admin/synthetic/credentials")
@role_required("ADMIN")
def admin_synthetic_credentials():
    path = BASE_DIR / "data" / "generated_credentials.csv"
    if not path.exists():
        flash("Credential export has not been generated yet.", "error")
        return redirect(url_for("admin_synthetic"))
    return send_file(path, as_attachment=True)

@app.route("/admin/import", methods=["GET", "POST"])
@role_required("ADMIN")
def admin_import():
    preview = None
    if request.method == "POST" and "file" in request.files:
        dataset = request.form["dataset"]
        uploaded = request.files["file"]
        conn = connect()
        try:
            preview = preview_import(conn, dataset, uploaded.filename, uploaded.read())
        finally:
            conn.close()
    return render_template("import.html", preview=preview, preview_json=json.dumps(preview) if preview else "")


@app.post("/admin/import/commit")
@role_required("ADMIN")
def admin_import_commit():
    preview = json.loads(request.form["preview_json"])
    conn = connect()
    try:
        try:
            count = commit_import(conn, preview)
            flash(f"Imported {count} row(s).", "success")
        except Exception as exc:
            flash(str(exc), "error")
    finally:
        conn.close()
    return redirect(url_for("admin_import"))



@app.route("/my-timetable/export/<fmt>")
@login_required
def my_timetable_export(fmt):
    user = current_user()
    if user["role"] not in {"STUDENT", "LECTURER"}:
        flash("Personal timetable export is available to students and lecturers.", "error")
        return redirect(url_for("timetable"))
    conn = connect()
    try:
        semester = active_semester(conn)
        version = visible_version(conn, semester["semester_id"], user["role"])
        if not version:
            flash("No published timetable is available yet.", "error")
            return redirect(url_for("timetable"))
        if fmt == "xlsx":
            path = export_personal_excel(conn, version["version_id"], user, EXPORT_DIR / f"my_timetable_{user['user_id']}.xlsx")
        elif fmt == "pdf":
            path = export_personal_pdf(conn, version["version_id"], user, EXPORT_DIR / f"my_timetable_{user['user_id']}.pdf")
        else:
            flash("Unsupported export format.", "error")
            return redirect(url_for("timetable"))
    finally:
        conn.close()
    return send_file(path, as_attachment=True)

@app.route("/admin/export/<int:version_id>/<fmt>")
@role_required("ADMIN")
def admin_export(version_id, fmt):
    conn = connect()
    try:
        if fmt == "xlsx":
            path = export_excel(conn, version_id, EXPORT_DIR / f"timetable_v{version_id}.xlsx")
        elif fmt == "pdf":
            path = export_pdf(conn, version_id, EXPORT_DIR / f"timetable_v{version_id}.pdf")
        else:
            flash("Unsupported export format.", "error")
            return redirect(url_for("timetable", version_id=version_id))
    finally:
        conn.close()
    return send_file(path, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
