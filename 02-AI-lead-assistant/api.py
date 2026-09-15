import os
import re
import html
import json
import traceback

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import (
    FastAPI,
    Request
)

from fastapi.responses import (
    HTMLResponse,
    JSONResponse
)

from pydantic import BaseModel

from starlette.middleware.sessions import (
    SessionMiddleware
)

from lead_assistant import (
    process_customer_message
)

from database import (
    get_default_business,
    get_business_by_slug,
    check_database_rate_limit
)

from dashboard import (
    router as dashboard_router
)


# =====================================
# APP
# =====================================

app = FastAPI(
    title="AI Business Assistant"
)


# =====================================
# SESSION MIDDLEWARE
# =====================================

SESSION_SECRET = os.getenv(
    "SESSION_SECRET",
    "local-development-secret-change-before-production"
)


app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="ai_business_owner_session",
    max_age=60 * 60 * 12,
    same_site="lax",
    https_only=False
)


# =====================================
# DASHBOARD ROUTER
# =====================================

app.include_router(
    dashboard_router
)


# =====================================
# REQUEST MODEL
# =====================================

class CustomerMessage(BaseModel):

    message: str

    session_id: str

    business_slug: str | None = None


# =====================================
# BUSINESS TIMEZONE
# =====================================

BUSINESS_TIMEZONE = os.getenv(
    "BUSINESS_TIMEZONE",
    "America/New_York"
)


# =====================================
# DATE CONTEXT
# =====================================

def add_date_context(
    customer_message
):

    now = datetime.now(
        ZoneInfo(
            BUSINESS_TIMEZONE
        )
    )


    today = now.date()

    tomorrow = (
        today
        + timedelta(
            days=1
        )
    )

    day_after_tomorrow = (
        today
        + timedelta(
            days=2
        )
    )


    lower_message = (
        customer_message.lower()
    )


    relative_dates = []


    # =================================
    # DAY AFTER TOMORROW
    # =================================

    if re.search(
        r"\bday after tomorrow\b",
        lower_message
    ):

        relative_dates.append(
            "The phrase 'day after tomorrow' "
            "means "
            + day_after_tomorrow.strftime(
                "%A, %B %d, %Y"
            )
            + " ("
            + day_after_tomorrow.isoformat()
            + ")."
        )


    # =================================
    # TOMORROW
    # =================================

    elif re.search(
        r"\btomorrow\b",
        lower_message
    ):

        relative_dates.append(
            "The word 'tomorrow' means "
            + tomorrow.strftime(
                "%A, %B %d, %Y"
            )
            + " ("
            + tomorrow.isoformat()
            + ")."
        )


    # =================================
    # TODAY
    # =================================

    if re.search(
        r"\btoday\b",
        lower_message
    ):

        relative_dates.append(
            "The word 'today' means "
            + today.strftime(
                "%A, %B %d, %Y"
            )
            + " ("
            + today.isoformat()
            + ")."
        )


    # =================================
    # ALWAYS GIVE CURRENT DATE
    # =================================

    date_context = (
        "\n\n"
        "[DATE CONTEXT FROM BOOKING SERVER]\n"
        "Current local date: "
        + today.strftime(
            "%A, %B %d, %Y"
        )
        + " ("
        + today.isoformat()
        + ")."
    )


    if relative_dates:

        date_context += (
            "\n"
            + "\n".join(
                relative_dates
            )
        )


    date_context += (
        "\nUse these resolved calendar dates "
        "when interpreting the customer's "
        "booking request. Do not calculate "
        "a different date."
    )


    return (
        customer_message
        + date_context
    )


# =====================================
# CHAT PAGE
# =====================================

def build_chat_page(
    business_name,
    business_slug
):

    safe_business_name = html.escape(
        str(
            business_name
        )
    )


    javascript_business_slug = (
        json.dumps(
            str(
                business_slug
            )
        )
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
        __BUSINESS_NAME__
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

            font-family:
                Arial,
                Helvetica,
                sans-serif;

        }


        .chat-container {

            width: 420px;

            max-width:
                calc(
                    100vw - 30px
                );

            height: 650px;

            max-height:
                calc(
                    100vh - 30px
                );

            background: #1c1c1c;

            border-radius: 18px;

            overflow: hidden;

            display: flex;

            flex-direction: column;

            box-shadow:
                0
                20px
                60px
                rgba(
                    0,
                    0,
                    0,
                    0.45
                );

        }


        .chat-header {

            background: #272727;

            padding: 20px;

            flex-shrink: 0;

        }


        .chat-header h1 {

            margin: 0;

            color: white;

            font-size: 24px;

        }


        .chat-header p {

            margin:
                6px
                0
                0
                0;

            color: #bdbdbd;

            font-size: 14px;

        }


        .chat-messages {

            flex: 1;

            overflow-y: auto;

            padding: 18px;

            display: flex;

            flex-direction: column;

            gap: 14px;

        }


        .message {

            max-width: 78%;

            padding:
                12px
                15px;

            border-radius: 16px;

            line-height: 1.4;

            font-size: 16px;

            word-wrap: break-word;

        }


        .assistant {

            align-self: flex-start;

            background: #353535;

            color: white;

            border-bottom-left-radius:
                6px;

        }


        .customer {

            align-self: flex-end;

            background: white;

            color: black;

            border-bottom-right-radius:
                6px;

        }


        .typing {

            display: none;

            align-self: flex-start;

            background: #353535;

            color: #cfcfcf;

            padding:
                10px
                14px;

            border-radius: 16px;

            font-size: 14px;

        }


        .chat-input-area {

            background: #272727;

            padding: 14px;

            flex-shrink: 0;

        }


        .input-row {

            display: flex;

            gap: 10px;

        }


        #messageInput {

            flex: 1;

            min-width: 0;

            padding:
                12px
                14px;

            border: none;

            border-radius: 8px;

            outline: none;

            font-size: 14px;

        }


        #sendButton {

            padding:
                12px
                20px;

            border: none;

            border-radius: 8px;

            background: white;

            color: black;

            font-weight: bold;

            cursor: pointer;

        }


        #sendButton:disabled {

            opacity: 0.55;

            cursor: not-allowed;

        }


        .input-info {

            margin-top: 7px;

            text-align: right;

            color: #aaa;

            font-size: 11px;

        }

    </style>

</head>


<body>

    <div class="chat-container">


        <div class="chat-header">

            <h1>
                __BUSINESS_NAME__
            </h1>

            <p>
                AI Assistant • Online
            </p>

        </div>


        <div
            class="chat-messages"
            id="chatMessages"
        >

            <div
                class="message assistant"
            >
                Hi! How can I help you today?
            </div>


            <div
                class="typing"
                id="typingIndicator"
            >
                Typing...
            </div>

        </div>


        <div class="chat-input-area">

            <div class="input-row">

                <input
                    id="messageInput"
                    type="text"
                    maxlength="500"
                    placeholder="Type your message..."
                    autocomplete="off"
                >


                <button
                    id="sendButton"
                    type="button"
                >
                    Send
                </button>

            </div>


            <div
                class="input-info"
                id="characterCounter"
            >
                0 / 500
            </div>

        </div>


    </div>


<script>


const BUSINESS_SLUG =
    __BUSINESS_SLUG__;


const chatMessages =
    document.getElementById(
        "chatMessages"
    );


const messageInput =
    document.getElementById(
        "messageInput"
    );


const sendButton =
    document.getElementById(
        "sendButton"
    );


const typingIndicator =
    document.getElementById(
        "typingIndicator"
    );


const characterCounter =
    document.getElementById(
        "characterCounter"
    );


const sessionStorageKey =
    "ai_business_session_"
    + BUSINESS_SLUG;


let sessionId =
    localStorage.getItem(
        sessionStorageKey
    );


if (!sessionId) {

    if (
        window.crypto
        &&
        crypto.randomUUID
    ) {

        sessionId =
            crypto.randomUUID();

    } else {

        sessionId =
            Date.now().toString()
            + "-"
            + Math.random()
                .toString(36)
                .substring(2);

    }


    localStorage.setItem(
        sessionStorageKey,
        sessionId
    );

}


function addMessage(
    text,
    sender
) {

    const message =
        document.createElement(
            "div"
        );


    message.classList.add(
        "message",
        sender
    );


    message.textContent =
        text;


    chatMessages.insertBefore(
        message,
        typingIndicator
    );


    chatMessages.scrollTop =
        chatMessages.scrollHeight;

}


function showTyping() {

    typingIndicator.style.display =
        "block";


    chatMessages.scrollTop =
        chatMessages.scrollHeight;

}


function hideTyping() {

    typingIndicator.style.display =
        "none";

}


async function sendMessage() {

    const message =
        messageInput.value.trim();


    if (!message) {

        return;

    }


    if (
        message.length > 500
    ) {

        addMessage(
            "Please keep your message under 500 characters.",
            "assistant"
        );

        return;

    }


    addMessage(
        message,
        "customer"
    );


    messageInput.value =
        "";


    updateCharacterCounter();


    sendButton.disabled =
        true;


    showTyping();


    try {

        const response =
            await fetch(
                "/message",
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

                                message:
                                    message,

                                session_id:
                                    sessionId,

                                business_slug:
                                    BUSINESS_SLUG

                            }
                        )

                }
            );


        const rawText =
            await response.text();


        let data;


        try {

            data =
                JSON.parse(
                    rawText
                );

        } catch (
            parseError
        ) {

            console.error(
                "Invalid server response:",
                rawText
            );


            throw new Error(
                "Invalid server response"
            );

        }


        hideTyping();


        if (
            response.status
            === 429
        ) {

            addMessage(
                data.response
                ||
                "You've sent too many messages. Please wait a moment.",
                "assistant"
            );

            return;

        }


        if (
            !response.ok
        ) {

            console.error(
                "Server error:",
                data
            );


            addMessage(
                data.response
                ||
                "Sorry, I couldn't connect to the assistant.",
                "assistant"
            );

            return;

        }


        addMessage(
            data.response
            ||
            "Sorry, I had trouble processing that.",
            "assistant"
        );


    } catch (
        error
    ) {

        hideTyping();


        console.error(
            "Chat error:",
            error
        );


        addMessage(
            "Sorry, I couldn't connect to the assistant.",
            "assistant"
        );


    } finally {

        sendButton.disabled =
            false;


        messageInput.focus();

    }

}


function updateCharacterCounter() {

    characterCounter.textContent =
        messageInput.value.length
        + " / 500";

}


sendButton.addEventListener(
    "click",
    sendMessage
);


messageInput.addEventListener(
    "keydown",
    function(
        event
    ) {

        if (
            event.key
            === "Enter"
            &&
            !event.shiftKey
        ) {

            event.preventDefault();

            sendMessage();

        }

    }
);


messageInput.addEventListener(
    "input",
    updateCharacterCounter
);


messageInput.focus();


</script>

</body>

</html>
"""


    page = page.replace(
        "__BUSINESS_NAME__",
        safe_business_name
    )


    page = page.replace(
        "__BUSINESS_SLUG__",
        javascript_business_slug
    )


    return page


# =====================================
# DEFAULT CHAT
# =====================================

@app.get(
    "/",
    response_class=HTMLResponse
)
def home():

    business = (
        get_default_business()
    )


    if not business:

        return HTMLResponse(
            content="""
                <html>
                    <body>
                        <h1>
                            Business unavailable
                        </h1>
                    </body>
                </html>
            """,
            status_code=404
        )


    return HTMLResponse(
        content=build_chat_page(
            business["name"],
            business["slug"]
        )
    )


# =====================================
# BUSINESS CHAT
# =====================================

@app.get(
    "/b/{business_slug}",
    response_class=HTMLResponse
)
def business_chat(
    business_slug: str
):

    business = (
        get_business_by_slug(
            business_slug
        )
    )


    if not business:

        return HTMLResponse(
            content="""
                <html>

                    <body
                        style="
                            background:#101010;
                            color:white;
                            font-family:Arial;
                            text-align:center;
                            padding-top:100px;
                        "
                    >

                        <h1>
                            Business not found
                        </h1>

                        <p>
                            This AI assistant is not available.
                        </p>

                    </body>

                </html>
            """,
            status_code=404
        )


    return HTMLResponse(
        content=build_chat_page(
            business["name"],
            business["slug"]
        )
    )


# =====================================
# MESSAGE API
# =====================================

@app.post(
    "/message"
)
def message(
    customer: CustomerMessage,
    request: Request
):

    try:

        customer_message = (
            customer.message.strip()
        )


        # =================================
        # VALIDATE MESSAGE
        # =================================

        if not customer_message:

            return {

                "response":
                    "Please enter a message.",

                "lead_status":
                    "none",

                "booking_status":
                    "none"

            }


        if (
            len(
                customer_message
            )
            > 500
        ):

            return {

                "response":
                    "Please keep your message under 500 characters.",

                "lead_status":
                    "none",

                "booking_status":
                    "none"

            }


        # =================================
        # FIND BUSINESS
        # =================================

        if customer.business_slug:

            business = (
                get_business_by_slug(
                    customer.business_slug
                )
            )

        else:

            business = (
                get_default_business()
            )


        if not business:

            return JSONResponse(
                status_code=404,
                content={

                    "response":
                        "Sorry, this business is currently unavailable.",

                    "lead_status":
                        "error",

                    "booking_status":
                        "error"

                }
            )


        business_id = (
            business["id"]
        )


        # =================================
        # RESOLVE RELATIVE DATES
        # =================================

        ai_customer_message = (
            add_date_context(
                customer_message
            )
        )


        # =================================
        # CLIENT IDENTITY
        # =================================

        client_ip = "unknown"


        if request.client:

            client_ip = (
                request.client.host
            )


        client_key = (

            str(
                business_id
            )

            + ":"

            + client_ip

            + ":"

            + customer.session_id

        )


        # =================================
        # RATE LIMIT
        # =================================

        rate_limit = (
            check_database_rate_limit(

                client_key=
                    client_key,

                max_requests=
                    15,

                window_seconds=
                    60,

                minimum_interval_seconds=
                    0,

                business_id=
                    business_id

            )
        )


        if not rate_limit[
            "allowed"
        ]:

            wait_seconds = (
                rate_limit.get(
                    "wait_seconds",
                    60
                )
            )


            return JSONResponse(
                status_code=429,
                content={

                    "response":
                        (
                            "You've sent too many messages. "
                            "Please wait about "
                            + str(
                                wait_seconds
                            )
                            + " seconds."
                        ),

                    "lead_status":
                        "rate_limited",

                    "booking_status":
                        "none"

                }
            )


        # =================================
        # PROCESS MESSAGE
        # =================================

        result = (
            process_customer_message(

                customer_message=
                    ai_customer_message,

                session_id=
                    customer.session_id,

                business_id=
                    business_id

            )
        )


        return result


    except Exception as error:

        print(
            "\n"
            "====================================="
        )

        print(
            "MESSAGE API ERROR"
        )

        print(
            "====================================="
        )

        traceback.print_exc()

        print(
            "ERROR:",
            repr(
                error
            )
        )

        print(
            "=====================================\n"
        )


        return JSONResponse(
            status_code=500,
            content={

                "response":
                    "Sorry, I couldn't connect to the assistant.",

                "lead_status":
                    "error",

                "booking_status":
                    "error"

            }
        )


# =====================================
# HEALTH CHECK
# =====================================

@app.get(
    "/health"
)
def health():

    business = (
        get_default_business()
    )


    return {

        "status":
            "ok",

        "default_business":
            (
                business["slug"]
                if business
                else None
            )

    }