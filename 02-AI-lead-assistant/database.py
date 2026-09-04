import os
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta


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

            self.connection.row_factory = sqlite3.Row

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
# TIMESTAMPS
# =====================================

def current_timestamp():

    return datetime.now().strftime(
        "%Y-%m-%d %I:%M %p"
    )


def rate_limit_timestamp():

    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S.%f"
    )


# =====================================
# DATABASE SETUP
# =====================================

def setup_database():

    conn = get_connection()
    cursor = conn.cursor()

    try:

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

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rate_limits (
                    id BIGSERIAL PRIMARY KEY,
                    client_key TEXT NOT NULL,
                    request_time TEXT NOT NULL
                )
            """)

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

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rate_limits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_key TEXT NOT NULL,
                    request_time TEXT NOT NULL
                )
            """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_rate_limits_client_key
            ON rate_limits(client_key)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_rate_limits_request_time
            ON rate_limits(request_time)
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

        cursor.execute("""
            SELECT session_id
            FROM sessions
            WHERE session_id = ?
        """, (
            session_id,
        ))

        existing = cursor.fetchone()

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
# RATE LIMIT
# =====================================

def check_database_rate_limit(
    client_key,
    max_requests=15,
    window_seconds=60,
    minimum_interval_seconds=0
):

    now = datetime.now()

    cutoff = (
        now
        - timedelta(
            seconds=window_seconds
        )
    )

    cutoff_string = cutoff.strftime(
        "%Y-%m-%d %H:%M:%S.%f"
    )

    now_string = now.strftime(
        "%Y-%m-%d %H:%M:%S.%f"
    )

    conn = get_connection()
    cursor = conn.cursor()

    try:

        # =================================
        # REMOVE OLD RECORDS
        # =================================

        cursor.execute("""
            DELETE FROM rate_limits
            WHERE request_time < ?
        """, (
            cutoff_string,
        ))


        # =================================
        # COUNT THIS VISITOR'S REQUESTS
        # =================================

        cursor.execute("""
            SELECT COUNT(*) AS request_count
            FROM rate_limits
            WHERE client_key = ?
            AND request_time >= ?
        """, (
            client_key,
            cutoff_string
        ))

        row = cursor.fetchone()

        request_count = (
            int(
                row["request_count"]
            )
            if row
            else 0
        )


        # =================================
        # BLOCK IF LIMIT REACHED
        # =================================

        if request_count >= max_requests:

            cursor.execute("""
                SELECT request_time
                FROM rate_limits
                WHERE client_key = ?
                AND request_time >= ?
                ORDER BY request_time ASC
                LIMIT 1
            """, (
                client_key,
                cutoff_string
            ))

            oldest_row = cursor.fetchone()

            wait_seconds = window_seconds

            if oldest_row:

                try:

                    oldest_request = datetime.strptime(
                        oldest_row["request_time"],
                        "%Y-%m-%d %H:%M:%S.%f"
                    )

                    unlock_time = (
                        oldest_request
                        + timedelta(
                            seconds=window_seconds
                        )
                    )

                    wait_seconds = max(
                        1,
                        int(
                            (
                                unlock_time
                                - now
                            ).total_seconds()
                        ) + 1
                    )

                except (
                    ValueError,
                    TypeError
                ):
                    pass

            conn.commit()

            print(
                f"RATE LIMIT BLOCKED: "
                f"{client_key} "
                f"({request_count}/{max_requests})"
            )

            return {
                "allowed": False,
                "reason": "limit_reached",
                "wait_seconds": wait_seconds
            }


        # =================================
        # RECORD ALLOWED REQUEST
        # =================================

        cursor.execute("""
            INSERT INTO rate_limits (
                client_key,
                request_time
            )
            VALUES (?, ?)
        """, (
            client_key,
            now_string
        ))

        conn.commit()

        print(
            f"RATE LIMIT ALLOWED: "
            f"{client_key} "
            f"({request_count + 1}/{max_requests})"
        )

        return {
            "allowed": True,
            "reason": None,
            "wait_seconds": 0
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# =====================================
# INITIALIZE DATABASE
# =====================================

setup_database()