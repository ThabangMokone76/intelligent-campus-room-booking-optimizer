from database.db import init_database, DATABASE_PATH

if __name__ == "__main__":
    init_database()
    print(f"Database initialized: {DATABASE_PATH}")
