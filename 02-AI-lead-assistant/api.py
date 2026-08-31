from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from lead_assistant import process_customer_message
from dashboard import router as dashboard_router


app = FastAPI()
app.include_router(dashboard_router)


# =====================================
# CUSTOMER REQUEST FORMAT
# =====================================

class CustomerMessage(BaseModel):
    message: str
    session_id: str


# =====================================
# CHAT WEBSITE
# =====================================

@app.get("/", response_class=HTMLResponse)
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

    <title>Freedom Auto Detailing</title>


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

            background: #111;

            color: white;

            font-family: Arial, sans-serif;

        }


        .chat-container {

            width: 420px;

            height: 650px;

            display: flex;

            flex-direction: column;

            overflow: hidden;

            background: #1c1c1c;

            border-radius: 18px;

            box-shadow:
                0 15px 50px rgba(0, 0, 0, 0.5);

        }


        .header {

            padding: 20px;

            background: #252525;

        }


        .header h2 {

            margin: 0;

        }


        .header p {

            margin: 5px 0 0;

            color: #aaa;

            font-size: 14px;

        }


        .messages {

            flex: 1;

            padding: 20px;

            display: flex;

            flex-direction: column;

            gap: 12px;

            overflow-y: auto;

        }


        .message {

            max-width: 80%;

            padding: 12px 15px;

            border-radius: 15px;

            line-height: 1.4;

        }


        .bot {

            align-self: flex-start;

            background: #333;

        }


        .user {

            align-self: flex-end;

            background: white;

            color: #111;

        }


        .typing {

            display: none;

            align-self: flex-start;

            color: #999;

            font-size: 13px;

        }


        .input-area {

            display: flex;

            gap: 10px;

            padding: 15px;

            background: #252525;

        }


        input {

            flex: 1;

            padding: 12px;

            border: none;

            border-radius: 8px;

            outline: none;

            font-size: 14px;

        }


        button {

            padding: 12px 18px;

            border: none;

            border-radius: 8px;

            cursor: pointer;

            font-weight: bold;

        }


        button:hover {

            opacity: 0.85;

        }


        button:disabled {

            opacity: 0.5;

            cursor: not-allowed;

        }

    </style>

</head>


<body>


<div class="chat-container">


    <div class="header">

        <h2>
            Freedom Auto Detailing
        </h2>

        <p>
            AI Assistant • Online
        </p>

    </div>


    <div
        class="messages"
        id="messages"
    >

        <div class="message bot">
            Hey! 👋 How can we help with your vehicle today?
        </div>


        <div
            class="typing"
            id="typing"
        >
            Assistant is typing...
        </div>

    </div>


    <div class="input-area">


        <input
            id="messageInput"
            type="text"
            placeholder="Type your message..."
            autocomplete="off"
        >


        <button
            id="sendButton"
            onclick="sendMessage()"
        >
            Send
        </button>


    </div>


</div>


<script>


const input =
    document.getElementById("messageInput");


const messages =
    document.getElementById("messages");


const typing =
    document.getElementById("typing");


const sendButton =
    document.getElementById("sendButton");


// =====================================
// CUSTOMER SESSION
// =====================================

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


// =====================================
// SEND MESSAGE
// =====================================

async function sendMessage() {


    const text =
        input.value.trim();


    if (!text) {

        return;

    }


    const userMessage =
        document.createElement("div");


    userMessage.className =
        "message user";


    userMessage.textContent =
        text;


    messages.insertBefore(
        userMessage,
        typing
    );


    input.value = "";

    input.disabled = true;

    sendButton.disabled = true;

    typing.style.display = "block";


    messages.scrollTop =
        messages.scrollHeight;


    try {


        const response = await fetch(

            "/message",

            {

                method: "POST",

                headers: {

                    "Content-Type":
                        "application/json"

                },

                body: JSON.stringify({

                    message: text,

                    session_id: sessionId

                })

            }

        );


        const data =
            await response.json();


        typing.style.display =
            "none";


        const botMessage =
            document.createElement("div");


        botMessage.className =
            "message bot";


        botMessage.textContent =
            data.response ||
            "Sorry, something went wrong.";


        messages.insertBefore(
            botMessage,
            typing
        );


        messages.scrollTop =
            messages.scrollHeight;


    }

    catch (error) {


        console.error(error);


        typing.style.display =
            "none";


        const errorMessage =
            document.createElement("div");


        errorMessage.className =
            "message bot";


        errorMessage.textContent =
            "Sorry, I couldn't connect to the assistant.";


        messages.insertBefore(
            errorMessage,
            typing
        );

    }


    input.disabled = false;

    sendButton.disabled = false;

    input.focus();

}


// =====================================
// ENTER TO SEND
// =====================================

input.addEventListener(

    "keydown",

    function(event) {


        if (event.key === "Enter") {

            sendMessage();

        }


    }

);


</script>


</body>

</html>
"""


# =====================================
# AI MESSAGE ENDPOINT
# =====================================

@app.post("/message")
def receive_message(customer: CustomerMessage):

    result = process_customer_message(
        customer.message,
        customer.session_id
    )

    return result