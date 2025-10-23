from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.sql.expression import cast
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional
from pydantic import BaseModel
from db.database import SessionLocal # Ensure you have a database dependency defined
from models.brokerage.finance import VehicleRate

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/calculate-vehicle-quote")
def calculate_quote_for_shipment(
    required_truck_type: str,
    equipment_type: str,
    trailer_type: str,
    trailer_length: str,
    distance: int,
    minimum_weight_bracket: int,  # replace minimum_weight_bracket with actual truck tonnage
    db: Session = Depends(get_db)
):
    """
    Calculate the vehicle rate quote using simple base rate + increment per tonne method.
    """
    try:
        # Construct the vehicle string
        vehicle_string = f"{required_truck_type.lower()}{equipment_type.lower()}{trailer_type.lower()}{trailer_length.lower()}"

        # Query the VehicleRate table for the matching vehicle
        vehicle_rate = db.query(VehicleRate).filter(VehicleRate.name == vehicle_string).first()

        if not vehicle_rate:
            raise HTTPException(
                status_code=404,
                detail=f"No vehicle rate found for vehicle string: {vehicle_string}"
            )

        # Extract base_rate and increment_per_tonne
        base_rate = float(vehicle_rate.base_rate)
        increment_per_tonne = int(vehicle_rate.increment_per_tonne)
        base_bracket = int(vehicle_rate.base_weight_bracket)  # base truck tonnage in VehicleRate table

        base_tonnage = (base_bracket / 1000)

        tonnage_increment = (minimum_weight_bracket - base_tonnage)

        increment = tonnage_increment * increment_per_tonne

        # Calculate rate per km
        rate_per_km = base_rate + increment

        # Calculate the quote
        quote = rate_per_km * distance

        # Return rounded integer
        return int(round(quote))

    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

def calculate_total_shipment_quote(
    qoute_per_shipment: int,
    total_shipments: int
) -> int:
    """
    Calculate the total shipment quote based on quote per shipment and the total number of shipments.

    :param quote_per_shipment: The cost for a single shipment.
    :param total_shipments: The total number of shipments.
    :return: The total shipment quote.
    """
    return (qoute_per_shipment * 1.5) * total_shipments

def calculate_qoute_for_power_shipment(
    required_truck_type: str,
    axle_configuration: str,
    distance: int,
    minimum_weight_bracket: int, # replace minimum_weight_bracket with actual truck tonnage
    db: Session = Depends(get_db)
):
    """
    Calculate the vehicle rate quote using simple base rate + increment per tonne method.
    """
    try:
        # Construct the vehicle string
        vehicle_string = f"{required_truck_type.lower()}{axle_configuration.lower()}"

        # Query the VehicleRate table for the matching vehicle
        vehicle_rate = db.query(VehicleRate).filter(VehicleRate.name == vehicle_string).first()

        if not vehicle_rate:
            raise HTTPException(
                status_code=404,
                detail=f"No vehicle rate found for vehicle string: {vehicle_string}"
            )

        # Extract base_rate and increment_per_tonne
        base_rate = float(vehicle_rate.base_rate)
        increment_per_tonne = int(vehicle_rate.increment_per_tonne)
        base_bracket = int(vehicle_rate.base_weight_bracket)  # base truck tonnage in VehicleRate table

        base_tonnage = (base_bracket / 1000)

        tonnage_increment = (minimum_weight_bracket - base_tonnage)

        increment = tonnage_increment * increment_per_tonne

        # Calculate rate per km
        rate_per_km = base_rate + increment

        # Calculate the quote
        quote = rate_per_km * distance

        # Return rounded integer
        return int(round(quote))

    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
