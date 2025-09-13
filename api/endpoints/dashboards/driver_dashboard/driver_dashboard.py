from models.user import Driver
from schemas.auth import LoginRequest, LoginResponse
from utils.auth import get_current_user, verify_password
from utils.jwt_handler import create_access_token
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from datetime import date
from models.brokerage.assigned_shipments import Assigned_Spot_Ftl_Shipments, Assigned_Power_Shipments

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/driver-sign-in", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    print("Login request received for:", request.email)
    
    # Check the `Carrier Director` table
    user = db.query(Driver).filter(Driver.email == request.email).first()
    if user:
        role = "Driver"
    else:
        print("User not found in any database.")
        raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password
    if not verify_password(request.password, user.password_hash):
        print("Password verification failed for:", request.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    print(f"User authenticated successfully as {role}: {user.email}")

    # Create token with role-specific information
    token = create_access_token({"id": user.id, "email": user.email, "first_name": user.first_name, "last_name": user.last_name, "company_id": user.company_id})
    print("Generated JWT token:", token)

    return {"access_token": token, "token_type": "bearer"}

 

@router.get("/driver/account")
def driver_get_account_information(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    user_id = current_user.get("id")
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    try:
        driver = db.query(Driver).filter(Driver.id == user_id).first()
        fleet = db.query(Carrier).filter(Carrier.id == company_id).first()

        return {
            "driver_information": {
                "id": driver.id,
                "verification_status": driver.is_verified,
                "status": driver.status,
                "availability_status": driver.service_status,
                "first_name": driver.first_name,
                "last_name": driver.last_name,
                "nationality": driver.nationality,
                "id_number": driver.id_number,
                "license_number": driver.license_number,
                "licnese_expiry_date": driver.license_expiry_date,
                "prdp_number": driver.prdp_number,
                "prdp_expiry_date": driver.prdp_expiry_date,
                "passport_number": driver.passport_number,
                "home_address": driver.home_address,
                "email": driver.email,
                "phone_number": driver.phone_number,
                "total_shipments_completed": driver.total_shipments_completed,
                "total_distance_driven": driver.total_distance_driven,
                "rating": f"{driver.rating}/5"
                },
            
            "fleet_information": {
                "id": fleet.id,
                "company_name": fleet.legal_business_name,
                "country_of_incorporation": fleet.country_of_incorporation,
                "company_address": fleet.business_address,
                "company_email": fleet.business_email,
                "company_phone_number": fleet.business_phone_number,
                "fleet_size": fleet.number_of_vehicles,
                "completed_shipments": fleet.number_of_completed_shipments
            },

            "documents": {
                "id_document": driver.id_document,
                "drivers_license": driver.license_document,
                "prdp": driver.prdp_document,
                "proof_of_address": driver.proof_of_address,
                "passport": driver.passport_document,
            },
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/driver-summary")
def get_driver_summary(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    user_id = current_user.get("id")
    company_id = current_user.get("company_id")

    try:
        # Get driver by linked user_id (adjust if Driver.id == User.id is correct in your schema)
        driver = db.query(Driver).filter(Driver.id == user_id).first()
        if not driver:
            raise HTTPException(status_code=404, detail="Driver profile not found")

        today = date.today()

        # FTL shipments (upcoming only)
        upcoming_ftl_shipments = db.query(Assigned_Spot_Ftl_Shipments).filter(
            Assigned_Spot_Ftl_Shipments.driver_id == driver.id,
            Assigned_Spot_Ftl_Shipments.status.in_(["Assigned", "In-Progress"]),
            Assigned_Spot_Ftl_Shipments.pickup_date >= today
        ).all()

        # Power shipments (upcoming only)
        upcoming_power_shipments = db.query(Assigned_Power_Shipments).filter(
            Assigned_Power_Shipments.driver_id == driver.id,
            Assigned_Power_Shipments.status.in_(["Assigned", "In-Progress"]),
            Assigned_Power_Shipments.pickup_date >= today
        ).all()

        # Count total upcoming
        upcoming_shipments = len(upcoming_ftl_shipments + upcoming_power_shipments)

        return {
            "upcoming_shipments": upcoming_shipments,
            "completed_shipments": driver.total_shipments_completed,
            "distance_driven": driver.total_distance_driven,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
