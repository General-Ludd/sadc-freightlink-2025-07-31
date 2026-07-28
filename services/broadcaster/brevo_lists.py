import sib_api_v3_sdk

from .brevo_client import get_brevo_api_client



def get_lists():


    client = get_brevo_api_client()

    api = sib_api_v3_sdk.ContactsApi(client)


    return api.get_lists()



def create_list(name):


    client = get_brevo_api_client()

    api = sib_api_v3_sdk.ContactsApi(client)


    data = sib_api_v3_sdk.CreateList(

        name=name,

        folder_id=1

    )


    return api.create_list(data)