import os
import re
import html
import hmac
import hashlib
import secrets

from datetime import (
    datetime,
    timezone
)

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status
)

from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse
)

from fastapi.security import (
    HTTPBasic,
    HTTPBasicCredentials
)

from database import (
    get_connection,
    get_business_by_slug,
    get_default_business,
    get_services_for_business,
    get_business_hours_rows
)


# =====================================
# ROUTER
# =====================================

router = APIRouter()

admin_security = HTTPBasic()


# =====================================
# OWNER ACCOUNT TABLE
# =====================================

def ensure_business_users_table():

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS business_users (
                business_id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)

        conn.commit()

    finally:

        conn.close()


ensure_business_users_table()


# =====================================
# HELPERS
# =====================================

def safe(
    value
):

    if value is None:

        return ""

    return html.escape(
        str(value)
    )


def now_string():

    return (
        datetime.now(
            timezone.utc
        )
        .isoformat()
    )


def make_slug(
    name
):

    slug = (
        name
        .lower()
        .strip()
    )


    slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        slug
    )


    return (
        slug.strip("-")
    )


# =====================================
# PASSWORDS
# =====================================

def hash_password(
    password,
    salt=None
):

    if salt is None:

        salt = (
            secrets.token_hex(
                16
            )
        )


    password_hash = (
        hashlib.pbkdf2_hmac(

            "sha256",

            password.encode(
                "utf-8"
            ),

            salt.encode(
                "utf-8"
            ),

            200000

        )
        .hex()
    )


    return (
        salt,
        password_hash
    )


def verify_password(
    password,
    salt,
    expected_hash
):

    _, calculated_hash = (
        hash_password(
            password,
            salt
        )
    )


    return hmac.compare_digest(
        calculated_hash,
        expected_hash
    )


# =====================================
# DATABASE OWNER ACCOUNT
# =====================================

def get_database_owner_account(
    business_id
):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT
                username,
                password_salt,
                password_hash
            FROM business_users
            WHERE business_id = ?
        """, (
            business_id,
        ))


        return (
            cursor.fetchone()
        )


    finally:

        conn.close()


# =====================================
# LEGACY ENV CREDENTIALS
# =====================================

def get_environment_credentials(
    business
):

    slug_key = (
        business["slug"]
        .upper()
        .replace(
            "-",
            "_"
        )
    )


    username = os.getenv(
        "DASHBOARD_USERNAME_"
        + slug_key
    )


    password = os.getenv(
        "DASHBOARD_PASSWORD_"
        + slug_key
    )


    default_business = (
        get_default_business()
    )


    if (
        default_business
        and
        default_business["id"]
        ==
        business["id"]
    ):

        if not username:

            username = (
                os.getenv(
                    "DASHBOARD_USERNAME"
                )
            )


        if not password:

            password = (
                os.getenv(
                    "DASHBOARD_PASSWORD"
                )
            )


    return (
        username,
        password
    )


# =====================================
# OWNER LOGIN CHECK
# =====================================

def verify_owner_credentials(
    business,
    username,
    password
):

    owner_account = (
        get_database_owner_account(
            business["id"]
        )
    )


    if owner_account:

        username_matches = (
            secrets.compare_digest(

                str(username),

                str(
                    owner_account[
                        "username"
                    ]
                )

            )
        )


        password_matches = (
            verify_password(

                password,

                owner_account[
                    "password_salt"
                ],

                owner_account[
                    "password_hash"
                ]

            )
        )


        if (
            username_matches
            and
            password_matches
        ):

            return True


    # =================================
    # LEGACY ENV LOGIN
    # =================================

    env_username, env_password = (
        get_environment_credentials(
            business
        )
    )


    if (
        env_username
        and
        env_password
    ):

        username_matches = (
            secrets.compare_digest(

                str(username),

                str(env_username)

            )
        )


        password_matches = (
            secrets.compare_digest(

                str(password),

                str(env_password)

            )
        )


        if (
            username_matches
            and
            password_matches
        ):

            return True


    return False


# =====================================
# SESSION HELPERS
# =====================================

def owner_is_logged_in(
    request,
    business
):

    session_business_id = (
        request.session.get(
            "owner_business_id"
        )
    )


    if (
        session_business_id
        is None
    ):

        return False


    return (
        str(
            session_business_id
        )
        ==
        str(
            business["id"]
        )
    )


def require_owner_session(
    request,
    business
):

    if not owner_is_logged_in(
        request,
        business
    ):

        return False


    return True


# =====================================
# ADMIN LOGIN
# =====================================

def verify_admin_login(
    credentials
):

    username = os.getenv(
        "ADMIN_USERNAME"
    )


    password = os.getenv(
        "ADMIN_PASSWORD"
    )


    if (
        not username
        or
        not password
    ):

        raise HTTPException(
            status_code=503,
            detail=(
                "Admin login has not "
                "been configured."
            )
        )


    username_matches = (
        secrets.compare_digest(
            credentials.username,
            username
        )
    )


    password_matches = (
        secrets.compare_digest(
            credentials.password,
            password
        )
    )


    if not (
        username_matches
        and
        password_matches
    ):

        raise HTTPException(
            status_code=
                status.HTTP_401_UNAUTHORIZED,

            detail=
                "Incorrect admin login.",

            headers={
                "WWW-Authenticate":
                    "Basic"
            }
        )


    return True


# =====================================
# DATABASE DATA
# =====================================

def get_business_leads(
    business_id
):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT
                id,
                customer_name,
                phone_number,
                email,
                vehicle,
                requested_service,
                requested_time,
                status
            FROM leads
            WHERE business_id = ?
            ORDER BY id DESC
        """, (
            business_id,
        ))


        return (
            cursor.fetchall()
        )


    finally:

        conn.close()


def get_business_appointments(
    business_id
):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT
                id,
                customer_name,
                phone_number,
                vehicle,
                service,
                appointment_date,
                appointment_time,
                duration_minutes,
                status
            FROM appointments
            WHERE business_id = ?
            ORDER BY
                appointment_date DESC,
                appointment_time DESC
        """, (
            business_id,
        ))


        return (
            cursor.fetchall()
        )


    finally:

        conn.close()



# =====================================
# ADMIN BUSINESS LIST
# =====================================

def get_all_businesses():

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT
                id,
                name,
                slug,
                location,
                active
            FROM businesses
            ORDER BY id DESC
        """)

        return cursor.fetchall()

    finally:

        conn.close()


# =====================================
# SERVICE PARSER
# =====================================

def parse_services(
    services_text
):

    services = []


    lines = (
        services_text
        .strip()
        .splitlines()
    )


    for line in lines:

        if not line.strip():

            continue


        parts = [

            part.strip()

            for part
            in line.split("|")

        ]


        if (
            len(parts)
            != 3
        ):

            raise ValueError(
                "Each service must look like: "
                "Service Name|Price|Duration"
            )


        service_name = (
            parts[0]
        )


        try:

            price = float(
                parts[1]
            )


            duration = int(
                parts[2]
            )


        except ValueError:

            raise ValueError(
                "Price and duration must be numbers."
            )


        if not service_name:

            raise ValueError(
                "Service name cannot be blank."
            )


        if price < 0:

            raise ValueError(
                "Price cannot be negative."
            )


        if duration <= 0:

            raise ValueError(
                "Duration must be greater than zero."
            )


        services.append(
            {

                "name":
                    service_name,

                "price_cents":
                    int(
                        round(
                            price
                            * 100
                        )
                    ),

                "duration_minutes":
                    duration

            }
        )


    if not services:

        raise ValueError(
            "Add at least one service."
        )


    return services


# =====================================
# TIME VALIDATION
# =====================================

def valid_time(
    value
):

    if not value:

        return True


    return bool(
        re.fullmatch(
            r"(?:[01]\d|2[0-3]):[0-5]\d",
            value
        )
    )


def format_time_12_hour(value):

    if not value:
        return ""

    text = str(value).strip()

    try:
        return datetime.strptime(text[:5], "%H:%M").strftime("%I:%M %p").lstrip("0")
    except ValueError:
        return text


# =====================================
# LOGIN PAGE
# =====================================

def build_login_page(
    business,
    error_message=""
):

    error_html = ""


    if error_message:

        error_html = (
            '<div class="error">'
            + safe(error_message)
            + "</div>"
        )


    page = """
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>
    __BUSINESS_NAME__ Owner Login
</title>


<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    min-height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
    background: #101010;
    color: white;
    font-family: Arial, Helvetica, sans-serif;
}

.login-box {
    width: 420px;
    max-width: calc(100vw - 30px);
    background: #1c1c1c;
    padding: 32px;
    border-radius: 18px;
}

h1 {
    margin: 0;
    font-size: 28px;
}

.subtitle {
    color: #aaa;
    margin-top: 8px;
    margin-bottom: 25px;
}

label {
    display: block;
    margin-top: 16px;
    margin-bottom: 7px;
}

input {
    width: 100%;
    background: #292929;
    border: 1px solid #444;
    color: white;
    padding: 13px;
    border-radius: 8px;
    font-size: 15px;
}

button {
    width: 100%;
    margin-top: 24px;
    border: 0;
    border-radius: 9px;
    padding: 14px;
    background: white;
    color: black;
    font-weight: bold;
    cursor: pointer;
}

.error {
    margin-bottom: 15px;
    padding: 12px;
    border-radius: 8px;
    background: #481c1c;
}

#result {
    display: none;
    margin-top: 15px;
    padding: 12px;
    border-radius: 8px;
    background: #481c1c;
}

</style>

</head>


<body>

<div class="login-box">

<h1>
    __BUSINESS_NAME__
</h1>

<div class="subtitle">
    Owner Login
</div>

__ERROR__


<label>
    Username
</label>

<input
    id="username"
    autocomplete="username"
>


<label>
    Password
</label>

<input
    id="password"
    type="password"
    autocomplete="current-password"
>


<button
    id="loginButton"
    onclick="login()"
>
    Log In
</button>


<div id="result"></div>

</div>


<script>

const BUSINESS_SLUG =
    "__BUSINESS_SLUG__";


async function login() {

    const username =
        document.getElementById(
            "username"
        ).value.trim();


    const password =
        document.getElementById(
            "password"
        ).value;


    const button =
        document.getElementById(
            "loginButton"
        );


    const result =
        document.getElementById(
            "result"
        );


    result.style.display =
        "none";


    button.disabled =
        true;


    try {

        const response =
            await fetch(
                "/owner/login/"
                + BUSINESS_SLUG,
                {

                    method:
                        "POST",

                    headers: {

                        "Content-Type":
                            "application/json"

                    },

                    body:
                        JSON.stringify(
                            {

                                username:
                                    username,

                                password:
                                    password

                            }
                        )

                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            result.style.display =
                "block";


            result.textContent =
                data.detail
                ||
                "Login failed.";


            return;

        }


        window.location.href =
            "/dashboard/"
            + BUSINESS_SLUG;


    } catch (
        error
    ) {

        result.style.display =
            "block";


        result.textContent =
            "Could not connect to server.";


    } finally {

        button.disabled =
            false;

    }

}


document
    .getElementById(
        "password"
    )
    .addEventListener(
        "keydown",
        function(
            event
        ) {

            if (
                event.key
                === "Enter"
            ) {

                login();

            }

        }
    );

</script>

</body>

</html>
"""


    page = page.replace(
        "__BUSINESS_NAME__",
        safe(
            business["name"]
        )
    )


    page = page.replace(
        "__BUSINESS_SLUG__",
        safe(
            business["slug"]
        )
    )


    page = page.replace(
        "__ERROR__",
        error_html
    )


    return page


def appointment_action_html(business, appointment):

    current_status = str(appointment["status"] or "").lower()

    if current_status in {"completed", "cancelled", "canceled"}:
        return "—"

    slug = safe(business["slug"])
    appointment_id = safe(appointment["id"])

    return f"""
    <div class="appointment-actions">
        <form method="post" action="/dashboard/{slug}/appointments/{appointment_id}/complete">
            <button class="small-action complete" type="submit">Complete</button>
        </form>
        <form method="get" action="/dashboard/{slug}/appointments/{appointment_id}/reschedule">
            <button class="small-action reschedule" type="submit">Reschedule</button>
        </form>
        <form method="post" action="/dashboard/{slug}/appointments/{appointment_id}/cancel" onsubmit="return confirm('Cancel this appointment?');">
            <button class="small-action cancel" type="submit">Cancel</button>
        </form>
    </div>
    """


# =====================================
# DASHBOARD HTML
# =====================================

def build_dashboard_html(
    business,
    leads,
    appointments
):

    total_leads = (
        len(leads)
    )


    booked_leads = (
        sum(
            1

            for lead in leads

            if (
                str(
                    lead["status"]
                    or ""
                ).lower()
                ==
                "booked"
            )
        )
    )


    total_appointments = (
        len(
            appointments
        )
    )


    appointment_rows = ""


    for appointment in appointments:

        duration = safe(
            appointment[
                "duration_minutes"
            ]
        )


        if duration:

            duration = (
                duration
                + " min"
            )


        appointment_rows += f"""
        <tr>

            <td>
                {safe(appointment["customer_name"])}
            </td>

            <td>
                {safe(appointment["phone_number"])}
            </td>

            <td>
                {safe(appointment["vehicle"])}
            </td>

            <td>
                {safe(appointment["service"])}
            </td>

            <td>
                {safe(appointment["appointment_date"])}
            </td>

            <td>
                {safe(format_time_12_hour(appointment["appointment_time"]))}
            </td>

            <td>
                {duration}
            </td>

            <td>
                {safe(appointment["status"])}
            </td>

            <td>
                {appointment_action_html(business, appointment)}
            </td>

        </tr>
        """


    if not appointment_rows:

        appointment_rows = """
        <tr>

            <td colspan="9">
                No appointments yet.
            </td>

        </tr>
        """


    lead_rows = ""


    for lead in leads:

        lead_rows += f"""
        <tr>

            <td>
                {safe(lead["customer_name"])}
            </td>

            <td>
                {safe(lead["phone_number"])}
            </td>

            <td>
                {safe(lead["email"])}
            </td>

            <td>
                {safe(lead["vehicle"])}
            </td>

            <td>
                {safe(lead["requested_service"])}
            </td>

            <td>
                {safe(lead["requested_time"])}
            </td>

            <td>
                {safe(lead["status"])}
            </td>

        </tr>
        """


    if not lead_rows:

        lead_rows = """
        <tr>

            <td colspan="7">
                No leads yet.
            </td>

        </tr>
        """


    page = """
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>
    __BUSINESS_NAME__ Dashboard
</title>


<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: #101010;
    color: white;
    font-family: Arial, Helvetica, sans-serif;
}

.container {
    width: 95%;
    max-width: 1400px;
    margin: auto;
    padding: 30px 0 60px;
}

.header {
    margin-bottom: 30px;
}

.header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 20px;
    flex-wrap: wrap;
}

h1 {
    margin: 0;
    font-size: 32px;
}

.subtitle {
    color: #aaa;
    margin: 8px 0;
}

.tag {
    display: inline-block;
    padding: 7px 11px;
    background: #272727;
    color: #bbb;
    border-radius: 8px;
    font-size: 12px;
}

.actions {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
}

.button {
    display: inline-block;
    text-decoration: none;
    background: white;
    color: black;
    padding: 11px 16px;
    border-radius: 9px;
    font-weight: bold;
}

.button.secondary {
    background: #292929;
    color: white;
}

.cards {
    display: grid;
    grid-template-columns:
        repeat(
            3,
            minmax(
                0,
                1fr
            )
        );
    gap: 18px;
    margin-bottom: 35px;
}

.card {
    background: #1c1c1c;
    padding: 24px;
    border-radius: 16px;
}

.card-title {
    color: #aaa;
    font-size: 14px;
    margin-bottom: 10px;
}

.card-number {
    font-size: 34px;
    font-weight: bold;
}

.section {
    background: #1c1c1c;
    border-radius: 16px;
    padding: 22px;
    margin-bottom: 30px;
    overflow-x: auto;
}

table {
    width: 100%;
    min-width: 850px;
    border-collapse: collapse;
}

th {
    color: #aaa;
    text-align: left;
    padding: 12px;
    border-bottom: 1px solid #333;
}

td {
    padding: 14px 12px;
    border-bottom: 1px solid #292929;
}

.appointment-actions {
    display: flex;
    gap: 7px;
    flex-wrap: wrap;
}

.appointment-actions form {
    margin: 0;
}

.small-action {
    border: 0;
    border-radius: 7px;
    padding: 8px 10px;
    font-weight: bold;
    cursor: pointer;
}

.small-action.complete {
    background: #d9ffd9;
    color: #102510;
}

.small-action.reschedule {
    background: #dfe7ff;
}

.small-action.cancel {
    background: #ffd7d7;
    color: #351010;
}

@media (
    max-width: 700px
) {

    .cards {
        grid-template-columns:
            1fr;
    }

}

</style>

</head>


<body>

<div class="container">


<div class="header">

<div class="header-row">

<div>

<h1>
    __BUSINESS_NAME__
</h1>

<div class="subtitle">
    Owner Dashboard
</div>

<span class="tag">
    __BUSINESS_SLUG__
</span>

</div>


<div class="actions">

<a
    class="button"
    href="/b/__BUSINESS_SLUG_RAW__"
    target="_blank"
    rel="noopener noreferrer"
>
    View Chatbot
</a>

<a
    class="button"
    href="/dashboard/__BUSINESS_SLUG_RAW__/settings"
>
    Business Settings
</a>


<a
    class="button secondary"
    href="/owner/logout"
>
    Log Out
</a>

</div>

</div>

</div>


<div class="cards">


<div class="card">

<div class="card-title">
    Total Leads
</div>

<div class="card-number">
    __TOTAL_LEADS__
</div>

</div>


<div class="card">

<div class="card-title">
    Booked Leads
</div>

<div class="card-number">
    __BOOKED_LEADS__
</div>

</div>


<div class="card">

<div class="card-title">
    Appointments
</div>

<div class="card-number">
    __TOTAL_APPOINTMENTS__
</div>

</div>


</div>


<div class="section">

<h2>
    Appointments
</h2>

<table>

<thead>

<tr>
<th>Customer</th>
<th>Phone</th>
<th>Vehicle / Info</th>
<th>Service</th>
<th>Date</th>
<th>Time</th>
<th>Duration</th>
<th>Status</th>
<th>Actions</th>
</tr>

</thead>


<tbody>

__APPOINTMENT_ROWS__

</tbody>

</table>

</div>


<div class="section">

<h2>
    Leads
</h2>

<table>

<thead>

<tr>
<th>Customer</th>
<th>Phone</th>
<th>Email</th>
<th>Vehicle / Info</th>
<th>Service</th>
<th>Requested Time</th>
<th>Status</th>
</tr>

</thead>


<tbody>

__LEAD_ROWS__

</tbody>

</table>

</div>


</div>

</body>

</html>
"""


    page = page.replace(
        "__BUSINESS_NAME__",
        safe(
            business["name"]
        )
    )


    page = page.replace(
        "__BUSINESS_SLUG__",
        safe(
            business["slug"]
        )
    )


    page = page.replace(
        "__BUSINESS_SLUG_RAW__",
        str(
            business["slug"]
        )
    )


    page = page.replace(
        "__TOTAL_LEADS__",
        str(
            total_leads
        )
    )


    page = page.replace(
        "__BOOKED_LEADS__",
        str(
            booked_leads
        )
    )


    page = page.replace(
        "__TOTAL_APPOINTMENTS__",
        str(
            total_appointments
        )
    )


    page = page.replace(
        "__APPOINTMENT_ROWS__",
        appointment_rows
    )


    page = page.replace(
        "__LEAD_ROWS__",
        lead_rows
    )


    return page


@router.get(
    "/dashboard/{business_slug}/appointments/{appointment_id}/reschedule",
    response_class=HTMLResponse
)
def reschedule_appointment_page(
    business_slug: str,
    appointment_id: int,
    request: Request
):
    business = get_business_by_slug(business_slug)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found.")

    if not require_owner_session(request, business):
        return RedirectResponse(
            url="/owner/login/" + business["slug"],
            status_code=303
        )

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, customer_name, appointment_date, appointment_time
            FROM appointments
            WHERE id = ? AND business_id = ?
            LIMIT 1
        """, (appointment_id, business["id"]))
        appointment = cursor.fetchone()
    finally:
        conn.close()

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found.")

    customer = safe(appointment["customer_name"])
    current_date = safe(appointment["appointment_date"])
    current_time = str(appointment["appointment_time"] or "")[:5]
    slug = safe(business["slug"])

    return HTMLResponse(f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reschedule Appointment</title>
<style>
body {{ font-family: Arial, sans-serif; background:#101010; color:#fff; margin:0; padding:40px 20px; }}
.card {{ max-width:520px; margin:0 auto; background:#1d1d1d; padding:28px; border-radius:18px; }}
h1 {{ margin-top:0; }}
label {{ display:block; margin:18px 0 8px; color:#ccc; }}
input {{ width:100%; box-sizing:border-box; padding:12px; border-radius:8px; border:1px solid #555; background:#111; color:#fff; }}
.actions {{ display:flex; gap:10px; margin-top:24px; }}
button,a {{ padding:11px 16px; border:0; border-radius:8px; font-weight:700; text-decoration:none; cursor:pointer; }}
button {{ background:#fff; color:#111; }}
a {{ background:#333; color:#fff; }}
</style>
</head>
<body>
<div class="card">
<h1>Reschedule</h1>
<p>{customer}</p>
<form method="get" action="/dashboard/{slug}/appointments/{appointment_id}/reschedule/save">
<label>New date</label>
<input type="date" name="new_date" value="{current_date}" required>
<label>New time</label>
<input type="time" name="new_time" value="{safe(current_time)}" required>
<div class="actions">
<button type="submit">Save New Time</button>
<a href="/dashboard/{slug}">Back</a>
</div>
</form>
</div>
</body>
</html>
""")


@router.get(
    "/dashboard/{business_slug}/appointments/{appointment_id}/reschedule/save"
)
def save_rescheduled_appointment(
    business_slug: str,
    appointment_id: int,
    request: Request,
    new_date: str,
    new_time: str
):
    business = get_business_by_slug(business_slug)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found.")

    if not require_owner_session(request, business):
        return RedirectResponse(
            url="/owner/login/" + business["slug"],
            status_code=303
        )

    try:
        datetime.strptime(new_date, "%Y-%m-%d")
        datetime.strptime(new_time, "%H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date or time.")

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id
            FROM appointments
            WHERE id = ? AND business_id = ?
            LIMIT 1
        """, (appointment_id, business["id"]))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Appointment not found.")

        cursor.execute("""
            UPDATE appointments
            SET appointment_date = ?, appointment_time = ?, status = ?
            WHERE id = ? AND business_id = ?
        """, (
            new_date,
            new_time,
            "Booked",
            appointment_id,
            business["id"],
        ))
        conn.commit()
    finally:
        conn.close()

    return RedirectResponse(
        url="/dashboard/" + business["slug"],
        status_code=303
    )


# =====================================
# SETTINGS PAGE
# =====================================

def build_settings_page(
    business
):

    services = (
        get_services_for_business(
            business["id"]
        )
    )


    hours = (
        get_business_hours_rows(
            business["id"]
        )
    )


    owner = (
        get_database_owner_account(
            business["id"]
        )
    )


    services_text = ""


    for service in services:

        price = (
            service["price_cents"]
            / 100
        )


        if (
            float(
                price
            )
            .is_integer()
        ):

            price = int(
                price
            )


        services_text += (

            str(
                service["name"]
            )

            + "|"

            + str(
                price
            )

            + "|"

            + str(
                service[
                    "duration_minutes"
                ]
            )

            + "\n"

        )


    hour_map = {}


    for row in hours:

        hour_map[
            int(
                row["weekday"]
            )
        ] = row


    day_names = [

        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday"

    ]


    hour_rows = ""


    for weekday in range(
        7
    ):

        row = (
            hour_map.get(
                weekday
            )
        )


        open_time = ""
        close_time = ""


        if (
            row
            and
            not row["is_closed"]
        ):

            open_time = str(
                row["open_time"]
                or ""
            )


            close_time = str(
                row["close_time"]
                or ""
            )


        hour_rows += f"""
        <div class="day">
            {safe(day_names[weekday])}
        </div>

        <input
            id="day{weekday}Open"
            value="{safe(open_time)}"
            placeholder="closed"
        >

        <input
            id="day{weekday}Close"
            value="{safe(close_time)}"
            placeholder="closed"
        >
        """


    current_username = ""


    if owner:

        current_username = (
            owner["username"]
        )


    page = """
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>
    __BUSINESS_NAME__ Settings
</title>


<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: #101010;
    color: white;
    font-family: Arial, Helvetica, sans-serif;
}

.container {
    max-width: 900px;
    margin: 40px auto;
    padding: 20px;
}

.panel {
    background: #1c1c1c;
    border-radius: 18px;
    padding: 30px;
}

.top-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 15px;
    flex-wrap: wrap;
}

h1 {
    margin: 0;
}

.subtitle {
    color: #aaa;
    margin-top: 8px;
}

.back {
    color: black;
    background: white;
    text-decoration: none;
    padding: 11px 16px;
    border-radius: 9px;
    font-weight: bold;
}

label {
    display: block;
    margin-top: 22px;
    margin-bottom: 7px;
    font-weight: bold;
}

input,
textarea {
    width: 100%;
    padding: 12px;
    background: #292929;
    color: white;
    border: 1px solid #444;
    border-radius: 8px;
    font-size: 15px;
}

textarea {
    min-height: 160px;
    resize: vertical;
}

.help {
    color: #999;
    font-size: 13px;
    margin-top: 7px;
}

.hours-grid {
    display: grid;
    grid-template-columns:
        140px
        1fr
        1fr;
    gap: 10px;
    align-items: center;
}

.day {
    color: #ddd;
}

button {
    margin-top: 28px;
    padding: 14px 22px;
    border: 0;
    border-radius: 9px;
    background: white;
    color: black;
    font-weight: bold;
    cursor: pointer;
}

#result {
    display: none;
    margin-top: 20px;
    padding: 15px;
    border-radius: 10px;
}

.success {
    background: #17341f;
}

.error {
    background: #481c1c;
}

</style>

</head>


<body>

<div class="container">

<div class="panel">


<div class="top-row">

<div>

<h1>
    __BUSINESS_NAME__
</h1>

<div class="subtitle">
    Business Settings
</div>

</div>


<a
    class="back"
    href="/dashboard/__BUSINESS_SLUG__"
>
    Back to Dashboard
</a>

</div>


<label>
    Business Name
</label>

<input
    id="businessName"
    value="__BUSINESS_NAME__"
>


<label>
    Location
</label>

<input
    id="location"
    value="__LOCATION__"
>


<label>
    Services
</label>

<textarea
    id="services"
>__SERVICES__</textarea>


<div class="help">
    One service per line:
    Service Name | Price | Duration in minutes
</div>


<label>
    Business Hours
</label>


<div class="hours-grid">

__HOUR_ROWS__

</div>


<div class="help">
    Use 24-hour time internally.
    Leave both boxes blank for a closed day.
</div>


<label>
    Owner Username
</label>

<input
    id="ownerUsername"
    value="__OWNER_USERNAME__"
>


<label>
    New Password
</label>

<input
    id="ownerPassword"
    type="password"
    placeholder="Leave blank to keep current password"
>


<div class="help">
    Leave password blank unless you want to change it.
</div>


<button
    id="saveButton"
    onclick="saveSettings()"
>
    Save Changes
</button>


<div id="result"></div>


</div>

</div>


<script>

const BUSINESS_SLUG =
    "__BUSINESS_SLUG__";


async function saveSettings() {

    const resultBox =
        document.getElementById(
            "result"
        );


    const saveButton =
        document.getElementById(
            "saveButton"
        );


    const hours = [];


    for (
        let day = 0;
        day < 7;
        day++
    ) {

        hours.push(
            [

                document
                    .getElementById(
                        "day"
                        + day
                        + "Open"
                    )
                    .value
                    .trim(),

                document
                    .getElementById(
                        "day"
                        + day
                        + "Close"
                    )
                    .value
                    .trim()

            ]
        );

    }


    const payload = {

        business_name:
            document
                .getElementById(
                    "businessName"
                )
                .value
                .trim(),

        location:
            document
                .getElementById(
                    "location"
                )
                .value
                .trim(),

        services_text:
            document
                .getElementById(
                    "services"
                )
                .value,

        owner_username:
            document
                .getElementById(
                    "ownerUsername"
                )
                .value
                .trim(),

        owner_password:
            document
                .getElementById(
                    "ownerPassword"
                )
                .value,

        hours:
            hours

    };


    resultBox.style.display =
        "block";


    resultBox.className =
        "";


    resultBox.textContent =
        "Saving...";


    saveButton.disabled =
        true;


    try {

        const response =
            await fetch(
                "/dashboard/"
                + BUSINESS_SLUG
                + "/settings",
                {

                    method:
                        "POST",

                    headers: {

                        "Content-Type":
                            "application/json"

                    },

                    body:
                        JSON.stringify(
                            payload
                        )

                }
            );


        if (
            response.status
            === 401
        ) {

            window.location.href =
                "/owner/login/"
                + BUSINESS_SLUG;


            return;

        }


        const data =
            await response.json();


        if (!response.ok) {

            resultBox.className =
                "error";


            resultBox.textContent =
                data.detail
                ||
                "Could not save settings.";


            return;

        }


        resultBox.className =
            "success";


        resultBox.textContent =
            "Changes saved successfully.";


    } catch (
        error
    ) {

        resultBox.className =
            "error";


        resultBox.textContent =
            "Could not connect to server.";


    } finally {

        saveButton.disabled =
            false;

    }

}

</script>

</body>

</html>
"""


    page = page.replace(
        "__BUSINESS_NAME__",
        safe(
            business["name"]
        )
    )


    page = page.replace(
        "__BUSINESS_SLUG__",
        safe(
            business["slug"]
        )
    )


    page = page.replace(
        "__LOCATION__",
        safe(
            business["location"]
        )
    )


    page = page.replace(
        "__SERVICES__",
        safe(
            services_text.rstrip()
        )
    )


    page = page.replace(
        "__HOUR_ROWS__",
        hour_rows
    )


    page = page.replace(
        "__OWNER_USERNAME__",
        safe(
            current_username
        )
    )


    return page


# =====================================
# ONBOARDING PAGE
# =====================================

def build_onboarding_page(
    businesses
):

    business_rows = ""

    for business in businesses:

        business_id = safe(
            business["id"]
        )

        business_name = safe(
            business["name"]
        )

        business_slug = safe(
            business["slug"]
        )

        location = safe(
            business["location"]
        )

        active_text = (
            "Active"
            if business["active"]
            else "Inactive"
        )

        business_rows += f"""
        <tr>
            <td>{business_name}</td>
            <td>{business_slug}</td>
            <td>{location}</td>
            <td>{active_text}</td>
            <td>
                <div class="business-actions">

                    <a
                        class="mini-button"
                        href="/b/{business_slug}"
                        target="_blank"
                        rel="noopener noreferrer"
                    >
                        View Chatbot
                    </a>

                    <a
                        class="mini-button secondary"
                        href="/dashboard/{business_slug}"
                        target="_blank"
                        rel="noopener noreferrer"
                    >
                        View Dashboard
                    </a>

                    <form
                        method="post"
                        action="/admin/businesses/{business_id}/delete"
                        onsubmit="return confirm('Permanently delete {business_name} and all of its data? This cannot be undone.');"
                    >
                        <button
                            class="mini-button danger"
                            type="submit"
                        >
                            Delete Business
                        </button>
                    </form>

                </div>
            </td>
        </tr>
        """

    if not business_rows:

        business_rows = """
        <tr>
            <td colspan="5">
                No businesses yet.
            </td>
        </tr>
        """

    return f"""
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>
    Business Management
</title>

<style>

* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    background: #101010;
    color: white;
    font-family: Arial, Helvetica, sans-serif;
}}

.container {{
    width: 95%;
    max-width: 1200px;
    margin: 40px auto;
    padding-bottom: 60px;
}}

.panel {{
    background: #1c1c1c;
    padding: 30px;
    border-radius: 18px;
    margin-bottom: 28px;
}}

h1,
h2 {{
    margin-top: 0;
}}

p,
.help {{
    color: #aaa;
}}

label {{
    display: block;
    margin-top: 18px;
    margin-bottom: 7px;
    font-weight: bold;
}}

input,
textarea {{
    width: 100%;
    background: #292929;
    border: 1px solid #444;
    color: white;
    padding: 12px;
    border-radius: 8px;
    font-size: 15px;
}}

textarea {{
    min-height: 140px;
    resize: vertical;
}}

.hours-grid {{
    display: grid;
    grid-template-columns: 150px 1fr 1fr;
    gap: 10px;
    align-items: center;
}}

.day {{
    color: #ddd;
}}

#createButton {{
    margin-top: 25px;
    border: none;
    background: white;
    color: black;
    padding: 14px 22px;
    border-radius: 9px;
    font-weight: bold;
    cursor: pointer;
}}

#result {{
    margin-top: 22px;
    padding: 15px;
    border-radius: 10px;
    display: none;
    white-space: pre-wrap;
}}

.success {{
    background: #17341f;
}}

.error {{
    background: #481c1c;
}}

.table-wrap {{
    overflow-x: auto;
}}

table {{
    width: 100%;
    min-width: 850px;
    border-collapse: collapse;
}}

th {{
    color: #aaa;
    text-align: left;
    padding: 12px;
    border-bottom: 1px solid #333;
}}

td {{
    padding: 14px 12px;
    border-bottom: 1px solid #292929;
}}

.business-actions {{
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}}

.business-actions form {{
    margin: 0;
}}

.mini-button {{
    display: inline-block;
    border: 0;
    border-radius: 8px;
    padding: 9px 11px;
    background: white;
    color: #111;
    text-decoration: none;
    font-weight: bold;
    font-size: 13px;
    cursor: pointer;
}}

.mini-button.secondary {{
    background: #dfe7ff;
    color: #111;
}}

.mini-button.danger {{
    background: #ffd7d7;
    color: #351010;
}}

@media (
    max-width: 700px
) {{

    .hours-grid {{
        grid-template-columns: 1fr;
    }}

}}

</style>

</head>

<body>

<div class="container">

<div class="panel">

<h1>
    Business Management
</h1>

<p>
    Manage every business using your AI assistant.
</p>

<div class="table-wrap">

<table>

<thead>
<tr>
    <th>Business</th>
    <th>Slug</th>
    <th>Location</th>
    <th>Status</th>
    <th>Actions</th>
</tr>
</thead>

<tbody>
{business_rows}
</tbody>

</table>

</div>

</div>


<div class="panel">

<h2>
    Add New Business
</h2>

<p>
    Create a new AI assistant and owner dashboard.
</p>

<label>
    Business Name
</label>

<input
    id="businessName"
    placeholder="Example: Smith's Landscaping"
>


<label>
    Location
</label>

<input
    id="location"
    placeholder="Columbus, Ohio"
>


<label>
    Owner Dashboard Username
</label>

<input
    id="ownerUsername"
    placeholder="smithowner"
>


<label>
    Owner Dashboard Password
</label>

<input
    id="ownerPassword"
    type="password"
    placeholder="Create a password"
>


<label>
    Services
</label>

<textarea
    id="services"
    placeholder="Lawn Mowing|50|60&#10;Yard Cleanup|120|120&#10;Mulching|150|120"
></textarea>

<div class="help">
    One service per line:
    Service Name | Price | Duration in minutes
</div>


<label>
    Business Hours
</label>

<div class="hours-grid">

<div class="day">Monday</div>
<input id="day0Open" value="09:00">
<input id="day0Close" value="17:00">

<div class="day">Tuesday</div>
<input id="day1Open" value="09:00">
<input id="day1Close" value="17:00">

<div class="day">Wednesday</div>
<input id="day2Open" value="09:00">
<input id="day2Close" value="17:00">

<div class="day">Thursday</div>
<input id="day3Open" value="09:00">
<input id="day3Close" value="17:00">

<div class="day">Friday</div>
<input id="day4Open" value="09:00">
<input id="day4Close" value="17:00">

<div class="day">Saturday</div>
<input id="day5Open" value="10:00">
<input id="day5Close" value="14:00">

<div class="day">Sunday</div>
<input id="day6Open" placeholder="closed">
<input id="day6Close" placeholder="closed">

</div>

<div class="help">
    Leave both boxes empty for a closed day.
</div>

<button
    id="createButton"
    onclick="createBusiness()"
>
    Create Business
</button>

<div id="result"></div>

</div>

</div>

<script>

async function createBusiness() {{

    const resultBox =
        document.getElementById(
            "result"
        );

    const createButton =
        document.getElementById(
            "createButton"
        );

    const hours = [];

    for (
        let day = 0;
        day < 7;
        day++
    ) {{

        hours.push(
            [
                document
                    .getElementById(
                        "day"
                        + day
                        + "Open"
                    )
                    .value
                    .trim(),

                document
                    .getElementById(
                        "day"
                        + day
                        + "Close"
                    )
                    .value
                    .trim()
            ]
        );

    }}

    const payload = {{

        business_name:
            document
                .getElementById(
                    "businessName"
                )
                .value
                .trim(),

        location:
            document
                .getElementById(
                    "location"
                )
                .value
                .trim(),

        owner_username:
            document
                .getElementById(
                    "ownerUsername"
                )
                .value
                .trim(),

        owner_password:
            document
                .getElementById(
                    "ownerPassword"
                )
                .value,

        services_text:
            document
                .getElementById(
                    "services"
                )
                .value,

        hours:
            hours
    }};

    resultBox.style.display =
        "block";

    resultBox.className =
        "";

    resultBox.textContent =
        "Creating business...";

    createButton.disabled =
        true;

    try {{

        const response =
            await fetch(
                "/admin/onboard",
                {{
                    method:
                        "POST",

                    headers: {{
                        "Content-Type":
                            "application/json"
                    }},

                    body:
                        JSON.stringify(
                            payload
                        )
                }}
            );

        const data =
            await response.json();

        if (!response.ok) {{

            resultBox.className =
                "error";

            resultBox.textContent =
                data.detail
                ||
                "Could not create business.";

            return;

        }}

        resultBox.className =
            "success";

        resultBox.textContent =
            "BUSINESS CREATED\\n\\n"
            + "Name: "
            + data.business_name
            + "\\n"
            + "Chatbot: "
            + data.chat_url
            + "\\n"
            + "Owner Login: "
            + data.login_url;

        setTimeout(
            function() {{
                window.location.reload();
            }},
            900
        );

    }} catch (
        error
    ) {{

        resultBox.className =
            "error";

        resultBox.textContent =
            "Could not connect to server.";

    }} finally {{

        createButton.disabled =
            false;

    }}

}}

</script>

</body>

</html>
"""


# =====================================
# OWNER LOGIN ROUTES
# =====================================

@router.get(
    "/owner/login/{business_slug}",
    response_class=HTMLResponse
)
def owner_login_page(
    business_slug: str,
    request: Request
):

    business = (
        get_business_by_slug(
            business_slug
        )
    )


    if not business:

        raise HTTPException(
            status_code=404,
            detail=
                "Business not found."
        )


    if owner_is_logged_in(
        request,
        business
    ):

        return RedirectResponse(
            url=(
                "/dashboard/"
                + business["slug"]
            ),
            status_code=303
        )


    return HTMLResponse(
        build_login_page(
            business
        )
    )


@router.post(
    "/owner/login/{business_slug}"
)
async def owner_login(
    business_slug: str,
    request: Request
):

    business = (
        get_business_by_slug(
            business_slug
        )
    )


    if not business:

        raise HTTPException(
            status_code=404,
            detail=
                "Business not found."
        )


    try:

        data = (
            await request.json()
        )


    except Exception:

        raise HTTPException(
            status_code=400,
            detail=
                "Invalid login request."
        )


    username = str(
        data.get(
            "username",
            ""
        )
    ).strip()


    password = str(
        data.get(
            "password",
            ""
        )
    )


    if not verify_owner_credentials(
        business,
        username,
        password
    ):

        raise HTTPException(
            status_code=401,
            detail=
                "Incorrect username or password."
        )


    request.session.clear()


    request.session[
        "owner_business_id"
    ] = business["id"]


    request.session[
        "owner_business_slug"
    ] = business["slug"]


    request.session[
        "owner_username"
    ] = username


    return {

        "status":
            "logged_in",

        "dashboard_url":
            (
                "/dashboard/"
                + business["slug"]
            )

    }


@router.get(
    "/owner/logout"
)
def owner_logout(
    request: Request
):

    business_slug = (
        request.session.get(
            "owner_business_slug"
        )
    )


    request.session.clear()


    if business_slug:

        return RedirectResponse(
            url=(
                "/owner/login/"
                + str(
                    business_slug
                )
            ),
            status_code=303
        )


    return RedirectResponse(
        url="/",
        status_code=303
    )


# =====================================
# ADMIN ONBOARDING
# =====================================

@router.get(
    "/admin/onboard",
    response_class=HTMLResponse
)
def onboarding_page(
    credentials:
        HTTPBasicCredentials
        =
        Depends(
            admin_security
        )
):

    verify_admin_login(
        credentials
    )


    return HTMLResponse(
        build_onboarding_page(
            get_all_businesses()
        )
    )


@router.post(
    "/admin/onboard"
)
async def onboard_business(
    request: Request,
    credentials:
        HTTPBasicCredentials
        =
        Depends(
            admin_security
        )
):

    verify_admin_login(
        credentials
    )


    data = (
        await request.json()
    )


    business_name = str(
        data.get(
            "business_name",
            ""
        )
    ).strip()


    location = str(
        data.get(
            "location",
            ""
        )
    ).strip()


    owner_username = str(
        data.get(
            "owner_username",
            ""
        )
    ).strip()


    owner_password = str(
        data.get(
            "owner_password",
            ""
        )
    )


    services_text = str(
        data.get(
            "services_text",
            ""
        )
    )


    hours = data.get(
        "hours",
        []
    )


    if not business_name:

        raise HTTPException(
            status_code=400,
            detail=
                "Business name is required."
        )


    if not location:

        raise HTTPException(
            status_code=400,
            detail=
                "Location is required."
        )


    if (
        len(
            owner_username
        )
        < 3
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Username must be at "
                "least 3 characters."
            )
        )


    if (
        len(
            owner_password
        )
        < 8
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Password must be at "
                "least 8 characters."
            )
        )


    slug = make_slug(
        business_name
    )


    if not slug:

        raise HTTPException(
            status_code=400,
            detail=
                "Invalid business name."
        )


    if get_business_by_slug(
        slug
    ):

        raise HTTPException(
            status_code=409,
            detail=
                "Business already exists."
        )


    try:

        services = (
            parse_services(
                services_text
            )
        )


    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(
                error
            )
        )


    if (
        not isinstance(
            hours,
            list
        )
        or
        len(hours)
        != 7
    ):

        raise HTTPException(
            status_code=400,
            detail=
                "All 7 days need hours."
        )


    for day in hours:

        if (
            not isinstance(
                day,
                list
            )
            or
            len(day)
            != 2
        ):

            raise HTTPException(
                status_code=400,
                detail=
                    "Invalid business hours."
            )


        open_time = str(
            day[0]
            or ""
        ).strip()


        close_time = str(
            day[1]
            or ""
        ).strip()


        if (
            not valid_time(
                open_time
            )
            or
            not valid_time(
                close_time
            )
        ):

            raise HTTPException(
                status_code=400,
                detail=
                    "Hours must use HH:MM format."
            )


    salt, password_hash = (
        hash_password(
            owner_password
        )
    )


    conn = get_connection()
    cursor = conn.cursor()


    try:

        timestamp = (
            now_string()
        )


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

            VALUES (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?
            )
        """, (

            business_name,
            slug,
            location,
            None,
            None,
            True,
            timestamp,
            timestamp

        ))


        cursor.execute("""
            SELECT id
            FROM businesses
            WHERE slug = ?
        """, (
            slug,
        ))


        business = (
            cursor.fetchone()
        )


        if not business:

            raise RuntimeError(
                "Business was not created."
            )


        business_id = (
            business["id"]
        )


        for service in services:

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

                VALUES (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?
                )
            """, (

                business_id,

                service["name"],

                "",

                service[
                    "price_cents"
                ],

                service[
                    "duration_minutes"
                ],

                "service",

                True,

                timestamp

            ))


        for weekday in range(
            7
        ):

            open_time = str(
                hours[
                    weekday
                ][0]
                or ""
            ).strip()


            close_time = str(
                hours[
                    weekday
                ][1]
                or ""
            ).strip()


            is_closed = (
                not open_time
                or
                not close_time
            )


            if is_closed:

                open_time = None

                close_time = None


            cursor.execute("""
                INSERT INTO business_hours (
                    business_id,
                    weekday,
                    open_time,
                    close_time,
                    is_closed
                )

                VALUES (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?
                )
            """, (

                business_id,

                weekday,

                open_time,

                close_time,

                is_closed

            ))


        cursor.execute("""
            INSERT INTO business_users (
                business_id,
                username,
                password_salt,
                password_hash
            )

            VALUES (
                ?,
                ?,
                ?,
                ?
            )
        """, (

            business_id,

            owner_username,

            salt,

            password_hash

        ))


        conn.commit()


    except Exception as error:

        conn.rollback()


        print(
            "ONBOARDING ERROR:",
            repr(
                error
            )
        )


        raise HTTPException(
            status_code=500,
            detail=(
                "Could not create business. "
                "The username may already be in use."
            )
        )


    finally:

        conn.close()


    return {

        "status":
            "created",

        "business_name":
            business_name,

        "slug":
            slug,

        "chat_url":
            (
                "/b/"
                + slug
            ),

        "login_url":
            (
                "/owner/login/"
                + slug
            ),

        "dashboard_url":
            (
                "/dashboard/"
                + slug
            )

    }



# =====================================
# ADMIN DELETE BUSINESS
# =====================================

@router.post(
    "/admin/businesses/{business_id}/delete"
)
def delete_business(
    business_id: int,
    credentials:
        HTTPBasicCredentials
        =
        Depends(
            admin_security
        )
):

    verify_admin_login(
        credentials
    )

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT
                id,
                name,
                slug
            FROM businesses
            WHERE id = ?
            LIMIT 1
        """, (
            business_id,
        ))

        business = (
            cursor.fetchone()
        )

        if not business:

            raise HTTPException(
                status_code=404,
                detail=
                    "Business not found."
            )

        # Delete all business-owned records first.
        # This keeps old chatbot/dashboard links from retaining client data.
        for table_name in (
            "appointments",
            "leads",
            "chat_sessions",
            "rate_limits",
            "business_hours",
            "services",
            "business_users"
        ):

            cursor.execute(
                "DELETE FROM "
                + table_name
                + " WHERE business_id = ?",
                (
                    business_id,
                )
            )

        cursor.execute("""
            DELETE FROM businesses
            WHERE id = ?
        """, (
            business_id,
        ))

        conn.commit()

    except HTTPException:

        conn.rollback()
        raise

    except Exception as error:

        conn.rollback()

        print(
            "DELETE BUSINESS ERROR:",
            repr(
                error
            )
        )

        raise HTTPException(
            status_code=500,
            detail=
                "Could not delete business."
        )

    finally:

        conn.close()

    return RedirectResponse(
        url="/admin/onboard",
        status_code=303
    )


# =====================================
# DEFAULT DASHBOARD
# =====================================

@router.get(
    "/dashboard",
    response_class=HTMLResponse
)
def default_dashboard(
    request: Request
):

    business = (
        get_default_business()
    )


    if not business:

        raise HTTPException(
            status_code=404,
            detail=
                "Business not found."
        )


    if not require_owner_session(
        request,
        business
    ):

        return RedirectResponse(
            url=(
                "/owner/login/"
                + business["slug"]
            ),
            status_code=303
        )


    return HTMLResponse(
        build_dashboard_html(

            business,

            get_business_leads(
                business["id"]
            ),

            get_business_appointments(
                business["id"]
            )

        )
    )


# =====================================
# BUSINESS DASHBOARD
# =====================================

@router.get(
    "/dashboard/{business_slug}",
    response_class=HTMLResponse
)
def business_dashboard(
    business_slug: str,
    request: Request
):

    business = (
        get_business_by_slug(
            business_slug
        )
    )


    if not business:

        raise HTTPException(
            status_code=404,
            detail=
                "Business not found."
        )


    if not require_owner_session(
        request,
        business
    ):

        return RedirectResponse(
            url=(
                "/owner/login/"
                + business["slug"]
            ),
            status_code=303
        )


    return HTMLResponse(
        build_dashboard_html(

            business,

            get_business_leads(
                business["id"]
            ),

            get_business_appointments(
                business["id"]
            )

        )
    )


# =====================================
# APPOINTMENT ACTIONS
# =====================================

def update_appointment_status(business_id, appointment_id, new_status):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id
            FROM appointments
            WHERE id = ?
              AND business_id = ?
            LIMIT 1
        """, (
            appointment_id,
            business_id,
        ))

        if not cursor.fetchone():
            return False

        cursor.execute("""
            UPDATE appointments
            SET status = ?
            WHERE id = ?
              AND business_id = ?
        """, (
            new_status,
            appointment_id,
            business_id,
        ))
        conn.commit()
        return True
    finally:
        conn.close()


@router.post(
    "/dashboard/{business_slug}/appointments/{appointment_id}/complete"
)
def complete_appointment(
    business_slug: str,
    appointment_id: int,
    request: Request
):

    business = get_business_by_slug(business_slug)

    if not business:
        raise HTTPException(status_code=404, detail="Business not found.")

    if not require_owner_session(request, business):
        return RedirectResponse(
            url="/owner/login/" + business["slug"],
            status_code=303
        )

    if not update_appointment_status(business["id"], appointment_id, "Completed"):
        raise HTTPException(status_code=404, detail="Appointment not found.")

    return RedirectResponse(
        url="/dashboard/" + business["slug"],
        status_code=303
    )


@router.post(
    "/dashboard/{business_slug}/appointments/{appointment_id}/cancel"
)
def cancel_appointment(
    business_slug: str,
    appointment_id: int,
    request: Request
):

    business = get_business_by_slug(business_slug)

    if not business:
        raise HTTPException(status_code=404, detail="Business not found.")

    if not require_owner_session(request, business):
        return RedirectResponse(
            url="/owner/login/" + business["slug"],
            status_code=303
        )

    if not update_appointment_status(business["id"], appointment_id, "Cancelled"):
        raise HTTPException(status_code=404, detail="Appointment not found.")

    return RedirectResponse(
        url="/dashboard/" + business["slug"],
        status_code=303
    )


# =====================================
# SETTINGS PAGE
# =====================================

@router.get(
    "/dashboard/{business_slug}/settings",
    response_class=HTMLResponse
)
def business_settings_page(
    business_slug: str,
    request: Request
):

    business = (
        get_business_by_slug(
            business_slug
        )
    )


    if not business:

        raise HTTPException(
            status_code=404,
            detail=
                "Business not found."
        )


    if not require_owner_session(
        request,
        business
    ):

        return RedirectResponse(
            url=(
                "/owner/login/"
                + business["slug"]
            ),
            status_code=303
        )


    return HTMLResponse(
        build_settings_page(
            business
        )
    )


# =====================================
# SAVE SETTINGS
# =====================================

@router.post(
    "/dashboard/{business_slug}/settings"
)
async def save_business_settings(
    business_slug: str,
    request: Request
):

    business = (
        get_business_by_slug(
            business_slug
        )
    )


    if not business:

        raise HTTPException(
            status_code=404,
            detail=
                "Business not found."
        )


    if not require_owner_session(
        request,
        business
    ):

        raise HTTPException(
            status_code=401,
            detail=
                "Please log in."
        )


    data = (
        await request.json()
    )


    business_name = str(
        data.get(
            "business_name",
            ""
        )
    ).strip()


    location = str(
        data.get(
            "location",
            ""
        )
    ).strip()


    services_text = str(
        data.get(
            "services_text",
            ""
        )
    )


    owner_username = str(
        data.get(
            "owner_username",
            ""
        )
    ).strip()


    owner_password = str(
        data.get(
            "owner_password",
            ""
        )
    )


    hours = data.get(
        "hours",
        []
    )


    if not business_name:

        raise HTTPException(
            status_code=400,
            detail=
                "Business name is required."
        )


    if not location:

        raise HTTPException(
            status_code=400,
            detail=
                "Location is required."
        )


    try:

        services = (
            parse_services(
                services_text
            )
        )


    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(
                error
            )
        )


    if (
        not isinstance(
            hours,
            list
        )
        or
        len(hours)
        != 7
    ):

        raise HTTPException(
            status_code=400,
            detail=
                "All 7 days need hours."
        )


    for day in hours:

        if (
            not isinstance(
                day,
                list
            )
            or
            len(day)
            != 2
        ):

            raise HTTPException(
                status_code=400,
                detail=
                    "Invalid hours."
            )


        open_time = str(
            day[0]
            or ""
        ).strip()


        close_time = str(
            day[1]
            or ""
        ).strip()


        if (
            not valid_time(
                open_time
            )
            or
            not valid_time(
                close_time
            )
        ):

            raise HTTPException(
                status_code=400,
                detail=
                    "Hours must use HH:MM format."
            )


    existing_owner = (
        get_database_owner_account(
            business["id"]
        )
    )


    if existing_owner:

        if not owner_username:

            owner_username = (
                existing_owner[
                    "username"
                ]
            )


    elif (
        owner_password
        and
        not owner_username
    ):

        raise HTTPException(
            status_code=400,
            detail=
                "Enter an owner username."
        )


    if (
        owner_password
        and
        len(
            owner_password
        )
        < 8
    ):

        raise HTTPException(
            status_code=400,
            detail=
                "Password must be at least 8 characters."
        )


    conn = get_connection()
    cursor = conn.cursor()


    try:

        timestamp = (
            now_string()
        )


        cursor.execute("""
            UPDATE businesses

            SET
                name = ?,
                location = ?,
                updated_at = ?

            WHERE id = ?
        """, (

            business_name,

            location,

            timestamp,

            business["id"]

        ))


        # =================================
        # SERVICES
        # =================================

        cursor.execute("""
            DELETE FROM services
            WHERE business_id = ?
        """, (
            business["id"],
        ))


        for service in services:

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

                VALUES (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?
                )
            """, (

                business["id"],

                service["name"],

                "",

                service[
                    "price_cents"
                ],

                service[
                    "duration_minutes"
                ],

                "service",

                True,

                timestamp

            ))


        # =================================
        # HOURS
        # =================================

        cursor.execute("""
            DELETE FROM business_hours
            WHERE business_id = ?
        """, (
            business["id"],
        ))


        for weekday in range(
            7
        ):

            open_time = str(
                hours[
                    weekday
                ][0]
                or ""
            ).strip()


            close_time = str(
                hours[
                    weekday
                ][1]
                or ""
            ).strip()


            is_closed = (
                not open_time
                or
                not close_time
            )


            if is_closed:

                open_time = None

                close_time = None


            cursor.execute("""
                INSERT INTO business_hours (
                    business_id,
                    weekday,
                    open_time,
                    close_time,
                    is_closed
                )

                VALUES (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?
                )
            """, (

                business["id"],

                weekday,

                open_time,

                close_time,

                is_closed

            ))


        # =================================
        # OWNER ACCOUNT
        # =================================

        if existing_owner:

            if owner_username:

                cursor.execute("""
                    UPDATE business_users

                    SET username = ?

                    WHERE business_id = ?
                """, (

                    owner_username,

                    business["id"]

                ))


            if owner_password:

                salt, password_hash = (
                    hash_password(
                        owner_password
                    )
                )


                cursor.execute("""
                    UPDATE business_users

                    SET
                        password_salt = ?,
                        password_hash = ?

                    WHERE business_id = ?
                """, (

                    salt,

                    password_hash,

                    business["id"]

                ))


        elif (
            owner_username
            and
            owner_password
        ):

            salt, password_hash = (
                hash_password(
                    owner_password
                )
            )


            cursor.execute("""
                INSERT INTO business_users (
                    business_id,
                    username,
                    password_salt,
                    password_hash
                )

                VALUES (
                    ?,
                    ?,
                    ?,
                    ?
                )
            """, (

                business["id"],

                owner_username,

                salt,

                password_hash

            ))


        conn.commit()


    except Exception as error:

        conn.rollback()


        print(
            "SETTINGS SAVE ERROR:",
            repr(
                error
            )
        )


        raise HTTPException(
            status_code=500,
            detail=(
                "Could not save settings. "
                "That username may already be in use."
            )
        )


    finally:

        conn.close()


    return {

        "status":
            "saved"

    }


# =====================================
# LEADS API
# =====================================

@router.get(
    "/api/leads/{business_slug}"
)
def business_leads_api(
    business_slug: str,
    request: Request
):

    business = (
        get_business_by_slug(
            business_slug
        )
    )


    if not business:

        raise HTTPException(
            status_code=404,
            detail=
                "Business not found."
        )


    if not require_owner_session(
        request,
        business
    ):

        raise HTTPException(
            status_code=401,
            detail=
                "Please log in."
        )


    leads = (
        get_business_leads(
            business["id"]
        )
    )


    return JSONResponse(
        content={

            "business": {

                "id":
                    business["id"],

                "name":
                    business["name"],

                "slug":
                    business["slug"]

            },

            "leads": [

                dict(
                    lead
                )

                for lead
                in leads

            ]

        }
    )


# =====================================
# APPOINTMENTS API
# =====================================

@router.get(
    "/api/appointments/{business_slug}"
)
def business_appointments_api(
    business_slug: str,
    request: Request
):

    business = (
        get_business_by_slug(
            business_slug
        )
    )


    if not business:

        raise HTTPException(
            status_code=404,
            detail=
                "Business not found."
        )


    if not require_owner_session(
        request,
        business
    ):

        raise HTTPException(
            status_code=401,
            detail=
                "Please log in."
        )


    appointments = (
        get_business_appointments(
            business["id"]
        )
    )


    return JSONResponse(
        content={

            "business": {

                "id":
                    business["id"],

                "name":
                    business["name"],

                "slug":
                    business["slug"]

            },

            "appointments": [

                dict(
                    appointment
                )

                for appointment
                in appointments

            ]

        }
    )