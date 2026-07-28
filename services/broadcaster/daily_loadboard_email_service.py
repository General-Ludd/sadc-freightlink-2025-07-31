from sqlalchemy import distinct
from sqlalchemy.orm import Session


from models.user import CarrierUser, CarrierUsersMailList


from .brevo_contacts import (
    sync_carrier_contacts
)


from services.broadcaster.brevo_campaigns import (
    create_campaign,
    send_campaign
)


from .loadboard_email_template import (
    daily_loadboard_template
)



BREVO_TRANSPORTER_LIST_ID = 3





def send_daily_loadboard_broadcast(
        db: Session
):


    print(
        "Starting Daily Loadboard Broadcast"
    )



    emails = [

        row[0]

        for row in

        db.query(
            distinct(
                CarrierUsersMailList.email
            )
        )

        .filter(
            CarrierUsersMailList.email.isnot(None)
        )

        .all()

    ]



    if not emails:

        print(
            "No carriers found"
        )

        return



    print(
        f"{len(emails)} carriers found"
    )



    #
    # Sync contacts
    #

    sync_carrier_contacts(
        emails
    )



    #
    # Generate HTML
    #

    html = daily_loadboard_template()



    #
    # Create campaign
    #

    campaign = create_campaign(

        subject=
        "Today's Available Transport Requirements",

        html_content=html,

        list_id=
        BREVO_TRANSPORTER_LIST_ID

    )



    print(
        "Campaign Created:",
        campaign
    )



    #
    # Send immediately
    #

    send_campaign(
        campaign.id
    )


    print(
        "Broadcast completed"
    )