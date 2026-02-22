# migrate_db.py
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'app.db')

def upgrade():
    print(f"Applying database schema upgrades to {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. 尝试在 user 表添加 email 字段
        cursor.execute("ALTER TABLE user ADD COLUMN email VARCHAR(120)")
        cursor.execute("CREATE UNIQUE INDEX ix_user_email ON user (email)")
        print("Success: Added 'email' column to 'user' table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("Warning: Column 'email' already exists in 'user' table.")
        else:
            print(f"Error adding column to user: {e}")

    try:
        # 2. 创建 verification_code 表
        cursor.execute("""
            CREATE TABLE verification_code (
                id INTEGER PRIMARY KEY,
                email VARCHAR(120) NOT NULL,
                code VARCHAR(10) NOT NULL,
                purpose VARCHAR(50) NOT NULL,
                created_at DATETIME,
                expires_at DATETIME NOT NULL,
                is_used BOOLEAN NOT NULL CHECK (is_used IN (0, 1))
            )
        """)
        cursor.execute("CREATE INDEX ix_verification_code_email ON verification_code (email)")
        print("Success: Created 'verification_code' table.")
    except sqlite3.OperationalError as e:
        if "already exists" in str(e):
            print("Warning: Table 'verification_code' already exists.")
        else:
            print(f"Error creating verification_code table: {e}")

    conn.commit()
    conn.close()
    print("Database upgrade finished.")

if __name__ == '__main__':
    upgrade()
