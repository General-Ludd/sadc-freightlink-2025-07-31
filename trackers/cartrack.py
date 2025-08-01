import base64
import requests
from typing import Optional, Dict
from utils.sast_datetime import get_sast_time
from .cartrack_utils import CARTRACK_COUNTRY_API_MAP

def fetch_cartrack_vehicle_by_vin(api_username: str, api_token: str, vin: str, country: str) -> Optional[Dict]:
    """
    Fetch vehicle data from Cartrack by VIN with regional domain selection.

    :param api_username: Cartrack API username
    :param api_token: Cartrack API token
    :param vin: Vehicle Identification Number (VIN)
    :param country: Country code for regional domain selection
    :return: Vehicle data (if found) or None
    """

    # Get the base URL for the given country
    base_url = CARTRACK_COUNTRY_API_MAP.get(country)

    if not base_url:
        print(f"❌ No Cartrack API URL found for {country}")
        return None

    # Prepare the authorization header
    credentials = f"{api_username}:{api_token}"
    base64_auth = base64.b64encode(credentials.encode("ascii")).decode("ascii")
    headers = {
        "Authorization": f"Basic {base64_auth}",
        "Content-Type": "application/json"
    }

    # URL for vehicle status based on regional domain
    url = f"{base_url}/rest/vehicles/status"
    
    try:
        # Request to get the vehicle status
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        # Loop through the vehicles to find the matching VIN
        for vehicle in response.json().get("data", []):
            if str(vehicle.get("chassis_number")).upper() == str(vin).upper():
                location = vehicle.get("location", {})
                return {
                    "tracker_id": vehicle.get("vehicle_id"),  # still numeric from Cartrack
                    "latitude": str(location.get("latitude")),  # Convert to string for consistency
                    "longitude": str(location.get("longitude")),
                    "speed": str(vehicle.get("speed")),
                    "bearing": str(vehicle.get("bearing")),
                    "position_description": location.get("position_description", ""),
                    "time_stamp": get_sast_time().isoformat()
                }

        print(f"[Cartrack] Vehicle with VIN {vin} not found.")
        return None

    except Exception as e:
        print(f"[Cartrack API Error]: {e}")
        return None