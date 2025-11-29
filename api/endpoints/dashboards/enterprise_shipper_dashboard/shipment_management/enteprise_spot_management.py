from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.brokerage.assigned_shipments import Assigned_Spot_Ftl_Shipments
from models.brokerage.finance import BrokerageLedger, CarrierFinancialAccounts, FinancialAccounts, Interim_Invoice, Load_Invoice
from models.brokerage.loadboard import Ftl_Load_Board
from models.carrier import Carrier
from models.spot_bookings.dedicated_lane_ftl_shipment import FTL_Lane
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT, shipment_status_Update
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from models.spot_bookings.shipment_facility import ContactPerson, ShipmentFacility
from models.user import Driver
from models.vehicle import ShipperTrailer, Vehicle
from schemas.spot_bookings.dedicated_lanes_ftl_shipment import Ftl_Lanes_Summary_Response, Individual_FTL_Lane_Response, individual_shipment_or_lane_request, FTL_Lane_Dispute_Create
from schemas.spot_bookings.ftl_shipment import FTL_Shipment_Response, FTL_Shipments_Summary_Response, FTL_Shipment_Dispute_Create
from schemas.spot_bookings.power_shipment import POWER_SHIPMENT_RESPONSE, Power_Shipments_Summary_Response
from utils.auth import get_current_user
from utils.shipment_kpi_service import get_shipment_kpis
from services.cancellations.spot_cancellations import cancel_spot_ftl_shipment
from services.brokerage.disputes import shipper_dispute_ftl_shipment, shipper_dispute_ftl_lane
from enums import ShipperShipmentStatus

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/enterprise/ftl-shipment/{id}")
def shipper_get_individual_ftl_shipment(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):

    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")

    try:
        # ---------------------------------
        # 1. FETCH SHIPMENT
        # ---------------------------------
        shipment = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.id == id).first()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")

        # ---------------------------------
        # 2. FETCH RELATED OBJECTS
        # ---------------------------------
        facility = db.query(Corporation).filter(Corporation.id == shipment.shipper_company_id).first()
        user = db.query(Director).filter(Director.id == shipment.shipper_user_id).first()

        carrier = db.query(Carrier).filter(Carrier.id == shipment.carrier_id).first()
        vehicle = db.query(Vehicle).filter(Vehicle.id == shipment.vehicle_id).first()
        driver = db.query(Driver).filter(Driver.id == shipment.driver_id).first()

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

        statuses = db.query(shipment_status_Update.shipment_id == shipment.id,
                            shipment_status_Update.type == shipment.type).all()

        # ---------------------------------
        # 3. SAFE CALCULATIONS
        # ---------------------------------
        rate_per_km = (shipment.quote / shipment.distance) if shipment.distance else None
        rate_per_ton = (
            shipment.quote / shipment.minimum_weight_bracket
            if shipment.minimum_weight_bracket else None
        )

        # ---------------------------------
        # 4. GET SHIPMENT KPI DATA  ⬅️ NEW
        # ---------------------------------
        kpis = get_shipment_kpis(db, shipment.id)   # ⬅️

        # ---------------------------------
        # 4. BUILD RESPONSE
        # ---------------------------------
        return {
            "shipment_details": {
                "id": shipment.id,
                "invoice_id": shipment.invoice_id,
                "status": shipment.shipment_status,
                "trip_status": shipment.trip_status,
                "is_sub_shipment": shipment.is_subshipment,
                "lane_id": shipment.dedicated_lane_id,
                "shipment_type": shipment.type,
                "trip_type": shipment.trip_type,
                "load_type": shipment.load_type,
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
                "estimated_transit_time": shipment.estimated_transit_time,
                "route_preview_embed": shipment.route_preview_embed,
            },

            "carrier_information": {
                "id": carrier.id if carrier else None,
                "is_verified": carrier.is_verified if carrier else None,
                "status": carrier.status if carrier else None,
                "carrier_name": carrier.legal_business_name if carrier else None,
                "country_of_incorporation": carrier.country_of_incorporation if carrier else None,
                "carrier_registration_number": carrier.business_registration_number if carrier else None,
                "carrier_address": carrier.business_address if carrier else None,
                "carrier_email": carrier.business_email if carrier else None,
                "carrier_phone_number": carrier.business_phone_number if carrier else None,
                "git_insurance_company": carrier.name_of_git_cover_insurance_company if carrier else None,
                "git_policy_number": carrier.git_insurance_policy_number if carrier else None,
                "git_cover_amount": carrier.git_cover_amount if carrier else None,
                "liability_insurance_company": carrier.name_of_liability_cover_insurance_company if carrier else None,
                "liability_policy_number": carrier.liability_insurance_policy_number if carrier else None,
                "carrier_liability_cover_amount": carrier.liability_insurance_cover_amount if carrier else None,

                "carrier_documents": {
                    "registration_certificate": carrier.business_registration_certificate if carrier else None,
                    "proof_of_address": carrier.proof_of_address if carrier else None,
                    "git_insurance_certificate": carrier.git_insurance_certificate if carrier else None,
                    "liability_insurance_certificate": carrier.liability_insurance_certificate if carrier else None,
                },

                "assigned_vehicle": {
                    "id": vehicle.id if vehicle else None,
                    "is_verified": vehicle.is_verified if vehicle else None,
                    "status": vehicle.status if vehicle else None,
                    "make": vehicle.make if vehicle else None,
                    "model": vehicle.model if vehicle else None,
                    "year": vehicle.year if vehicle else None,
                    "color": vehicle.color if vehicle else None,
                    "axle_configuration": vehicle.axle_configuration if vehicle else None,
                    "license_plate": vehicle.license_plate if vehicle else None,
                    "license_expiry_date": vehicle.license_expiry_date if vehicle else None,
                    "vin": vehicle.vin if vehicle else None,
                    "vehicle_type": vehicle.type if vehicle else None,
                    "equipment_type": vehicle.equipment_type if vehicle else None,
                    "trailer_type": vehicle.trailer_type if vehicle else None,
                    "trailer_length": vehicle.trailer_length if vehicle else None,
                    "tare_weight": vehicle.tare_weight if vehicle else None,
                    "gvm_weight": vehicle.gvm_weight if vehicle else None,
                    "payload_capacity": vehicle.payload_capacity if vehicle else None,

                    "vehicle_documentation": {
                        "registration_or_leasing_certificate": vehicle.vrc_or_leasing if vehicle else None,
                        "license_disk": vehicle.vehicle_license_disk if vehicle else None,
                        "vehicle_roadworthy_certificate": vehicle.vehicle_road_worthy_certificate if vehicle else None,
                        "vehicle_tracking_certificate": vehicle.vehicle_tracking_certificate if vehicle else None,
                    },
                },

                "assigned_driver": {
                    "id": driver.id if driver else None,
                    "is_verified": driver.is_verified if driver else None,
                    "status": driver.status if driver else None,
                    "first_name": driver.first_name if driver else None,
                    "last_name": driver.last_name if driver else None,
                    "nationality": driver.nationality if driver else None,
                    "id_number": driver.id_number if driver else None,
                    "passport_number": driver.passport_number if driver else None,
                    "license_number": driver.license_number if driver else None,
                    "license_expiry_date": driver.license_expiry_date if driver else None,
                    "prdp_number": driver.prdp_number if driver else None,
                    "prdp_expiry_date": driver.prdp_expiry_date if driver else None,
                    "email": driver.email if driver else None,
                    "phone_number": driver.phone_number if driver else None,

                    "driver_documents": {
                        "id_document": driver.id_document if driver else None,
                        "passport_document": driver.passport_document if driver else None,
                        "license_document": driver.license_document if driver and driver.license_document else None,
                        "prdp_document": driver.prdp_document if driver and driver.prdp_document else None,
                    },
                },
            },

            "facility": {
                "facility_information": {
                    "id": facility.id,
                    "type": facility.type,
                    "facility_name": facility.legal_business_name,
                    "country": facility.country_of_incorporation,
                    "address": facility.business_address,
                    "email": facility.business_email,
                    "phone_number": facility.business_phone_number,
                    "is_verified": facility.is_verified,
                    "status": facility.status
                },
                "booked_by": {
                    "id": user.id,
                    "is_verified": user.is_verified,
                    "status": user.status,
                    "role": user.role,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "id_number": user.id_number,
                    "email": user.email,
                    "phone_number": user.phone_number,
                },
            },

            "financial": {
                "price": shipment.quote,
                "rate_per_kilometer": rate_per_km,
                "rate_per_ton": rate_per_ton,
                "distance": shipment.distance,
                "payment_terms": shipment.payment_terms,
                "invoice_due_date": shipment.invoice_due_date,
            },

            "pickup_facility": {
                "facility_name": pickup_facility.name,
                "address": pickup_facility.address,
                "time_window": f"{pickup_facility.start_time} - {pickup_facility.end_time}",
                "scheduling_type": pickup_facility.scheduling_type,
                "contact_name": f"{pickup_contact.first_name} {pickup_contact.last_name}" if pickup_contact else None,
                "email": pickup_contact.email if pickup_contact else None,
                "contact_phone": pickup_contact.phone_number if pickup_contact else None,
                "notes": pickup_facility.facility_notes,
            } if pickup_facility else None,

            "delivery_facility": {
                "facility_name": delivery_facility.name,
                "address": delivery_facility.address,
                "time_window": f"{delivery_facility.start_time} - {delivery_facility.end_time}",
                "scheduling_type": delivery_facility.scheduling_type,
                "contact_name": f"{delivery_contact.first_name} {delivery_contact.last_name}" if delivery_contact else None,
                "email": delivery_contact.email if delivery_contact else None,
                "contact_phone": delivery_contact.phone_number if delivery_contact else None,
                "notes": delivery_facility.facility_notes,
            } if delivery_facility else None,

            "status_tracking": [{
                "status": status.status,
                "trip_status": status.trip_status,
                "location_description": status.location_description,
                "created_at": status.created_at,
            } for status in statuses],

            # 6.  ADD KPI BLOCK TO RESPONSE  ⬅️ NEW
            # ---------------------------------
            "kpis": kpis["kpis"] if kpis else None,  # ⬅️
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/enterprise/ftl-lane/{id}")
def enterprise_shipper_get_individual_ftl_lane_id(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        # Fetch lane
        lane = db.query(FTL_Lane).filter(FTL_Lane.id == id).first()
        if not lane:
            raise HTTPException(status_code=404, detail="Lane not found")

        facility = db.query(Corporation).filter(Corporation.id == lane.shipper_company_id).first()
        user = db.query(Director).filter(Director.id == lane.shipper_user_id).first()

        # Safe queries (will return [] instead of None if nothing found)
        invoices = db.query(Interim_Invoice).filter(
            Interim_Invoice.contract_id == lane.id,
            Interim_Invoice.contract_type == lane.type
        ).all() or []

        sub_shipments = db.query(FTL_SHIPMENT).filter(
            FTL_SHIPMENT.dedicated_lane_id == lane.id
        ).all() or []

        carrier = db.query(Carrier).filter(Carrier.id == lane.carrier_id).first()

        pickup_facility = db.query(ShipmentFacility).filter_by(id=lane.pickup_facility_id).first()
        delivery_facility = db.query(ShipmentFacility).filter_by(id=lane.delivery_facility_id).first()

        pickup_contact = db.query(ContactPerson).filter_by(
            id=pickup_facility.contact_person
        ).first() if pickup_facility and pickup_facility.contact_person else None

        delivery_contact = db.query(ContactPerson).filter_by(
            id=delivery_facility.contact_person
        ).first() if delivery_facility and delivery_facility.contact_person else None

        return {
            "shipment_details": {
                "id": lane.id,
                "status": lane.status or "N/A",
                "type": lane.type or "N/A",
                "trip_type": lane.trip_type or "N/A",
                "load_type": lane.load_type or "N/A",
                "required_truck_type": lane.required_truck_type or "N/A",
                "equipment_type": lane.equipment_type or "N/A",
                "trailer_type": lane.trailer_type or "N/A",
                "trailer_length": lane.trailer_length or "N/A",
                "minimum_weight_bracket": lane.minimum_weight_bracket or "N/A",
                "priority_level": lane.priority_level or "N/A",
                "average_shipment_weight": lane.average_shipment_weight or 0,
                "commodity": lane.commodity or "N/A",
                "temperature_control": lane.temperature_control or False,
                "hazardous_materials": lane.hazardous_materials or False,
                "minimum_git_cover_amount": lane.minimum_git_cover_amount or 0,
                "minimum_liability_cover_amount": lane.minimum_liability_cover_amount or 0,
                "customer_referece_number": lane.customer_reference_number or "N/A",
                "packaging_type": lane.packaging_type or "N/A",
                "packaging_quantity": lane.packaging_quantity or 0,
                "pickup_number": lane.pickup_number or "N/A",
                "delivery_number": lane.delivery_number or "N/A",
                "distance": lane.distance or 0,
                "estimated_transit_time": lane.estimated_transit_time or "N/A",
                "origin_address": lane.complete_origin_address or "N/A",
                "destination_address": lane.complete_destination_address or "N/A",
                "pickup_notes": lane.pickup_notes or "N/A",
                "delivery_notes": lane.delivery_notes or "N/A",
                "start_date": lane.start_date,
                "end_date": lane.end_date,
                "route_preview_embed": lane.route_preview_embed or None,
            },

            "contract_information": {
                "recurrence_frequency": lane.recurrence_frequency or "N/A",
                "recurrence_days": lane.recurrence_days or [],
                "skip_weekends": lane.skip_weekends or False,
                "shipments_per_interval": lane.shipments_per_interval or 0,
                "total_shipments": lane.total_shipments or 0,
                "per_shipment_rate": lane.qoute_per_shipment or 0,
                "contract_rate": lane.contract_quote or 0,
                "payment_terms": lane.payment_terms or "N/A",
            },

            "payment_schedule": [{
                "invoice_id": invoice.id,
                "issue_date": invoice.billing_date,
                "due_date": invoice.due_date,
                "status": invoice.status or "N/A",
                "amount": invoice.due_amount or 0,
            } for invoice in invoices],

            "shipment_schedule": [{
                "id": sub_shipment.id,
                "origin": sub_shipment.origin_city_province or "N/A",
                "destination": sub_shipment.destination_city_province or "N/A",
                "pickup_date": sub_shipment.pickup_date,
                "status": sub_shipment.shipment_status or "N/A",
                "rate": sub_shipment.quote or 0,
                "invoice_status": sub_shipment.invoice_status or "N/A",
            } for sub_shipment in sub_shipments],

            "pickup_facility": {
                "facility_name": pickup_facility.name if pickup_facility else None,
                "address": pickup_facility.address if pickup_facility else None,
                "time_window": f"{pickup_facility.start_time} - {pickup_facility.end_time}" if pickup_facility else None,
                "scheduling_type": pickup_facility.scheduling_type if pickup_facility else None,
                "contact_name": f"{pickup_contact.first_name} {pickup_contact.last_name}" if pickup_contact else None,
                "email": pickup_contact.email if pickup_contact else None,
                "contact_phone": pickup_contact.phone_number if pickup_contact else None,
                "notes": pickup_facility.facility_notes if pickup_facility else None,
            } if pickup_facility else None,

            "delivery_facility": {
                "facility_name": delivery_facility.name if delivery_facility else None,
                "address": delivery_facility.address if delivery_facility else None,
                "time_window": f"{delivery_facility.start_time} - {delivery_facility.end_time}" if delivery_facility else None,
                "scheduling_type": delivery_facility.scheduling_type if delivery_facility else None,
                "contact_name": f"{delivery_contact.first_name} {delivery_contact.last_name}" if delivery_contact else None,
                "email": delivery_contact.email if delivery_contact else None,
                "contact_phone": delivery_contact.phone_number if delivery_contact else None,
                "notes": delivery_facility.facility_notes if delivery_facility else None,
            } if delivery_facility else None,

            "carrier_information": {
                "id": carrier.id if carrier else None,
                "is_verified": carrier.is_verified if carrier else None,
                "status": carrier.status if carrier else None,
                "carrier_name": carrier.legal_business_name if carrier else None,
                "country_of_incorporation": carrier.country_of_incorporation if carrier else None,
                "carrier_registration_number": carrier.business_registration_number if carrier else None,
                "carrier_address": carrier.business_address if carrier else None,
                "carrier_email": carrier.business_email if carrier else None,
                "carrier_phone_number": carrier.business_phone_number if carrier else None,
                "git_insurance_company": carrier.name_of_git_cover_insurance_company if carrier else None,
                "git_policy_number": carrier.git_insurance_policy_number if carrier else None,
                "git_cover_amount": carrier.git_cover_amount if carrier else None,
                "liability_insurance_company": carrier.name_of_liability_cover_insurance_company if carrier else None,
                "liability_policy_number": carrier.liability_insurance_policy_number if carrier else None,
                "carrier_liability_cover_amount": carrier.liability_insurance_cover_amount if carrier else None,
                "carrier_documents": {
                    "registration_certificate": carrier.business_registration_certificate if carrier else None,
                    "proof_of_address": carrier.proof_of_address if carrier else None,
                    "git_insurance_certificate": carrier.git_insurance_certificate if carrier else None,
                    "liability_insurance_certificate": carrier.liability_insurance_certificate if carrier else None,
                },
            } if carrier else None,
            "facility": {
                "facility_information": {
                    "id": facility.id,
                    "type": facility.type,
                    "facility_name": facility.legal_business_name,
                    "country": facility.country_of_incorporation,
                    "address": facility.business_address,
                    "email": facility.business_email,
                    "phone_number": facility.business_phone_number,
                    "is_verified": facility.is_verified,
                    "status": facility.status
                },
                "booked_by": {
                    "id": user.id,
                    "is_verified": user.is_verified,
                    "status": user.status,
                    "role": user.role,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "id_number": user.id_number,
                    "email": user.email,
                    "phone_number": user.phone_number,
                },
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))