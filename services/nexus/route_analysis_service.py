# route_analysis_service.py
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session
import polyline
from geopy.distance import geodesic
from math import radians, cos, sin, asin, sqrt
from typing import List, Dict, Any

# Function to calculate distance between two lat/lon points in km
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Radius of earth in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return R * c

# Example Border Post structure
# Replace with DB query result
border_posts = [
    {"id": 1, "border_name": "Beitbridge", "from_country_iso": "ZA", "to_country_iso": "ZW", "latitude": -22.2167, "longitude": 30.0},
    {"id": 2, "border_name": "Lebombo", "from_country_iso": "ZA", "to_country_iso": "MZ", "latitude": -25.4356, "longitude": 31.9556},
    # Add all border posts here...
]

# Function to detect borders crossed along a route
def detect_borders(route_coords: List[Dict[str, float]], radius_km=5) -> List[Dict[str, Any]]:
    detected_borders = []
    added_border_ids = set()
    
    for point in route_coords:
        lat, lon = point["lat"], point["lng"]
        for border in border_posts:
            dist = haversine(lat, lon, border["latitude"], border["longitude"])
            if dist <= radius_km and border["id"] not in added_border_ids:
                detected_borders.append({
                    "border_id": border["id"],
                    "border_name": border["border_name"],
                    "from_country": border["from_country_iso"],
                    "to_country": border["to_country_iso"],
                    "distance_to_border_km": round(dist, 2)
                })
                added_border_ids.add(border["id"])
    
    return detected_borders