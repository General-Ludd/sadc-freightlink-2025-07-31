from datetime import date
from typing import Optional
from models.shipper import Corporation
from models.brokerage.finance import FinancialAccounts
from models.user import Director
from enums import Axle_Configuration, EquipmentType, Lorry, Recurrence_Days, Recurrence_Frequency, TrailerLength, TrailerType, TruckType
from schemas.spot_bookings.dedicated_lanes_ftl_shipment import FTL_Lane_Create,  SpotFTLLaneQuoteRequest
from schemas.spot_bookings.ftl_shipment import FTL_Shipment_Booking, Admin_Client_FTL_Shipment_Booking, FTL_Shipment_docs_create
from schemas.shipment_facility import ShipmentFacilityCreate, FacilityContactCreate
from schemas.spot_bookings.power_shipment import POWER_Shipment_docs_create, Power_Shipment_Booking
from services.finance.finance import calculate_spot_ftl_lane_quote, calculate_spot_ftl_quote, calculate_spot_power_quote
from services.spot_bookings.dedicated_lanes_ftl_shipment import create_dedicated_lane_ftl_shipment
from services.spot_bookings.ftl_shipment import create_ftl_shipment, admin_create_client_ftl_shipment
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from services.spot_bookings.power_shipment import create_spot_power_shipment
from utils.auth import get_current_user
from utils.administration_auth import get_current_admin
from sqlalchemy import func


router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/api/get-client-company-summary/{id}")
def admin_fetch_client_summary(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        company = db.query(Corporation).filter(Corporation.id == id).first()
        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

        financial_account = db.query(FinancialAccounts).filter(FinancialAccounts.id == company.id).first()
        if not financial_account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Financial Account not found")

        booked_shipments = db.query(func.count(FTL_SHIPMENT.id)).filter(
            FTL_SHIPMENT.shipper_company_id == company.id,
            FTL_SHIPMENT.shipment_status == "Booked"
        ).scalar()

        assigned_shipments = db.query(func.count(FTL_SHIPMENT.id)).filter(
            FTL_SHIPMENT.shipper_company_id == company.id,
            FTL_SHIPMENT.shipment_status == "Assigned"
        ).scalar()

        in_progress_shipments = db.query(func.count(FTL_SHIPMENT.id)).filter(
            FTL_SHIPMENT.shipper_company_id == company.id,
            FTL_SHIPMENT.shipment_status == "In-Progress"
        ).scalar()

        completed_shipments = db.query(func.count(FTL_SHIPMENT.id)).filter(
            FTL_SHIPMENT.shipper_company_id == company.id,
            FTL_SHIPMENT.shipment_status == "Completed"
        ).scalar()

        cancelled_shipments = db.query(func.count(FTL_SHIPMENT.id)).filter(
            FTL_SHIPMENT.shipper_company_id == company.id,
            FTL_SHIPMENT.shipment_status == "Cancelled"
        ).scalar()

        return {
            "id": company.id,
            "company_name": company.legal_business_name,
            "registration_number": company.business_registration_number,
            "is_verified": company.is_verified,
            "status": company.status,
            "booked_shipments": booked_shipments,
            "assigned_shipments": assigned_shipments,
            "in_progress_shipments": in_progress_shipments,
            "completed_shipments": completed_shipments,
            "cancelled_shipments": cancelled_shipments,
            "total_spent": financial_account.total_spent,
            "total_outstanding": financial_account.total_outstanding
        }

@router.get("/admin/get-client-{id}-users")
def admin_fetch_client_users(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        users = db.query(Director).filter(Director.company_id == id).all()
        return [{
            "id": int,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            
        }for user in users]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/admin/spot/client-ftl-shipment-create", status_code=status.HTTP_201_CREATED)
def admin_create_client_spot_ftl_endpoint(
    shipment_data: Admin_Client_FTL_Shipment_Booking,
    pickup_facility_data: ShipmentFacilityCreate,
    dropoff_facility_data: ShipmentFacilityCreate,
    pickup_contact_data: FacilityContactCreate,
    dropoff_contact_data: FacilityContactCreate,
    shipment_documents_data: FTL_Shipment_docs_create,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        result = admin_create_client_ftl_shipment(
            db,
            shipment_data,
            pickup_facility_data,
            dropoff_facility_data,
            pickup_contact_data,
            dropoff_contact_data,
            shipment_documents_data,
            current_user=current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))