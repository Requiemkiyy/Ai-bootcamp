import os
import sqlite3
import json
from pathlib import Path


# =====================================
# DATABASE CONFIGURATION
# =====================================

BASE_DIR = Path(__file__).resolve().parent
SQLITE_PATH = BASE_DIR / "leads.db"

DATABASE_URL = os.getenv("DATABASE_URL")
IS_POSTGRES = bool(DATABASE_URL)


if IS_POSTGRES:
    import psycopg
    from psycopg.rows import dict_row


# =====================================
# DATABASE CURSOR WRAPPER
# =====================================

class DatabaseCursor:

    def __init__(self, cursor, postgres=False):
        self.cursor = cursor
        self.postgres = postgres

    def execute(self, query, params=None):

        if self.postgres:
            query = query.replace("?", "%s")

        if params is None:
            return self.cursor.execute(query)

        return self.cursor.execute(query, params)

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def close(self):
        return self.cursor.close()


# =====================================
# DATABASE CONNECTION WRAPPER
# =====================================

class DatabaseConnection:

    def __init__(self):

        self.postgres = IS_POSTGRES

        if self.postgres:

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
            self.postgres
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
# DATABASE SETUP
# =====================================

def setup_database():

    conn = get_connection()
    cursor = conn.cursor()

    try:

        # =================================
        # POSTGRES
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

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    customer_data TEXT NOT NULL,
                    booking_data TEXT NOT NULL,
                    messages TEXT NOT NULL,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)

        # =================================
        # SQLITE
        # =================================

        else:

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    customer_data TEXT NOT NULL,
                    booking_data TEXT NOT NULL,
                    messages TEXT NOT NULL,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# =====================================
# SESSION FUNCTIONS
# =====================================

def load_session(session_id):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT
                session_id,
                customer_data,
                booking_data,
                messages
            FROM sessions
            WHERE session_id = ?
        """, (
            session_id,
        ))

        row = cursor.fetchone()

        if not row:
            return None

        try:
            customer_data = json.loads(
                row["customer_data"]
            )

            booking_data = json.loads(
                row["booking_data"]
            )

            messages = json.loads(
                row["messages"]
            )

        except (
            json.JSONDecodeError,
            TypeError
        ):
            return None

        return {
            "customer_data": customer_data,
            "booking": booking_data,
            "messages": messages
        }

    finally:
        conn.close()


def save_session(
    session_id,
    session
):

    customer_data_json = json.dumps(
        session.get(
            "customer_data",
            {}
        )
    )

    booking_data_json = json.dumps(
        session.get(
            "booking",
            {}
        )
    )

    messages_json = json.dumps(
        session.get(
            "messages",
            []
        )
    )

    timestamp = current_timestamp()

    conn = get_connection()
    cursor = conn.cursor()

    try:

        # ---------------------------------
        # CHECK IF SESSION EXISTS
        # ---------------------------------

        cursor.execute("""
            SELECT session_id
            FROM sessions
            WHERE session_id = ?
        """, (
            session_id,
        ))

        existing = cursor.fetchone()

        # ---------------------------------
        # UPDATE EXISTING SESSION
        # ---------------------------------

        if existing:

            cursor.execute("""
                UPDATE sessions

                SET
                    customer_data = ?,
                    booking_data = ?,
                    messages = ?,
                    updated_at = ?

                WHERE session_id = ?
            """, (
                customer_data_json,
                booking_data_json,
                messages_json,
                timestamp,
                session_id
            ))

        # ---------------------------------
        # CREATE NEW SESSION
        # ---------------------------------

        else:

            cursor.execute("""
                INSERT INTO sessions (
                    session_id,
                    customer_data,
                    booking_data,
                    messages,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                customer_data_json,
                booking_data_json,
                messages_json,
                timestamp,
                timestamp
            ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def delete_session(session_id):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            DELETE FROM sessions
            WHERE session_id = ?
        """, (
            session_id,
        ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# =====================================
# TIMESTAMP
# =====================================

def current_timestamp():

    from datetime import datetime

    return datetime.now().strftime(
        "%Y-%m-%d %I:%M %p"
    )


# =====================================
# INITIALIZE DATABASE
# =====================================

setup_database()