from models.vehicle import Vehicle
from .cartrack import fetch_cartrack_vehicle_by_vin
from models.vehicle import Vehicle

def get_vehicle_location(vehicle: Vehicle):
    provider = vehicle.tracker_providers_name.lower()
    country = vehicle.tracker_providers_country.lower()

    if provider == "cartrack":
        return fetch_cartrack_vehicle_by_vin(api_username = vehicle.tracker_api_username, api_token = vehicle.tracker_api_token, vin = vehicle.vin, country = vehicle.tracker_providers_country)

    # Placeholder: more providers will be added here later
    return None