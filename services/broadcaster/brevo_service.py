import requests
from typing import List
from dotenv import load_dotenv
import os
from fastapi import APIRouter, HTTPException

router = APIRouter()
load_dotenv()

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
BREV0_API_KEY = os.getenv("BREVO_KEY")
BREVO_SENDER_NAME = os.getenv("BREVO_SENDER_NAME")
BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL")

def send_email(
    recipients: List[str],
    subject: str,
    html_content: str,
):
    """
    Sends a transactional email through Brevo.
    """

    if not recipients:
        print("No recipients supplied.")
        return

    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json",
    }

    payload = {
        "sender": {
            "name": BREVO_SENDER_NAME,
            "email": BREVO_SENDER_EMAIL,
        },
        "to": [{"email": email} for email in recipients],
        "subject": subject,
        "htmlContent": html_content,
    }

    response = requests.post(
        BREVO_API_URL,
        headers=headers,
        json=payload,
        timeout=60,
    )

    if response.status_code >= 300:
        print(response.status_code)
        print(response.text)
        raise Exception("Failed to send email via Brevo.")

    return response.json()