import sqlite3
import pymysql
import os
from dotenv import load_dotenv

load_dotenv(override=True)

# Global flag to track if we are using SQLite fallback
USING_SQLITE = False

class SQLiteCursor:
    def __init__(self, sqlite_cursor):
        self.cursor = sqlite_cursor

    def execute(self, query, params=None):
        # Translate MySQL query to SQLite query
        query = query.replace('INT AUTO_INCREMENT PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT')
        query = query.replace('AUTO_INCREMENT', 'AUTOINCREMENT')
        query = query.replace("ENUM('Admin', 'Manager', 'Employee')", "VARCHAR(50)")
        query = query.replace('%s', '?')
        
        if params is None:
            return self.cursor.execute(query)
        else:
            return self.cursor.execute(query, params)

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def fetchall(self):
        rows = self.cursor.fetchall()
        return [dict(r) for r in rows]

    @property
    def lastrowid(self):
        return self.cursor.lastrowid

class SQLiteConnection:
    def __init__(self, db_path='study_genie.db'):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def cursor(self):
        return SQLiteCursor(self.conn.cursor())

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()

def get_db_connection():
    global USING_SQLITE
    if USING_SQLITE:
        return SQLiteConnection()
    try:
        return pymysql.connect(
            host=os.getenv('MYSQL_HOST', 'localhost'),
            user=os.getenv('MYSQL_USER', 'root'),
            password=os.getenv('MYSQL_PASSWORD', ''),
            database=os.getenv('MYSQL_DB', 'study_genie'),
            cursorclass=pymysql.cursors.DictCursor
        )
    except Exception:
        USING_SQLITE = True
        print("Warning: Failed to connect to MySQL. Falling back to local SQLite database 'study_genie.db'.")
        return SQLiteConnection()

def init_db():
    global USING_SQLITE
    conn = None
    try:
        # Try initializing MySQL database
        conn = pymysql.connect(
            host=os.getenv('MYSQL_HOST', 'localhost'),
            user=os.getenv('MYSQL_USER', 'root'),
            password=os.getenv('MYSQL_PASSWORD', '')
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {os.getenv('MYSQL_DB', 'study_genie')}")
        conn.commit()
        conn.close()
        
        conn = get_db_connection()
        cursor = conn.cursor()
    except Exception as e:
        print(f"Warning: MySQL initialization failed ({e}). Falling back to SQLite.")
        USING_SQLITE = True
        conn = get_db_connection()
        cursor = conn.cursor()

    # Create Users table (works for both MySQL and SQLite)
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role ENUM('Admin', 'Manager', 'Employee') NOT NULL,
                totp_secret VARCHAR(32),
                is_verified BOOLEAN DEFAULT FALSE,
                employee_id VARCHAR(50) UNIQUE,
                full_name VARCHAR(255),
                mobile_number VARCHAR(15),
                department VARCHAR(100),
                designation VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
    except Exception as e:
        print(f"Error creating users table: {e}")

    # Create Reports table (works for both MySQL and SQLite)
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INT AUTO_INCREMENT PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                stored_name VARCHAR(255) NOT NULL,
                file_size INT NOT NULL,
                uploaded_by VARCHAR(255) NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
    except Exception as e:
        print(f"Error creating reports table: {e}")

    # Create Activity Logs table (works for both MySQL and SQLite)
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_email VARCHAR(255) NOT NULL,
                action_type VARCHAR(100) NOT NULL,
                description TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
    except Exception as e:
        print(f"Error creating activity_logs table: {e}")

    # Safely add new columns to existing tables (both MySQL and SQLite)
    alter_queries = [
        "ALTER TABLE users ADD COLUMN totp_secret VARCHAR(32)",
        "ALTER TABLE users ADD COLUMN employee_id VARCHAR(50) UNIQUE",
        "ALTER TABLE users ADD COLUMN full_name VARCHAR(255)",
        "ALTER TABLE users ADD COLUMN mobile_number VARCHAR(15)",
        "ALTER TABLE users ADD COLUMN department VARCHAR(100)",
        "ALTER TABLE users ADD COLUMN designation VARCHAR(100)",
        "ALTER TABLE users ADD COLUMN attendance_status VARCHAR(50) DEFAULT 'Not Marked'"
    ]
    for q in alter_queries:
        try:
            cursor.execute(q)
            conn.commit()
        except Exception:
            pass

    conn.close()

if __name__ == '__main__':
    try:
        init_db()
        print("Database initialized successfully. Using SQLite:", USING_SQLITE)
    except Exception as e:
        print(f"Error initializing database: {e}")
