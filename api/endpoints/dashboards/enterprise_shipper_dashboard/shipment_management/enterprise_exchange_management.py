from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.Exchange.bidding import Lane_Tender_Bid
from models.Exchange.auction import Exchange_FTL_Lane_Bid, Exchange_FTL_Shipment_Bid, Exchange_POWER_Shipment_Bid
from models.Exchange.dedicated_ftl_lane import FTL_Lane_Exchange, Lane_Tender_RFQ, Lane_Tender_RFQ_Stop, Lane_Tender_RFQ_Vehicle_Config, Lane_Tender_RFQ_Volume_Profile, Lane_Tender_RFQ_Accessorial
from models.Exchange.bidding import Shipment_Auction_Bid
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
from services.exchange.auction import accept_auction_bid
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
                    "bid_rate": {
                        "rate": bid.main_bid_amount if bid.main_bid_amount else bid.secondary_bid_amount,
                        "rate_basis": bid.rate_basis,
                        "shipment_rate": bid.main_rate_per_shipment,
                    },
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
        # =========================================================
        # 1. QUERY THE REQUESTED AUCTION
        # =========================================================

        requested_auction = (
            db.query(Client_Shipment_Auction)
            .filter(
                Client_Shipment_Auction.id == id,
                Client_Shipment_Auction.client_id == company_id
            )
            .first()
        )

        if not requested_auction:
            raise HTTPException(
                status_code=404,
                detail="Load exchange not found"
            )

        # =========================================================
        # 2. QUERY BUNDLE METADATA AND ALL RELATED AUCTIONS
        # =========================================================

        bundle_metadata = None

        if requested_auction.bundle_id is not None:
            bundle_record = (
                db.query(Client_Shipment_Auction_Bundle)
                .filter(
                    Client_Shipment_Auction_Bundle.id
                    == requested_auction.bundle_id,
                    Client_Shipment_Auction_Bundle.client_id
                    == company_id
                )
                .first()
            )

            if bundle_record:
                bundle_metadata = {
                    "id": bundle_record.id,
                    "bundle_reference": bundle_record.bundle_reference,
                    "bundle_type": bundle_record.bundle_type,
                    "stage_count": bundle_record.stage_count,
                    "status": bundle_record.status,
                    "created_by_user_id": (
                        bundle_record.created_by_user_id
                    ),
                    "created_at": bundle_record.created_at,
                    "updated_at": bundle_record.updated_at,
                }

            # Retrieve every auction belonging to this bundle.
            # Always apply client isolation.
            bundle_auctions = (
                db.query(Client_Shipment_Auction)
                .filter(
                    Client_Shipment_Auction.bundle_id
                    == requested_auction.bundle_id,
                    Client_Shipment_Auction.client_id == company_id
                )
                .order_by(
                    Client_Shipment_Auction.bundle_trip_sequence.asc(),
                    Client_Shipment_Auction.id.asc()
                )
                .all()
            )

            # Defensive fallback if the requested auction is not
            # present in the returned bundle records.
            if not any(
                auction.id == requested_auction.id
                for auction in bundle_auctions
            ):
                bundle_auctions.append(requested_auction)

            # Re-establish deterministic stage order after fallback.
            bundle_auctions.sort(
                key=lambda auction: (
                    auction.bundle_trip_sequence
                    if auction.bundle_trip_sequence is not None
                    else 0,
                    auction.id
                )
            )

            is_bundle = True

        else:
            bundle_auctions = [requested_auction]
            is_bundle = False

        # =========================================================
        # 3. HELPER: SERIALIZE A BID
        # =========================================================

        def serialize_bid(bid, auction):
            primary_rate = bid.main_rate
            secondary_rate = bid.secondary_rate

            primary_savings = None
            secondary_savings = None

            if (
                primary_rate is not None
                and auction.procurement_target_rate is not None
            ):
                primary_savings = (
                    auction.procurement_target_rate - primary_rate
                )

            if (
                secondary_rate is not None
                and auction.procurement_target_rate is not None
            ):
                secondary_savings = (
                    auction.procurement_target_rate - secondary_rate
                )

            return {
                "id": bid.id,

                "primary_rate": {
                    "rate": primary_rate,
                    "rate_basis": bid.rate_basis,
                    "shipment_rate": bid.main_rate_per_shipment,
                    "total_rate": bid.total_main_rate,
                    "potential_savings": primary_savings,
                },

                "secondary_rate": (
                    {
                        "rate": secondary_rate,
                        "rate_basis": bid.rate_basis,
                        "shipment_rate": (
                            bid.secondary_rate_per_shipment
                        ),
                        "total_rate": bid.total_secondary_rate,
                        "potential_savings": secondary_savings,
                    }
                    if secondary_rate is not None
                    else None
                ),

                "number_of_loads": bid.number_of_loads,
                "status": bid.status,

                "carrier": {
                    "id": bid.carrier_id,
                    "name": bid.carrier_name,
                    "fleet_size": bid.fleet_size,
                    "primary_lanes": bid.primary_lanes,
                    "lead_time": bid.lead_time,
                },

                "submitted_at": bid.submitted_at,
            }

        # =========================================================
        # 4. HELPER: SERIALIZE ONE AUCTION / BUNDLE STAGE
        # =========================================================

        def serialize_auction(auction):
            # -----------------------------------------------------
            # 4.1 ROUTE STOPS
            # -----------------------------------------------------

            trip_points = (
                db.query(Client_Shipment_Auction_Stop)
                .filter(
                    Client_Shipment_Auction_Stop.auction_id
                    == auction.id
                )
                .order_by(
                    Client_Shipment_Auction_Stop.stop_sequence.asc()
                )
                .all()
            )

            origin = next(
                (
                    stop for stop in trip_points
                    if stop.stop_type == "Origin"
                ),
                None
            )

            intermediate_stops = [
                stop for stop in trip_points
                if stop.stop_type == "Intermediate"
            ]

            destination = next(
                (
                    stop for stop in trip_points
                    if stop.stop_type == "Destination"
                ),
                None
            )

            if not origin or not destination:
                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"Auction {auction.id} is missing a required "
                        "Origin or Destination stop"
                    )
                )

            # -----------------------------------------------------
            # 4.2 BIDS
            # -----------------------------------------------------

            bids = (
                db.query(Shipment_Auction_Bid)
                .filter(
                    Shipment_Auction_Bid.auction_id == auction.id
                )
                .order_by(
                    Shipment_Auction_Bid.main_rate.asc()
                )
                .all()
            )

            bid_information = [
                serialize_bid(bid, auction)
                for bid in bids
            ]

            # -----------------------------------------------------
            # 4.3 VEHICLE CONFIGURATIONS
            # -----------------------------------------------------

            configs = (
                db.query(Client_Shipment_Auction_Vehicle_Requirement)
                .filter(
                    Client_Shipment_Auction_Vehicle_Requirement.auction_id
                    == auction.id
                )
                .order_by(
                    Client_Shipment_Auction_Vehicle_Requirement.id.asc()
                )
                .all()
            )

            # -----------------------------------------------------
            # 4.4 TARGET SERVICE STANDARDS
            # -----------------------------------------------------

            target_sla = (
                db.query(Shipment_Auction_Service_Standard)
                .filter(
                    Shipment_Auction_Service_Standard.auction_id
                    == auction.id
                )
                .order_by(
                    Shipment_Auction_Service_Standard.id.asc()
                )
                .all()
            )

            target_service_levels = [
                {
                    "id": sla.id,
                    "standards": {
                        "type": sla.standard_type,
                        "target_value": sla.target_value,
                        "unit": sla.unit,
                        "is_mandatory": sla.is_mandatory,
                    },
                }
                for sla in target_sla
            ]

            # -----------------------------------------------------
            # 4.5 FACILITY DEMURRAGE / TURNAROUND
            # -----------------------------------------------------

            demurrage_protocols = (
                db.query(Auction_Turnaround_Window_Demurrage_Protocals)
                .filter(
                    Auction_Turnaround_Window_Demurrage_Protocals.auction_id
                    == auction.id
                )
                .all()
            )

            # Each protocol is attached to its own stop.
            demurrage_by_stop_id = {
                protocol.stop_id: protocol
                for protocol in demurrage_protocols
            }

            def serialize_demurrage(stop):
                if not stop:
                    return None

                protocol = demurrage_by_stop_id.get(stop.id)

                if not protocol:
                    return None

                return {
                    "id": protocol.id,
                    "stop_id": protocol.stop_id,
                    "demurrage_conditions": (
                        protocol.demurrage_conditions
                    ),
                    "turnaround_hours": (
                        protocol.loading_offloading_turnaround_hours
                    ),
                    "free_demurrage_hours": (
                        protocol.free_demurrage_hours
                    ),
                    "demurrage_rate_per_hour": (
                        protocol.demurrage_rate_per_hour
                    ),
                    "maximum_demurrage_incursion_hours": (
                        protocol.maximum_demurrage_incursion_hours
                    ),
                }

            # -----------------------------------------------------
            # 4.6 STOP SERIALIZER
            # -----------------------------------------------------

            def serialize_stop(stop):
                if not stop:
                    return None

                return {
                    "id": stop.id,
                    "stop_sequence": stop.stop_sequence,
                    "stop_type": stop.stop_type,

                    "city_province_country": {
                        "city_province": stop.city_province,
                        "country": stop.country,
                        "region": stop.region,
                    },

                    "facility_name": stop.facility_name,
                    "reference_number": stop.reference_number,
                    "address": stop.address,
                    "complete_address": stop.complete_address,
                    "scheduling_type": stop.scheduling_type,

                    "coordinates": {
                        "latitude": stop.latitude,
                        "longitude": stop.longitude,
                    },

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
                        "sunday": stop.open_sunday,
                    },

                    "contact_person": {
                        "first_name": stop.contact_first_name,
                        "last_name": stop.contact_last_name,
                        "phone": stop.contact_phone_number,
                        "email": stop.contact_email,
                    },

                    "facility_notes": stop.notes,

                    "demurrage_protocol": serialize_demurrage(stop),
                }

            # -----------------------------------------------------
            # 4.7 ACCESSORIAL CHARGES
            # -----------------------------------------------------

            accessorial_records = (
                db.query(Auction_Accessorial)
                .filter(
                    Auction_Accessorial.auction_id == auction.id
                )
                .order_by(
                    Auction_Accessorial.id.asc()
                )
                .all()
            )

            accessorial_information = [
                {
                    "id": item.id,
                    "charge_type": item.charge_type,
                    "treatment": item.treatment,
                    "threshold_value": item.threshold_value,
                    "threshold_unit": item.threshold_unit,
                    "notes": item.notes,
                }
                for item in accessorial_records
            ]

            # -----------------------------------------------------
            # 4.8 PERMITS / CERTIFICATIONS / DRIVER STANDARDS
            # -----------------------------------------------------

            certification_records = (
                db.query(
                    Auction_Carrier_Certification_Driver_Standards
                )
                .filter(
                    Auction_Carrier_Certification_Driver_Standards.auction_id
                    == auction.id
                )
                .order_by(
                    Auction_Carrier_Certification_Driver_Standards.id.asc()
                )
                .all()
            )

            certification_information = [
                {
                    "id": item.id,
                    "certification_name": item.certification_name,
                    "directives": (
                        item.driver_qualification_security_directives
                    ),
                    "is_required": item.is_required,
                }
                for item in certification_records
            ]

            # -----------------------------------------------------
            # 4.9 ESCORT POLICY
            # -----------------------------------------------------

            escort_policy_record = (
                db.query(Auction_Escort_Policy)
                .filter(
                    Auction_Escort_Policy.auction_id == auction.id
                )
                .order_by(
                    Auction_Escort_Policy.id.asc()
                )
                .first()
            )

            escort_policy_information = (
                {
                    "id": escort_policy_record.id,
                    "armed_escort_required": (
                        escort_policy_record.armed_escort_required
                    ),
                    "escort_expense_responsible_party": (
                        escort_policy_record.escort_expense_responsible_party
                    ),
                }
                if escort_policy_record
                else {
                    "armed_escort_required": False,
                    "escort_expense_responsible_party": None,
                }
            )

            # -----------------------------------------------------
            # 4.10 ROUTE SUMMARY FOR THIS AUCTION
            # -----------------------------------------------------

            origin_summary = {
                "stop_id": origin.id,
                "facility_name": origin.facility_name,
                "city_province": origin.city_province,
                "country": origin.country,
                "address": origin.address,
            }

            destination_summary = {
                "stop_id": destination.id,
                "facility_name": destination.facility_name,
                "city_province": destination.city_province,
                "country": destination.country,
                "address": destination.address,
            }

            # -----------------------------------------------------
            # 4.11 INDIVIDUAL SHIPMENT SUMMARY
            # -----------------------------------------------------

            shipment_summary = {
                "id": auction.id,
                "shipment_reference": auction.shipment_reference,
                "booking_reference": auction.booking_reference,

                "bundle_id": auction.bundle_id,
                "bundle_reference": auction.bundle_reference,
                "bundle_trip_sequence": auction.bundle_trip_sequence,
                "bundle_role": auction.bundle_role,

                "trip_type": auction.trip_type,
                "load_type": auction.load_type,
                "commodity": auction.commodity,
                "shipment_weight": auction.shipment_weight,

                "pickup_date": auction.pickup_date,
                "priority_level": auction.priority_level,

                "number_of_trucks_required": (
                    auction.number_of_trucks_required
                ),
                "slots_remaining": auction.slots_remaining,

                "status": auction.status,

                "origin": origin_summary,
                "destination": destination_summary,
            }

            # -----------------------------------------------------
            # 4.12 AUCTION SUMMARY
            # -----------------------------------------------------

            auction_summary = {
                "auction_id": auction.id,
                "end_time": auction.auction_closing_date,
                "bidding_activated": auction.bidding_activated,

                "pricing_basis": auction.pricing_basis,
                "rate_direction": auction.rate_direction,
                "benchmark": auction.procurement_target_rate,
                "book_now_rate": auction.book_now_rate,
                "vat_inclusive": auction.vat_included,

                "bid_count": len(bid_information),
            }

            # -----------------------------------------------------
            # 4.13 COMPLETE INDIVIDUAL AUCTION DETAILS
            # -----------------------------------------------------

            return {
                "shipment_summary": shipment_summary,
                "auction_summary": auction_summary,

                # -------------------------------------------------
                # LOAD INFORMATION
                # -------------------------------------------------

                "load_information": {
                    "id": auction.id,
                    "shipment_reference": auction.shipment_reference,
                    "booking_reference": auction.booking_reference,

                    "bundle_id": auction.bundle_id,
                    "bundle_reference": auction.bundle_reference,
                    "bundle_trip_sequence": auction.bundle_trip_sequence,
                    "bundle_role": auction.bundle_role,

                    "trip_type": auction.trip_type,
                    "load_type": auction.load_type,
                    "payment_terms": auction.payment_terms,

                    "number_of_trucks_required": (
                        auction.number_of_trucks_required
                    ),
                    "number_of_slots_remaining": auction.slots_remaining,

                    "pickup_date": auction.pickup_date,
                    "priority_level": auction.priority_level,
                    "customer_reference_number": (
                        auction.customer_reference_number
                    ),

                    "shipment_weight": auction.shipment_weight,
                    "commodity": auction.commodity,
                    "packaging_type": auction.packaging_type,
                    "packaging_quantity": auction.packaging_quantity,

                    "temperature_control": auction.temperature_control,
                    "temperature_control_spec": (
                        auction.target_temperature_spec
                    ),

                    "hazardous_materials": auction.hazardous_materials,
                    "hazchem_classification": (
                        auction.hazchem_classification
                    ),
                    "under_bond": auction.under_bond,
                    "rib_required": auction.rib_requirements,

                    "border_customs_responsibility": (
                        auction.border_customs_responsibility
                    ),

                    "distance": auction.distance,
                    "eta_date": auction.eta_date,
                    "estimated_transit_time": (
                        auction.estimated_transit_time
                    ),
                    "status": auction.status,

                    "pod_submission_local": (
                        auction.pod_submission_local
                    ),
                    "pod_submission_long_haul": (
                        auction.pod_submission_long_haul
                    ),
                    "pod_submission_cross_border": (
                        auction.pod_submission_cross_border
                    ),
                },

                # -------------------------------------------------
                # AUCTION INFORMATION
                # -------------------------------------------------

                "auction_information": {
                    "end_time": auction.auction_closing_date,
                    "bidding_activated": auction.bidding_activated,

                    "rates": {
                        "pricing_basis": auction.pricing_basis,
                        "rate_direction": auction.rate_direction,
                        "benchmark": auction.procurement_target_rate,
                        "book_now_rate": auction.book_now_rate,
                        "vat_inclusive": auction.vat_included,
                    },

                    "bids": bid_information,

                    "rate_inclusive_of": {
                        "fuel": auction.rate_includes_fuel,
                        "waiting_detention_time": (
                            auction.rate_includes_waiting_time
                        ),
                        "driver": auction.rate_includes_driver,
                        "maintenance": auction.rate_includes_maintenance,
                        "insurance": auction.rate_includes_insurance,
                        "tolls": auction.rate_includes_tolls,
                        "border_charges": (
                            auction.rate_includes_border_charges
                        ),
                        "empty_return": auction.rate_includes_empty_return,
                        "loading_assistance_charges": (
                            auction.rate_includes_loading_assistance
                        ),
                        "offloading_assistance_charges": (
                            auction.rate_includes_offloading_assistance
                        ),
                    },

                    "accessorials": accessorial_information,
                    "escort_policy": escort_policy_information,
                },

                # -------------------------------------------------
                # TRUCK REQUIREMENTS
                # -------------------------------------------------

                "truck_requirements": [
                    {
                        "configuration_type": config.configuration_type,
                        "truck_type": config.truck_type,
                        "equipment_type": config.equipment_type,
                        "trailer_type": config.trailer_type,
                        "trailer_length": config.trailer_length,
                        "is_required": config.is_required,

                        "minimum_weight_bracket": (
                            auction.minimum_weight_bracket
                        ),

                        "compliance_requirements": {
                            "vehicle_tracking_required": (
                                auction.vehicle_tracking_required
                            ),
                            "all_time_hour_control_room": (
                                auction.all_time_hour_control_room
                            ),
                            "driver_mobile_phone": (
                                auction.driver_mobile_phone
                            ),
                            "clean_compliant_equipment": (
                                auction.clean_compliant_equipment
                            ),
                        },

                        "accessorials_requirement": {
                            "pallet_management": auction.pallet_management,
                            "tarpaulin_compliance_required": (
                                auction.tarpaulin_compliance_required
                            ),
                            "corner_plates_required": (
                                auction.corner_plates_required
                            ),
                            "chock_blocks_required": (
                                auction.chock_blocks_required
                            ),
                            "ratchets_belts_required": (
                                auction.ratchets_belts_required
                            ),
                            "other_equipment_requirements": (
                                auction.other_equipment_requirements
                            ),
                        },
                    }
                    for config in configs
                ],

                # -------------------------------------------------
                # INSURANCE REQUIREMENTS
                # -------------------------------------------------

                "insurance_requirements": {
                    "minimum_git_cover": (
                        auction.minimum_git_cover_amount
                    ),
                    "minimum_liability_cover": (
                        auction.minimum_liability_cover_amount
                    ),
                    "git_all_risk_required": (
                        auction.git_all_risk_required
                    ),
                    "git_first_loss_required": (
                        auction.git_first_loss_required
                    ),
                    "git_driver_fidelity_required": (
                        auction.git_driver_fidelity_required
                    ),
                },

                # -------------------------------------------------
                # TARGET SERVICE LEVELS
                # -------------------------------------------------

                "target_service_levels": target_service_levels,

                # -------------------------------------------------
                # PERMITS AND CERTIFICATIONS
                # -------------------------------------------------

                "permits_and_certifications": certification_information,

                # -------------------------------------------------
                # ROUTE AND FACILITY INFORMATION
                # -------------------------------------------------

                "route_facilities_information": {
                    "origin_facility": serialize_stop(origin),

                    "stop_facilities": [
                        serialize_stop(stop)
                        for stop in intermediate_stops
                    ],

                    "destination_facility": serialize_stop(destination),

                    # Complete ordered route, useful for map displays.
                    "route_sequence": [
                        serialize_stop(stop)
                        for stop in trip_points
                    ],
                },
            }

        # =========================================================
        # 5. SERIALIZE EVERY AUCTION IN THE GROUP
        # =========================================================

        shipment_details = [
            serialize_auction(auction)
            for auction in bundle_auctions
        ]

        # =========================================================
        # 6. BUILD CONSOLIDATED OVERVIEW
        # =========================================================

        def safe_number(value):
            """
            Return a numeric value for aggregate counts.
            Missing values are treated as zero.
            """
            if value is None:
                return 0

            try:
                return float(value)
            except (TypeError, ValueError):
                return 0

        status_counts = {}

        for auction in bundle_auctions:
            status = (
                auction.status.value
                if hasattr(auction.status, "value")
                else auction.status
            )

            status_key = str(status) if status is not None else "Unknown"

            status_counts[status_key] = (
                status_counts.get(status_key, 0) + 1
            )

        route_sequence = [
            {
                "auction_id": item["shipment_summary"]["id"],
                "shipment_reference": (
                    item["shipment_summary"]["shipment_reference"]
                ),
                "bundle_trip_sequence": (
                    item["shipment_summary"]["bundle_trip_sequence"]
                ),
                "bundle_role": item["shipment_summary"]["bundle_role"],
                "origin": item["shipment_summary"]["origin"],
                "destination": item["shipment_summary"]["destination"],
                "status": item["shipment_summary"]["status"],
            }
            for item in shipment_details
        ]

        total_trucks_required = sum(
            safe_number(auction.number_of_trucks_required)
            for auction in bundle_auctions
        )

        total_slots_remaining = sum(
            safe_number(auction.slots_remaining)
            for auction in bundle_auctions
        )

        total_bids = sum(
            item["auction_summary"]["bid_count"]
            for item in shipment_details
        )

        overview = {
            "group_type": "bundle" if is_bundle else "single_auction",

            "requested_auction_id": requested_auction.id,

            "bundle_id": requested_auction.bundle_id,
            "bundle_reference": requested_auction.bundle_reference,

            "total_auctions": len(bundle_auctions),

            "declared_stage_count": (
                bundle_metadata.get("stage_count")
                if bundle_metadata
                else None
            ),

            "status_counts": status_counts,

            "total_number_of_trucks_required": total_trucks_required,
            "total_slots_remaining": total_slots_remaining,
            "total_bids_received": total_bids,

            "route_sequence": route_sequence,

            # Each auction keeps its own rate and pricing basis.
            # Do not sum rates from different stages because they may
            # use different pricing bases or currencies.
            "stage_rates": [
                {
                    "auction_id": item["auction_summary"]["auction_id"],
                    "shipment_reference": (
                        item["shipment_summary"]["shipment_reference"]
                    ),
                    "pricing_basis": (
                        item["auction_summary"]["pricing_basis"]
                    ),
                    "rate_direction": (
                        item["auction_summary"]["rate_direction"]
                    ),
                    "benchmark": item["auction_summary"]["benchmark"],
                    "book_now_rate": (
                        item["auction_summary"]["book_now_rate"]
                    ),
                    "bid_count": item["auction_summary"]["bid_count"],
                }
                for item in shipment_details
            ],
        }

        # =========================================================
        # 7. FINAL RESPONSE
        # =========================================================

        return {
            "group_type": (
                "bundle" if is_bundle else "single_auction"
            ),

            "overview": overview,

            "bundle": bundle_metadata,

            # Retains the same collection key used by the shipment
            # endpoint. Each entry represents one auction/stage.
            "shipments": shipment_details,
        }

    except HTTPException:
        raise

    except Exception as e:
        print(
            f"ERROR loading shipment auction {id}: {str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to retrieve load exchange information: "
                f"{str(e)}"
            )
        )

        
@router.post("/award-auction/{auction_id}/bid/{bid_id}")
def award_auction_bid(
    auction_id: int,
    bid_id: int,
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
        result = accept_auction_bid(
            auction_id,
            bid_id,
            db,
            current_user
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

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
        # =========================================================
        # STEP 1 - GET REQUESTED TENDER
        # =========================================================

        print("STEP 1 - querying requested tender")

        tender = (
            db.query(Lane_Tender_RFQ)
            .filter(Lane_Tender_RFQ.id == id)
            .first()
        )

        if not tender:
            raise HTTPException(
                status_code=404,
                detail="Tender not found"
            )

        print(f"STEP 1 SUCCESS - Tender ID: {tender.id}")

        # =========================================================
        # STEP 2 - RESOLVE ROOT / PARENT TENDER
        # =========================================================

        print("STEP 2 - resolving tender family root")

        root_tender = tender

        # Walk upwards through parent_tender_id until the
        # top-level/root tender is reached.
        visited_tender_ids = set()

        while getattr(root_tender, "parent_tender_id", None):

            # Prevent an accidental circular parent relationship
            if root_tender.id in visited_tender_ids:
                raise HTTPException(
                    status_code=500,
                    detail="Circular tender parent relationship detected"
                )

            visited_tender_ids.add(root_tender.id)

            parent_tender = (
                db.query(Lane_Tender_RFQ)
                .filter(
                    Lane_Tender_RFQ.id == root_tender.parent_tender_id
                )
                .first()
            )

            if not parent_tender:
                break

            root_tender = parent_tender

        print(
            f"STEP 2 SUCCESS - Root Tender ID: {root_tender.id}"
        )

        # =========================================================
        # STEP 3 - GET COMPLETE TENDER FAMILY
        # =========================================================

        print("STEP 3 - querying tender family")

        child_tenders = (
            db.query(Lane_Tender_RFQ)
            .filter(
                Lane_Tender_RFQ.parent_tender_id == root_tender.id
            )
            .order_by(Lane_Tender_RFQ.id.asc())
            .all()
        )

        # Root + all child/sub-tenders
        tender_family = [root_tender] + child_tenders

        # Remove duplicates just in case the requested tender
        # happens to already be represented in the family.
        unique_tenders = []
        seen_tender_ids = set()

        for family_tender in tender_family:
            if family_tender.id not in seen_tender_ids:
                unique_tenders.append(family_tender)
                seen_tender_ids.add(family_tender.id)

        tender_family = unique_tenders

        print(
            f"STEP 3 SUCCESS - "
            f"{len(tender_family)} tender(s) in family"
        )

        # =========================================================
        # HELPER FUNCTION
        # =========================================================

        def build_tender_information(tender):

            print(
                f"Building information for tender {tender.id}"
            )

            # -----------------------------------------------------
            # STOPS
            # -----------------------------------------------------

            tender_stops = (
                db.query(Lane_Tender_RFQ_Stop)
                .filter(
                    Lane_Tender_RFQ_Stop.tender_id == tender.id
                )
                .order_by(Lane_Tender_RFQ_Stop.id.asc())
                .all()
            )

            # -----------------------------------------------------
            # VEHICLE CONFIGURATIONS
            # -----------------------------------------------------

            tender_vehicle_configs = (
                db.query(Lane_Tender_RFQ_Vehicle_Config)
                .filter(
                    Lane_Tender_RFQ_Vehicle_Config.tender_id == tender.id
                )
                .all()
            )

            # -----------------------------------------------------
            # VOLUME PROFILES
            # -----------------------------------------------------

            tender_volumes_profiles = (
                db.query(Lane_Tender_RFQ_Volume_Profile)
                .filter(
                    Lane_Tender_RFQ_Volume_Profile.tender_id == tender.id
                )
                .order_by(
                    Lane_Tender_RFQ_Volume_Profile.period_sequence.asc()
                )
                .all()
            )

            # -----------------------------------------------------
            # ACCESSORIALS
            # -----------------------------------------------------

            tender_accessorials = (
                db.query(Lane_Tender_RFQ_Accessorial)
                .filter(
                    Lane_Tender_RFQ_Accessorial.tender_id == tender.id
                )
                .all()
            )

            # -----------------------------------------------------
            # BIDS
            # -----------------------------------------------------

            bids = (
                db.query(Lane_Tender_RFQ_Bids)
                .filter(
                    Lane_Tender_RFQ_Bids.tender_id == tender.id
                )
                .all()
            )

            # =====================================================
            # RETURN TENDER
            # =====================================================

            return {

                # -------------------------------------------------
                # HIERARCHY INFORMATION
                # -------------------------------------------------

                "tender_hierarchy": {
                    "tender_id": tender.id,
                    "parent_tender_id": getattr(
                        tender,
                        "parent_tender_id",
                        None
                    ),
                    "is_parent_tender": (
                        tender.id == root_tender.id
                    ),
                    "is_child_tender": (
                        tender.id != root_tender.id
                    ),
                    "family_root_tender_id": root_tender.id,
                },

                # -------------------------------------------------
                # ROUTING / SCOPE
                # -------------------------------------------------

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

                    "stop_addresses": [
                        stop.address
                        for stop in tender_stops
                    ],

                    "destination_address": tender.destination_address,

                    "route_polyline": tender.polyline,

                    "border_customs_responsibility":
                        tender.border_customs_responsibility,

                    "distance": tender.actual_distance_km,
                    "priority_level": tender.priority_level,
                    "contract_start_date": tender.contract_start_date,
                    "contract_end_date": tender.contract_end_date,
                    "customer_reference": tender.customer_reference,
                },

                # -------------------------------------------------
                # LOAD REQUIREMENTS
                # -------------------------------------------------

                "load_requirements_and_vehicle_configurations": {

                    "allowed_vehicle_configurations": [
                        {
                            "configuration_type":
                                config.configuration_type,

                            "truck_type":
                                config.truck_type,

                            "equipment_type":
                                config.equipment_type,

                            "trailer_type":
                                config.trailer_type or "--------",

                            "trailer_length":
                                config.trailer_length or "--------",
                        }
                        for config in tender_vehicle_configs
                    ],

                    "commodity": tender.commodity,
                    "avg_shipment_weight":
                        tender.average_shipment_weight_kg,

                    "minimum_weight_bracket":
                        tender.minimum_weight_bracket_kg,

                    "packaging_type":
                        tender.packaging_type,

                    "packaging_quantity":
                        tender.packaging_quantity,

                    "temperature_control":
                        tender.temperature_control,

                    "hazardous_materials":
                        tender.hazardous_materials,

                    "under_bond":
                        tender.under_bond,

                    "rib_requirements":
                        tender.rib_requirements,

                    "minimum_git_cover":
                        tender.minimum_git_cover_amount,

                    "minimum_liability_cover_amount":
                        tender.minimum_liability_cover_amount,

                    "insurance_requirements": {
                        "minimum_git_cover":
                            tender.minimum_git_cover_amount,

                        "minimum_liability_cover_amount":
                            tender.minimum_liability_cover_amount,

                        "git_all_risk_required":
                            tender.git_all_risk_required,

                        "git_first_loss_required":
                            tender.git_first_loss_required,

                        "driver_fidelity_required":
                            tender.git_driver_fidelity_required,
                    },

                    "equipment_load_securing": {
                        "tarpaulin_required":
                            tender.tarpaulin_compliance_required,

                        "corner_plates_required":
                            tender.corner_plates_required,

                        "chock_blocks_required":
                            tender.chock_blocks_required,

                        "ratchets_belts_required":
                            tender.ratchets_belts_required,
                    },
                },

                # -------------------------------------------------
                # SEASONALITY / VOLUME
                # -------------------------------------------------

                "seasonality_and_volume_profile": {

                    "volume_pattern_behavior":
                        tender.volume_entry_method,

                    "volume_commitment":
                        tender.volume_commitment,

                    "volumes": [
                        {
                            "period_sequence":
                                profile.period_sequence,

                            "period_label":
                                profile.period_label,

                            "period_date_start":
                                profile.period_start_date,

                            "period_date_end":
                                profile.period_end_date,

                            "day_of_week":
                                profile.day_of_week or "",

                            "expected_loads":
                                profile.expected_loads,
                        }
                        for profile in tender_volumes_profiles
                    ],
                },

                # -------------------------------------------------
                # COMMERCIAL CONDITIONS
                # -------------------------------------------------

                "rates_commercial_conditions": {

                    "rate_basis":
                        tender.pricing_basis,

                    "current_incumbent_rate":
                        tender.incumbent_transport_rate_per_shipment,

                    "procurement_target_rate":
                        tender.procurement_target_rate,

                    "desired_rate_direction":
                        tender.rate_direction,

                    "rate_inclusive_of": {
                        "fuel":
                            tender.rate_includes_fuel,

                        "driver":
                            tender.rate_includes_driver,

                        "maintenance":
                            tender.rate_includes_maintenance,

                        "insurance":
                            tender.rate_includes_insurance,

                        "tolls":
                            tender.rate_includes_tolls,

                        "border_charges":
                            tender.rate_includes_border_charges,

                        "empty_return":
                            tender.rate_includes_empty_return,

                        "waiting_time":
                            tender.rate_includes_waiting_time,

                        "loading_assistance":
                            tender.rate_includes_loading_assistance,

                        "offloading_assistance":
                            tender.rate_includes_offloading_assistance,
                    },

                    "fuel_treatment":
                        tender.fuel_treatment_type,

                    "vat_included":
                        tender.vat_included,

                    "base_diesel_price":
                        tender.base_diesel_price,

                    "review_period":
                        tender.fuel_review_period,

                    "fuel_component":
                        tender.fuel_component_percentage,

                    "rate_validity":
                        tender.rate_validity,

                    "questions_deadline":
                        tender.questions_deadline,

                    "tender_closing_date":
                        tender.tender_closing_date,

                    "supplier_bid_evaluation": {
                        "evaluation_price_enabled":
                            tender.evaluation_price_enabled,

                        "evaluation_capacity_enabled":
                            tender.evaluation_capacity_enabled,

                        "evaluation_service_enabled":
                            tender.evaluation_service_enabled,

                        "evaluation_compliance_enabled":
                            tender.evaluation_compliance_enabled,

                        "evaluation_flexibility_enabled":
                            tender.evaluation_flexibility_enabled,
                    },
                },

                # -------------------------------------------------
                # OPERATIONAL / COMPLIANCE / RISK
                # -------------------------------------------------

                "operational_compliance_risk_requirements": {

                    "proof_of_delivery_submissions": {
                        "local_hauls":
                            tender.pod_submission_local,

                        "long_hauls":
                            tender.pod_submission_long_haul,

                        "cross_border":
                            tender.pod_submission_cross_border,

                        "delivery_docs_sla":
                            tender.delivery_documentation_sla,
                    },

                    "claims_risk_management_governance": {
                        "claims_policy_framework":
                            tender.claims_risk_policy,

                        "special_risk_claims_protocol_":
                            tender.claims_risk_requirements,
                    },

                    "required_operational_conditions": {
                        "vehicle_tracking_required":
                            tender.vehicle_tracking_required,

                        "24_hour_control_room":
                            tender.all_time_hour_control_room,

                        "driver_mobile_phone":
                            tender.driver_mobile_phone,

                        "clean_compliant_equipment":
                            tender.clean_compliant_equipment,

                        "pallet_management":
                            tender.pallet_management,
                    },

                    "subcontracting_policy":
                        tender.subcontracting_policy,
                },

                # -------------------------------------------------
                # ACCESSORIALS
                # -------------------------------------------------

                "accessorials": [
                    {
                        column.name: getattr(accessorial, column.name)
                        for column in accessorial.__table__.columns
                    }
                    for accessorial in tender_accessorials
                ],

                # -------------------------------------------------
                # BIDS
                # -------------------------------------------------

                "bids": [
                    {
                        column.name: getattr(bid, column.name)
                        for column in bid.__table__.columns
                    }
                    for bid in bids
                ],
            }

        # =========================================================
        # STEP 4 - BUILD EVERY FAMILY MEMBER
        # =========================================================

        print("STEP 4 - building tender family information")

        family_data = []

        for family_tender in tender_family:
            family_data.append(
                build_tender_information(family_tender)
            )

        print("STEP 4 SUCCESS")

        # =========================================================
        # STEP 5 - RETURN FAMILY
        # =========================================================

        return {
            "tender_family_information": {
                "family_root_tender_id": root_tender.id,
                "requested_tender_id": id,
                "family_size": len(family_data),
                "has_family": len(family_data) > 1,
                "tenders": family_data,
            }
        }

    except HTTPException:
        raise

    except Exception as e:
        print(f"ERROR retrieving tender family: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

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