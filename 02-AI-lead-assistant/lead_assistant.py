from openai import OpenAI
import sqlite3
import json

from datetime import datetime, timedelta
from pathlib import Path


# =====================================
# SETTINGS
# =====================================

client = OpenAI()

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "leads.db"


# =====================================
# DATABASE CONNECTION
# =====================================

def get_connection():

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    return connection


# =====================================
# DATABASE SETUP
# =====================================

def setup_database():

    conn = get_connection()
    cursor = conn.cursor()

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

    conn.commit()


    try:

        cursor.execute("""
        ALTER TABLE leads
        ADD COLUMN status TEXT DEFAULT 'New'
        """)

        conn.commit()

    except sqlite3.OperationalError:
        pass


    try:

        cursor.execute("""
        ALTER TABLE leads
        ADD COLUMN created_at TEXT
        """)

        conn.commit()

    except sqlite3.OperationalError:
        pass


    try:

        cursor.execute("""
        ALTER TABLE appointments
        ADD COLUMN duration_minutes INTEGER
        """)

        conn.commit()

    except sqlite3.OperationalError:
        pass


    conn.close()


setup_database()


# =====================================
# GENERAL HELPERS
# =====================================

def current_timestamp():

    return datetime.now().strftime(
        "%Y-%m-%d %I:%M %p"
    )


def normalize_phone(phone_number):

    if not phone_number:
        return "Not provided"

    if phone_number == "Not provided":
        return "Not provided"

    digits = ""

    for character in phone_number:

        if character.isdigit():
            digits += character

    return digits


# =====================================
# SERVICE DURATIONS
# =====================================

def get_service_duration(service):

    service_lower = service.lower()

    duration = None


    if (
        "full interior" in service_lower
        and "exterior" in service_lower
    ):

        duration = 180


    elif "interior detail" in service_lower:

        duration = 120


    elif "exterior detail" in service_lower:

        duration = 90


    if duration is not None:

        if "pet hair" in service_lower:
            duration += 30

        if "seat shampoo" in service_lower:
            duration += 30

        if "headlight" in service_lower:
            duration += 30


    return duration


# =====================================
# LEAD FUNCTIONS
# =====================================

def find_lead(phone_number):

    clean_phone = normalize_phone(
        phone_number
    )

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM leads
    """)

    leads = cursor.fetchall()

    conn.close()


    for lead in leads:

        stored_phone = normalize_phone(
            lead["phone_number"]
        )

        if stored_phone == clean_phone:
            return dict(lead)


    return None


def save_lead(
    customer_name,
    phone_number,
    email,
    vehicle,
    requested_service,
    requested_time
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO leads (
        customer_name,
        phone_number,
        email,
        vehicle,
        requested_service,
        requested_time,
        status,
        created_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        customer_name,
        normalize_phone(phone_number),
        email,
        vehicle,
        requested_service,
        requested_time,
        "New",
        current_timestamp()
    ))

    conn.commit()
    conn.close()


def update_lead(
    customer_name,
    phone_number,
    email,
    vehicle,
    requested_service,
    requested_time
):

    existing_lead = find_lead(
        phone_number
    )

    if not existing_lead:
        return False


    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE leads

    SET
        customer_name = ?,
        phone_number = ?,
        email = ?,
        vehicle = ?,
        requested_service = ?,
        requested_time = ?

    WHERE id = ?
    """, (
        customer_name,
        normalize_phone(phone_number),
        email,
        vehicle,
        requested_service,
        requested_time,
        existing_lead["id"]
    ))

    conn.commit()
    conn.close()

    return True


def get_all_leads():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM leads
    ORDER BY id DESC
    """)

    results = cursor.fetchall()

    conn.close()

    return [
        dict(row)
        for row in results
    ]


def update_lead_status(
    lead_id,
    new_status
):

    allowed_statuses = [
        "New",
        "Contacted",
        "Booked",
        "Completed",
        "Lost"
    ]


    if new_status not in allowed_statuses:
        return False


    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE leads
    SET status = ?
    WHERE id = ?
    """, (
        new_status,
        lead_id
    ))

    conn.commit()
    conn.close()

    return True


def delete_lead(lead_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    DELETE FROM leads
    WHERE id = ?
    """, (
        lead_id,
    ))

    conn.commit()
    conn.close()


# =====================================
# BUSINESS HOURS
# =====================================

def get_business_hours(
    appointment_date
):

    try:

        date_object = datetime.strptime(
            appointment_date,
            "%Y-%m-%d"
        )

    except ValueError:

        return None


    weekday = date_object.weekday()


    # Monday-Friday
    if weekday <= 4:

        return {
            "open": "09:00",
            "close": "18:00"
        }


    # Saturday
    if weekday == 5:

        return {
            "open": "10:00",
            "close": "16:00"
        }


    # Sunday
    return None


# =====================================
# APPOINTMENT VALIDATION
# =====================================

def validate_appointment_time(
    appointment_date,
    appointment_time,
    service
):

    try:

        requested_start = datetime.strptime(
            f"{appointment_date} {appointment_time}",
            "%Y-%m-%d %H:%M"
        )

    except ValueError:

        return {
            "valid": False,
            "reason":
                "I need a valid date and time before I can book that."
        }


    if requested_start < datetime.now():

        return {
            "valid": False,
            "reason":
                "That appointment time has already passed."
        }


    hours = get_business_hours(
        appointment_date
    )


    if hours is None:

        return {
            "valid": False,
            "reason":
                "We're closed that day."
        }


    duration = get_service_duration(
        service
    )


    if duration is None:

        return {
            "valid": False,
            "reason":
                "A team member needs to confirm the duration of that service before booking it."
        }


    opening_time = datetime.strptime(
        f"{appointment_date} {hours['open']}",
        "%Y-%m-%d %H:%M"
    )


    closing_time = datetime.strptime(
        f"{appointment_date} {hours['close']}",
        "%Y-%m-%d %H:%M"
    )


    requested_end = (
        requested_start
        + timedelta(
            minutes=duration
        )
    )


    if requested_start < opening_time:

        return {
            "valid": False,
            "reason":
                "That time is before we open."
        }


    if requested_end > closing_time:

        return {
            "valid": False,
            "reason":
                "That service would run past closing time."
        }


    return {
        "valid": True,
        "start": requested_start,
        "end": requested_end,
        "duration": duration
    }


# =====================================
# GET APPOINTMENTS
# =====================================

def get_all_appointments():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM appointments

    ORDER BY
        appointment_date,
        appointment_time
    """)

    results = cursor.fetchall()

    conn.close()

    return [
        dict(row)
        for row in results
    ]


def get_appointments_for_date(
    appointment_date
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM appointments

    WHERE appointment_date = ?
    AND status != 'Cancelled'

    ORDER BY appointment_time
    """, (
        appointment_date,
    ))

    results = cursor.fetchall()

    conn.close()

    return [
        dict(row)
        for row in results
    ]


# =====================================
# CONFLICT CHECK
# =====================================

def appointment_slot_available(
    appointment_date,
    appointment_time,
    service
):

    validation = validate_appointment_time(
        appointment_date,
        appointment_time,
        service
    )


    if not validation["valid"]:

        return validation


    requested_start = validation["start"]
    requested_end = validation["end"]


    appointments = get_appointments_for_date(
        appointment_date
    )


    for appointment in appointments:

        try:

            existing_start = datetime.strptime(
                (
                    f"{appointment['appointment_date']} "
                    f"{appointment['appointment_time']}"
                ),
                "%Y-%m-%d %H:%M"
            )

        except ValueError:

            continue


        existing_duration = (
            appointment[
                "duration_minutes"
            ]
            or 120
        )


        existing_end = (
            existing_start
            + timedelta(
                minutes=existing_duration
            )
        )


        overlap = (
            requested_start < existing_end
            and requested_end > existing_start
        )


        if overlap:

            return {
                "valid": False,
                "reason":
                    "That appointment overlaps with another booking."
            }


    return validation


# =====================================
# FIND AVAILABLE TIMES
# =====================================

def find_available_slots(
    starting_date,
    service,
    max_slots=3,
    days_to_search=7
):

    duration = get_service_duration(
        service
    )


    if duration is None:
        return []


    try:

        search_date = datetime.strptime(
            starting_date,
            "%Y-%m-%d"
        )

    except ValueError:

        return []


    available_slots = []


    for day_offset in range(
        days_to_search
    ):

        day = (
            search_date
            + timedelta(
                days=day_offset
            )
        )


        date_string = day.strftime(
            "%Y-%m-%d"
        )


        hours = get_business_hours(
            date_string
        )


        if hours is None:
            continue


        opening = datetime.strptime(
            f"{date_string} {hours['open']}",
            "%Y-%m-%d %H:%M"
        )


        closing = datetime.strptime(
            f"{date_string} {hours['close']}",
            "%Y-%m-%d %H:%M"
        )


        slot = opening


        # If searching today,
        # don't suggest times that already passed

        if day.date() == datetime.now().date():

            while slot < datetime.now():

                slot += timedelta(
                    minutes=30
                )


        while (
            slot
            + timedelta(
                minutes=duration
            )
            <= closing
        ):

            time_string = slot.strftime(
                "%H:%M"
            )


            availability = appointment_slot_available(
                date_string,
                time_string,
                service
            )


            if availability["valid"]:

                available_slots.append({
                    "date":
                        date_string,

                    "time":
                        time_string
                })


                if (
                    len(
                        available_slots
                    )
                    >= max_slots
                ):

                    return available_slots


            slot += timedelta(
                minutes=30
            )


    return available_slots


# =====================================
# FORMAT AVAILABLE TIMES
# =====================================

def format_available_slots(
    slots
):

    if not slots:

        return (
            "I couldn't find an open appointment "
            "within the next week."
        )


    formatted = []


    for slot in slots:

        date_object = datetime.strptime(
            slot["date"],
            "%Y-%m-%d"
        )


        time_object = datetime.strptime(
            slot["time"],
            "%H:%M"
        )


        readable_date = date_object.strftime(
            "%A, %B %d"
        )


        readable_time = time_object.strftime(
            "%I:%M %p"
        ).lstrip("0")


        formatted.append(
            f"{readable_date} at {readable_time}"
        )


    return (
        "The next available times are: "
        + ", ".join(formatted)
        + "."
    )


# =====================================
# CREATE APPOINTMENT
# =====================================

def create_appointment(
    customer_name,
    phone_number,
    vehicle,
    service,
    appointment_date,
    appointment_time
):

    availability = appointment_slot_available(
        appointment_date,
        appointment_time,
        service
    )


    if not availability["valid"]:

        alternatives = find_available_slots(
            appointment_date,
            service,
            max_slots=3,
            days_to_search=7
        )


        return {
            "success": False,

            "reason":
                availability["reason"],

            "alternatives":
                alternatives
        }


    conn = get_connection()
    cursor = conn.cursor()


    cursor.execute("""
    INSERT INTO appointments (
        customer_name,
        phone_number,
        vehicle,
        service,
        appointment_date,
        appointment_time,
        duration_minutes,
        status,
        created_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        customer_name,
        normalize_phone(
            phone_number
        ),
        vehicle,
        service,
        appointment_date,
        appointment_time,
        availability[
            "duration"
        ],
        "Booked",
        current_timestamp()
    ))


    conn.commit()
    conn.close()


    return {
        "success": True
    }


# =====================================
# APPOINTMENT MANAGEMENT
# =====================================

def update_appointment_status(
    appointment_id,
    new_status
):

    allowed_statuses = [
        "Booked",
        "Completed",
        "Cancelled"
    ]


    if new_status not in allowed_statuses:
        return False


    conn = get_connection()
    cursor = conn.cursor()


    cursor.execute("""
    UPDATE appointments

    SET status = ?

    WHERE id = ?
    """, (
        new_status,
        appointment_id
    ))


    conn.commit()
    conn.close()

    return True


def delete_appointment(
    appointment_id
):

    conn = get_connection()
    cursor = conn.cursor()


    cursor.execute("""
    DELETE FROM appointments
    WHERE id = ?
    """, (
        appointment_id,
    ))


    conn.commit()
    conn.close()


# =====================================
# BUSINESS INFORMATION
# =====================================

business_info = """
BUSINESS:
Freedom Auto Detailing

LOCATION:
Columbus, Ohio

SERVICES:

Interior Detail - $120
Estimated duration: 2 hours

Exterior Detail - $80
Estimated duration: 1.5 hours

Full Interior + Exterior Detail - $180
Estimated duration: 3 hours

ADD-ONS:

Pet Hair Removal - $40
Adds approximately 30 minutes

Seat Shampoo - $35
Adds approximately 30 minutes

Headlight Restoration - $50
Adds approximately 30 minutes

BUSINESS HOURS:

Monday-Friday:
9 AM - 6 PM

Saturday:
10 AM - 4 PM

Sunday:
Closed

BOOKING RULES:

Appointments are only confirmed after the backend
successfully creates the appointment.

Never claim an appointment is booked before receiving
confirmation from the booking system.

Never invent availability.

Never invent prices.
"""


# =====================================
# CUSTOMER SESSION MEMORY
# =====================================

conversations = {}


# =====================================
# AI ASSISTANT
# =====================================

def process_customer_message(
    customer_message,
    session_id
):

    if session_id not in conversations:

        conversations[
            session_id
        ] = []


    conversation = conversations[
        session_id
    ]


    conversation.append({
        "role": "user",
        "content": customer_message
    })


    today = datetime.now().strftime(
        "%Y-%m-%d"
    )


    response = client.responses.create(
        model="gpt-5.4-mini",

        instructions=f"""
You are the customer-facing AI receptionist
for Freedom Auto Detailing.

Today's date is:

{today}

BUSINESS INFORMATION:

{business_info}


Return ONLY valid JSON:

{{
    "customer_name": "",
    "phone_number": "",
    "email": "",
    "vehicle": "",
    "requested_service": "",
    "requested_time": "",
    "appointment_date": "",
    "appointment_time": "",
    "wants_booking": false,
    "suggested_reply": ""
}}


RULES:

- Unknown values must be exactly:
  "Not provided"

- Remember information earlier
  in THIS conversation.

- Never invent customer information.

- Never invent prices.

- Never invent availability.

- Never claim an appointment is confirmed
  until the backend confirms it.

- Convert relative dates such as:
  tomorrow,
  Saturday,
  next Monday

  into YYYY-MM-DD.

- appointment_date format:
  YYYY-MM-DD

- appointment_time format:
  HH:MM

- 2 PM becomes:
  14:00

- wants_booking is true only when
  the customer clearly wants the appointment booked.

- Asking whether a time is available
  does NOT mean they want it booked.

- Suggested replies should be short,
  friendly,
  and professional.

- Return ONLY JSON.
""",

        input=conversation
    )


    try:

        lead_data = json.loads(
            response.output_text
        )


    except json.JSONDecodeError:

        return {
            "response":
                "Sorry, I had trouble processing that message.",

            "lead_status":
                "error",

            "booking_status":
                "none"
        }


    phone_number = normalize_phone(
        lead_data[
            "phone_number"
        ]
    )


    suggested_reply = lead_data[
        "suggested_reply"
    ]


    lead_status = "collecting"

    booking_status = "none"


    # =====================================
    # SAVE / UPDATE LEAD
    # =====================================

    lead_complete = (

        lead_data[
            "customer_name"
        ]
        != "Not provided"

        and

        phone_number
        != "Not provided"

        and

        lead_data[
            "vehicle"
        ]
        != "Not provided"

        and

        lead_data[
            "requested_service"
        ]
        != "Not provided"

    )


    if lead_complete:

        existing_lead = find_lead(
            phone_number
        )


        if existing_lead:

            update_lead(

                lead_data[
                    "customer_name"
                ],

                phone_number,

                lead_data[
                    "email"
                ],

                lead_data[
                    "vehicle"
                ],

                lead_data[
                    "requested_service"
                ],

                lead_data[
                    "requested_time"
                ]

            )

            lead_status = "updated"


        else:

            save_lead(

                lead_data[
                    "customer_name"
                ],

                phone_number,

                lead_data[
                    "email"
                ],

                lead_data[
                    "vehicle"
                ],

                lead_data[
                    "requested_service"
                ],

                lead_data[
                    "requested_time"
                ]

            )

            lead_status = "saved"


    # =====================================
    # BOOKING
    # =====================================

    wants_booking = lead_data.get(
        "wants_booking",
        False
    )


    appointment_date = lead_data.get(
        "appointment_date",
        "Not provided"
    )


    appointment_time = lead_data.get(
        "appointment_time",
        "Not provided"
    )


    booking_ready = (

        wants_booking is True

        and

        lead_complete

        and

        appointment_date
        not in [
            "",
            "Not provided"
        ]

        and

        appointment_time
        not in [
            "",
            "Not provided"
        ]

    )


    if booking_ready:

        result = create_appointment(

            lead_data[
                "customer_name"
            ],

            phone_number,

            lead_data[
                "vehicle"
            ],

            lead_data[
                "requested_service"
            ],

            appointment_date,

            appointment_time

        )


        # =================================
        # BOOKED
        # =================================

        if result["success"]:

            booking_status = "booked"


            readable_date = datetime.strptime(
                appointment_date,
                "%Y-%m-%d"
            ).strftime(
                "%A, %B %d"
            )


            readable_time = datetime.strptime(
                appointment_time,
                "%H:%M"
            ).strftime(
                "%I:%M %p"
            ).lstrip("0")


            suggested_reply = (

                f"You're confirmed for "
                f"{readable_date} at "
                f"{readable_time} for "
                f"{lead_data['requested_service']}. "
                f"We'll see you then!"

            )


            existing_lead = find_lead(
                phone_number
            )


            if existing_lead:

                update_lead_status(
                    existing_lead[
                        "id"
                    ],
                    "Booked"
                )


        # =================================
        # NOT AVAILABLE
        # =================================

        else:

            booking_status = "unavailable"


            alternative_text = (
                format_available_slots(
                    result[
                        "alternatives"
                    ]
                )
            )


            suggested_reply = (

                result["reason"]
                + " "
                + alternative_text

            )


    # =====================================
    # SAVE RESPONSE TO MEMORY
    # =====================================

    conversation.append({
        "role": "assistant",
        "content": suggested_reply
    })


    return {

        "response":
            suggested_reply,

        "lead_status":
            lead_status,

        "booking_status":
            booking_status

    }