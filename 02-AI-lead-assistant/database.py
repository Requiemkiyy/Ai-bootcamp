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
# CONNECTION
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
# COLUMN HELPERS
# =====================================

def column_exists(
    cursor,
    table_name,
    column_name
):

    if IS_POSTGRES:

        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = ?
            AND column_name = ?
        """, (
            table_name,
            column_name
        ))

        return cursor.fetchone() is not None

    cursor.execute(
        f"PRAGMA table_info({table_name})"
    )

    columns = cursor.fetchall()

    for column in columns:

        if column["name"] == column_name:
            return True

    return False


def add_column_if_missing(
    cursor,
    table_name,
    column_name,
    definition
):

    if column_exists(
        cursor,
        table_name,
        column_name
    ):
        return

    cursor.execute(
        f"""
        ALTER TABLE {table_name}
        ADD COLUMN {column_name} {definition}
        """
    )


# =====================================
# DATABASE SETUP
# =====================================

def setup_database():

    conn = get_connection()
    cursor = conn.cursor()

    try:

        # =================================
        # BUSINESSES
        # =================================

        if IS_POSTGRES:

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS businesses (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    slug TEXT NOT NULL UNIQUE,
                    location TEXT,
                    phone TEXT,
                    email TEXT,
                    active BOOLEAN DEFAULT TRUE,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)

        else:

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS businesses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    slug TEXT NOT NULL UNIQUE,
                    location TEXT,
                    phone TEXT,
                    email TEXT,
                    active INTEGER DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)


        # =================================
        # SERVICES
        # =================================

        if IS_POSTGRES:

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS services (
                    id BIGSERIAL PRIMARY KEY,
                    business_id BIGINT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    price_cents INTEGER NOT NULL,
                    duration_minutes INTEGER NOT NULL,
                    service_type TEXT DEFAULT 'service',
                    active BOOLEAN DEFAULT TRUE,
                    created_at TEXT
                )
            """)

        else:

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS services (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    price_cents INTEGER NOT NULL,
                    duration_minutes INTEGER NOT NULL,
                    service_type TEXT DEFAULT 'service',
                    active INTEGER DEFAULT 1,
                    created_at TEXT
                )
            """)


        # =================================
        # BUSINESS HOURS
        # =================================

        if IS_POSTGRES:

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS business_hours (
                    id BIGSERIAL PRIMARY KEY,
                    business_id BIGINT NOT NULL,
                    weekday INTEGER NOT NULL,
                    open_time TEXT,
                    close_time TEXT,
                    is_closed BOOLEAN DEFAULT FALSE
                )
            """)

        else:

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS business_hours (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_id INTEGER NOT NULL,
                    weekday INTEGER NOT NULL,
                    open_time TEXT,
                    close_time TEXT,
                    is_closed INTEGER DEFAULT 0
                )
            """)


        # =================================
        # LEADS
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


        # =================================
        # APPOINTMENTS
        # =================================

        if IS_POSTGRES:

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

        else:

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


        # =================================
        # SESSIONS
        # =================================

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
        # RATE LIMITS
        # =================================

        if IS_POSTGRES:

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rate_limits (
                    id BIGSERIAL PRIMARY KEY,
                    client_key TEXT NOT NULL,
                    request_time TEXT NOT NULL
                )
            """)

        else:

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rate_limits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_key TEXT NOT NULL,
                    request_time TEXT NOT NULL
                )
            """)


        # =================================
        # MULTI-BUSINESS COLUMNS
        # =================================

        business_id_type = (
            "BIGINT"
            if IS_POSTGRES
            else "INTEGER"
        )

        add_column_if_missing(
            cursor,
            "leads",
            "business_id",
            business_id_type
        )

        add_column_if_missing(
            cursor,
            "appointments",
            "business_id",
            business_id_type
        )

        add_column_if_missing(
            cursor,
            "sessions",
            "business_id",
            business_id_type
        )

        add_column_if_missing(
            cursor,
            "rate_limits",
            "business_id",
            business_id_type
        )


        # =================================
        # INDEXES
        # =================================

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_leads_business_id
            ON leads(business_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_appointments_business_id
            ON appointments(business_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_sessions_business_id
            ON sessions(business_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_services_business_id
            ON services(business_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_business_hours_business_id
            ON business_hours(business_id)
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
# DEFAULT BUSINESS
# =====================================

DEFAULT_BUSINESS_SLUG = (
    "freedom-auto-detailing"
)


# =====================================
# BUSINESS LOOKUPS
# =====================================

def get_business_by_id(
    business_id
):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT *
            FROM businesses
            WHERE id = ?
        """, (
            business_id,
        ))

        row = cursor.fetchone()

        if not row:
            return None

        return dict(row)

    finally:

        conn.close()


def get_business_by_slug(
    slug
):

    if not slug:
        return None

    slug = (
        str(slug)
        .strip()
        .lower()
    )

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT *
            FROM businesses
            WHERE slug = ?
        """, (
            slug,
        ))

        row = cursor.fetchone()

        if not row:
            return None

        return dict(row)

    finally:

        conn.close()


def get_default_business():

    return get_business_by_slug(
        DEFAULT_BUSINESS_SLUG
    )


# =====================================
# BUSINESS SERVICES
# =====================================

def get_services_for_business(
    business_id
):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        active_value = (
            True
            if IS_POSTGRES
            else 1
        )

        cursor.execute("""
            SELECT *
            FROM services

            WHERE business_id = ?
            AND active = ?

            ORDER BY
                service_type,
                id
        """, (
            business_id,
            active_value
        ))

        rows = cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# =====================================
# BUSINESS HOURS
# =====================================

def get_business_hours_rows(
    business_id
):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT *
            FROM business_hours
            WHERE business_id = ?
            ORDER BY weekday
        """, (
            business_id,
        ))

        rows = cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# =====================================
# SEED DEFAULT BUSINESS
# =====================================

def seed_default_business():

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT id
            FROM businesses
            WHERE slug = ?
        """, (
            DEFAULT_BUSINESS_SLUG,
        ))

        row = cursor.fetchone()

        if row:

            business_id = row["id"]

        else:

            active_value = (
                True
                if IS_POSTGRES
                else 1
            )

            timestamp = current_timestamp()

            cursor.execute("""
                INSERT INTO businesses (
                    name,
                    slug,
                    location,
                    phone,
                    email,
                    active,
                    created_at,
                    updated_at
                )

                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "Freedom Auto Detailing",
                DEFAULT_BUSINESS_SLUG,
                "Columbus, Ohio",
                None,
                None,
                active_value,
                timestamp,
                timestamp
            ))

            cursor.execute("""
                SELECT id
                FROM businesses
                WHERE slug = ?
            """, (
                DEFAULT_BUSINESS_SLUG,
            ))

            row = cursor.fetchone()

            business_id = row["id"]


        # =================================
        # SERVICES
        # =================================

        services_to_seed = [

            {
                "name":
                    "Interior Detail",

                "description":
                    "Complete interior detailing service.",

                "price_cents":
                    12000,

                "duration_minutes":
                    120,

                "service_type":
                    "service"
            },

            {
                "name":
                    "Exterior Detail",

                "description":
                    "Complete exterior detailing service.",

                "price_cents":
                    8000,

                "duration_minutes":
                    90,

                "service_type":
                    "service"
            },

            {
                "name":
                    "Full Interior + Exterior Detail",

                "description":
                    "Complete interior and exterior detailing service.",

                "price_cents":
                    18000,

                "duration_minutes":
                    180,

                "service_type":
                    "service"
            },

            {
                "name":
                    "Pet Hair Removal",

                "description":
                    "Pet hair removal add-on.",

                "price_cents":
                    4000,

                "duration_minutes":
                    30,

                "service_type":
                    "addon"
            },

            {
                "name":
                    "Seat Shampoo",

                "description":
                    "Seat shampoo add-on.",

                "price_cents":
                    3500,

                "duration_minutes":
                    30,

                "service_type":
                    "addon"
            },

            {
                "name":
                    "Headlight Restoration",

                "description":
                    "Headlight restoration add-on.",

                "price_cents":
                    5000,

                "duration_minutes":
                    30,

                "service_type":
                    "addon"
            }
        ]

        active_value = (
            True
            if IS_POSTGRES
            else 1
        )

        for service in services_to_seed:

            cursor.execute("""
                SELECT id
                FROM services
                WHERE business_id = ?
                AND name = ?
            """, (
                business_id,
                service["name"]
            ))

            existing = cursor.fetchone()

            if existing:
                continue

            cursor.execute("""
                INSERT INTO services (
                    business_id,
                    name,
                    description,
                    price_cents,
                    duration_minutes,
                    service_type,
                    active,
                    created_at
                )

                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                business_id,
                service["name"],
                service["description"],
                service["price_cents"],
                service["duration_minutes"],
                service["service_type"],
                active_value,
                current_timestamp()
            ))


        # =================================
        # BUSINESS HOURS
        # =================================

        hours_to_seed = [

            (0, "09:00", "18:00", False),
            (1, "09:00", "18:00", False),
            (2, "09:00", "18:00", False),
            (3, "09:00", "18:00", False),
            (4, "09:00", "18:00", False),
            (5, "10:00", "16:00", False),
            (6, None, None, True)
        ]

        for (
            weekday,
            open_time,
            close_time,
            is_closed
        ) in hours_to_seed:

            cursor.execute("""
                SELECT id
                FROM business_hours
                WHERE business_id = ?
                AND weekday = ?
            """, (
                business_id,
                weekday
            ))

            existing = cursor.fetchone()

            if existing:
                continue

            closed_value = (
                bool(is_closed)
                if IS_POSTGRES
                else int(is_closed)
            )

            cursor.execute("""
                INSERT INTO business_hours (
                    business_id,
                    weekday,
                    open_time,
                    close_time,
                    is_closed
                )

                VALUES (?, ?, ?, ?, ?)
            """, (
                business_id,
                weekday,
                open_time,
                close_time,
                closed_value
            ))


        # =================================
        # BACKFILL EXISTING DATA
        # =================================

        cursor.execute("""
            UPDATE leads
            SET business_id = ?
            WHERE business_id IS NULL
        """, (
            business_id,
        ))

        cursor.execute("""
            UPDATE appointments
            SET business_id = ?
            WHERE business_id IS NULL
        """, (
            business_id,
        ))

        cursor.execute("""
            UPDATE sessions
            SET business_id = ?
            WHERE business_id IS NULL
        """, (
            business_id,
        ))

        cursor.execute("""
            UPDATE rate_limits
            SET business_id = ?
            WHERE business_id IS NULL
        """, (
            business_id,
        ))

        conn.commit()

        return business_id

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()


# =====================================
# SESSION FUNCTIONS
# =====================================

def load_session(
    session_id,
    business_id=None
):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        if business_id is None:

            cursor.execute("""
                SELECT
                    customer_data,
                    booking_data,
                    messages,
                    business_id

                FROM sessions

                WHERE session_id = ?
            """, (
                session_id,
            ))

        else:

            cursor.execute("""
                SELECT
                    customer_data,
                    booking_data,
                    messages,
                    business_id

                FROM sessions

                WHERE session_id = ?
                AND business_id = ?
            """, (
                session_id,
                business_id
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

            "customer_data":
                customer_data,

            "booking":
                booking_data,

            "messages":
                messages,

            "business_id":
                row["business_id"]
        }

    finally:

        conn.close()


def save_session(
    session_id,
    session,
    business_id=None
):

    if business_id is None:

        business_id = session.get(
            "business_id"
        )

    if business_id is None:

        default_business = (
            get_default_business()
        )

        if default_business:

            business_id = (
                default_business["id"]
            )


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
                    business_id = ?,
                    customer_data = ?,
                    booking_data = ?,
                    messages = ?,
                    updated_at = ?

                WHERE session_id = ?
            """, (
                business_id,
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
                    business_id,
                    customer_data,
                    booking_data,
                    messages,
                    created_at,
                    updated_at
                )

                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                business_id,
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


def delete_session(
    session_id,
    business_id=None
):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        if business_id is None:

            cursor.execute("""
                DELETE FROM sessions
                WHERE session_id = ?
            """, (
                session_id,
            ))

        else:

            cursor.execute("""
                DELETE FROM sessions
                WHERE session_id = ?
                AND business_id = ?
            """, (
                session_id,
                business_id
            ))

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()


# =====================================
# DATABASE RATE LIMIT
# =====================================

def check_database_rate_limit(
    client_key,
    max_requests=15,
    window_seconds=60,
    minimum_interval_seconds=0,
    business_id=None
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


    if business_id is None:

        default_business = (
            get_default_business()
        )

        if default_business:

            business_id = (
                default_business["id"]
            )


    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            DELETE FROM rate_limits
            WHERE request_time < ?
        """, (
            cutoff_string,
        ))


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

            wait_seconds = (
                window_seconds
            )

            if oldest_row:

                try:

                    oldest_request = (
                        datetime.strptime(
                            oldest_row[
                                "request_time"
                            ],
                            "%Y-%m-%d %H:%M:%S.%f"
                        )
                    )

                    unlock_time = (
                        oldest_request
                        + timedelta(
                            seconds=
                                window_seconds
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

                "allowed":
                    False,

                "reason":
                    "limit_reached",

                "wait_seconds":
                    wait_seconds
            }


        cursor.execute("""
            INSERT INTO rate_limits (
                business_id,
                client_key,
                request_time
            )

            VALUES (?, ?, ?)
        """, (
            business_id,
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

            "allowed":
                True,

            "reason":
                None,

            "wait_seconds":
                0
        }

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()


# =====================================
# INITIALIZE
# =====================================

setup_database()

DEFAULT_BUSINESS_ID = (
    seed_default_business()
)