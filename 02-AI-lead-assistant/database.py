import os
import sqlite3
from pathlib import Path


# =====================================
# DATABASE SETTINGS
# =====================================

BASE_DIR = Path(__file__).resolve().parent
SQLITE_PATH = BASE_DIR / "leads.db"

DATABASE_URL = os.getenv("DATABASE_URL")

IS_POSTGRES = bool(DATABASE_URL)


# =====================================
# POSTGRES IMPORT
# =====================================

if IS_POSTGRES:
    import psycopg
    from psycopg.rows import dict_row


# =====================================
# CURSOR WRAPPER
# =====================================

class DatabaseCursor:

    def __init__(
        self,
        cursor,
        is_postgres
    ):
        self.cursor = cursor
        self.is_postgres = is_postgres


    def execute(
        self,
        query,
        parameters=()
    ):

        # SQLite uses ?
        # PostgreSQL uses %s

        if self.is_postgres:
            query = query.replace(
                "?",
                "%s"
            )

        self.cursor.execute(
            query,
            parameters
        )

        return self


    def fetchone(self):
        return self.cursor.fetchone()


    def fetchall(self):
        return self.cursor.fetchall()


    def close(self):
        self.cursor.close()


# =====================================
# CONNECTION WRAPPER
# =====================================

class DatabaseConnection:

    def __init__(self):

        if IS_POSTGRES:

            self.connection = psycopg.connect(
                DATABASE_URL,
                row_factory=dict_row
            )

        else:

            self.connection = sqlite3.connect(
                SQLITE_PATH
            )

            self.connection.row_factory = (
                sqlite3.Row
            )


    def cursor(self):

        return DatabaseCursor(
            self.connection.cursor(),
            IS_POSTGRES
        )


    def commit(self):
        self.connection.commit()


    def rollback(self):
        self.connection.rollback()


    def close(self):
        self.connection.close()


# =====================================
# GET CONNECTION
# =====================================

def get_connection():

    return DatabaseConnection()


# =====================================
# CREATE TABLES
# =====================================

def setup_database():

    conn = get_connection()
    cursor = conn.cursor()

    try:

        # =================================
        # POSTGRES TABLES
        # =================================

        if IS_POSTGRES:

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS leads (

                    id BIGSERIAL PRIMARY KEY,

                    customer_name TEXT,

                    phone_number TEXT,

                    email TEXT,

                    vehicle TEXT,

                    requested_service TEXT,

                    requested_time TEXT,

                    status TEXT DEFAULT 'New',

                    created_at TEXT

                )
            """)


            cursor.execute("""
                CREATE TABLE IF NOT EXISTS appointments (

                    id BIGSERIAL PRIMARY KEY,

                    customer_name TEXT,

                    phone_number TEXT,

                    vehicle TEXT,

                    service TEXT,

                    appointment_date TEXT,

                    appointment_time TEXT,

                    duration_minutes INTEGER,

                    status TEXT DEFAULT 'Booked',

                    created_at TEXT

                )
            """)

        # =================================
        # LOCAL SQLITE TABLES
        # =================================

        else:

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS leads (

                    id INTEGER
                    PRIMARY KEY
                    AUTOINCREMENT,

                    customer_name TEXT,

                    phone_number TEXT,

                    email TEXT,

                    vehicle TEXT,

                    requested_service TEXT,

                    requested_time TEXT,

                    status TEXT DEFAULT 'New',

                    created_at TEXT

                )
            """)


            cursor.execute("""
                CREATE TABLE IF NOT EXISTS appointments (

                    id INTEGER
                    PRIMARY KEY
                    AUTOINCREMENT,

                    customer_name TEXT,

                    phone_number TEXT,

                    vehicle TEXT,

                    service TEXT,

                    appointment_date TEXT,

                    appointment_time TEXT,

                    duration_minutes INTEGER,

                    status TEXT DEFAULT 'Booked',

                    created_at TEXT

                )
            """)


        conn.commit()


    except Exception:

        conn.rollback()
        raise


    finally:

        conn.close()


# =====================================
# INITIALIZE DATABASE
# =====================================

setup_database()