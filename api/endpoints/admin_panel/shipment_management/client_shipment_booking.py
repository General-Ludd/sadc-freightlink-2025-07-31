from datetime import date
from typing import Optional
from models.shipper import Corporation
from models.brokerage.finance import FinancialAccounts
from models.user import Director
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT, FTL_Shipment_Docs
from models.spot_bookings.shipment_facility import ContactPerson, ShipmentFacility
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
from fastapi import Request
import json


router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/get-client-company-summary/{id}")
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
    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@router.get("/admin/client/{id}/past-shipments")
def admin_fetch_client_users(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        shipments = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.shipper_company_id == id).all()

        return [
            {
                "id": shipment.id,
                "origin": shipment.origin_city_province,
                "destination": shipment.destination_city_province,
                "customer_reference_number": shipment.customer_reference_number,
                "shipment_weight": shipment.shipment_weight,
                "commodity": shipment.commodity,
                "pickup_date": shipment.pickup_date,
                "status": shipment.shipment_status,
            }
            for shipment in shipments
        ]

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@router.get("/admin/client/shipment/{id}")
def admin_fetch_client_users(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        shipment = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.id == id).first()

        shipment_docs = db.query(FTL_Shipment_Docs).filter(FTL_Shipment_Docs.shipment_id == shipment.id).first()

        # ---------------------------------
        # 2. FETCH RELATED OBJECTS
        # ---------------------------------
        pickup_facility = db.query(ShipmentFacility).filter_by(id=shipment.pickup_facility_id).first()
        delivery_facility = db.query(ShipmentFacility).filter_by(id=shipment.delivery_facility_id).first()

        pickup_contact = (
            db.query(ContactPerson).filter_by(id=pickup_facility.contact_person).first()
            if pickup_facility else None
        )
        delivery_contact = (
            db.query(ContactPerson).filter_by(id=delivery_facility.contact_person).first()
            if delivery_facility else None
        )

        # ---------------------------------
        # 4. BUILD RESPONSE
        # ---------------------------------
        return {
            "shipment_details": {
                "id": shipment.id,
                "required_truck_type": shipment.required_truck_type,
                "required_equipment_type": shipment.equipment_type,
                "required_trailer_type": shipment.trailer_type,
                "required_trailer_length": shipment.trailer_length,
                "minimum_weight_bracket": shipment.minimum_weight_bracket,
                "origin_address": shipment.complete_origin_address,
                "destination_address": shipment.complete_destination_address,
                "pickup_date": shipment.pickup_date,
                "priority_level": shipment.priority_level,
                "customer_reference_number": shipment.customer_reference_number,
                "shipment_weight": shipment.shipment_weight,
                "commodity": shipment.commodity,
                "temperature_control": shipment.temperature_control,
                "hazardous_materials": shipment.hazardous_materials,
                "minimum_git_cover_amount": shipment.minimum_git_cover_amount,
                "minimum_liability_cover_amount": shipment.minimum_liability_cover_amount,
                "packaging_quantity": shipment.packaging_quantity,
                "packaging_type": shipment.packaging_type,
                "pickup_number": shipment.pickup_number,
                "delivery_number": shipment.delivery_number,
                "pickup_notes": shipment.pickup_notes,
                "delivery_notes": shipment.delivery_notes,
                "distance": shipment.distance,
            },

            "shipment_documents": {
                "commercial_invoice": shipment_docs.commercial_invoice if shipment_docs else None,
                "packaging_list": shipment_docs.packaging_list if shipment_docs else None,
                "customs_declaration_form": shipment_docs.customs_declaration_form if shipment_docs else None,
                "import_or_export_permits": shipment_docs.import_or_export_permits if shipment_docs else None,
                "certificate_of_origin": shipment_docs.certificate_of_origin if shipment_docs else None,
                "da5501orsad500": shipment_docs.da5501orsad500 if shipment_docs else None,
                "proof_of_delivery": shipment.pod_document if shipment.pod_document else None,
            },

            "pickup_facility": {
                "facility_name": pickup_facility.name,
                "start_time": {pickup_facility.start_time},
                "end_time": {pickup_facility.end_time},
                "scheduling_type": pickup_facility.scheduling_type,
                "notes": pickup_facility.facility_notes,
            } if pickup_facility else None,

            "pickup_contact": {
                "first_name": {pickup_contact.first_name} if pickup_contact else None,
                "last_name": {pickup_contact.last_name} if pickup_contact else None,
                "contact_phone": pickup_contact.phone_number if pickup_contact else None,
                "email": pickup_contact.email if pickup_contact else None,
            } if pickup_contact else None,

            "delivery_facility": {
                "facility_name": delivery_facility.name,
                "start_time": {delivery_facility.start_time},
                "end_time": {delivery_facility.end_time},
                "scheduling_type": delivery_facility.scheduling_type,
                "notes": delivery_facility.facility_notes,
            } if delivery_facility else None,
            
            "delivery_contact": {
                "first_name": {delivery_contact.first_name} if delivery_contact else None,
                "last_name": {delivery_contact.last_name} if delivery_contact else None,
                "contact_phone": delivery_contact.phone_number if delivery_contact else None,
                "email": delivery_contact.email if delivery_contact else None,
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/clients/{id}/users")
def admin_fetch_client_users(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:

        company = db.query(Corporation).filter(
            Corporation.id == id
        ).first()

        if not company:
            raise HTTPException(
                status_code=404,
                detail="Company not found"
            )

        users = db.query(Director).filter(
            Director.company_id == id
        ).all()

        return [
            {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role,
            }
            for user in users
        ]

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

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
    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

SUCCESS_STATUSES = ["Assigned", "In-Transit", "Completed"]
FAILED_STATUSES = ["Cancelled", "Failed"]

@router.get("/admin/fetch-client/{client_id}/routes")
def admin_fetch_client_routes(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:

        shipments = (
            db.query(FTL_SHIPMENT)
            .filter(FTL_SHIPMENT.shipper_company_id == client_id)
            .order_by(FTL_SHIPMENT.created_at.desc())   # Latest first
            .all()
        )

        routes = []
        seen_routes = set()

        for shipment in shipments:

            route_key = (
                shipment.origin_city_province,
                shipment.destination_city_province,
            )

            if route_key in seen_routes:
                continue

            seen_routes.add(route_key)

            # Count all bookings on this lane
            previous_bookings = (
                db.query(FTL_SHIPMENT)
                .filter(
                    FTL_SHIPMENT.shipper_company_id == client_id,
                    FTL_SHIPMENT.origin_city_province == shipment.origin_city_province,
                    FTL_SHIPMENT.destination_city_province == shipment.destination_city_province,
                )
                .count()
            )

            # Successful shipments
            successful = (
                db.query(FTL_SHIPMENT)
                .filter(
                    FTL_SHIPMENT.shipper_company_id == client_id,
                    FTL_SHIPMENT.origin_city_province == shipment.origin_city_province,
                    FTL_SHIPMENT.destination_city_province == shipment.destination_city_province,
                    FTL_SHIPMENT.shipment_status.in_(SUCCESS_STATUSES),
                )
                .count()
            )

            # Failed shipments
            failed = (
                db.query(FTL_SHIPMENT)
                .filter(
                    FTL_SHIPMENT.shipper_company_id == client_id,
                    FTL_SHIPMENT.origin_city_province == shipment.origin_city_province,
                    FTL_SHIPMENT.destination_city_province == shipment.destination_city_province,
                    FTL_SHIPMENT.shipment_status.in_(FAILED_STATUSES),
                )
                .count()
            )

            total = successful + failed

            success_rate = (
                round((successful / total) * 100, 2)
                if total > 0
                else 0
            )

            routes.append({
                "LSI": shipment.id,
                "trip_type": shipment.trip_type,
                "last_booked": shipment.created_at,
                "previous_bookings": previous_bookings,

                "origin": shipment.origin_city_province,
                "destination": shipment.destination_city_province,
                "distance": shipment.distance,

                "truck_type": shipment.required_truck_type,
                "equipment_type": shipment.equipment_type,

                "trailer_type": shipment.trailer_type,
                "trailer_length": shipment.trailer_length,

                "minimum_weight_bracket": shipment.minimum_weight_bracket,
                "commodity": shipment.commodity,

                "rate": shipment.quote,

                "success_rate": success_rate,

                "route_preview_embed": shipment.route_preview_embed,
            })

        return routes

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )