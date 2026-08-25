from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.brokerage.assigned_shipments import Assigned_Spot_Ftl_Shipments
from models.brokerage.finance import BrokerageLedger, Lane_Slot_Ledger, CarrierFinancialAccounts, FinancialAccounts, Interim_Invoice, Load_Invoice
from models.brokerage.loadboard import Ftl_Load_Board
from models.shipper import Corporation
from models.user import Director
from models.carrier import Carrier
from models.spot_bookings.dedicated_lane_ftl_shipment import Client_Lane
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT, FTL_Shipment_Docs, shipment_status_Update
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from models.spot_bookings.shipment_facility import ContactPerson, ShipmentFacility
from models.user import Driver
from models.vehicle import ShipperTrailer, Vehicle
from schemas.spot_bookings.dedicated_lanes_ftl_shipment import Ftl_Lanes_Summary_Response, Individual_FTL_Lane_Response, individual_shipment_or_lane_request, FTL_Lane_Dispute_Create
from schemas.spot_bookings.ftl_shipment import FTL_Shipment_Response, FTL_Shipments_Summary_Response, FTL_Shipment_Dispute_Create
from schemas.spot_bookings.power_shipment import POWER_SHIPMENT_RESPONSE, Power_Shipments_Summary_Response
from utils.auth import get_current_user
from utils.shipment_kpi_service import get_shipment_kpis
from utils.lane_kpi_service import get_lane_kpis
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
def enterprise_shipper_get_individual_ftl_shipment(
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

        shipment_docs = db.query(FTL_Shipment_Docs).filter(FTL_Shipment_Docs.shipment_id == shipment.id).first()

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

        try:
            statuses = (
                db.query(shipment_status_Update)
                .filter(
                    shipment_status_Update.shipment_id == shipment.id,
                    shipment_status_Update.type == shipment.type
                )
                .order_by(shipment_status_Update.created_at.asc())
                .all()
            )
        except SQLAlchemyError as e:
            db.rollback()
            statuses = []
            print("Failed to fetch statuses:", e)

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

            "shipment_documents": {
                "commercial_invoice": shipment_docs.commercial_invoice if shipment_docs else None,
                "packaging_list": shipment_docs.packaging_list if shipment_docs else None,
                "customs_declaration_form": shipment_docs.customs_declaration_form if shipment_docs else None,
                "import_or_export_permits": shipment_docs.import_or_export_permits if shipment_docs else None,
                "certificate_of_origin": shipment_docs.certificate_of_origin if shipment_docs else None,
                "da5501orsad500": shipment_docs.da5501orsad500 if shipment_docs else None,
                "proof_of_delivery": shipment.pod_document if shipment.pod_document else None,
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
                } if vehicle else None,

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
                } if driver else None,
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

            "financial": {
                "price": shipment.quote,
                "rate_per_kilometer": rate_per_km,
                "rate_per_ton": rate_per_ton,
                "distance": shipment.distance,
                "payment_terms": shipment.payment_terms,
                "invoice_status": shipment.invoice_status,
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
                "eta_date": shipment.eta_date,
                "eta_window": shipment.eta_window,
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
            } for status in statuses] if statuses else None,

            # 6.  ADD KPI BLOCK TO RESPONSE  ⬅️ NEW
            # ---------------------------------
            "kpis": kpis["kpis"] if kpis else None,  # ⬅️
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/enterprise/client-lane/{id}")
def client_get_individual_lane_id(
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
        lane = db.query(Client_Lane).filter(Client_Lane.id == id).first()
        if not lane:
            raise HTTPException(status_code=404, detail="Lane not found")

        facility = db.query(Corporation).filter(Corporation.id == lane.client_id).first()
        user = db.query(Director).filter(Director.id == lane.publisher_user_id).first()

        # Safe queries (will return [] instead of None if nothing found)
        invoices = db.query(Interim_Invoice).filter(
            Interim_Invoice.contract_id == lane.id,
            Interim_Invoice.contract_type == lane.type
        ).all() or []

        sub_shipments = db.query(FTL_SHIPMENT).filter(
            FTL_SHIPMENT.dedicated_lane_id == lane.id
        ).all() or []

        ledgers = db.query(Dedicated_Lane_BrokerageLedger).filter(
            Dedicated_Lane_BrokerageLedger.client_lane_id == lane.id,
        ).all() or []

        # Prepare carrier info list
        carrier_information_list = []

        for ledger in ledgers:
            carrier = db.query(Carrier).filter(Carrier.id == ledger.carrier_id).first()
            if not carrier:
                continue

            carrier_information_list.append({
                "ledger_id": ledger.id,
                "carrier_id": carrier.id,
                "is_verified": carrier.is_verified,
                "status": carrier.status,
                "carrier_name": carrier.legal_business_name,
                "country_of_incorporation": carrier.country_of_incorporation,
                "carrier_registration_number": carrier.business_registration_number,
                "carrier_address": carrier.business_address,
                "carrier_email": carrier.business_email,
                "carrier_phone_number": carrier.business_phone_number,
                "git_insurance_company": carrier.name_of_git_cover_insurance_company,
                "git_policy_number": carrier.git_insurance_policy_number,
                "git_cover_amount": carrier.git_cover_amount,
                "liability_insurance_company": carrier.name_of_liability_cover_insurance_company,
                "liability_policy_number": carrier.liability_insurance_policy_number,
                "carrier_liability_cover_amount": carrier.liability_insurance_cover_amount,
                "carrier_documents": {
                    "registration_certificate": carrier.business_registration_certificate,
                    "proof_of_address": carrier.proof_of_address,
                    "git_insurance_certificate": carrier.git_insurance_certificate,
                    "liability_insurance_certificate": carrier.liability_insurance_certificate,
                },
                # Custom ledger-specific info
                "number_of_assigned_slots": ledger.total_slots_assigned,
                "total_shipments_per_slot": ledger.shipments_per_slot,
                "rate_per_shipment": lane.booking_amount_per_shipment,
                "total_contract_rate": lane.contract_booking_amount,
            })

        # fetch lane KPIs
        lane_kpis = get_lane_kpis(db, lane.id)

        return {
            "lane_details": {
                "id": lane.id,
                "tender_id": lane.tender_id,
                "lane_status": lane.contract_status,
                "lane_title": lane.lane_title,
                "lane_length_categry": lane.lane_length_category,
                "lane_category": lane.lane_category,
                "scope_description": lane.scope_description,
                "business_unit": lane.business_unit,
                "cost_centre_project_code": lane.cost_centre_project_code,
                "parent_lane_id": lane.parent_lane_id,
                "lane_reference": lane.lane_reference,
                "contract_start_date": lane.contract_start_date,
                "contract_end_date": lane.contract_end_date,
                "actual_distance_km": lane.actual_distance_km,
                "polyline": lane.polyline,

                "load_requirements_and_cargo": {
                    "commodity": lane.commodity or "N/A",
                    "average_shipment_weight": lane.average_shipment_weight or 0,
                    "minimum_weight_bracket": lane.minimum_weight_bracket_kg,
                    "packaging_type": lane.packaging_type or "N/A",
                    "packaging_quantity": lane.packaging_quantity or 0,
                    "temperature_control": lane.temperature_control,
                    "target_temperature_spec": lane.target_temperature_spec,
                    "hazardous_materials": lane.hazardous_materials,
                    "hazchem_classification": lane.hazchem_classification,
                    "under_bond": lane.under_bond,
                    "rib_requirements": lane.rib_requirements,
                },
                "route": {
                    "origin_address": lane.origin_address,
                    "destination_address": lane.destination_address
                },

                "procurement_commercial_baseline": {
                    "pricing_basis": lane.pricing_basis,
                    "incumbent_transport_rate_per_shipment": lane.incumbent_transport_rate_per_shipment,
                    "incumbent_contract_rate": lane.incumbent_contract_rate,
                    "procurement_target_rate": lane.procurement_target_rate,
                    "procurement_target_contract_rate": lane.procurement_target_contract_rate,
                    "awarded_contract_rate": lane.awarded_contract_rate,
                    "vat_treatment": lane.vat_treatment,
                    "rate_validity": lane.rate_validity,
                },

                "payment_invoicing": {
                    "payment_terms": lane.payment_terms,
                    "invoice_submission_frequency": lane.invoice_submission_frequency,
                    "invoice_submission_deadline": lane.invoice_submission_deadline,
                },

                "rate_inclusion_guidelines": {
                    "rate_includes_fuel": lane.rate_includes_fuel,
                    "rate_includes_driver": lane.rate_includes_driver,
                    "rate_includes_maintenance": lane.rate_includes_maintenance,
                    "rate_includes_insurance": lane.rate_includes_insurance,
                    "rate_includes_tolls": lane.rate_includes_tolls,
                    "rate_includes_border_charges": lane.rate_includes_border_charges,
                    "rate_includes_empty_return": lane.rate_includes_empty_return,
                    "rate_includes_waiting_time": lane.rate_includes_waiting_time,
                    "rate_includes_loading_assistance": lane.rate_includes_loading_assistance,
                    "rate_includes_offloading_assistance": lane.rate_includes_offloading_assistance
                },
                "insurance_requirements": {
                    "minimum_git_cover_amount": lane.minimum_git_cover_amount,
                    "minimum_liability_cover_amount": lane.minimum_liability_cover_amount,
                    "git_all_risk_required": lane.git_all_risk_required,
                    "git_first_loss_required": lane.git_first_loss_required,
                    "git_driver_fidelity_required": lane.git_driver_fidelity_required,
                },
                "documentation_and_risk": {
                    "delivery_documentation_sla": lane.delivery_documentation_sla,
                    "claims_risk_policy": lane.claims_risk_policy,
                    "claims_risk_requirements": lane.claims_risk_requirements,
                },
                "operational_requirements": {
                    "vehicle_tracking_required": lane.vehicle_tracking_required,
                    "all_time_hour_control_room": lane.all_time_hour_control_room,
                    "driver_mobile_phone": lane.driver_mobile_phone,
                    "clean_compliant_equipment": lane.clean_compliant_equipment,
                    "pallet_management": lane.pallet_management,
                    "pod_submission_local": lane.pod_submission_local,
                    "pod_submission_long_haul": lane.pod_submission_long_haul,
                    "pod_submission_cross_border": lane.pod_submission_cross_border,
                    "subcontracting_policy": lane.subcontracting_policy
                },
                "equipment_compliance": {
                    "tarpaulin_compliance_required": lane.tarpaulin_compliance_required,
                    "corner_plates_required": lane.corner_plates_required,
                    "chock_blocks_required": lane.chock_blocks_required,
                    "ratchets_belts_required": lane.ratchets_belts_required,
                    "other_equipment_requirements": lane.other_equipment_requirements,
                },
            },
            "payment_schedule": [{
                "invoice_id": invoice.id,
                "issue_date": invoice.billing_date,
                "due_date": invoice.due_date,
                "status": invoice.status or "N/A",
                "amount": invoice.due_amount or 0,
            } for invoice in invoices],

            "carrier_information": carrier_information_list,
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
            "kpis": lane_kpis["kpis"] if lane_kpis else None,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))