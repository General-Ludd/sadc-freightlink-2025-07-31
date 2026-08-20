from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.Exchange.auction import Exchange_FTL_Lane_Bid, Exchange_FTL_Shipment_Bid, Exchange_POWER_Shipment_Bid, Lane_Tender_RFQ_Bids
from models.Exchange.dedicated_ftl_lane import FTL_Lane_Exchange, Lane_Tender_RFQ, Lane_Tender_RFQ_Stop, Lane_Tender_RFQ_Vehicle_Config, Lane_Tender_RFQ_Volume_Profile, Lane_Tender_RFQ_Accessorial
from models.shipper import Corporation
from models.user import Director
from models.Exchange.ftl_shipment import FTL_SHIPMENT_EXCHANGE
from models.Exchange.power_shipment import POWER_SHIPMENT_EXCHANGE
from models.brokerage.loadboards.exchange_loadboards import Exchange_Ftl_Load_Board, Exchange_Power_Load_Board
from models.spot_bookings.shipment_facility import ContactPerson, ShipmentFacility
from models.vehicle import ShipperTrailer
from schemas.exchange_bookings.auction import Accept_Bid, Exchange_FTL_Lane_ShipperSide_BidResponse, Exchange_Id, FTL_Exchange_ShipperSide_BidResponse, POWER_Exchange_ShipperSide_BidResponse
from schemas.exchange_bookings.dedicated_ftl_lane import Exchange_Ftl_Lane_Response, Exchange_Ftl_Lane_Summary_Response
from schemas.exchange_bookings.ftl_shipment import Exchange_FTL_Shipment_Response, Exchange_Ftl_Shipments_Summary_Response
from schemas.exchange_bookings.power_shipment import Exchange_Power_Shipments_Summary_Response, exchange_power_shipment_response
from services.exchange.auction import accept_slot_based_ftl_lane_exchange_bid, accept_ftl_shipment_exchange_bid, accept_power_shipment_exchange_bid
from services.cancellations.exchange_cancellations import cancel_exchange_ftl_booking, cancel_exchange_power_booking, cancel_exchange_ftl_lane_booking
from utils.auth import get_current_user

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/tender/{id}")
def get_tender_information(
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
        print("STEP 1 - querying tender")

        tender = db.query(Lane_Tender_RFQ).filter(
            Lane_Tender_RFQ.id == id
        ).first()

        print("STEP 1 SUCCESS")


        print("STEP 2 - querying stops")

        tender_stops = db.query(
            Lane_Tender_RFQ_Stop
        ).filter(
            Lane_Tender_RFQ_Stop.tender_id == id
        ).all()

        print("STEP 2 SUCCESS")


        print("STEP 3 - querying vehicle configs")

        tender_vehicle_configs = db.query(
            Lane_Tender_RFQ_Vehicle_Config
        ).filter(
            Lane_Tender_RFQ_Vehicle_Config.tender_id == id
        ).all()

        print("STEP 3 SUCCESS")


        print("STEP 4 - querying volume profiles")

        tender_volumes_profiles = db.query(
            Lane_Tender_RFQ_Volume_Profile
        ).filter(
            Lane_Tender_RFQ_Volume_Profile.tender_id == id
        ).all()

        print("STEP 4 SUCCESS")


        print("STEP 5 - querying accessorials")

        tender_accessorials = db.query(
            Lane_Tender_RFQ_Accessorial
        ).filter(
            Lane_Tender_RFQ_Accessorial.tender_id == id
        ).all()

        print("STEP 5 SUCCESS")


        print("STEP 6 - querying bids")

        bids = db.query(
            Lane_Tender_RFQ_Bids
        ).filter(
            Lane_Tender_RFQ_Bids.tender_id == id
        ).all()

        print("STEP 6 SUCCESS")
        return {
            "tender_scope_routing_information": {
                "id": tender.id,
                "title": tender.tender_title,
                "scope_description": tender.scope_description,
                "business_unit": tender.business_unit,
                "cost_centre": tender.cost_centre_project_code,
                "tender_length": tender.tender_length_category,
                "tender_category": tender.tender_category,
                "origin_address": tender.origin_address,
                "stop_addresses": [stop.address for stop in tender_stops],
                "destination_address": tender.destination_address,
                "route_polyline": tender.polyline,
                "border_customs_responsibility": tender.border_customs_responsibility,
                "distance": tender.actual_distance_km,
                "priority_level": tender.priority_level,
                "contract_start_date": tender.contract_start_date,
                "contract_end_date": tender.contract_end_date,
                "customer_reference": tender.customer_reference,
            },
            "load_requirements_and_vehicle_configurations": {
                "allowed_vehicle_configurations": [{
                    "configuration_type": config.configuration_type,
                    "truck_type": config.required_truck_type,
                    "equipment_type": config.equipment_type,
                    "trailer_type": config.trailer_type or "--------",
                    "trailer_length": config.trailer_length or "--------",
                } for config in tender_vehicle_configs],

                "commodity": tender.commodity,
                "avg_shipment_weight": tender.average_shipment_weight_kg,
                "minimum_weight_bracket": tender.minimum_weight_bracket_kg,
                "packaging_type": tender.packaging_type,
                "packaging_quantity": tender.packaging_quantity,
                "temperature_control": tender.temperature_control,
                "hazardous_materials": tender.hazardous_materials,
                "under_bond": tender.under_bond,
                "rib_requirements": tender.rib_requirements,
                "minimum_git_cover": tender.minimum_git_cover_amount,
                "minimum_liability_cover_amount": tender.minimum_liability_cover_amount,
                "insurance_requirements": {
                    "minimum_git_cover": tender.minimum_git_cover_amount,
                    "minimum_liability_cover_amount": tender.minimum_liability_cover_amount,
                    "git_all_risk_required": tender.git_all_risk_required,
                    "git_first_loss_required": tender.git_first_loss_required,
                    "driver_fidelity_required": tender.driver_fidelity_required,
                },
                "equipment_load_securing": {
                    "tarpaulin_required": tender.tarpaulin_compliance_required,
                    "corner_plates_required": tender.corner_plates_required,
                    "chock_blocks_required": tender.chock_blocks_required,
                    "ratchets_belts_required": tender.ratchets_belts_required,
                },
            },
            "seasonality_and_volume_profile":{
                "volume_pattern_behavior": tender.volume_entry_method,
                "volume_commitment": tender.volume_commitment,
                "volumes": [{
                    "period_sequence": profile.period_sequence,
                    "period_label": profile.period_label,
                    "period_date_start": profile.period_start_date,
                    "period_date_end": profile.period_end_date,
                    "day_of_week": profile.day_of_week or "",
                    "expected_loads": profile.expected_loads,
                } for profile in tender_volumes_profiles]
            },
            "rates_commercial_conditions": {
                "rate_basis": tender.pricing_basis,
                "current_incumbent_rate": tender.incumbent_transport_rate_per_shipment,
                "procurement_target_rate": tender.procurement_target_rate,
                "desired_rate_direction": tender.rate_direction,
                "rate_inclusive_of": {
                    "fuel": tender.rate_includes_fuel,
                    "driver": tender.rate_includes_driver,
                    "maintenance": tender.rate_includes_maintenance,
                    "insurance": tender.rate_includes_insurance,
                    "tolls": tender.rate_includes_tolls,
                    "border_charges": tender.rate_includes_border_charges,
                    "empty_return": tender.rate_includes_empty_return,
                    "waiting_time": tender.rate_includes_waiting_time,
                    "loading_assistance": tender.rate_includes_loading_assistance,
                    "offloading_assistance": tender.rate_includes_offloading_assistance,
                },
                "fuel_treatment": tender.fuel_treatment_type,
                "vat_treatment": tender.vat_treatment,
                "base_diesel_price": tender.base_diesel_price,
                "review_period": tender.fuel_review_period,
                "fuel_component": tender.fuel_component_percentage,
                "rate_validity": tender.rate_validity,
                "questions_deadline": tender.questions_deadline,
                "tender_closing_date": tender.tender_closing_date,
                "supplier_bid_evaluation": {
                    "evaluation_price_enabled": tender.evaluation_price_enabled,
                    "evaluation_capacity_enabled": tender.evaluation_capacity_enabled,
                    "evaluation_service_enabled": tender.evaluation_service_enabled,
                    "evaluation_compliance_enabled": tender.evaluation_compliance_enabled,
                    "evaluation_flexibility_enabled": tender.evaluation_flexibility_enabled,
                },
                "bids": [{
                    "id": bid.id,
                    "status": bid.status,
                    "carrier_id": bid.carrier_id,
                    "carrier_name": bid.carrier_name,
                    "fleet_size": bid.fleet_size,
                    "primary_lanes": bid.primary_lanes,
                    "per_shipment_bid": bid.bid_per_shipment,
                    "slots_per_interval": bid.slots_per_interval,
                    "per_slot_size": bid.per_slot_size,
                    "notes": bid.bid_notes,
                    "submitted_at": bid.submitted_at,
                } for bid in bids]
            },
            "operational_compliance_risk_requirements": {
                "proof_of_delivery_submissions": {
                    "local_hauls": tender.pod_submission_local,
                    "long_hauls": tender.pod_submission_long_haul,
                    "cross_border": tender.pod_submission_cross_border,
                    "delivery_docs_sla": tender.delivery_documentation_sla,
                },
                "claims_risk_management_governance": {
                    "claims_policy_framework": tender.claims_risk_policy,
                    "special_risk_claims_protocol_": tender.claims_risk_requirements,
                },
                "required_operational_conditions": {
                    "vehicle_tracking_required": tender.vehicle_tracking_required,
                    "24_hour_control_room": tender.all_time_hour_control_room,
                    "driver_mobile_phone": tender.driver_mobile_phone,
                    "clean_compliant_equipment": tender.clean_compliant_equipment,
                    "pallet_management": tender.pallet_management,
                },
                "subcontracting_policy": tender.subcontracting_policy,
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/enterprise/ftl-shipment-exchange/{id}")
def get_enterprise_single_ftl_exchange_details(
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
        exchange = db.query(FTL_SHIPMENT_EXCHANGE).filter(FTL_SHIPMENT_EXCHANGE.id == id).first()
        facility = db.query(Corporation).filter(Corporation.id == exchange.shipper_company_id).first()
        user = db.query(Director).filter(Director.id == exchange.shipper_user_id).first()

        pickup_facility = db.query(ShipmentFacility).filter_by(id=exchange.pickup_facility_id).first()
        delivery_facility = db.query(ShipmentFacility).filter_by(id=exchange.delivery_facility_id).first()

        pickup_contact = db.query(ContactPerson).filter_by(id=pickup_facility.contact_person).first() if pickup_facility else None
        delivery_contact = db.query(ContactPerson).filter_by(id=delivery_facility.contact_person).first() if delivery_facility else None
        
        bids = db.query(Exchange_FTL_Shipment_Bid).filter(Exchange_FTL_Shipment_Bid.exchange_id == exchange.id).all()
        
        return {
            "id": exchange.id,
            "exchange_status": exchange.auction_status,
            "type": exchange.type,
            "trip_type": exchange.trip_type,
            "load_type": exchange.load_type,
            "booked_by": exchange.shipper_user_id,
            "required_truck_type": exchange.required_truck_type,
            "equipment_type": exchange.equipment_type,
            "trailer_type": exchange.trailer_type,
            "trailer_length": exchange.trailer_length,
            "minimum_weight_bracket": exchange.minimum_weight_bracket,
            "minimum_git_cover": exchange.minimum_git_cover_amount,
            "minimum_liability_cover": exchange.minimum_liability_cover_amount,
            "origin_address": exchange.complete_origin_address,
            "destination_address": exchange.complete_destination_address,
            "pickup_date": exchange.pickup_date,
            "priority_level": exchange.priority_level,
            "customer_reference": exchange.customer_reference_number,
            "shipment_weight": exchange.shipment_weight,
            "commodity": exchange.commodity,
            "temperature_control": exchange.temperature_control,
            "hazardous_materials": exchange.hazardous_materials,
            "packaging_quantity": exchange.packaging_quantity,
            "packaging_type": exchange.packaging_type,
            "pickup_number": exchange.pickup_number,
            "delivery_number": exchange.delivery_number,
            "pickup_notes": exchange.pickup_notes,
            "delivery_notes": exchange.delivery_notes,
            "distance": exchange.distance,
            "estimated_transit_time": exchange.estimated_transit_time,
            "offer_rate": exchange.offer_price,
            "suggested_rate": exchange.suggested_price,
            "winning_bid_amount": exchange.winning_bid_price,
            "trip_savings": exchange.trip_savings,
            "exchange_saving": exchange.exchange_savings,
            "route_preview_embed": exchange.route_preview_embed,
            "created_at": exchange.created_at,
            "end_time": exchange.end_time,

            "exchange_finance": {
                "offer_rate": exchange.offer_price,
                "suggested_rate": exchange.suggested_price,
                "best_offer_rate": exchange.leading_bid_amount,
                "payment_terms": exchange.payment_terms,
                "bids": [{
                    "id": bid.id,
                    "status": bid.status,
                    "carrier": bid.carrier_id,
                    "amount": bid.baked_bid_amount,
                    "submitted_at": bid.submitted_at,
                } for bid in bids],
            },

            "pickup_facility": {
                "facility_name": pickup_facility.name if pickup_facility else None,
                "address": pickup_facility.address if pickup_facility else None,
                "time_window": f"{pickup_facility.start_time} - {pickup_facility.end_time}",
                "contact_name": f"{pickup_contact.first_name} - {pickup_contact.last_name}" if pickup_contact else None,
                "email": pickup_contact.email if pickup_contact else None,
                "contact_phone": pickup_contact.phone_number if pickup_contact else None,
                "notes": pickup_facility.facility_notes if pickup_facility else None,
            } if pickup_facility else None,

            "delivery_facility": {
                "facility_name": delivery_facility.name if pickup_facility else None,
                "address": delivery_facility.address if delivery_facility else None,
                "time_window": f"{delivery_facility.start_time} - {delivery_facility.end_time}",
                "contact_name": f"{delivery_contact.first_name} - {delivery_contact.last_name}" if pickup_contact else None,
                "email": delivery_contact.email if pickup_contact else None,
                "contact_phone": delivery_contact.phone_number if delivery_contact else None,
                "notes": delivery_facility.facility_notes if delivery_facility else None,
            } if delivery_facility else None,

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

@router.get("/shipper/ftl-lane-exchange/{id}")
def shipper_single_ftl_lane_exchange_detials(
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
        exchange = db.query(FTL_Lane_Exchange).filter(FTL_Lane_Exchange.id == id,
                                                          FTL_Lane_Exchange.shipper_company_id == company_id).first()

        facility = db.query(Corporation).filter(Corporation.id == exchange.shipper_company_id).first()
        user = db.query(Director).filter(Director.id == exchange.shipper_user_id).first()

        bids = db.query(Exchange_FTL_Lane_Bid).filter(Exchange_FTL_Lane_Bid.exchange_id == exchange.id,
                                                      Exchange_FTL_Lane_Bid.type == exchange.type).all()

        pickup_facility = db.query(ShipmentFacility).filter_by(id=exchange.pickup_facility_id).first()
        delivery_facility = db.query(ShipmentFacility).filter_by(id=exchange.delivery_facility_id).first()

        pickup_contact = db.query(ContactPerson).filter_by(id=pickup_facility.contact_person).first() if pickup_facility else None
        delivery_contact = db.query(ContactPerson).filter_by(id=delivery_facility.contact_person).first() if delivery_facility else None

        return {
            "exchange_lane_details": {
                "id": exchange.id,
                "type": exchange.type,
                "trip_type": exchange.trip_type,
                "load_type": exchange.load_type,
                "required_truck_type": exchange.required_truck_type,
                "equipment_type": exchange.equipment_type,
                "trailer_type": exchange.trailer_type,
                "trailer_length": exchange.trailer_length,
                "minimum_weight_bracket": exchange.minimum_weight_bracket,
                "priority_level": exchange.priority_level,
                "average_shipment_weight": exchange.average_shipment_weight,
                "commodity": exchange.commodity,
                "temperature_control": exchange.temperature_control,
                "hazardous_materials": exchange.hazardous_materials,
                "minimum_git_cover": exchange.minimum_git_cover_amount,
                "minimum_liability_cover": exchange.minimum_liability_cover_amount,
                "customer_reference": exchange.customer_reference_number,
                "packaging_type": exchange.packaging_type,
                "packaging_quantity": exchange.packaging_quantity,
                "pickup_number": exchange.pickup_number,
                "delivery_number": exchange.delivery_number,
                "distance": exchange.distance,
                "estimated_transit_time": exchange.estimated_transit_time,
                "origin_address": exchange.origin_address,
                "destination_address": exchange.destination_address,
                "pickup_notes": exchange.pickup_notes,
                "delivery_notes": exchange.delivery_notes,
                "start_date": exchange.start_date,
                "end_date": exchange.end_date,
                "created": exchange.created_at,
                "status": exchange.auction_status,
                "end_time": exchange.exchange_end_time,

                "lane_contract_details": {
                    "recurrence_frequency": exchange.recurrence_frequency,
                    "recurrence_days": exchange.recurrence_days,
                    "shipments_per_interval": exchange.shipments_per_interval,
                    "total_shipments": exchange.total_shipments,
                    "available_slots": exchange.available_slots,
                    "total_shipment_per_slot": exchange.each_slot_size,
                    "per_shipment_offer_rate": exchange.per_shipment_offer_rate,
                    "contract_offer_rate": exchange.contract_offer_rate,
                    "payment_terms": exchange.payment_terms,
                },

                "financial_information": {
                    "suggested_per_shipment_rate": exchange.suggested_per_shipment_rate,
                    "suggested_contract_rate": exchange.suggested_contract_rate,
                    "per_shipment_offer_rate": exchange.per_shipment_offer_rate,
                    "contract_offer_rate": exchange.contract_offer_rate,
                    "per_shipment_savings": (
                        exchange.suggested_per_shipment_rate - exchange.per_shipment_offer_rate
                        if exchange.suggested_per_shipment_rate is not None and exchange.per_shipment_offer_rate is not None
                        else None
                    ),
                    "contract_savings": (
                        exchange.suggested_contract_rate - exchange.contract_offer_rate
                        if exchange.suggested_contract_rate is not None and exchange.contract_offer_rate is not None
                        else None
                    ),
                    "trip_savings": (
                        exchange.per_shipment_offer_rate - exchange.leading_per_shipment_bid_amount
                        if exchange.per_shipment_offer_rate is not None and exchange.leading_per_shipment_bid_amount is not None
                        else None
                    ),
                    "exchange_savings": (
                        exchange.contract_offer_rate - exchange.leading_contract_bid_amount
                        if exchange.contract_offer_rate is not None and exchange.leading_contract_bid_amount is not None
                        else None
                    ),
                },

                "exchange_finance": {
                    "suggested_per_shipment_rate": exchange.suggested_per_shipment_rate,
                    "suggested_contract_rate": exchange.suggested_contract_rate,
                    "per_shipment_offer_rate": exchange.per_shipment_offer_rate,
                    "contract_offer_rate": exchange.contract_offer_rate,
                    "leading_per_shipment_bid": exchange.leading_per_shipment_bid_amount,
                    "leading_contract_bid": exchange.leading_contract_bid_amount,
                    "number_of_bids": exchange.number_of_bids_submitted,
                    "payment_terms": exchange.payment_terms,

                    "bid": [{
                        "id": bid.id,
                        "status": bid.status,
                        "carrier_id": bid.carrier_id,
                        "requested_slots": bid.requested_slots,
                        "each_slot_size": f"{bid.each_slot_size} total shipments",
                        "per_shipment_rate": bid.baked_per_shipment_bid_amount,
                        "per_slot_contract_bid": bid.baked_contract_bid_amount,
                        "total_contract_bid_rate": bid.baked_contract_bid_amount * bid.requested_slots,
                        "submitted_at": bid.submitted_at,
                    } for bid in bids]
                },
            },

            "pickup_facility": {
                "facility_name": pickup_facility.name if pickup_facility else None,
                "address": pickup_facility.address if pickup_facility else None,
                "time_window": f"{pickup_facility.start_time} - {pickup_facility.end_time}",
                "scheduling_type": pickup_facility.scheduling_type,
                "contact_name": f"{pickup_contact.first_name} - {pickup_contact.last_name}" if pickup_contact else None,
                "email": pickup_contact.email if pickup_contact else None,
                "contact_phone": pickup_contact.phone_number if pickup_contact else None,
                "notes": pickup_facility.facility_notes if pickup_facility else None,
            } if pickup_facility else None,

            "delivery_facility": {
                "facility_name": delivery_facility.name if delivery_facility else None,
                "address": delivery_facility.address if delivery_facility else None,
                "time_window": f"{delivery_facility.start_time} - {delivery_facility.end_time}",
                "scheduling_type": delivery_facility.scheduling_type,
                "contact_name": f"{delivery_contact.first_name} - {delivery_contact.last_name}" if pickup_contact else None,
                "email": delivery_contact.email if pickup_contact else None,
                "contact_phone": delivery_contact.phone_number if delivery_contact else None,
                "notes": delivery_facility.facility_notes if delivery_facility else None,
            } if delivery_facility else None,

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