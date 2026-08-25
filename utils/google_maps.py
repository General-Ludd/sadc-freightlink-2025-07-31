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
    Calculate complete driving route:

    Origin
        -> Stop 1
        -> Stop 2
        -> ...
        -> Destination

    Returns:
    - Total distance
    - Total transit time
    - Complete address information
    - City / Province
    - Region
    - Country
    - Latitude
    - Longitude
    - Google encoded polyline
    - Google Maps embed URL
    """

    if not GOOGLE_MAPS_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Google Maps API key not configured."
        )

    # =========================================================
    # STEP 1 — PREPARE WAYPOINTS
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

    # =========================================================
    # STEP 2 — GET ORIGIN DETAILS
    # =========================================================

    origin = get_location_details(
        input_data.origin_address
    )

    # =========================================================
    # STEP 3 — GET STOP DETAILS
    # =========================================================

    stops = []

    for index, waypoint in enumerate(waypoints, start=1):

        stop = get_location_details(waypoint)

        stops.append({
            "stop_sequence": index,
            "input_address": waypoint,
            "complete_address": stop["complete_address"],
            "city_province": stop["city_province"],
            "city": stop["city"],
            "province": stop["province"],
            "country": stop["country"],
            "region": stop["region"],
            "latitude": stop["latitude"],
            "longitude": stop["longitude"]
        })

    # =========================================================
    # STEP 4 — GET DESTINATION DETAILS
    # =========================================================

    destination = get_location_details(
        input_data.destination_address
    )

    # =========================================================
    # STEP 5 — GOOGLE DIRECTIONS API
    # =========================================================

    directions_url = (
        "https://maps.googleapis.com/maps/api/directions/json"
    )

    directions_params = {
        "origin": input_data.origin_address,
        "destination": input_data.destination_address,
        "mode": "driving",
        "key": GOOGLE_MAPS_API_KEY
    }

    # ---------------------------------------------------------
    # Add waypoints
    # ---------------------------------------------------------

    if waypoints:

        directions_params["waypoints"] = "|".join(
            waypoints
        )

    # =========================================================
    # STEP 6 — REQUEST COMPLETE ROUTE
    # =========================================================

    try:

        directions_response = requests.get(
            directions_url,
            params=directions_params,
            timeout=20
        )

        directions_response.raise_for_status()

        directions_result = directions_response.json()

    except requests.exceptions.RequestException as e:

        raise HTTPException(
            status_code=500,
            detail=(
                "Google Maps Directions API error: "
                f"{str(e)}"
            )
        )

    # =========================================================
    # STEP 7 — VALIDATE DIRECTIONS RESPONSE
    # =========================================================

    if (
        directions_result.get("status") != "OK"
        or not directions_result.get("routes")
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Google Maps could not calculate the complete "
                "route between the supplied addresses."
            )
        )

    route = directions_result["routes"][0]

    # =========================================================
    # STEP 8 — GET COMPLETE POLYLINE
    # =========================================================

    polyline = route.get(
        "overview_polyline",
        {}
    ).get(
        "points"
    )

    if not polyline:

        raise HTTPException(
            status_code=400,
            detail="Google Maps did not return a route polyline."
        )

    # =========================================================
    # STEP 9 — CALCULATE TOTAL DISTANCE & DURATION
    # =========================================================

    total_distance_meters = 0
    total_duration_seconds = 0

    for leg in route.get("legs", []):

        total_distance_meters += (
            leg["distance"]["value"]
        )

        total_duration_seconds += (
            leg["duration"]["value"]
        )

    # =========================================================
    # STEP 10 — CONVERT DISTANCE TO KM
    # =========================================================

    distance_km = round(
        total_distance_meters / 1000,
        1
    )

    # =========================================================
    # STEP 11 — CONVERT DURATION
    # =========================================================

    total_hours = total_duration_seconds // 3600

    total_minutes = (
        total_duration_seconds % 3600
    ) // 60

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
    # STEP 12 — GOOGLE MAPS EMBED URL
    # =========================================================

    embed_url = (
        "https://www.google.com/maps/embed/v1/directions"
        f"?key={GOOGLE_MAPS_API_KEY}"
        f"&origin={input_data.origin_address.replace(' ', '+')}"
        f"&destination={input_data.destination_address.replace(' ', '+')}"
        "&mode=driving"
    )

    if waypoints:

        encoded_waypoints = "|".join(
            waypoint.replace(" ", "+")
            for waypoint in waypoints
        )

        embed_url += (
            f"&waypoints={encoded_waypoints}"
        )

    # =========================================================
    # STEP 13 — BUILD RESPONSE
    # =========================================================

    response_data = {

        # =====================================================
        # ROUTE SUMMARY
        # =====================================================

        "distance": distance_km,
        "duration": duration_text,

        # =====================================================
        # POLYLINE
        # =====================================================

        "polyline": polyline,

        # =====================================================
        # ORIGIN
        # =====================================================

        "origin_address": input_data.origin_address,
        "complete_origin_address": origin["complete_address"],
        "origin_city_province": origin["city_province"],
        "origin_country": origin["country"],
        "origin_region": origin["region"],
        "origin_latitude": origin["latitude"],
        "origin_longitude": origin["longitude"],

        # =====================================================
        # STOPS
        # =====================================================

        "stops": stops,

        # =====================================================
        # DESTINATION
        # =====================================================

        "destination_address": input_data.destination_address,
        "complete_destination_address": destination["complete_address"],
        "destination_city_province": destination["city_province"],
        "destination_country": destination["country"],
        "destination_region": destination["region"],
        "destination_latitude": destination["latitude"],
        "destination_longitude": destination["longitude"],

        # =====================================================
        # GOOGLE MAPS
        # =====================================================

        "google_maps_embed_url": embed_url
    }

    # =========================================================
    # STEP 14 — FLATTEN STOP DATA
    # =========================================================
    #
    # Keeps compatibility with your existing shipment fields.
    # =========================================================

    for stop in stops:

        sequence = stop["stop_sequence"]

        response_data[
            f"stop_{sequence}_address"
        ] = stop["input_address"]

        response_data[
            f"complete_stop_{sequence}_address"
        ] = stop["complete_address"]

        response_data[
            f"stop_{sequence}_city_province"
        ] = stop["city_province"]

        response_data[
            f"stop_{sequence}_country"
        ] = stop["country"]

        response_data[
            f"stop_{sequence}_region"
        ] = stop["region"]

        response_data[
            f"stop_{sequence}_latitude"
        ] = stop["latitude"]

        response_data[
            f"stop_{sequence}_longitude"
        ] = stop["longitude"]

    # =========================================================
    # STEP 15 — DEBUG LOGGING
    # =========================================================

    print(
        "========== GOOGLE MAPS ROUTE COMPLETE =========="
    )

    print(
        f"Distance: {distance_km} km"
    )

    print(
        f"Duration: {duration_text}"
    )

    print(
        f"Polyline length: {len(polyline)} characters"
    )

    print(
        f"Origin GPS: "
        f"{origin['latitude']}, "
        f"{origin['longitude']}"
    )

    for stop in stops:

        print(
            f"Stop {stop['stop_sequence']} GPS: "
            f"{stop['latitude']}, "
            f"{stop['longitude']}"
        )

    print(
        f"Destination GPS: "
        f"{destination['latitude']}, "
        f"{destination['longitude']}"
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