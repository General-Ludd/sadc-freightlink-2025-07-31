import os
from dotenv import load_dotenv

import sib_api_v3_sdk


load_dotenv()



def get_brevo_configuration():

    configuration = sib_api_v3_sdk.Configuration()

    configuration.api_key["api-key"] = os.getenv(
        "BREVO_API_KEY"
    )

    return configuration



def get_brevo_api_client():

    configuration = get_brevo_configuration()

    return sib_api_v3_sdk.ApiClient(configuration)