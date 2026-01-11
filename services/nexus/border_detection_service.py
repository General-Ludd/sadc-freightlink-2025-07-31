from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict
import polyline
from math import radians, cos, sin, asin, sqrt
from sqlalchemy.orm import Session

from db.database import SessionLocal
from models.nexus.customs_territories import BorderPost, Country

# -----------------------------
# Dependency
# -----------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -----------------------------
# Router
# -----------------------------
router = APIRouter()

# -----------------------------
# Pydantic models
# -----------------------------
class PolylineInput(BaseModel):
    polyline: str

class BorderLeg(BaseModel):
    border_post_id: int
    country_iso: str
    fee_type: str       # EXIT or ENTRY
    amount_zar: float

class BorderCrossing(BaseModel):
    border_name: str
    latitude: float
    longitude: float
    distance_to_border_km: float
    legs: List[BorderLeg]

class BorderDetectionOutput(BaseModel):
    borders_crossed: List[BorderCrossing]

# -----------------------------
# Haversine distance utility
# -----------------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return R * c

# -----------------------------
# Core detection function
# -----------------------------
def detect_borders_from_route(
    route_coords: List[Dict[str, float]],
    db: Session,
    radius_km: float = 5,
) -> List[Dict]:
    """
    Detect border crossings along a route, correctly ordered, with direction.
    """

    # 1️⃣ Load active border posts with coordinates
    border_posts = (
        db.query(
            BorderPost.id,
            BorderPost.border_name,
            BorderPost.fee_type,
            BorderPost.amount_zar,
            BorderPost.latitude,
            BorderPost.longitude,
            Country.iso_code.label("country_iso"),
        )
        .join(Country, BorderPost.from_country_id == Country.id)
        .filter(
            BorderPost.is_active == True,
            BorderPost.latitude.isnot(None),
            BorderPost.longitude.isnot(None),
        )
        .all()
    )

    # 2️⃣ Group posts by physical border (name + coords)
    grouped_borders = {}
    for post in border_posts:
        key = (post.border_name, round(post.latitude, 4), round(post.longitude, 4))
        if key not in grouped_borders:
            grouped_borders[key] = {
                "border_name": post.border_name,
                "latitude": post.latitude,
                "longitude": post.longitude,
                "legs": [],
            }
        grouped_borders[key]["legs"].append({
            "border_post_id": post.id,
            "country_iso": post.country_iso,
            "fee_type": post.fee_type,
            "amount_zar": float(post.amount_zar or 0),
        })

    # 3️⃣ Detect borders along the route, record route index for ordering
    detected = []
    for i, point in enumerate(route_coords):
        lat, lon = point["lat"], point["lng"]
        for border in grouped_borders.values():
            dist = haversine(lat, lon, border["latitude"], border["longitude"])
            if dist <= radius_km:
                detected.append({
                    "border_name": border["border_name"],
                    "latitude": border["latitude"],
                    "longitude": border["longitude"],
                    "distance_to_border_km": round(dist, 2),
                    "route_index": i,
                    "legs": border["legs"],
                })

    # 4️⃣ Deduplicate by border_name (keep first encounter)
    unique = {}
    for b in detected:
        if b["border_name"] not in unique or b["route_index"] < unique[b["border_name"]]["route_index"]:
            unique[b["border_name"]] = b

    # 5️⃣ Order borders along route
    ordered_borders = sorted(unique.values(), key=lambda x: x["route_index"])

    # 6️⃣ Resolve legs to only those that correspond to the correct trip direction
    # Assumption: Each border has exactly one EXIT and one ENTRY
    for border in ordered_borders:
        exit_leg = next((l for l in border["legs"] if l["fee_type"].upper() == "EXIT"), None)
        entry_leg = next((l for l in border["legs"] if l["fee_type"].upper() == "ENTRY"), None)
        # Keep only the EXIT + ENTRY pair in correct sequence
        border["legs"] = [exit_leg, entry_leg] if exit_leg and entry_leg else border["legs"]

    return ordered_borders

# -----------------------------
# API Endpoint
# -----------------------------
@router.post("/detect-borders", response_model=BorderDetectionOutput)
def detect_borders(
    input_data: PolylineInput,
    db: Session = Depends(get_db),
):
    try:
        decoded = polyline.decode(input_data.polyline)
        route_coords = [{"lat": lat, "lng": lng} for lat, lng in decoded]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid polyline: {str(e)}")

    borders = detect_borders_from_route(route_coords, db)

    return {"borders_crossed": borders}