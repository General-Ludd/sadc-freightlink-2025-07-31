from sqlalchemy import distinct
from sqlalchemy.orm import Session

from models.user import CarrierUser

from services.broadcaster.brevo_service import send_email
from services.broadcaster.loadboard_email_template import daily_loadboard_template


def send_daily_loadboard_broadcast(db: Session):

    print("Fetching carrier email addresses...")

    emails = [
        row[0]
        for row in db.query(distinct(CarrierUser.email))
        .filter(CarrierUser.email.isnot(None))
        .all()
    ]

    if not emails:
        print("No carrier email addresses found.")
        return

    print(f"Recipients: {len(emails)}")

    html = daily_loadboard_template()

    send_email(
        recipients=emails,
        subject="Today's Adhoc Transport Requirements",
        html_content=html,
    )

    print("Daily loadboard email sent.")