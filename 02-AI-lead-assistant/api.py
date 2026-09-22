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


# Keep local HTTP development working, while allowing
# production to require HTTPS-only owner session cookies.
COOKIE_SECURE = (
    os.getenv(
        "COOKIE_SECURE",
        "false"
    )
    .strip()
    .lower()
    in (
        "1",
        "true",
        "yes",
        "on"
    )
)


app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="ai_business_owner_session",
    max_age=60 * 60 * 12,
    same_site="lax",
    https_only=COOKIE_SECURE
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
# NEXORA AI WEBSITE
# =====================================

@app.get(
    "/",
    response_class=HTMLResponse
)
def home():

    return HTMLResponse(
        content="""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="ORVELIUS provides AI-powered customer assistants for local service businesses, helping capture leads, answer customer questions, and schedule appointments.">
    <title>ORVELIUS | AI Customer Assistants for Businesses</title>

    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        html { scroll-behavior: smooth; }
        body {
            background: #09090b;
            color: #f5f5f5;
            font-family: Arial, Helvetica, sans-serif;
            line-height: 1.6;
        }
        a { color: inherit; text-decoration: none; }
        .wrap { width: min(1120px, calc(100% - 40px)); margin: 0 auto; }
        nav {
            position: sticky; top: 0; z-index: 20;
            background: rgba(9,9,11,.92);
            border-bottom: 1px solid #25252b;
            backdrop-filter: blur(12px);
        }
        .nav-inner {
            min-height: 72px; display: flex; align-items: center;
            justify-content: space-between; gap: 20px;
        }
        .brand { font-size: 22px; font-weight: 800; letter-spacing: -.5px; }
        .nav-links { display: flex; align-items: center; gap: 24px; color: #c7c7ce; font-size: 14px; }
        .button {
            display: inline-flex; align-items: center; justify-content: center;
            min-height: 48px; padding: 0 22px; border-radius: 10px;
            background: #fff; color: #09090b; font-weight: 700;
        }
        .button.secondary { background: transparent; color: #fff; border: 1px solid #34343c; }
        .hero { padding: 110px 0 90px; text-align: center; }
        .eyebrow {
            display: inline-block; margin-bottom: 22px; padding: 7px 12px;
            border: 1px solid #303038; border-radius: 999px;
            color: #c9c9d1; font-size: 13px;
        }
        .hero h1 {
            max-width: 850px; margin: 0 auto;
            font-size: clamp(42px,7vw,76px); line-height: 1.02; letter-spacing: -3px;
        }
        .hero p {
            max-width: 690px; margin: 26px auto 0;
            color: #aaaab3; font-size: 19px;
        }
        .hero-actions {
            margin-top: 34px; display: flex; justify-content: center;
            flex-wrap: wrap; gap: 12px;
        }
        section { padding: 85px 0; border-top: 1px solid #202026; }
        .section-heading { max-width: 680px; margin-bottom: 42px; }
        .section-heading h2 {
            font-size: clamp(30px,4vw,46px); line-height: 1.1; letter-spacing: -1.5px;
        }
        .section-heading p { margin-top: 14px; color: #aaaab3; font-size: 17px; }
        .grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 18px; }
        .card {
            padding: 28px; border: 1px solid #292930;
            border-radius: 16px; background: #111114;
        }
        .card h3 { margin-bottom: 10px; font-size: 19px; }
        .card p { color: #a9a9b2; font-size: 15px; }
        .steps { counter-reset: step; }
        .step::before {
            counter-increment: step; content: "0" counter(step);
            display: block; margin-bottom: 18px; color: #777782;
            font-weight: 700; font-size: 13px;
        }
        .pricing {
            max-width: 620px; margin: 0 auto; padding: 42px;
            border: 1px solid #34343d; border-radius: 20px; background: #111114;
        }
        .price { margin: 20px 0 4px; font-size: 52px; font-weight: 800; letter-spacing: -2px; }
        .price span { color: #9b9ba5; font-size: 17px; font-weight: 400; letter-spacing: 0; }
        .pricing ul { margin: 28px 0; padding-left: 20px; color: #c7c7ce; }
        .pricing li { margin: 10px 0; }
        .pricing .button { width: 100%; }
        .legal-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
        .legal-card p { margin-bottom: 12px; color: #a9a9b2; font-size: 14px; }
        footer {
            padding: 45px 0; border-top: 1px solid #202026;
            color: #888892; font-size: 14px;
        }
        .footer-inner { display: flex; justify-content: space-between; gap: 20px; flex-wrap: wrap; }
        @media (max-width: 780px) {
            .nav-links a:not(.button) { display: none; }
            .hero { padding: 80px 0 70px; }
            .hero h1 { letter-spacing: -2px; }
            .grid, .legal-grid { grid-template-columns: 1fr; }
            section { padding: 65px 0; }
            .pricing { padding: 28px; }
        }
    </style>
</head>
<body>
    <nav>
        <div class="wrap nav-inner">
            <a class="brand" href="/">ORVELIUS</a>
            <div class="nav-links">
                <a href="#features">Features</a>
                <a href="#pricing">Pricing</a>
                <a href="#policies">Policies</a>
                <a class="button" href="https://buy.stripe.com/28E4gr7p4eVrg6G9w6g7e00">Get Started</a>
            </div>
        </div>
    </nav>

    <main>
        <header class="hero">
            <div class="wrap">
                <div class="eyebrow">AI customer assistance for service businesses</div>
                <h1>Turn customer conversations into booked business.</h1>
                <p>
                    ORVELIUS gives local service businesses an AI-powered customer
                    assistant that can answer service questions, capture leads, and
                    help customers schedule appointments.
                </p>
                <div class="hero-actions">
                    <a class="button" href="https://buy.stripe.com/28E4gr7p4eVrg6G9w6g7e00">Get Started</a>
                    <a class="button secondary" href="#features">See What It Does</a>
                </div>
            </div>
        </header>

        <section id="features">
            <div class="wrap">
                <div class="section-heading">
                    <h2>Built to handle the conversations that turn into customers.</h2>
                    <p>Your assistant uses your business information, services, pricing, and hours to help customers around the clock.</p>
                </div>
                <div class="grid">
                    <div class="card"><h3>AI Customer Support</h3><p>Answer common questions about services, pricing, availability, and business information.</p></div>
                    <div class="card"><h3>Lead Capture</h3><p>Collect customer contact information and service requests so opportunities are not lost.</p></div>
                    <div class="card"><h3>Appointment Booking</h3><p>Help customers request available appointment times based on your services and business hours.</p></div>
                    <div class="card"><h3>Owner Dashboard</h3><p>View leads and appointments from a private business dashboard.</p></div>
                    <div class="card"><h3>Business Controls</h3><p>Update services, prices, and operating hours without rebuilding the assistant.</p></div>
                    <div class="card"><h3>Business-Specific Setup</h3><p>Each assistant is configured around the individual business instead of using generic answers.</p></div>
                </div>
            </div>
        </section>

        <section>
            <div class="wrap">
                <div class="section-heading">
                    <h2>Simple setup.</h2>
                    <p>Get from business information to a working customer assistant without a complicated software rollout.</p>
                </div>
                <div class="grid steps">
                    <div class="card step"><h3>Tell us about your business</h3><p>Provide your services, prices, operating hours, and other information customers need.</p></div>
                    <div class="card step"><h3>We configure your assistant</h3><p>Your business gets its own customer-facing assistant and private management dashboard.</p></div>
                    <div class="card step"><h3>Start handling customers</h3><p>Customers can ask questions, submit their information, and request appointments.</p></div>
                </div>
            </div>
        </section>

        <section id="pricing">
            <div class="wrap">
                <div class="pricing">
                    <p class="eyebrow">AI Business Assistant</p>
                    <h2>One straightforward monthly plan.</h2>
                    <div class="price">$149 <span>/ month</span></div>
                    <ul>
                        <li>AI customer assistant</li>
                        <li>Lead capture</li>
                        <li>Appointment booking</li>
                        <li>Private owner dashboard</li>
                        <li>Service, price, and hours management</li>
                    </ul>
                    <a class="button" href="https://buy.stripe.com/28E4gr7p4eVrg6G9w6g7e00">Subscribe Now</a>
                </div>
            </div>
        </section>

        <section id="contact">
            <div class="wrap">
                <div class="section-heading">
                    <h2>Interested in ORVELIUS?</h2>
                    <p>Contact ORVELIUS to discuss your business and determine whether the AI Business Assistant fits your customer workflow.</p>
                </div>
                <div class="card">
                    <h3>Customer support and sales</h3>
                    <p>Email: support@orvelius.com</p>
                </div>
            </div>
        </section>

        <section id="policies">
            <div class="wrap">
                <div class="section-heading">
                    <h2>Legal & Policies</h2>
                    <p>Effective September 21, 2026. These terms apply to ORVELIUS business customers and use of the ORVELIUS AI Business Assistant.</p>
                </div>
                <div class="legal-grid">
                    <div class="card legal-card" id="terms">
                        <h3>Terms of Service</h3>
                        <p><strong>Subscription.</strong> ORVELIUS provides subscription-based AI customer assistance software for businesses. The current standard plan is $149 USD per month, billed automatically on a recurring monthly basis until cancelled. Applicable taxes may be added where required.</p>
                        <p><strong>Service.</strong> The service may include an AI customer assistant, lead capture, appointment-request and booking features, an owner dashboard, and tools for managing business services, pricing, and hours. Features may evolve as the service is improved.</p>
                        <p><strong>Customer responsibilities.</strong> Customers must provide accurate and lawful business information, maintain appropriate access credentials, review their configured assistant and business settings, and use information collected through ORVELIUS in accordance with applicable law. Customers are responsible for determining whether the service is suitable for their business.</p>
                        <p><strong>AI limitations.</strong> AI-generated responses may occasionally be inaccurate, incomplete, or unexpected. ORVELIUS does not guarantee that every message, lead, appointment request, or automated response will be error-free. Customers should independently review important business, legal, financial, safety, or other high-impact information.</p>
                        <p><strong>No results guarantee.</strong> ORVELIUS does not guarantee any specific number of leads, appointments, customers, sales, revenue, profit, or other business result.</p>
                        <p><strong>Acceptable use.</strong> Customers may not use the service for unlawful, fraudulent, abusive, deceptive, infringing, or harmful activity; attempt unauthorized access; interfere with service operation; or use the service in a manner that violates third-party rights.</p>
                        <p><strong>Availability and third parties.</strong> Availability may be affected by maintenance, internet or hosting failures, AI providers, payment processors, database providers, or other third-party systems. ORVELIUS may modify, maintain, suspend, or discontinue portions of the service when reasonably necessary.</p>
                        <p><strong>Payment and suspension.</strong> Customers authorize recurring charges associated with their selected subscription. If payment fails or remains unpaid, ORVELIUS may restrict or suspend access until the account is brought current.</p>
                        <p><strong>Intellectual property.</strong> ORVELIUS retains ownership of its software, platform, designs, systems, and related intellectual property. Customers retain ownership of business information and content they provide, subject to the rights reasonably necessary for ORVELIUS and its service providers to host, process, transmit, and display that information to provide the service.</p>
                        <p><strong>Limitation of liability.</strong> To the maximum extent permitted by applicable law, ORVELIUS will not be liable for indirect, incidental, special, consequential, exemplary, or lost-profit damages arising from use of or inability to use the service. To the maximum extent permitted by applicable law, ORVELIUS's aggregate liability arising from the service will not exceed the amounts paid by the customer to ORVELIUS during the three months immediately preceding the event giving rise to the claim.</p>
                        <p><strong>Governing law.</strong> These Terms are governed by the laws of the State of Ohio, without regard to conflict-of-law principles, except where applicable law requires otherwise.</p>
                        <p><strong>Changes.</strong> ORVELIUS may update these Terms from time to time. Material changes will be reflected by an updated effective date and, when appropriate, additional notice.</p>
                        <p><strong>Contact.</strong> Questions about these Terms may be sent to support@orvelius.com.</p>
                    </div>
                    <div class="card legal-card" id="privacy">
                        <h3>Privacy Policy</h3>
                        <p><strong>Information processed.</strong> ORVELIUS may process business account information and information submitted through customer-facing assistants, including names, phone numbers, email addresses, service requests, appointment details, messages, and business configuration information.</p>
                        <p><strong>How information is used.</strong> Information is used to provide, secure, maintain, troubleshoot, and improve the service; operate lead and appointment functionality; communicate with customers; process subscriptions; and comply with legal obligations.</p>
                        <p><strong>Service providers.</strong> Information may be processed by third-party providers used to operate ORVELIUS, including hosting, database, AI, email, and payment providers. Those providers process information according to their applicable terms and privacy practices.</p>
                        <p><strong>Selling information.</strong> ORVELIUS does not sell personal information submitted through the service.</p>
                        <p><strong>Business customers.</strong> Businesses using ORVELIUS are responsible for their own privacy notices, legal obligations, permissions, and handling of information relating to their end customers.</p>
                        <p><strong>Security and retention.</strong> ORVELIUS uses reasonable technical and organizational measures intended to protect information, but no internet service can guarantee absolute security. Information may be retained for as long as reasonably necessary to provide the service, maintain records, resolve disputes, enforce agreements, and comply with law.</p>
                        <p><strong>Requests and contact.</strong> Privacy questions or requests may be sent to support@orvelius.com. ORVELIUS may need to verify a request before acting on it.</p>
                    </div>
                    <div class="card legal-card" id="cancellation">
                        <h3>Cancellation Policy</h3>
                        <p>Customers may cancel a monthly subscription at any time before the next renewal. Cancellation prevents future renewal charges and generally becomes effective at the end of the current paid billing period.</p>
                        <p>Customers may continue using paid subscription features through the end of that billing period unless access is suspended for nonpayment, misuse, security reasons, or another permitted reason. Access may end when the paid period expires.</p>
                        <p>Cancellation requests may be made through any cancellation method ORVELIUS makes available or by contacting support@orvelius.com.</p>
                    </div>
                    <div class="card legal-card" id="refunds">
                        <h3>Refund Policy</h3>
                        <p>Monthly subscription charges are generally non-refundable once a billing period begins, and ORVELIUS does not ordinarily provide prorated refunds or credits for unused time after cancellation.</p>
                        <p>Exceptions may be made where required by applicable law, where a billing error occurred, or at ORVELIUS's discretion. Customers should contact support@orvelius.com promptly regarding suspected billing errors.</p>
                        <p>Any separately agreed setup, onboarding, customization, or development fee will be governed by the written terms presented for that work.</p>
                    </div>
                </div>
            </div>
        </section>
    </main>

    <footer>
        <div class="wrap footer-inner">
            <div>© 2026 ORVELIUS. All rights reserved.</div>
            <div><a href="#terms">Terms</a> · <a href="#privacy">Privacy</a> · <a href="#cancellation">Cancellation</a> · <a href="#refunds">Refunds</a></div>
        </div>
    </footer>
</body>
</html>
        """
    )


# =====================================
# PUBLIC LEGAL PAGES
# =====================================

def _legal_page(title: str, body: str):
    return HTMLResponse(
        content=f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | ORVELIUS</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ margin: 0; background: #090b10; color: #eef1f7; font-family: Arial, Helvetica, sans-serif; line-height: 1.7; }}
        .wrap {{ width: min(900px, calc(100% - 40px)); margin: 0 auto; }}
        header {{ border-bottom: 1px solid #242936; padding: 24px 0; }}
        .brand {{ color: #fff; font-weight: 800; letter-spacing: .16em; text-decoration: none; }}
        main {{ padding: 64px 0 80px; }}
        h1 {{ font-size: clamp(2rem, 5vw, 3.5rem); margin: 0 0 8px; }}
        .effective {{ color: #9ca6b8; margin-bottom: 38px; }}
        h2 {{ margin-top: 34px; font-size: 1.2rem; }}
        p {{ color: #c8ceda; }}
        a {{ color: #fff; }}
        footer {{ border-top: 1px solid #242936; padding: 26px 0; color: #8f98aa; }}
        .links a {{ margin-right: 18px; }}
    </style>
</head>
<body>
<header><div class="wrap"><a class="brand" href="/">ORVELIUS</a></div></header>
<main><div class="wrap">
    <h1>{title}</h1>
    <p class="effective">Effective September 21, 2026</p>
    {body}
</div></main>
<footer><div class="wrap links"><a href="/">Home</a><a href="/terms">Terms</a><a href="/privacy">Privacy</a></div></footer>
</body>
</html>
        """
    )


@app.get("/terms", response_class=HTMLResponse)
def terms_of_service():
    return _legal_page(
        "Terms of Service",
        """
        <h2>Subscription</h2>
        <p>ORVELIUS provides subscription-based AI customer assistance software for businesses. The current standard plan is $149 USD per month, billed automatically on a recurring monthly basis until cancelled. Applicable taxes may be added where required.</p>
        <h2>Service</h2>
        <p>The service may include an AI customer assistant, lead capture, appointment-request and booking features, an owner dashboard, and tools for managing business services, pricing, and hours. Features may evolve as the service is improved.</p>
        <h2>Customer responsibilities</h2>
        <p>Customers must provide accurate and lawful business information, maintain appropriate access credentials, review their configured assistant and business settings, and use information collected through ORVELIUS in accordance with applicable law. Customers are responsible for determining whether the service is suitable for their business.</p>
        <h2>AI limitations</h2>
        <p>AI-generated responses may occasionally be inaccurate, incomplete, or unexpected. ORVELIUS does not guarantee that every message, lead, appointment request, or automated response will be error-free. Customers should independently review important business, legal, financial, safety, or other high-impact information.</p>
        <h2>No results guarantee</h2>
        <p>ORVELIUS does not guarantee any specific number of leads, appointments, customers, sales, revenue, profit, or other business result.</p>
        <h2>Acceptable use</h2>
        <p>Customers may not use the service for unlawful, fraudulent, abusive, deceptive, infringing, or harmful activity; attempt unauthorized access; interfere with service operation; or use the service in a manner that violates third-party rights.</p>
        <h2>Availability and third parties</h2>
        <p>Availability may be affected by maintenance, internet or hosting failures, AI providers, payment processors, database providers, or other third-party systems. ORVELIUS may modify, maintain, suspend, or discontinue portions of the service when reasonably necessary.</p>
        <h2>Payment and suspension</h2>
        <p>Customers authorize recurring charges associated with their selected subscription. If payment fails or remains unpaid, ORVELIUS may restrict or suspend access until the account is brought current.</p>
        <h2>Cancellation and refunds</h2>
        <p>Customers may cancel a monthly subscription at any time before the next renewal. Cancellation prevents future renewal charges and generally becomes effective at the end of the current paid billing period. Monthly subscription charges are generally non-refundable once a billing period begins, and ORVELIUS does not ordinarily provide prorated refunds or credits for unused time after cancellation. Exceptions may be made where required by applicable law, where a billing error occurred, or at ORVELIUS's discretion. Cancellation or billing questions may be sent to support@orvelius.com.</p>
        <h2>Intellectual property</h2>
        <p>ORVELIUS retains ownership of its software, platform, designs, systems, and related intellectual property. Customers retain ownership of business information and content they provide, subject to the rights reasonably necessary for ORVELIUS and its service providers to host, process, transmit, and display that information to provide the service.</p>
        <h2>Limitation of liability</h2>
        <p>To the maximum extent permitted by applicable law, ORVELIUS will not be liable for indirect, incidental, special, consequential, exemplary, or lost-profit damages arising from use of or inability to use the service. To the maximum extent permitted by applicable law, ORVELIUS's aggregate liability arising from the service will not exceed the amounts paid by the customer to ORVELIUS during the three months immediately preceding the event giving rise to the claim.</p>
        <h2>Governing law</h2>
        <p>These Terms are governed by the laws of the State of Ohio, without regard to conflict-of-law principles, except where applicable law requires otherwise.</p>
        <h2>Changes</h2>
        <p>ORVELIUS may update these Terms from time to time. Material changes will be reflected by an updated effective date and, when appropriate, additional notice.</p>
        <h2>Contact</h2>
        <p>Questions about these Terms may be sent to <a href="mailto:support@orvelius.com">support@orvelius.com</a>.</p>
        """
    )


@app.get("/privacy", response_class=HTMLResponse)
def privacy_policy():
    return _legal_page(
        "Privacy Policy",
        """
        <h2>Information processed</h2>
        <p>ORVELIUS may process business account information and information submitted through customer-facing assistants, including names, phone numbers, email addresses, service requests, appointment details, messages, and business configuration information.</p>
        <h2>How information is used</h2>
        <p>Information is used to provide, secure, maintain, troubleshoot, and improve the service; operate lead and appointment functionality; communicate with customers; process subscriptions; and comply with legal obligations.</p>
        <h2>Service providers and disclosure</h2>
        <p>Information may be processed or disclosed to third-party providers used to operate ORVELIUS, including hosting, database, AI, email, and payment providers, as reasonably necessary to provide the service. Information may also be disclosed when required by law, to protect rights or security, or in connection with a business transfer. Those providers process information according to their applicable terms and privacy practices.</p>
        <h2>Selling information</h2>
        <p>ORVELIUS does not sell personal information submitted through the service.</p>
        <h2>Business customers</h2>
        <p>Businesses using ORVELIUS are responsible for their own privacy notices, legal obligations, permissions, and handling of information relating to their end customers.</p>
        <h2>Security</h2>
        <p>ORVELIUS uses reasonable technical and organizational measures intended to safeguard information. However, no internet service or method of electronic storage can guarantee absolute security.</p>
        <h2>Retention</h2>
        <p>Information may be retained for as long as reasonably necessary to provide the service, maintain records, resolve disputes, enforce agreements, and comply with legal obligations.</p>
        <h2>Your choices and requests</h2>
        <p>Privacy questions or requests concerning access, correction, or deletion may be sent to support@orvelius.com. ORVELIUS may need to verify a request before acting on it, and some information may be retained where legally permitted or required.</p>
        <h2>Changes</h2>
        <p>ORVELIUS may update this Privacy Policy from time to time. Changes will be reflected by an updated effective date and, when appropriate, additional notice.</p>
        <h2>Contact</h2>
        <p>Privacy questions or requests may be sent to <a href="mailto:support@orvelius.com">support@orvelius.com</a>.</p>
        """
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