import sib_api_v3_sdk

from .brevo_client import get_brevo_api_client



def create_contact(email):


    client = get_brevo_api_client()


    api = sib_api_v3_sdk.ContactsApi(
        client
    )


    contact = sib_api_v3_sdk.CreateContact(

        email=email,

        update_enabled=True

    )


    try:

        response = api.create_contact(
            contact
        )


        print(
            "Contact created:",
            email
        )


        return response


    except Exception as e:

        print(
            "FAILED CONTACT:",
            email
        )

        print(e)

        return None





def sync_carrier_contacts(emails):


    success = 0


    for email in emails:

        result = create_contact(email)


        if result:
            success += 1



    print(
        f"Brevo sync finished: {success}/{len(emails)}"
    )


    return success