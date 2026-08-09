from datetime import date
from typing import Optional, List
from models.shipper import Corporation
from models.brokerage.finance import FinancialAccounts
from models.user import Director
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT, FTL_Shipment_Docs
from models.spot_bookings.shipment_facility import ContactPerson, ShipmentFacility
from enums import Axle_Configuration, EquipmentType, Lorry, Recurrence_Days, Recurrence_Frequency, TrailerLength, TrailerType, TruckType
from schemas.spot_bookings.route_booking import Admin_Bulk_Create_Route
from schemas.spot_bookings.dedicated_lanes_ftl_shipment import FTL_Lane_Create,  SpotFTLLaneQuoteRequest
from schemas.spot_bookings.ftl_shipment import FTL_Shipment_Booking, Admin_Client_FTL_Shipment_Booking, FTL_Shipment_docs_create
from schemas.shipment_facility import ShipmentFacilityCreate, FacilityContactCreate
from schemas.spot_bookings.power_shipment import POWER_Shipment_docs_create, Power_Shipment_Booking
from services.finance.finance import calculate_spot_ftl_lane_quote, calculate_spot_ftl_quote, calculate_spot_power_quote
from services.spot_bookings.dedicated_lanes_ftl_shipment import create_dedicated_lane_ftl_shipment
from services.spot_bookings.ftl_shipment import create_ftl_shipment, admin_create_client_ftl_shipment
from services.spot_bookings.route_booking import admin_bulk_create_client_ftl_shipment
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
import traceback



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

        # ============================================================
        # 1. GET SHIPMENT
        # ============================================================

        shipment = (
            db.query(FTL_SHIPMENT)
            .filter(FTL_SHIPMENT.id == id)
            .first()
        )

        if not shipment:
            raise HTTPException(
                status_code=404,
                detail=f"Shipment {id} not found"
            )

        # ============================================================
        # 2. GET SHIPMENT DOCUMENTS
        # ============================================================

        shipment_docs = (
            db.query(FTL_Shipment_Docs)
            .filter(
                FTL_Shipment_Docs.shipment_id == shipment.id
            )
            .first()
        )

        # ============================================================
        # 3. GET PICKUP FACILITY + CONTACT
        # ============================================================

        pickup_facility = (
            db.query(ShipmentFacility)
            .filter(
                ShipmentFacility.id == shipment.pickup_facility_id
            )
            .first()
        )

        pickup_contact = (
            db.query(ContactPerson)
            .filter(
                ContactPerson.id == pickup_facility.contact_person
            )
            .first()
            if pickup_facility
            and pickup_facility.contact_person
            else None
        )

        # ============================================================
        # 4. GET DELIVERY FACILITY + CONTACT
        # ============================================================

        delivery_facility = (
            db.query(ShipmentFacility)
            .filter(
                ShipmentFacility.id == shipment.delivery_facility_id
            )
            .first()
        )

        delivery_contact = (
            db.query(ContactPerson)
            .filter(
                ContactPerson.id == delivery_facility.contact_person
            )
            .first()
            if delivery_facility
            and delivery_facility.contact_person
            else None
        )

        # ============================================================
        # 5. BUILD DYNAMIC STOP ADDRESSES
        # ============================================================
        #
        # IMPORTANT:
        #
        # This array contains ONLY addresses.
        #
        # No facility information.
        # No contact information.
        # No facility IDs.
        #
        # Example:
        #
        # "stops": [
        #     {
        #         "stop_number": 1,
        #         "address": "Lusikisiki, 4820, South Africa"
        #     },
        #     {
        #         "stop_number": 2,
        #         "address": "Mthatha, South Africa"
        #     }
        # ]
        #
        # ============================================================

        stop_addresses = []

        for stop_number in range(1, 6):

            stop_address = getattr(
                shipment,
                f"stop_{stop_number}_address",
                None
            )

            if stop_address:
                stop_addresses.append({
                    "stop_number": stop_number,
                    "address": stop_address
                })

        # ============================================================
        # 6. BUILD DYNAMIC STOP FACILITIES + CONTACTS
        # ============================================================
        #
        # Facility/contact information is kept completely separate
        # from shipment_details.stops.
        #
        # ============================================================

        stop_facilities = []

        for stop_number in range(1, 6):

            # --------------------------------------------------------
            # Get stop address
            # --------------------------------------------------------

            stop_address = getattr(
                shipment,
                f"stop_{stop_number}_address",
                None
            )

            # --------------------------------------------------------
            # Get stop facility ID
            # --------------------------------------------------------

            stop_facility_id = getattr(
                shipment,
                f"stop_{stop_number}_facility_id",
                None
            )

            # --------------------------------------------------------
            # If there is no stop at all, skip it
            # --------------------------------------------------------

            if not stop_address and not stop_facility_id:
                continue

            stop_facility = None
            stop_contact = None

            # ========================================================
            # QUERY FACILITY
            # ========================================================

            if stop_facility_id:

                stop_facility = (
                    db.query(ShipmentFacility)
                    .filter(
                        ShipmentFacility.id == stop_facility_id
                    )
                    .first()
                )

            # ========================================================
            # QUERY CONTACT PERSON
            # ========================================================

            if (
                stop_facility
                and stop_facility.contact_person
            ):

                stop_contact = (
                    db.query(ContactPerson)
                    .filter(
                        ContactPerson.id
                        == stop_facility.contact_person
                    )
                    .first()
                )

            # ========================================================
            # BUILD STOP FACILITY OBJECT
            # ========================================================

            stop_facilities.append({

                "stop_number": stop_number,

                "address": stop_address,

                "facility": {

                    "facility_id": (
                        stop_facility.id
                        if stop_facility
                        else stop_facility_id
                    ),

                    "facility_name": (
                        stop_facility.name
                        if stop_facility
                        else None
                    ),

                    "start_time": (
                        str(stop_facility.start_time)
                        if (
                            stop_facility
                            and stop_facility.start_time
                        )
                        else None
                    ),

                    "end_time": (
                        str(stop_facility.end_time)
                        if (
                            stop_facility
                            and stop_facility.end_time
                        )
                        else None
                    ),

                    "scheduling_type": (
                        stop_facility.scheduling_type
                        if stop_facility
                        else None
                    ),

                    "notes": (
                        stop_facility.facility_notes
                        if stop_facility
                        else None
                    ),
                },

                "contact": {

                    "first_name": (
                        stop_contact.first_name
                        if stop_contact
                        else None
                    ),

                    "last_name": (
                        stop_contact.last_name
                        if stop_contact
                        else None
                    ),

                    "contact_phone": (
                        stop_contact.phone_number
                        if stop_contact
                        else None
                    ),

                    "email": (
                        stop_contact.email
                        if stop_contact
                        else None
                    ),
                }
            })

        # ============================================================
        # 7. RETURN RESPONSE
        # ============================================================

        return {

            # ========================================================
            # SHIPMENT DETAILS
            # ========================================================

            "shipment_details": {

                "id": shipment.id,

                "trip_type": shipment.trip_type,

                "required_truck_type": (
                    shipment.required_truck_type
                ),

                "required_equipment_type": (
                    shipment.equipment_type
                ),

                "required_trailer_type": (
                    shipment.trailer_type
                ),

                "required_trailer_length": (
                    shipment.trailer_length
                ),

                "minimum_weight_bracket": (
                    shipment.minimum_weight_bracket
                ),

                # ----------------------------------------------------
                # ORIGIN
                # ----------------------------------------------------

                "origin_address": (
                    shipment.complete_origin_address
                ),

                # ----------------------------------------------------
                # STOPS
                #
                # ONLY ADDRESSES ARE RETURNED HERE
                # ----------------------------------------------------

                "stops": stop_addresses,

                # ----------------------------------------------------
                # DESTINATION
                # ----------------------------------------------------

                "destination_address": (
                    shipment.complete_destination_address
                ),

                "pickup_date": shipment.pickup_date,

                "priority_level": shipment.priority_level,

                "customer_reference_number": (
                    shipment.customer_reference_number
                ),

                "shipment_weight": shipment.shipment_weight,

                "commodity": shipment.commodity,

                "temperature_control": (
                    shipment.temperature_control
                ),

                "hazardous_materials": (
                    shipment.hazardous_materials
                ),

                "minimum_git_cover_amount": (
                    shipment.minimum_git_cover_amount
                ),

                "minimum_liability_cover_amount": (
                    shipment.minimum_liability_cover_amount
                ),

                "packaging_quantity": (
                    shipment.packaging_quantity
                ),

                "packaging_type": (
                    shipment.packaging_type
                ),

                "pickup_number": shipment.pickup_number,

                "delivery_number": shipment.delivery_number,

                "pickup_notes": shipment.pickup_notes,

                "delivery_notes": shipment.delivery_notes,

                "distance": shipment.distance,
            },

            # ========================================================
            # SHIPMENT DOCUMENTS
            # ========================================================

            "shipment_documents": {

                "commercial_invoice": (
                    shipment_docs.commercial_invoice
                    if shipment_docs
                    else None
                ),

                "packaging_list": (
                    shipment_docs.packaging_list
                    if shipment_docs
                    else None
                ),

                "customs_declaration_form": (
                    shipment_docs.customs_declaration_form
                    if shipment_docs
                    else None
                ),

                "import_or_export_permits": (
                    shipment_docs.import_or_export_permits
                    if shipment_docs
                    else None
                ),

                "certificate_of_origin": (
                    shipment_docs.certificate_of_origin
                    if shipment_docs
                    else None
                ),

                "da5501orsad500": (
                    shipment_docs.da5501orsad500
                    if shipment_docs
                    else None
                ),

                "proof_of_delivery": (
                    shipment.pod_document
                    if shipment.pod_document
                    else None
                ),
            },

            # ========================================================
            # PICKUP FACILITY
            # ========================================================

            "pickup_facility": {

                "facility_id": (
                    pickup_facility.id
                    if pickup_facility
                    else None
                ),

                "facility_name": (
                    pickup_facility.name
                    if pickup_facility
                    else None
                ),

                "start_time": (
                    str(pickup_facility.start_time)
                    if (
                        pickup_facility
                        and pickup_facility.start_time
                    )
                    else None
                ),

                "end_time": (
                    str(pickup_facility.end_time)
                    if (
                        pickup_facility
                        and pickup_facility.end_time
                    )
                    else None
                ),

                "scheduling_type": (
                    pickup_facility.scheduling_type
                    if pickup_facility
                    else None
                ),

                "notes": (
                    pickup_facility.facility_notes
                    if pickup_facility
                    else None
                ),
            } if pickup_facility else None,

            # ========================================================
            # PICKUP CONTACT
            # ========================================================

            "pickup_contact": {

                "first_name": (
                    pickup_contact.first_name
                    if pickup_contact
                    else None
                ),

                "last_name": (
                    pickup_contact.last_name
                    if pickup_contact
                    else None
                ),

                "contact_phone": (
                    pickup_contact.phone_number
                    if pickup_contact
                    else None
                ),

                "email": (
                    pickup_contact.email
                    if pickup_contact
                    else None
                ),
            } if pickup_contact else None,

            # ========================================================
            # DYNAMIC STOP FACILITIES + CONTACTS
            # ========================================================

            "stop_facilities": stop_facilities,

            # ========================================================
            # DELIVERY FACILITY
            # ========================================================

            "delivery_facility": {

                "facility_id": (
                    delivery_facility.id
                    if delivery_facility
                    else None
                ),

                "facility_name": (
                    delivery_facility.name
                    if delivery_facility
                    else None
                ),

                "start_time": (
                    str(delivery_facility.start_time)
                    if (
                        delivery_facility
                        and delivery_facility.start_time
                    )
                    else None
                ),

                "end_time": (
                    str(delivery_facility.end_time)
                    if (
                        delivery_facility
                        and delivery_facility.end_time
                    )
                    else None
                ),

                "scheduling_type": (
                    delivery_facility.scheduling_type
                    if delivery_facility
                    else None
                ),

                "notes": (
                    delivery_facility.facility_notes
                    if delivery_facility
                    else None
                ),
            } if delivery_facility else None,

            # ========================================================
            # DELIVERY CONTACT
            # ========================================================

            "delivery_contact": {

                "first_name": (
                    delivery_contact.first_name
                    if delivery_contact
                    else None
                ),

                "last_name": (
                    delivery_contact.last_name
                    if delivery_contact
                    else None
                ),

                "contact_phone": (
                    delivery_contact.phone_number
                    if delivery_contact
                    else None
                ),

                "email": (
                    delivery_contact.email
                    if delivery_contact
                    else None
                ),
            } if delivery_contact else None,
        }

    except HTTPException:
        raise

    except Exception as e:

        print("============================================================")
        print("ERROR IN admin_fetch_client_users")
        print("============================================================")
        print(f"Shipment ID: {id}")
        print(f"Error: {str(e)}")
        print("============================================================")

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

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
    stop_facilities_data: Optional[List[ShipmentFacilityCreate]] = None,
    stop_contacts_data: Optional[List[FacilityContactCreate]] = None,
    shipment_documents_data: FTL_Shipment_docs_create = None,
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
            stop_facilities_data,
            stop_contacts_data,
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

@router.post("/admin/client-bulk-route-booking")
def admin_client_bulk_route_bookin(
    route_data: Admin_Bulk_Create_Route,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        return admin_bulk_create_client_ftl_shipment(
            db=db,
            route_data=route_data,
            current_user=current_user
        )

    except HTTPException as e:
        print("=================================")
        print("HTTPException")
        print("Status:", e.status_code)
        print("Detail:", e.detail)
        print("=================================")
        raise

    except Exception as e:
        print("=================================")
        print("UNHANDLED EXCEPTION")
        traceback.print_exc()
        print("=================================")
        raise

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

