from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.Exchange.auction import Exchange_FTL_Lane_Bid, Exchange_FTL_Shipment_Bid, Exchange_POWER_Shipment_Bid, Lane_Tender_RFQ_Bids
from models.Exchange.dedicated_ftl_lane import FTL_Lane_Exchange, Lane_Tender_RFQ, Lane_Tender_RFQ_Stop, Lane_Tender_RFQ_Vehicle_Config, Lane_Tender_RFQ_Volume_Profile, Lane_Tender_RFQ_Accessorial
from models.Exchange.auction import Shipment_Auction_Bid
from models.shipper import Corporation
from models.user import Director
from models.Exchange.ftl_shipment import Client_Shipment_Auction, Client_Shipment_Auction_Stop, Client_Shipment_Auction_Vehicle_Requirement
from models.Exchange.ftl_shipment import FTL_SHIPMENT_EXCHANGE
from models.Exchange.power_shipment import POWER_SHIPMENT_EXCHANGE
from services.brokerage.tender.tender_award import award_tender_bid
from models.brokerage.loadboards.exchange_loadboards import Exchange_Ftl_Load_Board, Exchange_Power_Load_Board
from models.spot_bookings.shipment_facility import ContactPerson, ShipmentFacility
from models.vehicle import ShipperTrailer
from schemas.exchange_bookings.auction import Accept_Bid, Exchange_FTL_Lane_ShipperSide_BidResponse, Exchange_Id, FTL_Exchange_ShipperSide_BidResponse, POWER_Exchange_ShipperSide_BidResponse
from schemas.exchange_bookings.dedicated_ftl_lane import Exchange_Ftl_Lane_Response, Exchange_Ftl_Lane_Summary_Response
from schemas.exchange_bookings.ftl_shipment import Exchange_FTL_Shipment_Response, Exchange_Ftl_Shipments_Summary_Response
from schemas.exchange_bookings.power_shipment import Exchange_Power_Shipments_Summary_Response, exchange_power_shipment_response
from services.cancellations.exchange_cancellations import cancel_exchange_ftl_booking, cancel_exchange_power_booking, cancel_exchange_ftl_lane_booking
from utils.auth import get_current_user

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/load-exchanges")
def get_load_exchange(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")

    try:
        print("STEP 1 - querying exchanges")

        exchanges = db.query(Client_Shipment_Auction).filter(
            Client_Shipment_Auction.client_id == company_id
        ).all()

        print(f"STEP 1: Found {len(exchanges)} exchanges")

        response = []

        for exchange in exchanges:

            origin = db.query(Client_Shipment_Auction_Stop).filter(
                Client_Shipment_Auction_Stop.auction_id == exchange.id,
                Client_Shipment_Auction_Stop.stop_type == "Origin"
            ).first()

            stops = db.query(Client_Shipment_Auction_Stop).filter(
                Client_Shipment_Auction_Stop.auction_id == exchange.id,
                Client_Shipment_Auction_Stop.stop_type == "Intermediate"
            ).all()

            destination = db.query(Client_Shipment_Auction_Stop).filter(
                Client_Shipment_Auction_Stop.auction_id == exchange.id,
                Client_Shipment_Auction_Stop.stop_type == "Destination"
            ).first()

            primary_equipment = db.query(Client_Shipment_Auction_Vehicle_Requirement).filter(
                Client_Shipment_Auction_Vehicle_Requirement.auction_id == exchange.id,
                Client_Shipment_Auction_Vehicle_Requirement.configuration_type == "Primary"
            ).first()

            bids = db.query(Shipment_Auction_Bid).filter(
                Shipment_Auction_Bid.auction_id == exchange.id
            ).all()

            lowest_bid = min(
                [bid.rate for bid in bids if bid.rate is not None],
                default=None
            )

            print(f"Exchange {exchange.id}: {len(bids)} bids found")

            response.append({
                "id": exchange.id,
                "status": exchange.status,
                "hazchem_information": {
                    "hazardous": exchange.hazardous_materials,
                    "hazchem_classification": exchange.hazchem_classification if exchange.hazchem_classification else None,
                },
                "origin": {
                    "pickup": origin.city_province if origin else None,
                    "facility": origin.facility_name if origin else None,
                    "date": exchange.pickup_date,
                    "pickup_window": {
                        "start_time": origin.operating_start_time,
                        "end_time": origin.operating_end_time,
                    },
                },
                "load_corridor_information": {
                    "distance": exchange.distance,
                    "stops": len(stops),
                    "required_equipment": (
                        f"{primary_equipment.truck_type if primary_equipment.truck_type == 'Rigid' else primary_equipment.trailer_type} - {primary_equipment.equipment_type}"
                        if primary_equipment else None
                    ),
                    "trucks_required": exchange.number_of_trucks_required,
                },
                "destination": {
                    "delivery": destination.city_province if destination else None,
                    "facility": destination.facility_name if destination else None,
                    "eta_date": exchange.eta_date,
                    "window": {
                        "start_time": destination.operating_start_time,
                        "end_time": destination.operating_end_time,
                    },
                },
                "financial": {
                    "bids_quotes_in": len(bids) if bids else 0,
                    "lowest": lowest_bid,
                    "budget": exchange.procurement_target_rate
                },
            })

        return {
            "exchanges": response
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/load-exchange/{id}/summary")
def get_load_exchange_summary(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")

    try:
        print("STEP 1 - querying exchange")

        exchange = db.query(Client_Shipment_Auction).filter(Client_Shipment_Auction.id == id).first()
        if not exchange:
            raise HTTPException(status_code=404, detail="Load exchange not found")

        trip_points = db.query(Client_Shipment_Auction_Stop).filter(Client_Shipment_Auction_Stop.auction_id == exchange.id).order_by(Client_Shipment_Auction_Stop.stop_sequence.asc()).all()
        bids = db.query(Shipment_Auction_Bid).filter(Shipment_Auction_Bid.auction_id == exchange.id).order_by(Shipment_Auction_Bid.rate.asc()).all()

        origin = db.query(Client_Shipment_Auction_Stop).filter(Client_Shipment_Auction_Stop.auction_id == exchange.id, Client_Shipment_Auction_Stop.stop_type == "Origin").first()
        stops = db.query(Client_Shipment_Auction_Stop).filter(Client_Shipment_Auction_Stop.auction_id == exchange.id).all()
        destination = db.query(Client_Shipment_Auction_Stop).filter(Client_Shipment_Auction_Stop.auction_id == exchange.id, Client_Shipment_Auction_Stop.stop_type == "Destination").first()

        if not origin:

            raise HTTPException(status_code=500, detail="Origin stop not found")

        if not destination:
            raise HTTPException(status_code=500, detail="Destination stop not found")

        return {
            "summary": {
                "id": exchange.id,
                "status": exchange.status,
                "description_info": {
                    "commodity": exchange.commodity,
                    "packaging": exchange.packaging_quantity if exchange.packaging_type else None,
                    "packaging_type": exchange.packaging_type if exchange.packaging_type else None,
                    "weight_per_shipment": exchange.shipment_weight,
                },
                "hazchem": {
                    "hazardous_material": exchange.hazardous_materials,
                    "hazchem_classification": exchange.hazchem_classification,
                },
                "trucks_required": exchange.number_of_trucks_required,
                "corridor_specs": f"{exchange.distance} km ~ {exchange.trip_type} {exchange.priority_level} priority load ({len(stops)} stops)",
                "target_budget": exchange.procurement_target_rate,
                "pickup_schedule": {
                    "pickup_date": exchange.pickup_date,
                    "pickup_window": {
                        "start_time": origin.operating_start_time,
                        "end_time": origin.operating_end_time,
                    },
                },
                "delivery_eta": {
                    "eta_date": exchange.eta_date,
                    "delivery_window": {
                        "start_time": destination.operating_start_time,
                        "end_time": destination.operating_end_time,
                    },
                },
                "live_carrier_quotes": [{
                    "id": bid.id,
                    "carrier_name": bid.carrier_name,
                    "lead_time": bid.lead_time,
                    "rate": bid.rate,
                    "number_of_loads": bid.number_of_loads,
                    "notes": bid.notes,
                    "savings": (exchange.procurement_target_rate - bid.rate) if bid.rate is not None and exchange.procurement_target_rate is not None else None,
                } for bid in bids],
            },
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/load-exchange/{id}")
def get_load_exchange_information(
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
        print("STEP 1 - querying auction")
        exchange = db.query(Client_Shipment_Auction).filter(Client_Shipment_Auction.id == id).first()
        if not exchange:
            raise HTTPException(status_code=404, detail="Load exchange not found")

        trip_points = db.query(Client_Shipment_Auction_Stop).filter(Client_Shipment_Auction_Stop.auction_id == exchange.id).order_by(Client_Shipment_Auction_Stop.stop_sequence.asc()).all()
        bids = db.query(Shipment_Auction_Bid).filter(Shipment_Auction_Bid.auction_id == exchange.id).order_by(Shipment_Auction_Bid.rate.asc()).all()
        configs = db.query(Client_Shipment_Auction_Vehicle_Requirement).filter(Client_Shipment_Auction_Vehicle_Requirement.auction_id == exchange.id).all()

        origin = db.query(Client_Shipment_Auction_Stop).filter(Client_Shipment_Auction_Stop.auction_id == exchange.id, Client_Shipment_Auction_Stop.stop_type == "Origin").first()
        stops = db.query(Client_Shipment_Auction_Stop).filter(Client_Shipment_Auction_Stop.auction_id == exchange.id, Client_Shipment_Auction_Stop.stop_type == "Intermediate").all()
        destination = db.query(Client_Shipment_Auction_Stop).filter(Client_Shipment_Auction_Stop.auction_id == exchange.id, Client_Shipment_Auction_Stop.stop_type == "Destination").first()

        return {
            "load_information": {
                "id": exchange.id,
                "shipment_reference": exchange.shipment_reference,
                "booking_reference": exchange.booking_reference,
                "trip_type": exchange.trip_type,
                "load_type": exchange.load_type,
                "payment_terms": exchange.payment_terms,
                "number_of_trucks_required": exchange.number_of_trucks_required,
                "number_of_slots_remaining": exchange.slots_remaining,
                "pickup_date": exchange.pickup_date,
                "priority_level": exchange.priority_level,
                "customer_reference_number": exchange.customer_reference_number,
                "pod_submission_local": exchange.pod_submission_local,
                "pod_submission_long_haul": exchange.pod_submission_long_haul,
                "pod_submission_cross_border": exchange.pod_submission_cross_border,
                "auction_information": {
                    "end_time": exchange.auction_closing_date,
                    "bidding_activated": exchange.bidding_activated,
                    "rates": {
                        "pricing_basis": exchange.pricing_basis,
                        "rate_direction": exchange.rate_direction,
                        "benchmark": exchange.procurement_target_rate,
                        "book_now_rate": exchange.book_now_rate if exchange.book_now_rate else None,
                        "vat_inclusive": exchange.vat_included,
                    },
                    "bids": [{
                        "id": bid.id,
                        "rate": bid.rate,
                        "number_of_loads": bid.number_of_loads,
                        "status": bid.status,
                        "potential_savings": (exchange.procurement_target_rate - bid.rate) if bid.rate is not None and exchange.procurement_target_rate is not None else None,
                        "carrier": {
                            "id": bid.carrier_id,
                            "name": bid.carrier_name,
                            "fleet_size": bid.fleet_size,
                            "primary_lanes": bid.primary_lanes,
                            "lead_time": bid.lead_time,
                        },
                        "submitted_at": bid.submitted_at,
                    } for bid in bids],
                    "rate_inclusive_of": {
                        "fuel": exchange.rate_includes_fuel,
                        "waiting_detention_time": exchange.rate_includes_waiting_time,
                        "driver": exchange.rate_includes_driver,
                        "maintenance": exchange.rate_includes_maintenance,
                        "insurance": exchange.rate_includes_insurance,
                        "tolls": exchange.rate_includes_tolls,
                        "border_charges": exchange.rate_includes_border_charges,
                        "empty_return": exchange.rate_includes_empty_return,
                        "loading_assistance_charges": exchange.rate_includes_loading_assistance,
                        "offloading_assistance_charges": exchange.rate_includes_offloading_assistance,
                    },
                },
                "load_information": {
                    "number_of_trucks_required": exchange.number_of_trucks_required,
                    "number_of_slots_remaining": exchange.slots_remaining,
                    "pickup_date": exchange.pickup_date,
                    "shipment_weight": exchange.shipment_weight,
                    "commodity": exchange.commodity,
                    "packaging_type": exchange.packaging_type,
                    "packaging_quantity": exchange.packaging_quantity,
                    "temperature_control": exchange.temperature_control,
                    "temperature_control_spec": exchange.target_temperature_spec,
                    "hazardous_materials": exchange.hazardous_materials,
                    "hazchem_classification": exchange.hazchem_classification,
                    "under_bond": exchange.under_bond,
                    "rib_required": exchange.rib_requirements,
                },
                "truck_requirements": [{
                    "configuration_type": config.configuration_type,
                    "truck_type": config.truck_type,
                    "equipment_type": config.equipment_type,
                    "trailer_type": config.trailer_type if config.trailer_type else None,
                    "trailer_length": config.trailer_length if config.trailer_length else None,
                    "minimum_weight_bracket": exchange.minimum_weight_bracket,
                    "compliance_requirements": {
                        "vehicle_tracking_required": exchange.vehicle_tracking_required,
                        "all_time_hour_control_room": exchange.all_time_hour_control_room,
                        "driver_mobile_phone": exchange.driver_mobile_phone,
                        "clean_compliant_equipment": exchange.clean_compliant_equipment,
                    },
                    "accessorials_requirement": {
                        "pallet_management": exchange.pallet_management,
                        "tarpaulin_compliance_required": exchange.tarpaulin_compliance_required,
                        "corner_plates_required": exchange.corner_plates_required,
                        "chock_blocks_required": exchange.chock_blocks_required,
                        "ratchets_belts_required": exchange.ratchets_belts_required,
                        "other_equipment_requirements": exchange.other_equipment_requirements,
                    },
                } for config in configs],
                "insurance_requirements": {
                    "minimum_git_cover": exchange.minimum_git_cover_amount,
                    "minimum_liability_cover": exchange.minimum_liability_cover_amount,
                    "git_all_risk_required": exchange.git_all_risk_required,
                    "git_first_loss_required": exchange.git_first_loss_required,
                    "git_driver_fidelity_required": exchange.git_driver_fidelity_required,
                },
                "route_facilities_information": {
                    "origin_facility": {
                        "stop_type": origin.stop_type,
                        "city_province_country": {
                            "city_province": origin.city_province,
                            "country": origin.country,
                        },
                        "facility_name": origin.facility_name,
                        "reference_number": origin.reference_number,
                        "address": origin.address,
                        "scheduling_type": origin.scheduling_type,
                        "operating_hours": {
                            "start_time": origin.operating_start_time,
                            "end_time": origin.operating_end_time,
                        },
                        "operating_days": {
                            "monday": origin.open_monday,
                            "tuesday": origin.open_tuesday,
                            "wednesday": origin.open_wednesday,
                            "thursday": origin.open_thursday,
                            "friday": origin.open_friday,
                            "saturday": origin.open_saturday,
                            "sunday": origin.open_sunday
                        },
                        "contact_person": {
                            "first_name": origin.contact_first_name,
                            "last_name": origin.contact_first_name,
                            "phone": origin.contact_phone_number,
                            "email": origin.contact_email,
                        },
                        "facility_notes": origin.notes,
                    },
                    "stop_facilities": [{
                        "stop_type": stop.stop_type,
                        "city_province_country": {
                            "city_province": stop.city_province,
                            "country": stop.country,
                        },
                        "facility_name": stop.facility_name,
                        "reference_number": stop.reference_number,
                        "address": stop.address,
                        "scheduling_type": stop.scheduling_type,
                        "operating_hours": {
                            "start_time": stop.operating_start_time,
                            "end_time": stop.operating_end_time,
                        },
                        "operating_days": {
                            "monday": stop.open_monday,
                            "tuesday": stop.open_tuesday,
                            "wednesday": stop.open_wednesday,
                            "thursday": stop.open_thursday,
                            "friday": stop.open_friday,
                            "saturday": stop.open_saturday,
                            "sunday": stop.open_sunday
                        },
                        "contact_person": {
                            "first_name": stop.contact_first_name,
                            "last_name": stop.contact_first_name,
                            "phone": stop.contact_phone_number,
                            "email": stop.contact_email,
                        },
                        "facility_notes": stop.notes,
                    } for stop in stops] if stops else None,
                    "destination_facility": {
                        "stop_type": destination.stop_type,
                        "city_province_country": {
                            "city_province": destination.city_province,
                            "country": destination.country,
                        },
                        "facility_name": destination.facility_name,
                        "reference_number": destination.reference_number,
                        "address": destination.address,
                        "scheduling_type": destination.scheduling_type,
                        "operating_hours": {
                            "start_time": destination.operating_start_time,
                            "end_time": destination.operating_end_time,
                        },
                        "operating_days": {
                            "monday": destination.open_monday,
                            "tuesday": destination.open_tuesday,
                            "wednesday": destination.open_wednesday,
                            "thursday": destination.open_thursday,
                            "friday": destination.open_friday,
                            "saturday": destination.open_saturday,
                            "sunday": destination.open_sunday
                        },
                        "contact_person": {
                            "first_name": destination.contact_first_name,
                            "last_name": destination.contact_first_name,
                            "phone": destination.contact_phone_number,
                            "email": destination.contact_email,
                        },
                        "facility_notes": destination.notes,
                    },
                },
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
                "publisher_user_id": tender.publisher_user_id,
                "proposed_rounds": tender.proposed_rounds,
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
                    "truck_type": config.truck_type,
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
                    "driver_fidelity_required": tender.git_driver_fidelity_required,
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

@router.get("/tender/{id}/bids")
def get_tender_rfq_bids(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        bids = db.query(Lane_Tender_RFQ_Bids).filter(Lane_Tender_RFQ_Bids.tender_id == id).all()

        return {
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
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tender/{tender_id}/award-bid/{bid_id}")
def award_tender_bid_endpoint(
    tender_id: int,
    bid_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        return award_tender_bid(
            db=db,
            tender_id=tender_id,
            bid_id=bid_id,
            current_user=current_user
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print("Tender award error:", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to award tender bid: {str(e)}"
        )

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