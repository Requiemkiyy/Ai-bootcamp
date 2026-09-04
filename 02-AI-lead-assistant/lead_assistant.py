from openai import OpenAI
import json
import traceback

from datetime import datetime, timedelta

from database import get_connection


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

            time_object = datetime.strptime(
                appointment_time,
                "%H:%M"
            )

            readable_date = date_object.strftime(
                "%A, %B %d, %Y"
            )

            readable_time = time_object.strftime(
                "%I:%M %p"
            ).lstrip("0")

            return (
                f"{readable_date} at "
                f"{readable_time}"
            )

        except ValueError:

            return (
                f"{appointment_date} at "
                f"{appointment_time}"
            )

    if appointment_date != "Not provided":

        return appointment_date

    return appointment_time


# =====================================
# SERVICE DURATIONS
# =====================================

def get_service_duration(service):

    service = clean_value(service)

    if service == "Not provided":
        return None

    service_lower = service.lower()

    duration = None

    if (
        "full" in service_lower
        and "interior" in service_lower
        and "exterior" in service_lower
    ):

        duration = 180

    elif "interior" in service_lower:

        duration = 120

    elif "exterior" in service_lower:

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

    if clean_phone == "Not provided":
        return None

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

    try:

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
        """, (
            customer_name,
            normalize_phone(
                phone_number
            ),
            email,
            vehicle,
            requested_service,
            requested_time,
            existing_lead["id"]
        ))

        conn.commit()

        return True

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()


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

    try:

        cursor.execute("""
            UPDATE leads
            SET status = ?
            WHERE id = ?
        """, (
            new_status,
            lead_id
        ))

        conn.commit()

        return True

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()


def delete_lead(
    lead_id
):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            DELETE FROM leads
            WHERE id = ?
        """, (
            lead_id,
        ))

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

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

    except (
        ValueError,
        TypeError
    ):

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
            (
                f"{appointment_date} "
                f"{appointment_time}"
            ),
            "%Y-%m-%d %H:%M"
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
                "I need a valid detailing service before booking that."
        }

    opening_time = datetime.strptime(
        (
            f"{appointment_date} "
            f"{hours['open']}"
        ),
        "%Y-%m-%d %H:%M"
    )

    closing_time = datetime.strptime(
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
        "start":
            requested_start,
        "end":
            requested_end,
        "duration":
            duration
    }


# =====================================
# APPOINTMENT FUNCTIONS
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
# APPOINTMENT CONFLICT CHECK
# =====================================

def appointment_slot_available(
    appointment_date,
    appointment_time,
    service
):

    validation = (
        validate_appointment_time(
            appointment_date,
            appointment_time,
            service
        )
    )

    if not validation["valid"]:

        return validation

    requested_start = (
        validation["start"]
    )

    requested_end = (
        validation["end"]
    )

    appointments = (
        get_appointments_for_date(
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
            or 120
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

        hours = (
            get_business_hours(
                date_string
            )
        )

        if hours is None:
            continue

        opening = (
            datetime.strptime(
                (
                    f"{date_string} "
                    f"{hours['open']}"
                ),
                "%Y-%m-%d %H:%M"
            )
        )

        closing = (
            datetime.strptime(
                (
                    f"{date_string} "
                    f"{hours['close']}"
                ),
                "%Y-%m-%d %H:%M"
            )
        )

        slot = opening

        if (
            day.date()
            == datetime.now().date()
        ):

            while (
                slot
                < datetime.now()
            ):

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
                    date_string,
                    time_string,
                    service
                )
            )

            if availability[
                "valid"
            ]:

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

                    return (
                        available_slots
                    )

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

        date_object = (
            datetime.strptime(
                slot["date"],
                "%Y-%m-%d"
            )
        )

        time_object = (
            datetime.strptime(
                slot["time"],
                "%H:%M"
            )
        )

        readable_date = (
            date_object.strftime(
                "%A, %B %d"
            )
        )

        readable_time = (
            time_object.strftime(
                "%I:%M %p"
            )
            .lstrip("0")
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
    customer_name,
    phone_number,
    vehicle,
    service,
    appointment_date,
    appointment_time
):

    availability = (
        appointment_slot_available(
            appointment_date,
            appointment_time,
            service
        )
    )

    if not availability["valid"]:

        alternatives = (
            find_available_slots(
                appointment_date,
                service,
                max_slots=3,
                days_to_search=7
            )
        )

        return {
            "success": False,
            "reason":
                availability[
                    "reason"
                ],
            "alternatives":
                alternatives
        }

    conn = get_connection()
    cursor = conn.cursor()

    try:

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

    except Exception:

        conn.rollback()
        raise

    finally:

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

    if (
        new_status
        not in allowed_statuses
    ):
        return False

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            UPDATE appointments
            SET status = ?
            WHERE id = ?
        """, (
            new_status,
            appointment_id
        ))

        conn.commit()

        return True

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()


def delete_appointment(
    appointment_id
):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            DELETE FROM appointments
            WHERE id = ?
        """, (
            appointment_id,
        ))

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

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


def create_session():

    return {

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

        "messages": []
    }


# =====================================
# SAFE AI JSON PARSER
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
# UPDATE CUSTOMER MEMORY
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
        "requested_time",
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
# AI ASSISTANT
# =====================================

def process_customer_message(
    customer_message,
    session_id
):

    try:

        # -------------------------------------
        # CREATE / LOAD SESSION
        # -------------------------------------

        if (
            session_id
            not in conversations
        ):

            conversations[
                session_id
            ] = create_session()

        session = conversations[
            session_id
        ]

        customer_data = session[
            "customer_data"
        ]

        messages = session[
            "messages"
        ]


        # -------------------------------------
        # SAVE CUSTOMER MESSAGE
        # -------------------------------------

        messages.append({
            "role": "user",
            "content":
                customer_message
        })

        if len(messages) > 20:

            messages[:] = (
                messages[-20:]
            )

        today = (
            datetime.now()
            .strftime(
                "%Y-%m-%d"
            )
        )


        # =====================================
        # OPENAI REQUEST
        # =====================================

        response = (
            client.responses.create(

                model=
                    "gpt-5.4-mini",

                instructions=f"""
You are the customer-facing AI receptionist
for Freedom Auto Detailing.

TODAY'S DATE:
{today}

BUSINESS INFORMATION:

{business_info}

KNOWN CUSTOMER INFORMATION:

{json.dumps(customer_data)}

You are having a normal conversation with a customer.

Your job is to understand the customer's latest message,
preserve information learned earlier, collect missing
information, and produce a short friendly reply.

INFORMATION TO COLLECT:

- customer name
- phone number
- email if provided
- vehicle
- requested service
- requested date
- requested time

IMPORTANT RULES:

- Never erase information already shown in
  KNOWN CUSTOMER INFORMATION.

- Never invent customer information.

- Never invent prices.

- Never invent availability.

- Never say an appointment is confirmed.
  Python handles the final booking.

- Unknown information must be exactly:
  "Not provided"

- Understand short replies using conversation context.

Examples:

Assistant:
"What service would you like?"

Customer:
"Full interior and exterior"

That means the requested service is
Full Interior + Exterior Detail.

Assistant:
"What day and time works for you?"

Customer:
"Saturday at 1pm"

That means:

appointment_date:
the correct upcoming Saturday in YYYY-MM-DD

appointment_time:
13:00

requested_time:
a readable version of the requested date and time

wants_booking:
true

RELATIVE DATES:

Convert relative dates such as:

tomorrow
Saturday
next Saturday
Monday
next Monday

into YYYY-MM-DD based on TODAY'S DATE.

appointment_date format:
YYYY-MM-DD

appointment_time format:
HH:MM

Examples:

1 PM = 13:00
1:30 PM = 13:30
2 PM = 14:00

BOOKING INTENT:

wants_booking should be true when the customer is
actively trying to schedule the service.

Examples that indicate booking intent:

"Saturday at 1pm"
"I want Saturday"
"Book me for Saturday"
"Can I come tomorrow at 2?"
"Yes that time works"

If the customer is only asking a general question like:

"Are you open Saturday?"

then wants_booking should be false.

LEAD COLLECTION:

If the customer wants an appointment but their name
or phone number is missing, ask for ONE of those
missing pieces in suggested_reply.

Do not claim the appointment is booked yet.

RETURN ONLY VALID JSON.

Use exactly these keys:

{{
    "customer_name": "Not provided",
    "phone_number": "Not provided",
    "email": "Not provided",
    "vehicle": "Not provided",
    "requested_service": "Not provided",
    "requested_time": "Not provided",
    "appointment_date": "Not provided",
    "appointment_time": "Not provided",
    "wants_booking": false,
    "suggested_reply": ""
}}
""",

                input=messages
            )
        )


        # =====================================
        # PARSE AI RESPONSE
        # =====================================

        lead_data = parse_ai_json(
            response.output_text
        )


        # =====================================
        # UPDATE CUSTOMER MEMORY
        # =====================================

        update_customer_memory(
            customer_data,
            lead_data
        )


        # =====================================
        # GET CURRENT CUSTOMER DATA
        # =====================================

        customer_name = (
            clean_value(
                customer_data.get(
                    "customer_name"
                )
            )
        )

        phone_number = (
            normalize_phone(
                customer_data.get(
                    "phone_number"
                )
            )
        )

        email = (
            clean_value(
                customer_data.get(
                    "email"
                )
            )
        )

        vehicle = (
            clean_value(
                customer_data.get(
                    "vehicle"
                )
            )
        )

        requested_service = (
            clean_value(
                customer_data.get(
                    "requested_service"
                )
            )
        )

        appointment_date = (
            clean_value(
                customer_data.get(
                    "appointment_date"
                )
            )
        )

        appointment_time = (
            clean_value(
                customer_data.get(
                    "appointment_time"
                )
            )
        )


        # =====================================
        # FIX REQUESTED TIME AUTOMATICALLY
        # =====================================

        generated_requested_time = (
            build_requested_time(
                appointment_date,
                appointment_time
            )
        )

        if (
            generated_requested_time
            != "Not provided"
        ):

            customer_data[
                "requested_time"
            ] = (
                generated_requested_time
            )


        requested_time = (
            clean_value(
                customer_data.get(
                    "requested_time"
                )
            )
        )


        # =====================================
        # AI REPLY
        # =====================================

        suggested_reply = (
            clean_value(
                lead_data.get(
                    "suggested_reply"
                )
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


        lead_status = (
            "collecting"
        )

        booking_status = (
            "none"
        )


        # =====================================
        # LEAD COMPLETENESS
        # =====================================

        lead_complete = (
            customer_name
            != "Not provided"

            and

            phone_number
            != "Not provided"

            and

            vehicle
            != "Not provided"

            and

            requested_service
            != "Not provided"
        )


        # =====================================
        # SAVE / UPDATE LEAD
        # =====================================

        if lead_complete:

            existing_lead = (
                find_lead(
                    phone_number
                )
            )

            if existing_lead:

                update_lead(

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


        # =====================================
        # BOOKING READY?
        # =====================================

        booking_ready = (
            wants_booking is True

            and

            lead_complete

            and

            appointment_date
            != "Not provided"

            and

            appointment_time
            != "Not provided"
        )


        # =====================================
        # CREATE BOOKING
        # =====================================

        if booking_ready:

            result = (
                create_appointment(

                    customer_name,

                    phone_number,

                    vehicle,

                    requested_service,

                    appointment_date,

                    appointment_time
                )
            )


            # ---------------------------------
            # BOOKED
            # ---------------------------------

            if result[
                "success"
            ]:

                booking_status = (
                    "booked"
                )

                readable_date = (
                    datetime.strptime(
                        appointment_date,
                        "%Y-%m-%d"
                    )
                    .strftime(
                        "%A, %B %d"
                    )
                )

                readable_time = (
                    datetime.strptime(
                        appointment_time,
                        "%H:%M"
                    )
                    .strftime(
                        "%I:%M %p"
                    )
                    .lstrip("0")
                )

                suggested_reply = (

                    f"You're confirmed for "
                    f"{readable_date} at "
                    f"{readable_time} for "
                    f"{requested_service}. "
                    f"We'll see you then!"
                )

                existing_lead = (
                    find_lead(
                        phone_number
                    )
                )

                if existing_lead:

                    update_lead_status(

                        existing_lead[
                            "id"
                        ],

                        "Booked"
                    )


            # ---------------------------------
            # UNAVAILABLE
            # ---------------------------------

            else:

                booking_status = (
                    "unavailable"
                )

                alternative_text = (
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

                    + alternative_text
                )


        # =====================================
        # SAVE ASSISTANT MESSAGE
        # =====================================

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


        # =====================================
        # RESPONSE TO WEBSITE
        # =====================================

        return {

            "response":
                suggested_reply,

            "lead_status":
                lead_status,

            "booking_status":
                booking_status
        }


    # =========================================
    # ERROR HANDLING
    # =========================================

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