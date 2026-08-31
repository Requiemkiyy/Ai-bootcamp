import sqlite3
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse


router = APIRouter()


# =====================================
# FILE LOCATIONS
# =====================================

BASE_DIR = Path(__file__).resolve().parent

DATABASE_PATH = BASE_DIR / "leads.db"

DASHBOARD_PATH = BASE_DIR / "dashboard.html"


# =====================================
# DASHBOARD PAGE
# =====================================

@router.get("/dashboard")
def dashboard():

    return FileResponse(
        DASHBOARD_PATH
    )


# =====================================
# GET ALL LEADS
# =====================================

@router.get("/api/leads")
def get_leads():

    conn = sqlite3.connect(
        DATABASE_PATH
    )

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()


    cursor.execute("""
        SELECT
            id,
            customer_name,
            phone_number,
            email,
            vehicle,
            requested_service,
            requested_time
        FROM leads
        ORDER BY id DESC
    """)


    rows = cursor.fetchall()


    conn.close()


    leads = []


    for row in rows:

        leads.append({
            "id": row["id"],
            "customer_name": row["customer_name"],
            "phone_number": row["phone_number"],
            "email": row["email"],
            "vehicle": row["vehicle"],
            "requested_service": row["requested_service"],
            "requested_time": row["requested_time"]
        })


    return leads