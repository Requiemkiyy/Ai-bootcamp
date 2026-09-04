import os
import secrets

from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status
)

from fastapi.responses import FileResponse

from fastapi.security import (
    HTTPBasic,
    HTTPBasicCredentials
)

from database import get_connection


router = APIRouter()

security = HTTPBasic()

BASE_DIR = Path(
    __file__
).resolve().parent

DASHBOARD_PATH = (
    BASE_DIR
    / "dashboard.html"
)


# =====================================
# DASHBOARD LOGIN
# =====================================

def verify_dashboard_login(
    credentials: HTTPBasicCredentials = Depends(
        security
    )
):

    expected_username = os.getenv(
        "DASHBOARD_USERNAME"
    )

    expected_password = os.getenv(
        "DASHBOARD_PASSWORD"
    )

    if (
        not expected_username
        or not expected_password
    ):

        raise HTTPException(
            status_code=
                status.HTTP_503_SERVICE_UNAVAILABLE,

            detail=
                "Dashboard login is not configured."
        )

    username_ok = secrets.compare_digest(
        credentials.username.encode(
            "utf-8"
        ),

        expected_username.encode(
            "utf-8"
        )
    )

    password_ok = secrets.compare_digest(
        credentials.password.encode(
            "utf-8"
        ),

        expected_password.encode(
            "utf-8"
        )
    )

    if not (
        username_ok
        and password_ok
    ):

        raise HTTPException(
            status_code=
                status.HTTP_401_UNAUTHORIZED,

            detail=
                "Incorrect username or password.",

            headers={
                "WWW-Authenticate":
                    "Basic"
            }
        )

    return credentials.username


# =====================================
# DASHBOARD PAGE
# =====================================

@router.get("/dashboard")
def dashboard(
    _: str = Depends(
        verify_dashboard_login
    )
):

    return FileResponse(
        DASHBOARD_PATH
    )


# =====================================
# LEADS API
# =====================================

@router.get("/api/leads")
def get_leads(
    _: str = Depends(
        verify_dashboard_login
    )
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
                status,
                created_at
            FROM leads
            ORDER BY id DESC
        """)

        rows = cursor.fetchall()

        leads = []

        for row in rows:

            leads.append({
                "id":
                    row["id"],

                "customer_name":
                    row["customer_name"],

                "phone_number":
                    row["phone_number"],

                "email":
                    row["email"],

                "vehicle":
                    row["vehicle"],

                "requested_service":
                    row["requested_service"],

                "requested_time":
                    row["requested_time"],

                "status":
                    row["status"],

                "created_at":
                    row["created_at"]
            })

        return leads

    finally:

        conn.close()