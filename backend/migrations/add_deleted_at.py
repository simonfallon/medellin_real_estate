import sqlite3

DATABASE_URL = "real_estate.db"


def migrate():
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()

    try:
        cursor.execute("ALTER TABLE properties ADD COLUMN deleted_at DATETIME")
        print("Successfully added deleted_at column.")
        conn.commit()
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("Column deleted_at already exists.")
        else:
            print(f"Error executing migration: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
