from pathlib import Path
import shutil

from database.db import DATABASE_PATH, connect, init_database
from database.seed_demo import seed
from database.upgrade_existing import ensure_users
from database.migrations import apply_runtime_migrations

SEED_DATABASE_PATH = Path(__file__).resolve().parent / "synthetic_seed.db"


def _counts(path=None):
    conn = connect(path)
    try:
        return {
            "students": conn.execute("SELECT COUNT(*) FROM students").fetchone()[0],
            "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "registrations": conn.execute("SELECT COUNT(*) FROM student_module_registrations").fetchone()[0],
        }
    finally:
        conn.close()


def ensure_synthetic_ready(path=None):
    """Ensure the approved synthetic demo is available and login-ready.

    Normal startup is idempotent. If the target database is missing or empty,
    restore the bundled verified synthetic seed database instead of regenerating
    thousands of password hashes on every fresh extraction.
    """
    target = Path(path) if path else DATABASE_PATH
    init_database(target)
    counts = _counts(target)
    if counts["students"] and counts["users"] and counts["registrations"]:
        conn = connect(target)
        try:
            apply_runtime_migrations(conn)
            conn.commit()
        finally:
            conn.close()
        return counts

    if not SEED_DATABASE_PATH.exists():
        raise RuntimeError("Synthetic seed database is missing. Rebuild it with database.seed_synthetic.")

    # Close all handles before replacing the SQLite file.
    shutil.copy2(SEED_DATABASE_PATH, target)
    init_database(target)
    counts = _counts(target)
    if not (counts["students"] and counts["users"] and counts["registrations"]):
        raise RuntimeError("Synthetic seed database did not contain the required population.")
    conn = connect(target)
    try:
        apply_runtime_migrations(conn)
        conn.commit()
    finally:
        conn.close()
    return counts


def ensure_demo_ready(path=None):
    """Backward-compatible small-demo bootstrap retained for legacy tests/tools."""
    init_database(path)
    conn = connect(path)
    try:
        has_data = conn.execute("SELECT COUNT(*) FROM faculties").fetchone()[0] > 0
        has_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0
    finally:
        conn.close()

    if not has_data:
        seed(path)
        conn = connect(path)
        try:
            apply_runtime_migrations(conn)
            conn.commit()
        finally:
            conn.close()
        return
    if not has_users:
        conn = connect(path)
        try:
            ensure_users(conn)
            conn.commit()
        finally:
            conn.close()

    conn = connect(path)
    try:
        apply_runtime_migrations(conn)
        conn.commit()
    finally:
        conn.close()
