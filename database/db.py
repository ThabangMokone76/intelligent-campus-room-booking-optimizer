import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "database" / "campus_timetable.db"
SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"


def connect(path=None):
    db_path = Path(path) if path else DATABASE_PATH
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_database(path=None):
    connection = connect(path)
    try:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        connection.commit()
    finally:
        connection.close()


def scalar(connection, sql, params=()):
    row = connection.execute(sql, params).fetchone()
    return None if row is None else row[0]
