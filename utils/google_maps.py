from datetime import date, datetime, time, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests
from dotenv import load_dotenv
import os
from typing import Optional, List

# Initialize router
router = APIRouter()
load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

class AddressInput(BaseModel):
    origin_address: str
    destination_address: str
    waypoints: Optional[List[str]] = None

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
    Calculate total distance, duration, and geolocation metadata
    between origin, optional waypoints, and final destination.

    Existing calls using only origin_address and destination_address
    will continue to work exactly as before.
    """

    if not GOOGLE_MAPS_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Google Maps API key not configured."
        )

    # =========================================================
    # STEP 1 - Prepare Waypoints
    # =========================================================

    waypoints = input_data.waypoints or []

    # Remove empty waypoint values
    waypoints = [
        waypoint.strip()
        for waypoint in waypoints
        if waypoint and waypoint.strip()
    ]

    # Maximum of 5 waypoints
    if len(waypoints) > 5:
        raise HTTPException(
            status_code=400,
            detail="A maximum of 5 waypoints are allowed."
        )

    print("========== GOOGLE MAPS DISTANCE CALCULATION ==========")
    print(f"Origin: {input_data.origin_address}")
    print(f"Waypoints: {waypoints}")
    print(f"Destination: {input_data.destination_address}")

    # =========================================================
    # STEP 2 - Get Origin Location Details
    # =========================================================

    (
        complete_origin_address,
        origin_city_province,
        origin_country,
        origin_region
    ) = get_location_details(
        input_data.origin_address
    )

    # =========================================================
    # STEP 3 - Get Waypoint Location Details
    # =========================================================

    waypoint_details = []

    for index, waypoint in enumerate(waypoints, start=1):

        print(
            f"Getting Google Maps details for Waypoint {index}: "
            f"{waypoint}"
        )

        (
            complete_waypoint_address,
            waypoint_city_province,
            waypoint_country,
            waypoint_region
        ) = get_location_details(waypoint)

        waypoint_details.append({
            "complete_address": complete_waypoint_address,
            "city_province": waypoint_city_province,
            "country": waypoint_country,
            "region": waypoint_region,
        })

    # =========================================================
    # STEP 4 - Get Destination Location Details
    # =========================================================

    (
        complete_destination_address,
        destination_city_province,
        destination_country,
        destination_region
    ) = get_location_details(
        input_data.destination_address
    )

    # =========================================================
    # STEP 5 - Google Distance Matrix
    # =========================================================
    #
    # Google will calculate:
    #
    # Origin
    #    ↓
    # Stop 1
    #    ↓
    # Stop 2
    #    ↓
    # ...
    #    ↓
    # Destination
    #
    # We then add all individual route legs together.
    # =========================================================

    url = "https://maps.googleapis.com/maps/api/distancematrix/json"

    params = {
        "origins": input_data.origin_address,
        "destinations": input_data.destination_address,
        "key": GOOGLE_MAPS_API_KEY,
    }

    if waypoints:
        params["destinations"] = "|".join(
            waypoints + [input_data.destination_address]
        )

    try:
        response = requests.get(
            url,
            params=params
        )

        response.raise_for_status()

    except requests.exceptions.RequestException as e:

        raise HTTPException(
            status_code=500,
            detail=f"Google Maps Distance Matrix API error: {str(e)}"
        )

    result = response.json()

    if result.get("status") != "OK" or not result.get("rows"):

        raise HTTPException(
            status_code=400,
            detail="Invalid response from Google Maps API."
        )

    # =========================================================
    # IMPORTANT:
    #
    # Distance Matrix with:
    #
    # origins = Origin
    # destinations = Stop1 | Stop2 | Destination
    #
    # gives:
    #
    # Origin -> Stop1
    # Origin -> Stop2
    # Origin -> Destination
    #
    # That is NOT what we want.
    #
    # Therefore we calculate each leg individually.
    # =========================================================

    route_points = [
        input_data.origin_address,
        *waypoints,
        input_data.destination_address
    ]

    total_distance_meters = 0
    total_duration_seconds = 0

    # =========================================================
    # STEP 6 - Calculate Each Route Leg
    # =========================================================

    for index in range(len(route_points) - 1):

        leg_origin = route_points[index]
        leg_destination = route_points[index + 1]

        print(
            f"Calculating Leg {index + 1}: "
            f"{leg_origin} -> {leg_destination}"
        )

        leg_params = {
            "origins": leg_origin,
            "destinations": leg_destination,
            "key": GOOGLE_MAPS_API_KEY,
        }

        try:

            leg_response = requests.get(
                url,
                params=leg_params
            )

            leg_response.raise_for_status()

        except requests.exceptions.RequestException as e:

            raise HTTPException(
                status_code=500,
                detail=(
                    f"Google Maps Distance Matrix API error "
                    f"for route leg {index + 1}: {str(e)}"
                )
            )

        leg_result = leg_response.json()

        try:

            element = leg_result["rows"][0]["elements"][0]

            if element.get("status") != "OK":

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Google Maps could not calculate route "
                        f"from '{leg_origin}' to '{leg_destination}'."
                    )
                )

            total_distance_meters += element["distance"]["value"]
            total_duration_seconds += element["duration"]["value"]

        except HTTPException:
            raise

        except (IndexError, KeyError) as e:

            raise HTTPException(
                status_code=500,
                detail=(
                    f"Error parsing Google Maps response "
                    f"for route leg {index + 1}: {str(e)}"
                )
            )

    # =========================================================
    # STEP 7 - Convert Total Route Distance
    # =========================================================

    distance_km = total_distance_meters // 1000

    # Convert seconds into readable duration
    total_hours = total_duration_seconds // 3600
    total_minutes = (total_duration_seconds % 3600) // 60

    if total_hours > 0:

        duration_text = (
            f"{total_hours} hour"
            f"{'s' if total_hours != 1 else ''} "
            f"{total_minutes} min"
        )

    else:

        duration_text = (
            f"{total_minutes} min"
        )

    # =========================================================
    # STEP 8 - Google Maps Embed URL
    # =========================================================

    embed_url = (
        f"https://www.google.com/maps/embed/v1/directions"
        f"?key={GOOGLE_MAPS_API_KEY}"
        f"&origin={input_data.origin_address.replace(' ', '+')}"
        f"&destination={input_data.destination_address.replace(' ', '+')}"
        f"&mode=driving"
    )

    # Add waypoints to Google Maps embed
    if waypoints:

        encoded_waypoints = "|".join(
            waypoint.replace(" ", "+")
            for waypoint in waypoints
        )

        embed_url += (
            f"&waypoints={encoded_waypoints}"
        )

    # =========================================================
    # STEP 9 - Build Response
    # =========================================================

    response_data = {
        "distance": distance_km,
        "duration": duration_text,

        # Origin
        "complete_origin_address": complete_origin_address,
        "origin_city_province": origin_city_province,
        "origin_country": origin_country,
        "origin_region": origin_region,

        # Destination
        "complete_destination_address": complete_destination_address,
        "destination_city_province": destination_city_province,
        "destination_country": destination_country,
        "destination_region": destination_region,

        # Google Maps
        "google_maps_embed_url": embed_url,
    }

    # =========================================================
    # STEP 10 - Add Waypoint Metadata Dynamically
    # =========================================================

    for index, waypoint in enumerate(
        waypoint_details,
        start=1
    ):

        response_data[
            f"complete_stop_{index}_address"
        ] = waypoint["complete_address"]

        response_data[
            f"stop_{index}_city_province"
        ] = waypoint["city_province"]

        response_data[
            f"stop_{index}_country"
        ] = waypoint["country"]

        response_data[
            f"stop_{index}_region"
        ] = waypoint["region"]

    print(
        "========== GOOGLE MAPS CALCULATION COMPLETE =========="
    )

    print(
        f"Total Distance: {distance_km} km"
    )

    print(
        f"Total Duration: {duration_text}"
    )

    return response_data


########################### ETA Date, ETA Window, Polyline's Function ###################################
class RouteETAInput(BaseModel):
    origin_address: str
    destination_address: str
    start_date: date  # Format: YYYY-MM-DD
    start_time: time  # Format: HH:MM
    waypoints: Optional[List[str]] = None

@router.post("/get-eta-and-polyline")
def get_eta_and_polyline(input_data: RouteETAInput):

    if not GOOGLE_MAPS_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Google Maps API key not configured."
        )

    print("========== ETA + POLYLINE CALCULATION ==========")

    # =========================================================
    # STEP 1 - Prepare Waypoints
    # =========================================================

    waypoints = input_data.waypoints or []

    waypoints = [
        waypoint.strip()
        for waypoint in waypoints
        if waypoint and waypoint.strip()
    ]

    if len(waypoints) > 5:
        raise HTTPException(
            status_code=400,
            detail="A maximum of 5 waypoints are allowed."
        )

    print(f"Origin: {input_data.origin_address}")
    print(f"Waypoints: {waypoints}")
    print(f"Destination: {input_data.destination_address}")

    # =========================================================
    # STEP 2 - Build Complete Route
    # =========================================================

    route_points = [
        input_data.origin_address,
        *waypoints,
        input_data.destination_address
    ]

    # =========================================================
    # STEP 3 - Calculate Total Travel Duration
    # =========================================================

    distance_url = (
        "https://maps.googleapis.com/maps/api/distancematrix/json"
    )

    total_duration_seconds = 0

    for index in range(len(route_points) - 1):

        leg_origin = route_points[index]
        leg_destination = route_points[index + 1]

        print(
            f"Calculating ETA Leg {index + 1}: "
            f"{leg_origin} -> {leg_destination}"
        )

        distance_params = {
            "origins": leg_origin,
            "destinations": leg_destination,
            "key": GOOGLE_MAPS_API_KEY,
        }

        try:

            distance_response = requests.get(
                distance_url,
                params=distance_params
            )

            distance_response.raise_for_status()

            distance_data = distance_response.json()

        except requests.exceptions.RequestException as e:

            raise HTTPException(
                status_code=500,
                detail=(
                    f"Distance Matrix API error on route leg "
                    f"{index + 1}: {str(e)}"
                )
            )

        try:

            element = (
                distance_data["rows"][0]["elements"][0]
            )

            if element.get("status") != "OK":

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Invalid route between "
                        f"{leg_origin} and {leg_destination}."
                    )
                )

            duration_seconds = element["duration"]["value"]

            total_duration_seconds += duration_seconds

        except HTTPException:
            raise

        except (IndexError, KeyError) as e:

            raise HTTPException(
                status_code=500,
                detail=(
                    f"Error parsing Distance Matrix response "
                    f"for route leg {index + 1}: {str(e)}"
                )
            )

    print(
        f"Total route duration: "
        f"{total_duration_seconds} seconds"
    )

    # =========================================================
    # STEP 4 - Calculate ETA
    # =========================================================

    start_datetime = datetime.combine(
        input_data.start_date,
        input_data.start_time
    )

    eta_datetime = (
        start_datetime
        + timedelta(seconds=total_duration_seconds)
    )

    eta_window_start = (
        eta_datetime - timedelta(hours=1)
    ).strftime("%H:%M")

    eta_window_end = (
        eta_datetime + timedelta(hours=1)
    ).strftime("%H:%M")

    eta_date = eta_datetime.date().isoformat()

    # =========================================================
    # STEP 5 - Get Google Directions Polyline
    # =========================================================

    directions_url = (
        "https://maps.googleapis.com/maps/api/directions/json"
    )

    directions_params = {
        "origin": input_data.origin_address,
        "destination": input_data.destination_address,
        "mode": "driving",
        "key": GOOGLE_MAPS_API_KEY,
    }

    # ---------------------------------------------------------
    # Add waypoints if they exist
    # ---------------------------------------------------------

    if waypoints:

        directions_params["waypoints"] = "|".join(
            waypoints
        )

    print("Requesting Google Directions Polyline")

    try:

        directions_response = requests.get(
            directions_url,
            params=directions_params
        )

        directions_response.raise_for_status()

        directions_data = directions_response.json()

    except requests.exceptions.RequestException as e:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Google Directions API error: {str(e)}"
            )
        )

    # =========================================================
    # STEP 6 - Validate Directions Response
    # =========================================================

    if directions_data.get("status") != "OK":

        raise HTTPException(
            status_code=400,
            detail=(
                "Google Maps could not calculate the "
                "requested route."
            )
        )

    try:

        route = directions_data["routes"][0]

        polyline = (
            route["overview_polyline"]["points"]
        )

    except (IndexError, KeyError) as e:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Error getting polyline from "
                f"Google Directions API: {str(e)}"
            )
        )

    print("Polyline successfully generated.")

    # =========================================================
    # STEP 7 - Return
    # =========================================================

    return {
        "eta_date": eta_date,
        "eta_window": (
            f"{eta_window_start} - "
            f"{eta_window_end}"
        ),
        "polyline": polyline
    }