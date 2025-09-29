import os
import requests
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
# Load environment variables
load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

def send_email(to_email: str, subject: str, text: str):
    try:
        msg = MIMEMultipart()
        msg["From"] = GMAIL_USER
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(text, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, to_email, msg.as_string())
        server.quit()

        print(f"✅ Email sent to {to_email}")
        return {"message": f"Email sent to {to_email}"}
    except Exception as e:
        print(f"❌ Email sending failed: {e}")
        return {"error": str(e)}