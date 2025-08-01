from datetime import date, datetime, time, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests
from dotenv import load_dotenv
import os

# Initialize router
router = APIRouter()
load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

class AddressInput(BaseModel):
    origin_address: str
    destination_address: str

# Map African countries to their regions
AFRICAN_REGION_MAPPING = {
    # North Africa
    "Algeria": "North Africa",
    "Egypt": "North Africa",
    "Libya": "North Africa",
    "Mauritania": "North Africa",
    "Morocco": "North Africa",
    "Sudan": "North Africa",
    "Tunisia": "North Africa",
    "Western Sahara": "North Africa",

    # West Africa
    "Benin": "West Africa",
    "Burkina Faso": "West Africa",
    "Cabo Verde": "West Africa",
    "Côte d'Ivoire": "West Africa",
    "Gambia": "West Africa",
    "Ghana": "West Africa",
    "Guinea": "West Africa",
    "Guinea-Bissau": "West Africa",
    "Liberia": "West Africa",
    "Mali": "West Africa",
    "Niger": "West Africa",
    "Nigeria": "West Africa",
    "Senegal": "West Africa",
    "Sierra Leone": "West Africa",
    "Togo": "West Africa",

    # Central Africa
    "Cameroon": "Central Africa",
    "Central African Republic": "Central Africa",
    "Chad": "Central Africa",
    "Congo": "Central Africa",
    "Democratic Republic of the Congo": "Central Africa",
    "Equatorial Guinea": "Central Africa",
    "Gabon": "Central Africa",
    "São Tomé and Príncipe": "Central Africa",

    # East Africa
    "Burundi": "East Africa",
    "Comoros": "East Africa",
    "Djibouti": "East Africa",
    "Eritrea": "East Africa",
    "Ethiopia": "East Africa",
    "Kenya": "East Africa",
    "Madagascar": "East Africa",
    "Malawi": "East Africa",
    "Mauritius": "East Africa",
    "Mozambique": "East Africa",
    "Rwanda": "East Africa",
    "Seychelles": "East Africa",
    "Somalia": "East Africa",
    "South Sudan": "East Africa",
    "Tanzania": "East Africa",
    "Uganda": "East Africa",
    "Zambia": "East Africa",

    # Southern Africa (SADC)
    "Angola": "Southern Africa",
    "Botswana": "Southern Africa",
    "Eswatini": "Southern Africa",
    "Lesotho": "Southern Africa",
    "Namibia": "Southern Africa",
    "South Africa": "Southern Africa",
    "Zimbabwe": "Southern Africa",
}

def get_location_details(address: str):
    """
    Fetch detailed location information (full address, city, province, country, region) from Google Maps.
    """
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": GOOGLE_MAPS_API_KEY}

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Google Maps Geocoding API error: {str(e)}")

    data = response.json()

    if "results" not in data or not data["results"]:
        raise HTTPException(status_code=400, detail=f"Invalid address: {address}")

    try:
        result = data["results"][0]
        complete_address = result.get("formatted_address", "Unknown address")
        components = result.get("address_components", [])

        city = province = country = "Unknown"

        for component in components:
            types = component.get("types", [])
            if "locality" in types:
                city = component.get("long_name", "Unknown")
            elif "administrative_area_level_1" in types:
                province = component.get("long_name", "Unknown")
            elif "country" in types:
                country = component.get("long_name", "Unknown")

        region = AFRICAN_REGION_MAPPING.get(country, "Unknown Region")

        return complete_address, f"{city}, {province}", country, region

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing geocoding response: {str(e)}")

@router.post("/calculate-distance")
def calculate_distance(input_data: AddressInput):
    """
    Calculate distance, duration, and geolocation metadata between origin and destination addresses.
    """
    if not GOOGLE_MAPS_API_KEY:
        raise HTTPException(status_code=500, detail="Google Maps API key not configured.")

    # Get enriched details for both locations
    complete_origin_address, origin_city_province, origin_country, origin_region = get_location_details(input_data.origin_address)
    complete_destination_address, destination_city_province, destination_country, destination_region = get_location_details(input_data.destination_address)

    # Use Google Distance Matrix API
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": input_data.origin_address,
        "destinations": input_data.destination_address,
        "key": GOOGLE_MAPS_API_KEY,
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Google Maps Distance Matrix API error: {str(e)}")

    result = response.json()

    if result.get("status") != "OK" or not result.get("rows"):
        raise HTTPException(status_code=400, detail="Invalid response from Google Maps API.")

    try:
        element = result["rows"][0]["elements"][0]
        if element.get("status") != "OK":
            raise HTTPException(status_code=400, detail="Error calculating distance or duration.")

        distance_meters = element["distance"]["value"]
        duration_text = element["duration"]["text"]
        distance_km = distance_meters // 1000
    except (IndexError, KeyError) as e:
        raise HTTPException(status_code=500, detail=f"Error parsing distance response: {str(e)}")

    embed_url = (
        f"https://www.google.com/maps/embed/v1/directions"
        f"?key={GOOGLE_MAPS_API_KEY}"
        f"&origin={input_data.origin_address.replace(' ', '+')}"
        f"&destination={input_data.destination_address.replace(' ', '+')}"
        f"&mode=driving"
    )

    return {
        "distance": distance_km,
        "duration": duration_text,
        "complete_origin_address": complete_origin_address,
        "origin_city_province": origin_city_province,
        "origin_country": origin_country,
        "origin_region": origin_region,
        "complete_destination_address": complete_destination_address,
        "destination_city_province": destination_city_province,
        "destination_country": destination_country,
        "destination_region": destination_region,
        "google_maps_embed_url": embed_url,
    }


########################### ETA Date, ETA Window, Polyline's Function ###################################
class RouteETAInput(BaseModel):
    origin_address: str
    destination_address: str
    start_date: date  # Format: YYYY-MM-DD
    start_time: time  # Format: HH:MM

@router.post("/get-eta-and-polyline")
def get_eta_and_polyline(input_data: RouteETAInput):
    if not GOOGLE_MAPS_API_KEY:
        raise HTTPException(status_code=500, detail="Google Maps API key not configured.")

    # Step 1: Call Google Distance Matrix API
    distance_url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    distance_params = {
        "origins": input_data.origin_address,
        "destinations": input_data.destination_address,
        "key": GOOGLE_MAPS_API_KEY,
    }

    try:
        distance_response = requests.get(distance_url, params=distance_params)
        distance_response.raise_for_status()
        distance_data = distance_response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Distance Matrix API error: {str(e)}")

    try:
        element = distance_data["rows"][0]["elements"][0]
        if element.get("status") != "OK":
            raise HTTPException(status_code=400, detail="Invalid route between addresses.")
        duration_seconds = element["duration"]["value"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing distance response: {str(e)}")

    # Step 2: Compute ETA datetime
    start_datetime = datetime.combine(input_data.start_date, input_data.start_time)
    eta_datetime = start_datetime + timedelta(seconds=duration_seconds)
    eta_window_start = (eta_datetime - timedelta(hours=1)).strftime("%H:%M")
    eta_window_end = (eta_datetime + timedelta(hours=1)).strftime("%H:%M")
    eta_date = eta_datetime.date().isoformat()

    # Step 3: Get route polyline from Directions API
    directions_url = "https://maps.googleapis.com/maps/api/directions/json"
    directions_params = {
        "origin": input_data.origin_address,
        "destination": input_data.destination_address,
        "mode": "driving",
        "key": GOOGLE_MAPS_API_KEY,
    }

    try:
        directions_response = requests.get(directions_url, params=directions_params)
        directions_response.raise_for_status()
        directions_data = directions_response.json()
        polyline = directions_data["routes"][0]["overview_polyline"]["points"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting polyline from Directions API: {str(e)}")

    # Step 4: Return result
    return {
        "eta_date": eta_date,
        "eta_window": f"{eta_window_start} - {eta_window_end}",
        "polyline": polyline
    }