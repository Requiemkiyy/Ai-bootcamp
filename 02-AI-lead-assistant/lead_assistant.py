from openai import OpenAI
import json
import traceback
from datetime import datetime, timedelta

from database import (
    get_connection,
    load_session,
    save_session,
    get_business_by_id,
    get_business_by_slug,
    get_default_business,
    get_services_for_business,
    get_business_hours_rows
)


# =====================================
# OPENAI
# =====================================

client = OpenAI()


# =====================================
# GENERAL HELPERS
# =====================================

def current_timestamp():

    return datetime.now().strftime(
        "%Y-%m-%d %I:%M %p"
    )


def clean_value(value):

    if value is None:
        return "Not provided"

    value = str(value).strip()

    if not value:
        return "Not provided"

    return value


def normalize_phone(phone_number):

    phone_number = clean_value(
        phone_number
    )

    if phone_number == "Not provided":
        return "Not provided"

    digits = "".join(
        character
        for character in phone_number
        if character.isdigit()
    )

    if not digits:
        return "Not provided"

    return digits


# =====================================
# CUSTOMER-FACING TIME FORMAT
# =====================================

def format_time_12_hour(time_value):

    if not time_value:
        return "Not provided"

    try:

        time_object = datetime.strptime(
            str(time_value),
            "%H:%M"
        )

        return (
            time_object
            .strftime("%I:%M %p")
            .lstrip("0")
        )

    except ValueError:

        return str(time_value)


def build_requested_time(
    appointment_date,
    appointment_time
):

    appointment_date = clean_value(
        appointment_date
    )

    appointment_time = clean_value(
        appointment_time
    )

    if (
        appointment_date == "Not provided"
        and
        appointment_time == "Not provided"
    ):
        return "Not provided"

    if (
        appointment_date != "Not provided"
        and
        appointment_time != "Not provided"
    ):

        try:

            date_object = datetime.strptime(
                appointment_date,
                "%Y-%m-%d"
            )

            readable_date = (
                date_object.strftime(
                    "%A, %B %d, %Y"
                )
            )

            readable_time = (
                format_time_12_hour(
                    appointment_time
                )
            )

            return (
                f"{readable_date} at "
                f"{readable_time}"
            )

        except ValueError:

            return (
                f"{appointment_date} at "
                f"{format_time_12_hour(appointment_time)}"
            )

    if appointment_date != "Not provided":
        return appointment_date

    return format_time_12_hour(
        appointment_time
    )


def is_simple_acknowledgement(message):

    clean_message = (
        message
        .strip()
        .lower()
        .replace(".", "")
        .replace("!", "")
    )

    acknowledgements = {
        "thanks",
        "thank you",
        "sounds good",
        "sound good",
        "okay",
        "ok",
        "alright",
        "alr",
        "bet",
        "perfect",
        "cool",
        "great",
        "got it",
        "see you then",
        "see you",
        "see you soon",
        "appreciate it"
    }

    return (
        clean_message
        in acknowledgements
    )


# =====================================
# BUSINESS
# =====================================

def resolve_business(
    business_id=None,
    business_slug=None
):

    business = None

    if business_id is not None:

        business = get_business_by_id(
            business_id
        )

    elif business_slug:

        business = get_business_by_slug(
            business_slug
        )

    else:

        business = get_default_business()

    return business


def get_business_services(
    business_id
):

    return get_services_for_business(
        business_id
    )


def build_business_info(
    business
):

    business_id = business["id"]

    services = get_business_services(
        business_id
    )

    hours = get_business_hours_rows(
        business_id
    )

    lines = []

    lines.append(
        f"BUSINESS:\n{business['name']}"
    )

    location = clean_value(
        business.get("location")
    )

    if location != "Not provided":

        lines.append(
            f"LOCATION:\n{location}"
        )

    lines.append("SERVICES:")

    for service in services:

        price = (
            service["price_cents"]
            / 100
        )

        duration = (
            service[
                "duration_minutes"
            ]
        )

        service_type = (
            service.get(
                "service_type",
                "service"
            )
        )

        label = (
            "ADD-ON"
            if service_type == "addon"
            else "SERVICE"
        )

        lines.append(
            (
                f"{label}: "
                f"{service['name']} - "
                f"${price:.2f} - "
                f"{duration} minutes"
            )
        )

    weekday_names = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday"
    ]

    lines.append(
        "BUSINESS HOURS:"
    )

    for row in hours:

        weekday = row["weekday"]

        day_name = (
            weekday_names[
                weekday
            ]
        )

        if row["is_closed"]:

            lines.append(
                f"{day_name}: Closed"
            )

        else:

            open_time = (
                format_time_12_hour(
                    row["open_time"]
                )
            )

            close_time = (
                format_time_12_hour(
                    row["close_time"]
                )
            )

            lines.append(
                (
                    f"{day_name}: "
                    f"{open_time} - "
                    f"{close_time}"
                )
            )

    lines.append(
        """
BOOKING RULES:

Appointments are only confirmed after the backend
successfully creates the appointment.

Never invent availability.
Never invent prices.
Never claim a booking is confirmed until Python confirms it.

Always display customer-facing times using
12-hour AM/PM format.

Examples:
09:00 = 9:00 AM
13:00 = 1:00 PM
16:00 = 4:00 PM
18:00 = 6:00 PM
"""
    )

    return "\n\n".join(
        lines
    )


# =====================================
# SERVICE MATCHING
# =====================================

def find_service(
    business_id,
    requested_service
):

    requested_service = clean_value(
        requested_service
    )

    if requested_service == "Not provided":
        return None

    requested_lower = (
        requested_service.lower()
    )

    services = get_business_services(
        business_id
    )

    # Exact match first.
    for service in services:

        if (
            service["name"].lower()
            == requested_lower
        ):

            return service

    # Partial match.
    for service in services:

        service_name = (
            service["name"]
            .lower()
        )

        if (
            service_name
            in requested_lower
            or
            requested_lower
            in service_name
        ):

            return service

    # Common detailing wording.
    for service in services:

        name = (
            service["name"]
            .lower()
        )

        if (
            "full" in requested_lower
            and
            "interior" in requested_lower
            and
            "exterior" in requested_lower
            and
            "full" in name
            and
            "interior" in name
            and
            "exterior" in name
        ):

            return service

    return None


def get_service_duration(
    business_id,
    requested_service
):

    service = find_service(
        business_id,
        requested_service
    )

    if not service:
        return None

    return int(
        service[
            "duration_minutes"
        ]
    )


# =====================================
# LEADS
# =====================================

def find_lead(
    business_id,
    phone_number
):

    clean_phone = normalize_phone(
        phone_number
    )

    if clean_phone == "Not provided":
        return None

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT *
            FROM leads
            WHERE business_id = ?
        """, (
            business_id,
        ))

        rows = cursor.fetchall()

        for row in rows:

            if (
                normalize_phone(
                    row["phone_number"]
                )
                == clean_phone
            ):

                return dict(row)

        return None

    finally:

        conn.close()


def save_lead(
    business_id,
    customer_name,
    phone_number,
    email,
    vehicle,
    requested_service,
    requested_time
):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            INSERT INTO leads (
                business_id,
                customer_name,
                phone_number,
                email,
                vehicle,
                requested_service,
                requested_time,
                status,
                created_at
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            business_id,
            customer_name,
            normalize_phone(
                phone_number
            ),
            email,
            vehicle,
            requested_service,
            requested_time,
            "New",
            current_timestamp()
        ))

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()


def update_lead(
    business_id,
    customer_name,
    phone_number,
    email,
    vehicle,
    requested_service,
    requested_time
):

    existing = find_lead(
        business_id,
        phone_number
    )

    if not existing:
        return False

    conn = get_connection()
    cursor = conn.cursor()

    try:

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
            AND business_id = ?
        """, (
            customer_name,
            normalize_phone(
                phone_number
            ),
            email,
            vehicle,
            requested_service,
            requested_time,
            existing["id"],
            business_id
        ))

        conn.commit()

        return True

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()


def update_lead_booking(
    business_id,
    phone_number,
    requested_time
):

    existing = find_lead(
        business_id,
        phone_number
    )

    if not existing:
        return False

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            UPDATE leads

            SET
                requested_time = ?,
                status = ?

            WHERE id = ?
            AND business_id = ?
        """, (
            requested_time,
            "Booked",
            existing["id"],
            business_id
        ))

        conn.commit()

        return True

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()


# =====================================
# BUSINESS HOURS LOOKUP
# =====================================

def get_hours_for_date(
    business_id,
    appointment_date
):

    try:

        date_object = (
            datetime.strptime(
                appointment_date,
                "%Y-%m-%d"
            )
        )

    except (
        ValueError,
        TypeError
    ):

        return None

    weekday = date_object.weekday()

    rows = get_business_hours_rows(
        business_id
    )

    for row in rows:

        if (
            int(row["weekday"])
            == weekday
        ):

            if row["is_closed"]:
                return None

            return {
                "open":
                    row["open_time"],

                "close":
                    row["close_time"]
            }

    return None


# =====================================
# APPOINTMENT VALIDATION
# =====================================

def validate_appointment_time(
    business_id,
    appointment_date,
    appointment_time,
    service
):

    try:

        requested_start = (
            datetime.strptime(
                (
                    f"{appointment_date} "
                    f"{appointment_time}"
                ),
                "%Y-%m-%d %H:%M"
            )
        )

    except (
        ValueError,
        TypeError
    ):

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

    hours = get_hours_for_date(
        business_id,
        appointment_date
    )

    if hours is None:

        return {
            "valid": False,
            "reason":
                "We're closed that day."
        }

    duration = get_service_duration(
        business_id,
        service
    )

    if duration is None:

        return {
            "valid": False,
            "reason":
                "I couldn't match that to one of our available services."
        }

    opening = datetime.strptime(
        (
            f"{appointment_date} "
            f"{hours['open']}"
        ),
        "%Y-%m-%d %H:%M"
    )

    closing = datetime.strptime(
        (
            f"{appointment_date} "
            f"{hours['close']}"
        ),
        "%Y-%m-%d %H:%M"
    )

    requested_end = (
        requested_start
        + timedelta(
            minutes=duration
        )
    )

    if requested_start < opening:

        return {
            "valid": False,
            "reason":
                (
                    "That time is before we open. "
                    f"We open at "
                    f"{format_time_12_hour(hours['open'])}."
                )
        }

    if requested_end > closing:

        return {
            "valid": False,
            "reason":
                (
                    "That service would run past closing time. "
                    f"We close at "
                    f"{format_time_12_hour(hours['close'])}."
                )
        }

    return {
        "valid": True,
        "start":
            requested_start,
        "end":
            requested_end,
        "duration":
            duration
    }


# =====================================
# APPOINTMENT QUERIES
# =====================================

def get_appointments_for_date(
    business_id,
    appointment_date
):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT *
            FROM appointments

            WHERE business_id = ?
            AND appointment_date = ?
            AND status != 'Cancelled'

            ORDER BY appointment_time
        """, (
            business_id,
            appointment_date
        ))

        rows = cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


def find_customer_appointment(
    business_id,
    phone_number,
    appointment_date,
    appointment_time
):

    clean_phone = normalize_phone(
        phone_number
    )

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT *
            FROM appointments

            WHERE business_id = ?
            AND appointment_date = ?
            AND appointment_time = ?
            AND status != 'Cancelled'
        """, (
            business_id,
            appointment_date,
            appointment_time
        ))

        rows = cursor.fetchall()

        for row in rows:

            if (
                normalize_phone(
                    row["phone_number"]
                )
                == clean_phone
            ):

                return dict(row)

        return None

    finally:

        conn.close()


# =====================================
# CONFLICT CHECK
# =====================================

def appointment_slot_available(
    business_id,
    appointment_date,
    appointment_time,
    service
):

    validation = (
        validate_appointment_time(
            business_id,
            appointment_date,
            appointment_time,
            service
        )
    )

    if not validation["valid"]:
        return validation

    requested_start = validation[
        "start"
    ]

    requested_end = validation[
        "end"
    ]

    appointments = (
        get_appointments_for_date(
            business_id,
            appointment_date
        )
    )

    for appointment in appointments:

        try:

            existing_start = (
                datetime.strptime(
                    (
                        f"{appointment['appointment_date']} "
                        f"{appointment['appointment_time']}"
                    ),
                    "%Y-%m-%d %H:%M"
                )
            )

        except (
            ValueError,
            TypeError
        ):

            continue

        existing_duration = (
            appointment[
                "duration_minutes"
            ]
            or 60
        )

        existing_end = (
            existing_start
            + timedelta(
                minutes=
                    existing_duration
            )
        )

        overlap = (
            requested_start
            < existing_end
            and
            requested_end
            > existing_start
        )

        if overlap:

            return {
                "valid": False,
                "reason":
                    "That appointment time is already taken."
            }

    return validation


# =====================================
# AVAILABLE SLOTS
# =====================================

def find_available_slots(
    business_id,
    starting_date,
    service,
    max_slots=3,
    days_to_search=7
):

    duration = get_service_duration(
        business_id,
        service
    )

    if duration is None:
        return []

    try:

        search_date = (
            datetime.strptime(
                starting_date,
                "%Y-%m-%d"
            )
        )

    except (
        ValueError,
        TypeError
    ):

        search_date = datetime.now()

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

        date_string = (
            day.strftime(
                "%Y-%m-%d"
            )
        )

        hours = get_hours_for_date(
            business_id,
            date_string
        )

        if hours is None:
            continue

        opening = datetime.strptime(
            (
                f"{date_string} "
                f"{hours['open']}"
            ),
            "%Y-%m-%d %H:%M"
        )

        closing = datetime.strptime(
            (
                f"{date_string} "
                f"{hours['close']}"
            ),
            "%Y-%m-%d %H:%M"
        )

        slot = opening

        if (
            day.date()
            == datetime.now().date()
        ):

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

            time_string = (
                slot.strftime(
                    "%H:%M"
                )
            )

            availability = (
                appointment_slot_available(
                    business_id,
                    date_string,
                    time_string,
                    service
                )
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


def format_available_slots(
    slots
):

    if not slots:

        return (
            "I couldn't find another open appointment "
            "within the next week."
        )

    formatted = []

    for slot in slots:

        date_object = datetime.strptime(
            slot["date"],
            "%Y-%m-%d"
        )

        readable_date = (
            date_object.strftime(
                "%A, %B %d"
            )
        )

        readable_time = (
            format_time_12_hour(
                slot["time"]
            )
        )

        formatted.append(
            (
                f"{readable_date} at "
                f"{readable_time}"
            )
        )

    return (
        "The next available times are: "
        + ", ".join(
            formatted
        )
        + "."
    )


# =====================================
# CREATE APPOINTMENT
# =====================================

def create_appointment(
    business_id,
    customer_name,
    phone_number,
    vehicle,
    service,
    appointment_date,
    appointment_time
):

    existing_customer_booking = (
        find_customer_appointment(
            business_id,
            phone_number,
            appointment_date,
            appointment_time
        )
    )

    if existing_customer_booking:

        return {
            "success": True,
            "already_exists": True
        }

    availability = (
        appointment_slot_available(
            business_id,
            appointment_date,
            appointment_time,
            service
        )
    )

    if not availability["valid"]:

        alternatives = (
            find_available_slots(
                business_id,
                appointment_date,
                service,
                max_slots=3,
                days_to_search=7
            )
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

    try:

        cursor.execute("""
            INSERT INTO appointments (
                business_id,
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

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            business_id,
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

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()

    return {
        "success": True,
        "already_exists": False
    }


# =====================================
# CREATE SESSION
# =====================================

def create_session(
    business_id
):

    return {

        "business_id":
            business_id,

        "customer_data": {

            "customer_name":
                "Not provided",

            "phone_number":
                "Not provided",

            "email":
                "Not provided",

            "vehicle":
                "Not provided",

            "requested_service":
                "Not provided",

            "requested_time":
                "Not provided",

            "appointment_date":
                "Not provided",

            "appointment_time":
                "Not provided"
        },

        "booking": {

            "confirmed":
                False,

            "appointment_date":
                "Not provided",

            "appointment_time":
                "Not provided"
        },

        "messages": []
    }


# =====================================
# JSON PARSER
# =====================================

def parse_ai_json(text):

    if not text:

        raise ValueError(
            "AI returned an empty response."
        )

    text = text.strip()

    if text.startswith("```"):

        if text.startswith(
            "```json"
        ):

            text = text[7:]

        else:

            text = text[3:]

        if text.endswith(
            "```"
        ):

            text = text[:-3]

        text = text.strip()

    try:

        return json.loads(
            text
        )

    except json.JSONDecodeError:

        start = text.find("{")
        end = text.rfind("}")

        if (
            start != -1
            and
            end != -1
            and
            end > start
        ):

            return json.loads(
                text[
                    start:
                    end + 1
                ]
            )

        raise


# =====================================
# CUSTOMER MEMORY
# =====================================

def update_customer_memory(
    customer_data,
    lead_data
):

    fields = [
        "customer_name",
        "phone_number",
        "email",
        "vehicle",
        "requested_service",
        "appointment_date",
        "appointment_time"
    ]

    for field in fields:

        new_value = clean_value(
            lead_data.get(
                field,
                "Not provided"
            )
        )

        if (
            new_value
            != "Not provided"
        ):

            customer_data[
                field
            ] = new_value


# =====================================
# PROCESS CUSTOMER MESSAGE
# =====================================

def process_customer_message(
    customer_message,
    session_id,
    business_id=None,
    business_slug=None
):

    try:

        # =================================
        # BUSINESS
        # =================================

        business = resolve_business(
            business_id=
                business_id,
            business_slug=
                business_slug
        )

        if not business:

            return {
                "response":
                    "Sorry, this business is currently unavailable.",

                "lead_status":
                    "error",

                "booking_status":
                    "error"
            }

        business_id = (
            business["id"]
        )

        business_info = (
            build_business_info(
                business
            )
        )


        # =================================
        # LOAD SESSION
        # =================================

        session = load_session(
            session_id,
            business_id
        )

        if session is None:

            session = create_session(
                business_id
            )

        session[
            "business_id"
        ] = business_id

        customer_data = (
            session[
                "customer_data"
            ]
        )

        booking_data = (
            session[
                "booking"
            ]
        )

        messages = (
            session[
                "messages"
            ]
        )


        # =================================
        # USER MESSAGE
        # =================================

        messages.append({
            "role":
                "user",

            "content":
                customer_message
        })

        if len(messages) > 20:

            messages[:] = (
                messages[-20:]
            )


        # =================================
        # POST-BOOKING RESPONSE
        # =================================

        if (
            booking_data.get(
                "confirmed",
                False
            )
            and
            is_simple_acknowledgement(
                customer_message
            )
        ):

            reply = (
                "Sounds good — see you then!"
            )

            messages.append({
                "role":
                    "assistant",

                "content":
                    reply
            })

            save_session(
                session_id,
                session,
                business_id
            )

            return {
                "response":
                    reply,

                "lead_status":
                    "updated",

                "booking_status":
                    "already_booked"
            }


        # =================================
        # AI
        # =================================

        today = (
            datetime.now()
            .strftime(
                "%Y-%m-%d"
            )
        )

        response = (
            client.responses.create(

                model=
                    "gpt-5.4-mini",

                instructions=f"""
You are the customer-facing AI receptionist
for the business below.

TODAY'S DATE:
{today}

BUSINESS INFORMATION:

{business_info}

KNOWN CUSTOMER INFORMATION:

{json.dumps(customer_data)}

CURRENT BOOKING STATE:

{json.dumps(booking_data)}

You must use ONLY the business information supplied above.

Do not invent services.
Do not invent prices.
Do not invent hours.
Do not invent availability.

IMPORTANT CUSTOMER-FACING TIME RULE:

Always speak to customers using 12-hour AM/PM time.

Say:
9:00 AM
1:00 PM
4:00 PM
6:00 PM

Never show customers:
09:00
13:00
16:00
18:00

Internally, appointment_time must still use HH:MM
24-hour format for the backend.

Your job is to:

- answer customer questions
- understand what service they want
- collect their name
- collect their phone number
- collect vehicle information when relevant
- understand requested appointment date/time
- help them schedule

Unknown information must be exactly:
"Not provided"

Never claim an appointment is confirmed.
Python confirms bookings.

Convert relative dates such as:
tomorrow
Saturday
next Saturday
Monday

into YYYY-MM-DD.

appointment_time must use HH:MM.

wants_booking should be true only when the customer
is actively choosing or requesting a booking time.

If CURRENT BOOKING STATE shows confirmed = true,
do not attempt to book the same appointment again.

RETURN ONLY VALID JSON.

Use exactly these keys:

{{
    "customer_name": "Not provided",
    "phone_number": "Not provided",
    "email": "Not provided",
    "vehicle": "Not provided",
    "requested_service": "Not provided",
    "appointment_date": "Not provided",
    "appointment_time": "Not provided",
    "wants_booking": false,
    "suggested_reply": ""
}}
""",

                input=
                    messages
            )
        )


        # =================================
        # PARSE AI
        # =================================

        lead_data = parse_ai_json(
            response.output_text
        )

        update_customer_memory(
            customer_data,
            lead_data
        )


        # =================================
        # CUSTOMER DATA
        # =================================

        customer_name = clean_value(
            customer_data.get(
                "customer_name"
            )
        )

        phone_number = normalize_phone(
            customer_data.get(
                "phone_number"
            )
        )

        email = clean_value(
            customer_data.get(
                "email"
            )
        )

        vehicle = clean_value(
            customer_data.get(
                "vehicle"
            )
        )

        requested_service = clean_value(
            customer_data.get(
                "requested_service"
            )
        )

        appointment_date = clean_value(
            customer_data.get(
                "appointment_date"
            )
        )

        appointment_time = clean_value(
            customer_data.get(
                "appointment_time"
            )
        )


        # =================================
        # NORMALIZE SERVICE
        # =================================

        matched_service = find_service(
            business_id,
            requested_service
        )

        if matched_service:

            requested_service = (
                matched_service["name"]
            )

            customer_data[
                "requested_service"
            ] = requested_service


        # =================================
        # REQUESTED TIME
        # =================================

        requested_time = (
            build_requested_time(
                appointment_date,
                appointment_time
            )
        )

        customer_data[
            "requested_time"
        ] = requested_time


        # =================================
        # AI REPLY
        # =================================

        suggested_reply = clean_value(
            lead_data.get(
                "suggested_reply"
            )
        )

        if (
            suggested_reply
            == "Not provided"
        ):

            suggested_reply = (
                "What else can I help you with?"
            )


        wants_booking = (
            lead_data.get(
                "wants_booking",
                False
            )
        )

        if isinstance(
            wants_booking,
            str
        ):

            wants_booking = (
                wants_booking
                .strip()
                .lower()
                == "true"
            )


        lead_status = "collecting"
        booking_status = "none"


        # =================================
        # LEAD COMPLETE
        # =================================

        lead_complete = (
            customer_name
            != "Not provided"

            and

            phone_number
            != "Not provided"

            and

            requested_service
            != "Not provided"
        )


        # =================================
        # MISSING BOOKING INFORMATION
        # =================================

        # Never let model-generated internal booking instructions reach
        # the customer when they are trying to book but required contact
        # information is still missing. Ask for the missing fields
        # deterministically instead.
        if (
            wants_booking is True
            and
            not lead_complete
        ):

            missing_fields = []

            if customer_name == "Not provided":
                missing_fields.append("name")

            if phone_number == "Not provided":
                missing_fields.append("phone number")

            if requested_service == "Not provided":
                missing_fields.append("service")

            if len(missing_fields) == 1:
                missing_text = missing_fields[0]

            elif len(missing_fields) == 2:
                missing_text = (
                    missing_fields[0]
                    + " and "
                    + missing_fields[1]
                )

            else:
                missing_text = (
                    ", ".join(
                        missing_fields[:-1]
                    )
                    + ", and "
                    + missing_fields[-1]
                )

            suggested_reply = (
                "Absolutely! To finish setting that up, "
                "what's your "
                + missing_text
                + "?"
            )

        # =================================
        # SAVE LEAD
        # =================================

        if lead_complete:

            existing = find_lead(
                business_id,
                phone_number
            )

            if existing:

                update_lead(
                    business_id,
                    customer_name,
                    phone_number,
                    email,
                    vehicle,
                    requested_service,
                    requested_time
                )

                lead_status = (
                    "updated"
                )

            else:

                save_lead(
                    business_id,
                    customer_name,
                    phone_number,
                    email,
                    vehicle,
                    requested_service,
                    requested_time
                )

                lead_status = (
                    "saved"
                )


        # =================================
        # ALREADY BOOKED
        # =================================

        if booking_data.get(
            "confirmed",
            False
        ):

            booking_status = (
                "already_booked"
            )

            confirmed_requested_time = (
                build_requested_time(

                    booking_data.get(
                        "appointment_date"
                    ),

                    booking_data.get(
                        "appointment_time"
                    )
                )
            )

            if lead_complete:

                update_lead_booking(
                    business_id,
                    phone_number,
                    confirmed_requested_time
                )

            messages.append({
                "role":
                    "assistant",

                "content":
                    suggested_reply
            })

            save_session(
                session_id,
                session,
                business_id
            )

            return {
                "response":
                    suggested_reply,

                "lead_status":
                    lead_status,

                "booking_status":
                    booking_status
            }


        # =================================
        # BOOKING READY
        # =================================

        booking_ready = (
            wants_booking is True

            and

            lead_complete

            and

            matched_service
            is not None

            and

            appointment_date
            != "Not provided"

            and

            appointment_time
            != "Not provided"
        )


        # =================================
        # CREATE BOOKING
        # =================================

        if booking_ready:

            result = create_appointment(
                business_id,
                customer_name,
                phone_number,
                vehicle,
                requested_service,
                appointment_date,
                appointment_time
            )

            if result["success"]:

                booking_status = (
                    "booked"
                )

                requested_time = (
                    build_requested_time(
                        appointment_date,
                        appointment_time
                    )
                )

                customer_data[
                    "requested_time"
                ] = requested_time

                booking_data[
                    "confirmed"
                ] = True

                booking_data[
                    "appointment_date"
                ] = appointment_date

                booking_data[
                    "appointment_time"
                ] = appointment_time

                update_lead_booking(
                    business_id,
                    phone_number,
                    requested_time
                )

                if result.get(
                    "already_exists",
                    False
                ):

                    suggested_reply = (
                        f"You're already confirmed for "
                        f"{requested_time} for "
                        f"{requested_service}."
                    )

                else:

                    suggested_reply = (
                        f"You're confirmed for "
                        f"{requested_time} for "
                        f"{requested_service}. "
                        f"We'll see you then!"
                    )

            else:

                booking_status = (
                    "unavailable"
                )

                alternatives = (
                    format_available_slots(
                        result.get(
                            "alternatives",
                            []
                        )
                    )
                )

                suggested_reply = (
                    result.get(
                        "reason",
                        "That time isn't available."
                    )
                    + " "
                    + alternatives
                )


        # =================================
        # SAVE SESSION
        # =================================

        messages.append({
            "role":
                "assistant",

            "content":
                suggested_reply
        })

        if len(messages) > 20:

            messages[:] = (
                messages[-20:]
            )

        save_session(
            session_id,
            session,
            business_id
        )


        # =================================
        # RETURN
        # =================================

        return {

            "response":
                suggested_reply,

            "lead_status":
                lead_status,

            "booking_status":
                booking_status
        }


    except Exception as error:

        print(
            "\n"
            "=====================================\n"
            "LEAD ASSISTANT ERROR\n"
            "====================================="
        )

        traceback.print_exc()

        print(
            "ERROR:",
            repr(error)
        )

        print(
            "=====================================\n"
        )

        return {

            "response":
                "Sorry, I had trouble processing that. Please try again.",

            "lead_status":
                "error",

            "booking_status":
                "error"
        }