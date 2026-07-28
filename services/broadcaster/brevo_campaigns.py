import sib_api_v3_sdk

from .brevo_client import get_brevo_api_client



def create_campaign(
        subject,
        html_content,
        list_id
):


    client = get_brevo_api_client()


    api = sib_api_v3_sdk.EmailCampaignsApi(client)



    campaign = sib_api_v3_sdk.CreateEmailCampaign(

        name=subject,

        subject=subject,


        sender={
            "name":
            "Dispatch | SADC FREIGHTLINK",

            "email":
            "operations@sadcfreightlink.com"
        },



        html_content=html_content,


        recipients={
            "listIds":[
                list_id
            ]
        }

    )


    response = api.create_email_campaign(
        campaign
    )


    return response





def send_campaign(campaign_id):


    client = get_brevo_api_client()


    api = sib_api_v3_sdk.EmailCampaignsApi(client)


    return api.send_email_campaign_now(
        campaign_id
    )