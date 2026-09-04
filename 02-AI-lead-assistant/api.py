from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from uuid import UUID
import traceback

from lead_assistant import process_customer_message
from dashboard import router as dashboard_router

from database import (
    check_database_rate_limit
)


# =====================================
# APP
# =====================================

app = FastAPI()

app.include_router(
    dashboard_router
)


# =====================================
# PROTECTION SETTINGS
# =====================================

MAX_MESSAGE_LENGTH = 500

RATE_LIMIT_WINDOW_SECONDS = 60

# PRODUCTION LIMIT
RATE_LIMIT_MAX_REQUESTS = 15

MIN_REQUEST_INTERVAL_SECONDS = 0.75


# =====================================
# REQUEST MODEL
# =====================================

class CustomerMessage(BaseModel):
    message: str
    session_id: str


# =====================================
# CLIENT IP
# =====================================

def get_client_ip(request: Request):

    forwarded_for = request.headers.get(
        "x-forwarded-for"
    )

    if forwarded_for:

        return (
            forwarded_for
            .split(",")[0]
            .strip()
        )

    if request.client:

        return request.client.host

    return "unknown"


# =====================================
# SESSION VALIDATION
# =====================================

def validate_session_id(
    session_id
):

    if not session_id:

        raise HTTPException(
            status_code=400,
            detail="Invalid session."
        )

    if len(session_id) > 100:

        raise HTTPException(
            status_code=400,
            detail="Invalid session."
        )

    try:

        UUID(session_id)

    except (
        ValueError,
        TypeError,
        AttributeError
    ):

        raise HTTPException(
            status_code=400,
            detail="Invalid session."
        )


# =====================================
# MESSAGE VALIDATION
# =====================================

def validate_message(
    message
):

    if message is None:

        raise HTTPException(
            status_code=400,
            detail="Please enter a message."
        )

    message = message.strip()

    if not message:

        raise HTTPException(
            status_code=400,
            detail="Please enter a message."
        )

    if (
        len(message)
        > MAX_MESSAGE_LENGTH
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                f"Messages must be under "
                f"{MAX_MESSAGE_LENGTH} characters."
            )
        )

    return message


# =====================================
# DATABASE RATE LIMIT
# =====================================

def enforce_rate_limit(
    request,
    session_id
):

    client_ip = get_client_ip(
        request
    )

    client_key = (
        f"{client_ip}:"
        f"{session_id}"
    )

    result = (
        check_database_rate_limit(

            client_key=
                client_key,

            max_requests=
                RATE_LIMIT_MAX_REQUESTS,

            window_seconds=
                RATE_LIMIT_WINDOW_SECONDS,

            minimum_interval_seconds=
                MIN_REQUEST_INTERVAL_SECONDS
        )
    )


    # ---------------------------------
    # ALLOWED
    # ---------------------------------

    if result.get(
        "allowed",
        False
    ):

        return


    # ---------------------------------
    # BLOCKED
    # ---------------------------------

    wait_seconds = result.get(
        "wait_seconds",
        1
    )

    raise HTTPException(

        status_code=429,

        detail=(
            "You've sent too many messages. "
            f"Please wait about "
            f"{wait_seconds} seconds."
        ),

        headers={
            "Retry-After":
                str(wait_seconds)
        }
    )


# =====================================
# CUSTOMER WEBSITE
# =====================================

@app.get(
    "/",
    response_class=HTMLResponse
)
def home():

    return """
<!DOCTYPE html>

<html lang="en">

<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>
        Freedom Auto Detailing
    </title>


    <style>

        * {
            box-sizing: border-box;
        }


        body {

            margin: 0;

            min-height: 100vh;

            display: flex;

            align-items: center;

            justify-content: center;

            background: #111111;

            color: #ffffff;

            font-family:
                Arial,
                Helvetica,
                sans-serif;
        }


        .chat-card {

            width: 420px;

            max-width:
                calc(100vw - 30px);

            height: 680px;

            max-height:
                calc(100vh - 30px);

            display: flex;

            flex-direction: column;

            overflow: hidden;

            background: #1b1b1b;

            border-radius: 18px;

            box-shadow:
                0 20px 60px
                rgba(
                    0,
                    0,
                    0,
                    0.45
                );
        }


        .header {

            padding: 20px;

            background: #282828;
        }


        .header h1 {

            margin: 0;

            font-size: 24px;
        }


        .header p {

            margin:
                6px
                0
                0;

            color: #b8c0cc;

            font-size: 14px;
        }


        .messages {

            flex: 1;

            overflow-y: auto;

            padding: 18px;

            display: flex;

            flex-direction: column;

            gap: 12px;
        }


        .bubble {

            max-width: 78%;

            padding:
                12px
                15px;

            border-radius: 15px;

            line-height: 1.4;

            word-wrap: break-word;
        }


        .bot {

            align-self: flex-start;

            background: #363636;
        }


        .user {

            align-self: flex-end;

            background: #ffffff;

            color: #111111;
        }


        .typing {

            align-self: flex-start;

            background: #363636;

            color: #cccccc;

            display: none;
        }


        .input-area {

            display: flex;

            gap: 10px;

            padding: 15px;

            background: #292929;
        }


        #message-input {

            flex: 1;

            min-width: 0;

            border: 0;

            outline: none;

            border-radius: 8px;

            padding:
                12px
                13px;

            font-size: 14px;
        }


        #send-button {

            border: 0;

            border-radius: 8px;

            padding:
                0
                18px;

            cursor: pointer;

            font-weight: 700;
        }


        #send-button:disabled {

            cursor: not-allowed;

            opacity: 0.6;
        }


        .counter {

            padding:
                0
                16px
                8px;

            background: #292929;

            text-align: right;

            color: #8f98a4;

            font-size: 11px;
        }


        .counter.warning {

            color: #ffcc66;
        }


    </style>

</head>


<body>


<div class="chat-card">


    <div class="header">

        <h1>
            Freedom Auto Detailing
        </h1>

        <p>
            AI Assistant • Online
        </p>

    </div>


    <div
        id="messages"
        class="messages"
    >

        <div class="bubble bot">
            Hi! How can I help you with your vehicle today?
        </div>


        <div
            id="typing"
            class="bubble typing"
        >
            Typing...
        </div>

    </div>


    <div class="input-area">

        <input
            id="message-input"
            type="text"
            maxlength="500"
            placeholder="Type your message..."
            autocomplete="off"
        >


        <button
            id="send-button"
        >
            Send
        </button>

    </div>


    <div
        id="counter"
        class="counter"
    >
        0 / 500
    </div>


</div>


<script>


    // =================================
    // SESSION
    // =================================

    let sessionId =
        localStorage.getItem(
            "freedom_detail_session"
        );


    if (!sessionId) {

        sessionId =
            crypto.randomUUID();

        localStorage.setItem(
            "freedom_detail_session",
            sessionId
        );
    }


    // =================================
    // ELEMENTS
    // =================================

    const messages =
        document.getElementById(
            "messages"
        );


    const typing =
        document.getElementById(
            "typing"
        );


    const input =
        document.getElementById(
            "message-input"
        );


    const sendButton =
        document.getElementById(
            "send-button"
        );


    const counter =
        document.getElementById(
            "counter"
        );


    // =================================
    // ADD MESSAGE
    // =================================

    function addMessage(
        text,
        sender
    ) {

        const bubble =
            document.createElement(
                "div"
            );


        bubble.classList.add(
            "bubble",
            sender
        );


        bubble.textContent =
            text;


        messages.insertBefore(
            bubble,
            typing
        );


        messages.scrollTop =
            messages.scrollHeight;
    }


    // =================================
    // CHARACTER COUNTER
    // =================================

    input.addEventListener(

        "input",

        () => {

            const length =
                input.value.length;


            counter.textContent =
                `${length} / 500`;


            if (
                length >= 450
            ) {

                counter.classList.add(
                    "warning"
                );

            } else {

                counter.classList.remove(
                    "warning"
                );
            }
        }
    );


    // =================================
    // SEND MESSAGE
    // =================================

    async function sendMessage() {


        const message =
            input.value.trim();


        if (!message) {

            return;
        }


        if (
            message.length > 500
        ) {

            addMessage(
                "That message is too long. Please keep it under 500 characters.",
                "bot"
            );

            return;
        }


        // -----------------------------
        // LOCK INPUT
        // -----------------------------

        input.value = "";


        counter.textContent =
            "0 / 500";


        counter.classList.remove(
            "warning"
        );


        input.disabled =
            true;


        sendButton.disabled =
            true;


        // -----------------------------
        // USER MESSAGE
        // -----------------------------

        addMessage(
            message,
            "user"
        );


        // -----------------------------
        // TYPING
        // -----------------------------

        typing.style.display =
            "block";


        messages.scrollTop =
            messages.scrollHeight;


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
                            JSON.stringify({

                                message:
                                    message,

                                session_id:
                                    sessionId
                            })
                    }
                );


            const rawText =
                await response.text();


            let data = null;


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
            }


            typing.style.display =
                "none";


            // -------------------------
            // RATE LIMIT
            // -------------------------

            if (
                response.status === 429
            ) {

                addMessage(
                    data?.detail
                    ||
                    "You've sent too many messages. Please wait a moment.",
                    "bot"
                );

                return;
            }


            // -------------------------
            // OTHER ERROR
            // -------------------------

            if (!response.ok) {

                addMessage(
                    data?.detail
                    ||
                    "Sorry, I couldn't process that message.",
                    "bot"
                );

                return;
            }


            // -------------------------
            // SUCCESS
            // -------------------------

            if (
                data
                &&
                data.response
            ) {

                addMessage(
                    data.response,
                    "bot"
                );

            } else {

                addMessage(
                    "Sorry, I couldn't connect to the assistant.",
                    "bot"
                );
            }


        } catch (
            error
        ) {


            console.error(
                error
            );


            typing.style.display =
                "none";


            addMessage(
                "Sorry, I couldn't connect to the assistant.",
                "bot"
            );


        } finally {


            input.disabled =
                false;


            sendButton.disabled =
                false;


            input.focus();
        }
    }


    // =================================
    // SEND BUTTON
    // =================================

    sendButton.addEventListener(
        "click",
        sendMessage
    );


    // =================================
    // ENTER KEY
    // =================================

    input.addEventListener(

        "keydown",

        event => {

            if (
                event.key === "Enter"
                &&
                !event.shiftKey
            ) {

                event.preventDefault();

                sendMessage();
            }
        }
    );


    input.focus();


</script>


</body>

</html>
"""


# =====================================
# MESSAGE API
# =====================================

@app.post("/message")
def message_endpoint(
    customer: CustomerMessage,
    request: Request
):

    try:


        # =================================
        # VALIDATE SESSION
        # =================================

        validate_session_id(
            customer.session_id
        )


        # =================================
        # VALIDATE MESSAGE
        # =================================

        clean_message = (
            validate_message(
                customer.message
            )
        )


        # =================================
        # DATABASE RATE LIMIT
        #
        # THIS RUNS BEFORE OPENAI.
        # =================================

        enforce_rate_limit(
            request,
            customer.session_id
        )


        # =================================
        # AI ASSISTANT
        # =================================

        result = (
            process_customer_message(
                clean_message,
                customer.session_id
            )
        )


        return result


    # =====================================
    # EXPECTED HTTP ERRORS
    # =====================================

    except HTTPException:

        raise


    # =====================================
    # UNEXPECTED ERROR
    # =====================================

    except Exception as error:


        print(
            "\n"
            "=====================================\n"
            "MESSAGE API ERROR\n"
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


        raise HTTPException(

            status_code=500,

            detail=(
                "Sorry, the assistant had "
                "trouble processing that."
            )
        )