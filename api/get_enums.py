from fastapi import APIRouter, Request, HTTPException, status, Response, Depends
from sqlalchemy.orm import Session
from db.database import SessionLocal
from enums import (
    Priority_Level,
    SchedulingType,
    TruckType,
    EquipmentType,
    TrailerType,
    TrailerLength,
    PricingBasis,
    RateDirectionTarget,
)

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================
# TRUCK TYPES
# ============================================================
@router.get("/priority-levels")
def get_priority_levels():
    return [
        priority_level.value
        for priority_level in Priority_Level
    ]

@router.get("/scheduling-types")
def get_scheduling_types():
    return [
        scheduling_type.value
        for scheduling_type in SchedulingType
    ]

# ============================================================
# TRUCK TYPES
# ============================================================
@router.get("/truck-types")
def get_truck_types():
    return [
        truck_type.value
        for truck_type in TruckType
    ]


# ============================================================
# EQUIPMENT TYPES
# ============================================================
@router.get("/equipment-types")
def get_equipment_types():
    return [
        equipment_type.value
        for equipment_type in EquipmentType
    ]


# ============================================================
# TRAILER TYPES
# ============================================================
@router.get("/trailer-types")
def get_trailer_types():
    return [
        trailer_type.value
        for trailer_type in TrailerType
    ]


# ============================================================
# TRAILER LENGTHS
# ============================================================
@router.get("/trailer_lengths")
def get_trailer_lengths():
    return [
        trailer_length.value
        for trailer_length in TrailerLength
    ]


# ============================================================
# PRICING BASIS
# ============================================================
@router.get("/pricing-basis")
def get_pricing_basis():
    return [
        pricing_basis.value
        for pricing_basis in PricingBasis
    ]


# ============================================================
# RATE DIRECTION
# ============================================================
@router.get("/rate-directions")
def get_rate_directions():
    return [
        rate_direction.value
        for rate_direction in RateDirectionTarget
    ]