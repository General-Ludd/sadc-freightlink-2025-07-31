from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.brokerage.assigned_lanes import Assigned_Ftl_Lanes
from models.brokerage.assigned_shipments import Assigned_Spot_Ftl_Shipments, Assigned_Power_Shipments
from models.brokerage.finance import CarrierFinancialAccounts
from models.carrier import Carrier, Notification, Carrier_Notification
from schemas.brokerage.finance import CarrierFinancialAccountResponse, Carrier_FinancialAccount_Create
from schemas.carrier import CarrierCompanyResponse, CarrierCreate
from schemas.user import CarrierUserResponse, DriverCreate, DriverResponse, CarrierUsers
from schemas.vehicle import TrailerCreate, TrailerResponse, VehicleCreate, VehicleResponse, VehicleUpdate
from services.carrier_service import fleet_create_driver, create_fleet_carrier
from services.carrier_dashboards import assign_primary_driver, assign_trailer_to_vehicle
from services.vehicle_service import create_trailer, create_vehicle
from utils.auth import get_current_user, verify_password
from utils.jwt_handler import create_access_token
from models.user import CarrierUser, Driver
from models.vehicle import Trailer, Vehicle
from models.spot_bookings.ftl_shipment import FTL_Shipment_Dispute, FTL_SHIPMENT
from models.spot_bookings.power_shipment import POWER_Shipment_Dispute, POWER_SHIPMENT
from schemas.auth import LoginRequest, LoginResponse

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/fleet-carrier-registration")
def process_fleet_carrier_registration(
    carrier_data: CarrierCreate,
    director_data: CarrierUsers,
    financial_data: Carrier_FinancialAccount_Create,
    db: Session = Depends(get_db),
):
    try:
        results = create_fleet_carrier(db, carrier_data, director_data, financial_data)
        return {f"Fleet Carrier Registrations successful. please login into your account and await verification"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/carrier-director-login", response_model=LoginResponse) #tested
def login(request: LoginRequest, db: Session = Depends(get_db)):
    print("Login request received for:", request.email)
    
    # Check the `Carrier Director` table
    user = db.query(CarrierUser).filter(CarrierUser.email == request.email).first()
    if user:
        role = "Director"
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

@router.get("/carrier-dashboard/home")
def get_carrier_dashboard_home(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    try:
        carrier = db.query(Carrier).filter(Carrier.id == company_id).first()
        if not carrier:
            raise HTTPException(
                status_code=404,
                detail="Carrier not found"
            )
        financial_account = db.query(CarrierFinancialAccounts).filter(CarrierFinancialAccounts.id == company_id).first()
        vehicles = db.query(Vehicle).filter(Vehicle.owner_id == company_id).all()
        trailers = db.query(Trailer).filter(Trailer.owner_id == company_id).all()
        drivers = db.query(Driver).filter(Driver.company_id == company_id).all()
        # Query FTL & POWER shipments for this carrier
        ftl_shipments = db.query(Assigned_Spot_Ftl_Shipments).filter(Assigned_Spot_Ftl_Shipments.carrier_id == company_id).all()
        power_shipments = db.query(Assigned_Power_Shipments).filter(Assigned_Power_Shipments.carrier_id == company_id).all()
        ftl_lane = db.query(Assigned_Ftl_Lanes).filter(Assigned_Ftl_Lanes.carrier_id == company_id).all()
        # Filter by status
        in_progress_shipments = [
            s for s in (ftl_shipments + power_shipments) if getattr(s, "status", None) == "In-Progress"
        ]
        assigned_shipments = [
            s for s in (ftl_shipments + power_shipments) if getattr(s, "status", None) == "Assigned"
        ]
        assigned_lanes = [
            l for l in ftl_lane if getattr(l, "status", None) == "Assigned"
        ]
        in_progress_lanes = [
            l for l in ftl_lane if getattr(l, "status", None) == "In-Progress"
        ]
        # Get disputes
        ftl_disputes = db.query(FTL_Shipment_Dispute).filter(FTL_Shipment_Dispute.carrier_company_id == company_id).all()
        power_disputes = db.query(POWER_Shipment_Dispute).filter(POWER_Shipment_Dispute.carrier_company_id == company_id).all()
        notifications = db.query(Carrier_Notification).filter(Carrier_Notification.company_id == company_id).all()
        active_disputes = [
            d for d in (ftl_disputes + power_disputes)
            if getattr(d, "status", None) == "Open"
        ]
        disputes = ftl_disputes + power_disputes

        return {
            "navbar_company_name": carrier.legal_business_name,
            "dashboard": {
                "fleet_vehicles": len(vehicles),
                "trailers": len(trailers),
                "drivers": len(drivers),
                "assigned_shipments": len(assigned_shipments),
                "in_progress_shipments": len(in_progress_shipments),
                "completed_shipments": carrier.number_of_completed_shipments,
                "assigned_lanes": len(assigned_lanes),
                "in_progress_lanes": len(in_progress_lanes),
                "completed_lanes": carrier.number_of_completed_dedicated_lanes,
                "rating": f"{carrier.rating}/5",
                "active_disputes": len(active_disputes),
                "total_earned": financial_account.total_earned,
                "total_withdrawn": financial_account.total_withdrawn,
                "current_balance": financial_account.current_balance,
                "holding_balance": financial_account.holding_balance,

                "shipment_management_and_disputes": {
                    "active_shipments": [
                        {
                            "id": s.id,
                            "type": "FTL" if isinstance(s, FTL) else "POWER",  # ensure we distinguish
                            "trip_status": s.trip_status,
                            "origin": s.origin_city_province,
                            "destination": s.destination_city_province,
                        }
                        for s in in_progress_shipments
                    ],

                    "disputes": [{
                        "id": dispute.id,
                        "shipment_id": dispute.shipment_id,
                        "shipment_type": dispute.shipment_type,
                    } for dispute in disputes],
                },


                "notifications_alerts": [{
                    "id": notification.id,
                    "type": notification.type,
                    "message": notification.message
                } for notification in notifications]
            }
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/carrier/notifications")
def get_carrier_account_notifications(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    try:
        notifications = db.query(Carrier_Notification).filter(Carrier_Notification.company_id == company_id).all()

        return {
            "notifications": [{
                "id": notification.id,
                "type": notification.type,
                "message": notification.message,
                "is_read": notification.is_read,
                "recieved_at": notification.created_at
            } for notification in notifications]
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/carrier/account")
def carrier_get_account_information(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    try:
        company = db.query(Carrier).filter(Carrier.id == company_id).first()
        director = db.query(CarrierUser).filter(CarrierUser.company_id == company.id,
                                                CarrierUser.is_director == True).first()
        financial_account = db.query(CarrierFinancialAccounts).filter(CarrierFinancialAccounts.id == company.id).first()

        return {
            "account_verification_status": {
                "company_information": company.is_verified,
                "director_information": director.is_verified,
                "financial_information": financial_account.is_verified,
            },

            "company_information": {
                "id": company.id,
                "is_verified": company.is_verified,
                "status": company.status,
                "type": company.type,
                "comapny_name": company.legal_business_name,
                "country_of_incorporation": company.country_of_incorporation,
                "business_registration_number": company.business_registration_number,
                "business_address": company.business_address,
                "business_email": company.business_email,
                "business_phone_number": company.business_phone_number,
                "number_of_vehicles": company.number_of_vehicles,
                "number_of_trailers": company.number_of_trailers,
                "number_of_drivers": company.number_of_drivers,
                "number_of_shipents_completed": company.number_of_completed_shipments,
                "number_of_completed_contracts": company.number_of_completed_dedicated_lanes,
                "number_of_in_progress_contracts": company.number_of_ongoing_dedicated_lanes,
                "rating": company.rating,
                "name_of_git_insurance_company": company.name_of_git_cover_insurance_company,
                "git_insurance_policy_number": company.git_insurance_policy_number,
                "git_cover_amount": company.git_cover_amount,
                "name_of_liability_cover_insurance_company": company.name_of_liability_cover_insurance_company,
                "liability_insurance_policy_number": company.liability_insurance_policy_number,
                "liability_insurance_cover_amount": company.liability_insurance_cover_amount,
                "company_documents": {
                    "business_registration_certificate": company.business_registration_certificate,
                    "proof_of_address": company.proof_of_address,
                    "git_insurance_certificate": company.git_insurance_certificate,
                    "liability_insurance_certificate": company.liability_insurance_certificate,
                }
            },

            "director_information": {
                "id": director.id,
                "first_name": director.first_name,
                "last_name": director.last_name,
                "nationality": director.nationality,
                "id_number": director.id_number,
                "home_address": director.home_address,
                "email": director.email,
                "phone_number": director.phone_number,
                "is_director": director.is_director,
                "is_verified": director.is_verified,
                "status": director.status,
                "director_documents": {
                    "id_document": director.id_document,
                    "proof_of_address": director.proof_of_address,
                }
            },

            "financial_information": {
                "banking_information": {
                    "bank_name": financial_account.bank_name,
                    "country": financial_account.bank_country,
                    "branch_code": financial_account.branch_code,
                    "account_number": financial_account.account_number,
                    "account_type": financial_account.account_type,
                    "banking_documents": {
                        "account_confirmation_letter": financial_account.account_confirmation_letter,
                    }
                },

                "financial_metrics": {
                    "total_contracts": company.number_of_completed_dedicated_lanes,
                    "total_shipments_completed": company.number_of_completed_shipments,
                    "holding_balance": financial_account.holding_balance,
                    "current_balance": financial_account.current_balance,
                    "total_earned": financial_account.total_earned,
                    "total_withdrawn": financial_account.total_withdrawn
                }
            }
        }
    except Exception as e:
        return {"error": str(e)}