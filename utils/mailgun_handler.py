import os
import requests

# Mailgun credentials
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
MAILGUN_FROM = os.getenv("MAILGUN_FROM")

def send_email(to_email: str, subject: str, text: str):
    """
    Sends an email using Mailgun's API.
    """
    response = requests.post(
        f"https://api.eu.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
        auth=("api", MAILGUN_API_KEY),
        data={
            "from": f"SADC FREIGHTLINK <{MAILGUN_FROM}>",
            "to": [to_email],
            "subject": subject,
            "text": text,
        },
    )

    if response.status_code != 200:
        raise Exception(f"Mailgun error: {response.text}")

    return response.json()
