from database import (
    get_connection,
    get_business_by_slug
)


# =====================================
# TEST BUSINESS
# =====================================

BUSINESS_NAME = "Elite Lawn Care"
BUSINESS_SLUG = "elite-lawn-care"
BUSINESS_LOCATION = "Columbus, Ohio"


SERVICES = [
    {
        "name": "Lawn Mowing",
        "description": "Standard lawn mowing service.",
        "price_cents": 5000,
        "duration_minutes": 60,
        "service_type": "service"
    },
    {
        "name": "Yard Cleanup",
        "description": "General yard cleanup service.",
        "price_cents": 12000,
        "duration_minutes": 120,
        "service_type": "service"
    },
    {
        "name": "Mulching",
        "description": "Mulch installation service.",
        "price_cents": 15000,
        "duration_minutes": 120,
        "service_type": "service"
    }
]


# Monday = 0
# Tuesday = 1
# Wednesday = 2
# Thursday = 3
# Friday = 4
# Saturday = 5
# Sunday = 6

BUSINESS_HOURS = [
    (0, "08:00", "17:00", False),
    (1, "08:00", "17:00", False),
    (2, "08:00", "17:00", False),
    (3, "08:00", "17:00", False),
    (4, "08:00", "17:00", False),
    (5, "09:00", "14:00", False),
    (6, None, None, True)
]


# =====================================
# CREATE BUSINESS
# =====================================

def create_test_business():

    existing_business = get_business_by_slug(
        BUSINESS_SLUG
    )

    if existing_business:

        print("")
        print("=====================================")
        print("BUSINESS ALREADY EXISTS")
        print("=====================================")
        print("Name:", existing_business["name"])
        print("Slug:", existing_business["slug"])
        print("ID:", existing_business["id"])
        print("=====================================")
        print("")

        return existing_business["id"]


    conn = get_connection()
    cursor = conn.cursor()

    try:

        # =================================
        # BUSINESS
        # =================================

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
            BUSINESS_NAME,
            BUSINESS_SLUG,
            BUSINESS_LOCATION,
            None,
            None,
            True,
            "2026-09-09",
            "2026-09-09"
        ))

        conn.commit()


        # =================================
        # GET BUSINESS ID
        # =================================

        cursor.execute("""
            SELECT id
            FROM businesses
            WHERE slug = ?
        """, (
            BUSINESS_SLUG,
        ))

        business = cursor.fetchone()

        if not business:

            raise RuntimeError(
                "Business was inserted but could not be found."
            )

        business_id = business["id"]


        # =================================
        # SERVICES
        # =================================

        for service in SERVICES:

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
                service["description"],
                service["price_cents"],
                service["duration_minutes"],
                service["service_type"],
                True,
                "2026-09-09"
            ))


        # =================================
        # HOURS
        # =================================

        for (
            weekday,
            open_time,
            close_time,
            is_closed
        ) in BUSINESS_HOURS:

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


        conn.commit()


        # =================================
        # SUCCESS
        # =================================

        print("")
        print("=====================================")
        print("ELITE LAWN CARE CREATED")
        print("=====================================")
        print("Business ID:", business_id)
        print("Name:", BUSINESS_NAME)
        print("Slug:", BUSINESS_SLUG)
        print("")
        print("Services:")
        print("- Lawn Mowing: $50")
        print("- Yard Cleanup: $120")
        print("- Mulching: $150")
        print("")
        print("URL:")
        print(
            "http://127.0.0.1:8000/b/"
            + BUSINESS_SLUG
        )
        print("=====================================")
        print("")

        return business_id


    except Exception:

        conn.rollback()
        raise


    finally:

        conn.close()


# =====================================
# RUN
# =====================================

if __name__ == "__main__":

    create_test_business()