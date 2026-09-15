import os
import requests
from dotenv import load_dotenv
import smtplib
import html
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
# Load environment variables
load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

##############################################################Password Reset Email####################################################################
def send_email(to_email: str, subject: str, text: str):
    try:
        # Escape text so it is safe to place inside HTML
        safe_text = html.escape(text)

        # Create email
        msg = MIMEMultipart("alternative")
        msg["From"] = GMAIL_USER
        msg["To"] = to_email
        msg["Subject"] = subject

        # ---------------------------------------------------------
        # PLAIN TEXT VERSION
        # ---------------------------------------------------------

        plain_text = text

        # ---------------------------------------------------------
        # HTML VERSION
        # ---------------------------------------------------------

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">

            <title>{html.escape(subject)}</title>

            <style>
                body {{
                    margin: 0;
                    padding: 0;
                    background-color: #f5f7fa;
                    font-family: Arial, Helvetica, sans-serif;
                    color: #1f2937;
                }}

                .email-wrapper {{
                    width: 100%;
                    padding: 40px 15px;
                    box-sizing: border-box;
                }}

                .email-container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: #ffffff;
                    border: 1px solid #e1e5eb;
                    border-radius: 12px;
                    overflow: hidden;
                }}

                .header {{
                    padding: 32px 30px 24px 30px;
                    text-align: center;
                    background-color: #ffffff;
                }}

                .brand {{
                    font-size: 24px;
                    font-weight: 700;
                    letter-spacing: 0.5px;
                    color: #182235;
                    margin: 0;
                }}

                .brand-subtitle {{
                    margin-top: 6px;
                    font-size: 12px;
                    color: #718096;
                    letter-spacing: 1.5px;
                    text-transform: uppercase;
                }}

                .content {{
                    padding: 10px 45px 40px 45px;
                    text-align: center;
                }}

                .title {{
                    font-size: 25px;
                    font-weight: 700;
                    color: #182235;
                    margin: 15px 0 14px 0;
                }}

                .message {{
                    font-size: 16px;
                    line-height: 1.6;
                    color: #5b6677;
                    margin: 0 auto 28px auto;
                    max-width: 470px;
                }}

                .code-label {{
                    font-size: 13px;
                    font-weight: 600;
                    color: #718096;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    margin-bottom: 10px;
                }}

                .verification-code {{
                    display: inline-block;
                    padding: 17px 28px;
                    background-color: #f1f4f8;
                    border-radius: 8px;
                    font-size: 32px;
                    font-weight: 700;
                    letter-spacing: 7px;
                    color: #182235;
                    margin-bottom: 28px;
                }}

                .security-message {{
                    margin: 0 auto;
                    max-width: 460px;
                    font-size: 13px;
                    line-height: 1.6;
                    color: #7a8494;
                }}

                .divider {{
                    height: 1px;
                    background-color: #e8ebef;
                    margin: 30px 0 25px 0;
                }}

                .footer {{
                    text-align: center;
                    padding: 24px 30px 30px 30px;
                    background-color: #fafbfc;
                }}

                .footer-brand {{
                    font-size: 14px;
                    font-weight: 700;
                    color: #182235;
                    margin-bottom: 7px;
                }}

                .footer-text {{
                    font-size: 12px;
                    line-height: 1.5;
                    color: #8a94a3;
                    margin: 0;
                }}

                @media only screen and (max-width: 600px) {{
                    .email-wrapper {{
                        padding: 20px 10px;
                    }}

                    .content {{
                        padding: 10px 25px 35px 25px;
                    }}

                    .title {{
                        font-size: 22px;
                    }}

                    .verification-code {{
                        font-size: 27px;
                        letter-spacing: 5px;
                        padding: 15px 20px;
                    }}
                }}
            </style>
        </head>

        <body>

            <div class="email-wrapper">

                <div class="email-container">

                    <!-- BRAND HEADER -->
                    <div class="header">
                        <div class="brand">
                            SADC FREIGHTLINK
                        </div>

                        <div class="brand-subtitle">
                            Enterprise Logistics & Freight Management
                        </div>
                    </div>


                    <!-- MAIN CONTENT -->
                    <div class="content">

                        <div class="title">
                            Password Reset Verification
                        </div>

                        <p class="message">
                            Here is your password reset verification code.
                            Enter this code in SADC FREIGHTLINK to continue
                            resetting your password.
                        </p>

                        <div class="code-label">
                            Verification Code
                        </div>

                        <div class="verification-code">
                            {safe_text}
                        </div>

                        <p class="security-message">
                            If you did not request a password reset for your
                            SADC FREIGHTLINK account, you can safely ignore
                            this email. Do not share this verification code
                            with anyone.
                        </p>

                        <div class="divider"></div>

                        <p class="security-message">
                            For your security, SADC FREIGHTLINK will never
                            ask you to share your verification code.
                        </p>

                    </div>


                    <!-- FOOTER -->
                    <div class="footer">

                        <div class="footer-brand">
                            SADC FREIGHTLINK
                        </div>

                        <p class="footer-text">
                            Enterprise Logistics Consulting & Freight Management
                        </p>

                        <p class="footer-text">
                            This is an automated message. Please do not reply
                            to this email.
                        </p>

                    </div>

                </div>

            </div>

        </body>
        </html>
        """

        # Attach both versions
        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        # ---------------------------------------------------------
        # SEND EMAIL
        # ---------------------------------------------------------

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)

        server.sendmail(
            GMAIL_USER,
            to_email,
            msg.as_string()
        )

        server.quit()

        print(f"✅ Email sent to {to_email}")

        return {
            "message": f"Email sent to {to_email}"
        }

    except Exception as e:

        print(f"❌ Email sending failed: {e}")

        return {
            "error": str(e)
        }