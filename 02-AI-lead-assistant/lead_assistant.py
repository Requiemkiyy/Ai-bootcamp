from openai import OpenAI
import sqlite3
import json

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel


# =====================================
# FASTAPI SETUP
# =====================================

app = FastAPI()


# =====================================
# OPENAI SETUP
# =====================================

client = OpenAI()


# =====================================
# DATABASE SETUP
# =====================================

conn = sqlite3.connect(
    "leads.db",
    check_same_thread=False
)

cursor = conn.cursor()


# =====================================
# LEADS TABLE
# =====================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT,
    phone_number TEXT,
    email TEXT,
    vehicle TEXT,
    requested_service TEXT,
    requested_time TEXT
)
""")


# =====================================
# CONVERSATION TABLE
# =====================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL
)
""")

conn.commit()


# =====================================
# LEAD DATABASE FUNCTIONS
# =====================================

def save_lead(
    customer_name,
    phone_number,
    email,
    vehicle,
    requested_service,
    requested_time
):
    cursor.execute("""
    INSERT INTO leads (
        customer_name,
        phone_number,
        email,
        vehicle,
        requested_service,
        requested_time
    )
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        customer_name,
        phone_number,
        email,
        vehicle,
        requested_service,
        requested_time
    ))

    conn.commit()


def find_lead(phone_number):
    cursor.execute("""
    SELECT *
    FROM leads
    WHERE phone_number = ?
    """, (phone_number,))

    return cursor.fetchone()


def update_lead(
    customer_name,
    phone_number,
    email,
    vehicle,
    requested_service,
    requested_time
):
    cursor.execute("""
    UPDATE leads
    SET
        customer_name = ?,
        email = ?,
        vehicle = ?,
        requested_service = ?,
        requested_time = ?
    WHERE phone_number = ?
    """, (
        customer_name,
        email,
        vehicle,
        requested_service,
        requested_time,
        phone_number
    ))

    conn.commit()


# =====================================
# CONVERSATION DATABASE FUNCTIONS
# =====================================

def save_message(
    conversation_id,
    role,
    content
):
    cursor.execute("""
    INSERT INTO conversations (
        conversation_id,
        role,
        content
    )
    VALUES (?, ?, ?)
    """, (
        conversation_id,
        role,
        content
    ))

    conn.commit()


def get_conversation(conversation_id):
    cursor.execute("""
    SELECT role, content
    FROM conversations
    WHERE conversation_id = ?
    ORDER BY id ASC
    """, (conversation_id,))

    rows = cursor.fetchall()

    conversation = []

    for row in rows:
        conversation.append({
            "role": row[0],
            "content": row[1]
        })

    return conversation


# =====================================
# PHONE CLEANING
# =====================================

def normalize_phone(phone_number):
    if not phone_number:
        return "Not provided"

    if phone_number == "Not provided":
        return "Not provided"

    digits = ""

    for character in phone_number:
        if character.isdigit():
            digits += character

    if not digits:
        return "Not provided"

    return digits


# =====================================
# BUSINESS INFORMATION
# =====================================

business_info = """
BUSINESS: Freedom Auto Detailing

SERVICES:
Interior Detail - $120
Exterior Detail - $80
Full Interior + Exterior Detail - $180

ADD-ONS:
Pet Hair Removal - $40
Seat Shampoo - $35
Headlight Restoration - $50

HOURS:
Monday-Friday: 9 AM - 6 PM
Saturday: 10 AM - 4 PM
Sunday: Closed

SERVICE AREA:
Columbus, Ohio

RULES:
Never invent a price.
If a customer requests something not listed,
say that a team member needs to confirm availability and pricing.
"""


# =====================================
# REQUEST MODEL
# =====================================

class CustomerMessage(BaseModel):
    conversation_id: str
    message: str


# =====================================
# HOME ROUTE
# =====================================

@app.get("/")
def home():
    return {
        "message": "AI Lead Assistant API is running"
    }
@app.get("/demo")
def demo():
    return FileResponse("chat.html")

# =====================================
# CHAT ROUTE
# =====================================

@app.post("/chat")
def chat(customer: CustomerMessage):

    conversation_id = customer.conversation_id
    customer_message = customer.message

    # =====================================
    # SAVE CUSTOMER MESSAGE
    # =====================================

    save_message(
        conversation_id,
        "user",
        customer_message
    )

    # =====================================
    # LOAD THIS CUSTOMER'S HISTORY
    # =====================================

    conversation = get_conversation(
        conversation_id
    )

    # =====================================
    # SEND CONVERSATION TO OPENAI
    # =====================================

    response = client.responses.create(
        model="gpt-5.4-mini",

        instructions=f"""
You are a lead assistant for a local car detailing business.

Here is the business information you must follow:

{business_info}

Return ONLY valid JSON using exactly this structure:

{{
    "lead_type": "",
    "customer_name": "",
    "phone_number": "",
    "email": "",
    "vehicle": "",
    "requested_service": "",
    "requested_time": "",
    "missing_information": "",
    "suggested_reply": ""
}}

RULES:

- Use ONLY the business information provided above.
- Never invent a price, service, hour, or policy.
- If the customer asks for something not listed,
  say a team member must confirm it.

- If information is unknown, use "Not provided".
- Never invent a customer name, phone number, or email.

- Remember information provided earlier in THIS
  customer's conversation.

- Do not repeatedly ask for information already provided.

- Try to collect:
  - Customer name
  - Phone number or email
  - Vehicle
  - Requested service
  - Requested date/time

- The Suggested Reply should be friendly,
  professional, and short.

- NEVER tell a customer that an appointment is booked,
  scheduled, confirmed, or "all set" unless a real
  booking system has successfully confirmed the appointment.

- Requested dates and times are ONLY requests
  until confirmed.

- If there is no booking confirmation,
  tell the customer their appointment request
  still needs confirmation.

- Return ONLY valid JSON.
- Do not include markdown.
- Do not put anything outside the JSON.
""",

        input=conversation
    )

    # =====================================
    # PROCESS AI RESPONSE
    # =====================================

    try:

        lead_data = json.loads(
            response.output_text
        )

        suggested_reply = lead_data[
            "suggested_reply"
        ]

        # =====================================
        # SAVE AI RESPONSE TO DATABASE
        # =====================================

        save_message(
            conversation_id,
            "assistant",
            suggested_reply
        )

        # =====================================
        # CLEAN PHONE NUMBER
        # =====================================

        phone_number = normalize_phone(
            lead_data["phone_number"]
        )

        lead_status = "collecting_information"

        # =====================================
        # CHECK IF LEAD IS READY
        # =====================================

        if (
            lead_data["customer_name"] != "Not provided"
            and phone_number != "Not provided"
            and lead_data["vehicle"] != "Not provided"
            and lead_data["requested_service"] != "Not provided"
        ):

            existing_lead = find_lead(
                phone_number
            )

            # =====================================
            # RETURNING LEAD
            # =====================================

            if existing_lead:

                update_lead(
                    lead_data["customer_name"],
                    phone_number,
                    lead_data["email"],
                    lead_data["vehicle"],
                    lead_data["requested_service"],
                    lead_data["requested_time"]
                )

                lead_status = "updated"

            # =====================================
            # NEW LEAD
            # =====================================

            else:

                save_lead(
                    lead_data["customer_name"],
                    phone_number,
                    lead_data["email"],
                    lead_data["vehicle"],
                    lead_data["requested_service"],
                    lead_data["requested_time"]
                )

                lead_status = "saved"

        # =====================================
        # RETURN API RESPONSE
        # =====================================

        return {
            "conversation_id": conversation_id,
            "reply": suggested_reply,
            "lead_status": lead_status
        }

    # =====================================
    # INVALID JSON SAFETY
    # =====================================

    except json.JSONDecodeError:

        return {
            "conversation_id": conversation_id,
            "error": "AI returned invalid JSON.",
            "raw_response": response.output_text
        }

    except KeyError as error:

        return {
            "conversation_id": conversation_id,
            "error": "AI response was missing a required field.",
            "missing_field": str(error)
        }