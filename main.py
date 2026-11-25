import os
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from google import genai
from google.genai import types

# Load environment variables from .env file
load_dotenv()

app = FastAPI(title="Coaching Center AI WhatsApp Assistant")

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "my_demo_token")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """
You are the WhatsApp Enquiry Assistant for our AI & Data Coaching Center.

LANGUAGE RULE:
Always reply strictly in clear, professional English. Never use Hindi, Hinglish, or any other language—even if the user messages you in Hindi or Hinglish, always respond exclusively in English.

SCOPE RULE:
Use ONLY the course facts below. Do not invent batch timings, discounts, certificates, or extra courses. Keep answers concise, friendly, and easy to read on WhatsApp.

COURSES OFFERED:
1. Python
   - Fees: ₹1,500
   - Duration: 1 Month
   - Subtopics: Variables & Data Types, Loops & Functions, Lists/Tuples/Dictionaries, OOP & File Handling, NumPy & Pandas Basics.

2. SQL
   - Fees: ₹2,000
   - Duration: 1 Month
   - Subtopics: SELECT/WHERE/ORDER BY, Joins (INNER, LEFT, RIGHT), GROUP BY & Aggregations, Subqueries & CTEs, Window Functions & Keys.

3. Machine Learning (ML)
   - Fees: ₹5,000
   - Subtopics: Data Cleaning & Feature Engineering, Linear & Logistic Regression, Decision Trees & Random Forest, XGBoost & Model Evaluation, K-Means Clustering.

4. Deep Learning (DL)
   - Fees: ₹6,000
   - Subtopics: Artificial Neural Networks (ANN), Activation Functions & Backpropagation, Convolutional Neural Networks (CNN), RNN & LSTM, Intro to Transformers.

STRICT BOUNDARY:
If someone asks about anything other than these 4 courses, their fees, duration, or subtopics, reply ONLY with:
"I only handle enquiries for our Python, SQL, Machine Learning, and Deep Learning courses."
"""


@app.get("/")
async def health_check():
    return {
        "status": "running",
        "service": "Coaching Center AI WhatsApp Assistant",
    }


@app.get("/webhook")
async def verify_webhook(request: Request):
    """Meta WhatsApp Cloud API Webhook Verification."""
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == VERIFY_TOKEN
    ):
        return Response(content=params.get("hub.challenge"), media_type="text/plain")
    return Response(status_code=403)


@app.post("/webhook")
async def handle_message(request: Request):
    """Receives incoming WhatsApp messages and replies via Gemini 3.8 Flash."""
    data = await request.json()
    try:
        value = data["entry"][0]["changes"][0]["value"]
        if "messages" not in value:
            return {"status": "ignored"}

        msg = value["messages"][0]
        if msg.get("type") != "text":
            return {"status": "non-text ignored"}

        sender_phone = msg["from"]
        user_text = msg["text"]["body"]

        ai_response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=user_text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.1,
            ),
        )

        reply_text = ai_response.text or "Please ask about our Python, SQL, Machine Learning, or Deep Learning courses."

        url = f"https://graph.facebook.com/v26.0/{PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": sender_phone,
            "type": "text",
            "text": {"body": reply_text},
        }
        async with httpx.AsyncClient(timeout=15.0) as http:
            resp = await http.post(url, json=payload, headers=headers)
            if resp.status_code >= 400:
                print("WhatsApp API error:", resp.status_code, resp.text)

    except Exception as e:
        print("Webhook error:", e)

    return {"status": "ok"}
