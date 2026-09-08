from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.Exchange.ftl_shipment import Client_Shipment_Auction, Client_Shipment_Auction_Stop, Client_Shipment_Auction_Vehicle_Requirement
from models.Exchange.dedicated_ftl_lane import Lane_Tender_RFQ, Lane_Tender_RFQ_Stop, Lane_Tender_RFQ_Vehicle_Config, Lane_Tender_RFQ_Volume_Profile, Lane_Tender_RFQ_Accessorial
from models.brokerage.loadboard import Shipment_Auction_Loadboard, Lane_Tender_Loadboard
from models.shipper import Corporation
from models.Exchange.dedicated_ftl_lane import Lane_Tender_RFQ_Stop, Lane_Tender_RFQ_Vehicle_Config, Lane_Tender_RFQ_Volume_Profile, Lane_Tender_RFQ_Accessorial, Turnaround_Window_Demurrage_Protocals, Carrier_Certification_Driver_Standards, Escort_Policy, Sla_incident_Reporting
from models.Exchange.auction import Exchange_FTL_Shipment_Bid, Exchange_FTL_Lane_Bid, Exchange_POWER_Shipment_Bid, Shipment_Auction_Bid, Lane_Tender_RFQ_Bids
from models.brokerage.loadboards.exchange_loadboards import Exchange_Ftl_Load_Board, Exchange_Ftl_Lane_LoadBoard
from models.carrier import Carrier
from schemas.brokerage.loadboard import IndividualLoadboardShipmentRequest
from schemas.brokerage.exchange_loadboards import Exchange_Ftl_Load_Board_Response, Exchange_Ftl_Loadboard_Summary_Response
from schemas.exchange_bookings.auction import Exchange_FTL_Lane_Bid_Create, Exchange_FTL_Shipment_Bid_Create, Exchange_FTL_Exchange_Loadboard_BidResponse, Exchange_POWER_Shipment_Bid_Create, Exchange_Power_Exchange_Loadboard_BidResponse, Create_Shipment_Bid
from schemas.exchange_bookings.ftl_shipment import Exchange_Ftl_Shipments_Summary_Response
from services.exchange.auction import place_auction_bid
from utils.auth import get_current_user

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/shipment-loadboard")
def get_shipments_loadboard(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")
    carrier = db.query(Carrier).filter(Carrier.id == company_id).first()
    if not carrier:
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")

    try:
        loadboards = db.query(Shipment_Auction_Loadboard).filter(
            Shipment_Auction_Loadboard.is_visible_to_carriers == True,
            Shipment_Auction_Loadboard.status == "Active"
        ).all()

        response = []

        for loadboard in loadboards:
            auction_id = loadboard.auction_id

            auction = db.query(Client_Shipment_Auction).filter(
                Client_Shipment_Auction.id == auction_id
            ).first()
            if not auction:
                continue

            client = db.query(Corporation).filter(
                Corporation.id == auction.client_id
            ).first()

            route_points = db.query(Client_Shipment_Auction_Stop).filter(
                Client_Shipment_Auction_Stop.auction_id == auction_id
            ).order_by(
                Client_Shipment_Auction_Stop.stop_sequence.asc()
            ).all()

            origin = next(
                (stop for stop in route_points if stop.stop_type == "Origin"),
                None
            )
            destination = next(
                (stop for stop in route_points if stop.stop_type == "Destination"),
                None
            )
            intermediate_stops = [
                stop for stop in route_points
                if stop.stop_type == "Intermediate"
            ]

            if not origin or not destination:
                continue

            pickup_window = None
            if origin.operating_start_time and origin.operating_end_time:
                pickup_window = f"{origin.operating_start_time} - {origin.operating_end_time}"

            delivery_window = None
            if destination.operating_start_time and destination.operating_end_time:
                delivery_window = f"{destination.operating_start_time} - {destination.operating_end_time}"

            vehicle_configurations = db.query(
                Client_Shipment_Auction_Vehicle_Requirement
            ).filter(
                Client_Shipment_Auction_Vehicle_Requirement.auction_id == auction_id
            ).all()

            requirements = [
                {
                    "configuration_type": config.configuration_type,
                    "truck_type": config.truck_type,
                    "equipment_type": config.equipment_type,
                    "trailer_type": config.trailer_type,
                    "trailer_length": config.trailer_length
                }
                for config in vehicle_configurations
            ]

            response.append({
                "id": loadboard.auction_id,
                "trip_type": loadboard.trip_type,
                "client": client.legal_business_name if client else None,
                "closing_date": loadboard.auction_closing_date,
                "route": {
                    "origin": {
                        "pickup": origin.complete_address or origin.address,
                        "facility_name": origin.facility_name or None,
                        "pickup_date": loadboard.pickup_date,
                        "pickup_window": pickup_window
                    },
                    "destination": {
                        "delivery": destination.complete_address or destination.address,
                        "facility_name": destination.facility_name or None,
                        "eta_date": loadboard.eta_date,
                        "delivery_window": delivery_window
                    },
                    "distance": loadboard.distance,
                    "minimum_transit_time": loadboard.estimated_transit_time,
                    "stops": len(intermediate_stops) if intermediate_stops else None,
                    "polyline": loadboard.polyline
                },
                "commodity": loadboard.commodity,
                "shipment_weight": loadboard.shipment_weight,
                "hazardous_materials": {
                    "hazardous": loadboard.hazardous_materials,
                    "hazchem_classification": loadboard.hazchem_classification if loadboard.hazchem_classification else None
                },
                "required_equipment_specification": requirements,
                "number_of_trucks_required": loadboard.number_of_trucks_required,
                "slot_remaining": loadboard.slots_remaining,
                "rate": {
                    "rate_basis": loadboard.pricing_basis,
                    "benchmark_rate": loadboard.benchmark_rate,
                    "benchmark_service_fee": loadboard.benchmark_rate_service_fee,
                    "book_now_rate": loadboard.book_now_rate if loadboard.book_now_rate else None,
                    "vat_included": loadboard.vat_included,
                    "bidding_allowed": loadboard.bidding_activated,
                    "bidding_direction": loadboard.rate_direction
                }
            })

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve shipment loadboard: {str(e)}"
        )

@router.get("/shipment-loadboard/{id}")
def get_loadboard_shipment(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")
    carrier = db.query(Carrier).filter(Carrier.id == company_id).first()
    if not carrier:
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")
    try:
        load = db.query(Shipment_Auction_Loadboard).filter(
            Shipment_Auction_Loadboard.auction_id == id,
            Shipment_Auction_Loadboard.is_visible_to_carriers == True
        ).first()
        if not load:
            raise HTTPException(status_code=404, detail="Loadboard shipment not found or not available")
        auction = db.query(Client_Shipment_Auction).filter(
            Client_Shipment_Auction.id == load.auction_id
        ).first()
        if not auction:
            raise HTTPException(status_code=404, detail="Auction not found")
        bids = db.query(Shipment_Auction_Bid).filter(Shipment_Auction_Bid.auction_id == auction.id,
                                                    Shipment_Auction_Bid.carrier_id == company_id).all()

        client = db.query(Corporation).filter(
            Corporation.id == auction.client_id
        ).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        route_points = db.query(Client_Shipment_Auction_Stop).filter(
            Client_Shipment_Auction_Stop.auction_id == auction.id
        ).order_by(
            Client_Shipment_Auction_Stop.stop_sequence.asc()
        ).all()
        if not route_points:
            raise HTTPException(status_code=404, detail="Route information not found")
        vehicle_configurations = db.query(
            Client_Shipment_Auction_Vehicle_Requirement
        ).filter(
            Client_Shipment_Auction_Vehicle_Requirement.auction_id == auction.id
        ).all()
        origin = next(
            (stop for stop in route_points if stop.stop_type == "Origin"),
            None
        )
        destination = next(
            (stop for stop in route_points if stop.stop_type == "Destination"),
            None
        )
        intermediate_stops = [
            stop for stop in route_points
            if stop.stop_type == "Intermediate"
        ]
        if not origin:
            raise HTTPException(status_code=500, detail="Origin stop not found")
        if not destination:
            raise HTTPException(status_code=500, detail="Destination stop not found")
        return {
            "load_information": {
                "id": load.auction_id,
                "client": client.legal_business_name,
                "closing_date": load.auction_closing_date,
                "trip_type": load.trip_type,
                "load_type": load.load_type,
                "priority_level": load.priority_level,
                "payment_terms": load.payment_terms,
                "pickup_date": load.pickup_date,
                "number_of_trucks_required": load.number_of_trucks_required,
                "remaining_slots": load.slots_remaining,
                "route": {
                    "origin": origin.city_province,
                    "stops": [
                        {
                            "location": stop.city_province,
                        }
                        for stop in intermediate_stops
                    ],
                    "destination": destination.city_province,
                    "distance": load.distance,
                    "transit_time": load.estimated_transit_time,
                    "eta_date": getattr(load, "eta_date", None),
                    "polyline": load.polyline,
                    "stop_count": len(intermediate_stops),
                },
                "exchange_and_bidding": {
                    "rules": {
                        "rate_basis": load.pricing_basis,
                        "vat_included": load.vat_included,
                        "bidding_allowed": load.bidding_activated,
                        "bidding_direction": load.rate_direction,
                    },
                    "my_placed_bids": [{
                        "id": bid.id,
                        "rate": bid.rate,
                        "no_of_loads": bid.number_of_loads,
                        "lead_time": bid.lead_time,
                        "notes": bid.notes,
                        "submitted_at": bid.submitted_at,
                    } for bid in bids],
                    "rates": {
                        "benchmark_rate": load.benchmark_rate,
                        "benchmark_rate_service_fee": load.benchmark_rate_service_fee,
                        "book_now_rate": load.book_now_rate,
                    },
                    "rates_inclusive_of": {
                        "fuel": load.rate_includes_fuel,
                        "driver": load.rate_includes_driver,
                        "maintenance": load.rate_includes_maintenance,
                        "insurance": load.rate_includes_insurance,
                        "tolls": load.rate_includes_tolls,
                        "border_fees_and_duty": load.rate_includes_border_charges,
                        "empty_return": load.rate_includes_empty_return,
                        "waiting_detention_time": load.rate_includes_waiting_time,
                        "loading_assistance": load.rate_includes_loading_assistance,
                        "offloading_assistance": load.rate_includes_offloading_assistance,
                    },
                },
                "equipment": {
                    "accepted_vehicle_configs": [
                        {
                            "config_type": config.configuration_type,
                            "truck_type": config.truck_type,
                            "equipment_type": config.equipment_type,
                            "trailer_type": config.trailer_type,
                            "trailer_length": config.trailer_length,
                            "is_required": config.is_required,
                        }
                        for config in vehicle_configurations
                    ],
                    "equipment_compliance": {
                        "tarpaulin_compliance_required": load.tarpaulin_compliance_required,
                        "corner_plates_required": load.corner_plates_required,
                        "chock_blocks_required": load.chock_blocks_required,
                        "ratchets_belts_required": load.ratchets_belts_required,
                        "other_equipment_requirements": load.other_equipment_requirements,
                    },
                },
                "cargo": {
                    "commodity": load.commodity,
                    "weight": load.shipment_weight,
                    "packaging_type": load.packaging_type,
                    "packaging_quantity": load.packaging_quantity,
                    "under_bond": load.under_bond,
                    "hazardous": {
                        "is_hazardous": load.hazardous_materials,
                        "hazchem_classification": getattr(load, "hazchem_classification", None),
                    },
                },
                "insurance_requirements": {
                    "minimum_git_cover_amount": load.minimum_git_cover_amount,
                    "minimum_liability_cover_amount": load.minimum_liability_cover_amount,
                    "git_all_risk_required": load.git_all_risk_required,
                    "git_first_loss_required": load.git_first_loss_required,
                    "git_driver_fidelity_required": load.git_driver_fidelity_required,
                },
                "operational_requirements": {
                    "vehicle_tracking_required": load.vehicle_tracking_required,
                    "all_time_hour_control_room": load.all_time_hour_control_room,
                    "driver_mobile_phone": load.driver_mobile_phone,
                    "clean_compliant_equipment": load.clean_compliant_equipment,
                    "pallet_management_chep": load.pallet_management,
                    "pod_submission_local": load.pod_submission_local,
                    "pod_submission_long_haul": load.pod_submission_long_haul,
                    "pod_submission_cross_border": load.pod_submission_cross_border,
                },
                "facilities": [
                    {
                        "sequence": facility.stop_sequence,
                        "type": facility.stop_type,
                        "name": facility.facility_name,
                        "location": facility.city_province,
                        "country": facility.country,
                        "scheduling_type": facility.scheduling_type,
                        "operations_window": f"{facility.operating_start_time} - {facility.operating_end_time}",
                        "operating_days": {
                            "monday": facility.open_monday,
                            "tuesday": facility.open_tuesday,
                            "wednesday": facility.open_wednesday,
                            "thursday": facility.open_thursday,
                            "friday": facility.open_friday,
                            "saturday": facility.open_saturday,
                            "sunday": facility.open_sunday,
                        },
                    }
                    for facility in route_points
                ],
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/place-exchange/{id}-bid")
def place_exchange_bid(
    id: int,
    bid_data: Create_Shipment_Bid,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")
    try:
        result = place_auction_bid(
            id,
            bid_data,
            db,
            current_user
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/tender-loadboard")
def get_loadboard_tenders(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # ========================================================
    # 1. GET CURRENT USER / CARRIER
    # ========================================================

    assert "company_id" in current_user, "Missing company_id in current_user"

    print(f"current_user: {current_user}")

    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    carrier = (
        db.query(Carrier)
        .filter(Carrier.id == company_id)
        .first()
    )

    if not carrier:
        raise HTTPException(
            status_code=400,
            detail="Carrier not found, not verified, or not active"
        )

    # ========================================================
    # 2. GET ALL TENDERS VISIBLE TO CARRIERS
    # ========================================================

    loadboard_tenders = (
        db.query(Lane_Tender_Loadboard)
        .filter(
            Lane_Tender_Loadboard.is_visible_to_carriers == True,
            Lane_Tender_Loadboard.status == "open"
        )
        .order_by(
            Lane_Tender_Loadboard.bid_closing_date.asc()
        )
        .all()
    )

    # ========================================================
    # 3. BUILD LOADBOARD RESPONSE
    # ========================================================

    response = []

    for loadboard_tender in loadboard_tenders:

        # ====================================================
        # 3.1 GET MASTER TENDER
        # ====================================================

        tender = (
            db.query(Lane_Tender_RFQ)
            .filter(
                Lane_Tender_RFQ.id == loadboard_tender.tender_id
            )
            .first()
        )

        if not tender:
            continue

        # ====================================================
        # 3.2 GET SHIPPER
        # ====================================================

        client = (
            db.query(Corporation)
            .filter(
                Corporation.id == tender.client_id
            )
            .first()
        )

        # ====================================================
        # 3.3 GET ALL ROUTE STOPS
        # ====================================================

        route_points = (
            db.query(Lane_Tender_RFQ_Stop)
            .filter(
                Lane_Tender_RFQ_Stop.tender_id == tender.id
            )
            .order_by(
                Lane_Tender_RFQ_Stop.stop_sequence.asc()
            )
            .all()
        )

        # ----------------------------------------------------
        # Skip malformed tenders with no stops
        # ----------------------------------------------------

        if not route_points:
            continue

        # ====================================================
        # 3.4 IDENTIFY ORIGIN / DESTINATION / STOPS
        # ====================================================

        origin_stop = route_points[0]

        destination_stop = route_points[-1]

        intermediate_stops = route_points[1:-1]

        # ====================================================
        # 3.5 BUILD ROUTE RESPONSE
        # ====================================================

        origin = {
            "stop_sequence": origin_stop.stop_sequence,
            "address": origin_stop.address,
            "complete_address": origin_stop.complete_address,
            "city_province": origin_stop.city_province,
            "country": origin_stop.country,
            "region": origin_stop.region,
        }

        destination = {
            "stop_sequence": destination_stop.stop_sequence,
            "address": destination_stop.address,
            "complete_address": destination_stop.complete_address,
            "city_province": destination_stop.city_province,
            "country": destination_stop.country,
            "region": destination_stop.region,
        }

        stops = [
            {
                "stop_sequence": stop.stop_sequence,
                "address": stop.address,
                "complete_address": stop.complete_address,
                "city_province": stop.city_province,
                "country": stop.country,
                "region": stop.region,
            }
            for stop in intermediate_stops
        ]

        # ====================================================
        # 3.6 GET EQUIPMENT REQUIREMENTS
        # ====================================================

        equipment_requirements = (
            db.query(Lane_Tender_RFQ_Vehicle_Config)
            .filter(
                Lane_Tender_RFQ_Vehicle_Config.tender_id == tender.id
            )
            .all()
        )

        # ====================================================
        # 3.7 BUILD TENDER CARD
        # ====================================================

        response.append({
            # ------------------------------------------------
            # IDENTITY
            # ------------------------------------------------

            "id": loadboard_tender.id,
            "tender_id": tender.id,
            "closing_date": loadboard_tender.bid_closing_date,
            "questions_deadline": loadboard_tender.questions_deadline,
            "title": loadboard_tender.tender_title,
            "tender_category": loadboard_tender.tender_category,
            "tender_length_category": (
                loadboard_tender.tender_length_category
            ),
            "shipper": (
                client.legal_business_name
                if client
                else None
            ),
            # ------------------------------------------------
            # ROUTE
            # ------------------------------------------------
            "route": {
                "origin": origin,
                "stops": stops,
                "destination": destination,
                "total_stops": len(route_points),
                "distance_km": (
                    loadboard_tender.actual_distance_km
                ),
                "polyline": loadboard_tender.polyline,
            },
            # ------------------------------------------------
            # CONTRACT
            # ------------------------------------------------
            "contract": {
                "start_date": (
                    loadboard_tender.contract_start_date
                ),
                "end_date": (
                    loadboard_tender.contract_end_date
                ),
            },
            # ------------------------------------------------
            # CARGO
            # ------------------------------------------------
            "cargo": {
                "commodity": (
                    loadboard_tender.commodity
                ),
                "load_type": (
                    loadboard_tender.load_type
                ),
                "average_shipment_weight_kg": (
                    loadboard_tender.average_shipment_weight_kg
                ),
                "minimum_weight_bracket_kg": (
                    loadboard_tender.minimum_weight_bracket_kg
                ),
                "packaging_type": (
                    loadboard_tender.packaging_type
                ),
                "packaging_quantity": (
                    loadboard_tender.packaging_quantity
                ),
                "temperature_control": (
                    loadboard_tender.temperature_control
                ),
                "target_temperature_spec": (
                    loadboard_tender.target_temperature_spec
                ),
                "under_bond": (
                    loadboard_tender.under_bond
                ),
                "hazchem": {
                    "hazardous_materials": (
                        loadboard_tender.hazardous_materials
                    ),

                    "hazchem_classification": (
                        loadboard_tender.hazchem_classification
                    ),
                },
            },
            # ------------------------------------------------
            # VOLUME
            # ------------------------------------------------
            "volume": {
                "entry_method": (
                    loadboard_tender.volume_entry_method
                ),
                "commitment": (
                    loadboard_tender.volume_commitment
                ),
            },
            # ------------------------------------------------
            # EQUIPMENT
            # ------------------------------------------------
            "required_equipment_specification": [
                {
                    "config_type": (
                        equipment.configuration_type
                    ),
                    "truck_type": (
                        equipment.truck_type
                    ),
                    "equipment_type": (
                        equipment.equipment_type
                    ),
                    "trailer_type": (
                        equipment.trailer_type
                    ),
                    "trailer_length": (
                        equipment.trailer_length
                    ),
                }
                for equipment in equipment_requirements
            ],
        })

    # ========================================================
    # 4. RETURN ALL TENDERS
    # ========================================================

    return {
        "count": len(response),
        "tenders": response
    }

@router.get("/tender-loadboard/{id}")
def get_tender_loadboard(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):

    # ============================================================
    # 1. VALIDATE CURRENT CARRIER
    # ============================================================

    assert "company_id" in current_user, "Missing company_id in current_user"

    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    carrier = (
        db.query(Carrier)
        .filter(Carrier.id == company_id)
        .first()
    )

    if not carrier:
        raise HTTPException(
            status_code=400,
            detail="Carrier not found, not verified, or not active"
        )

    try:

        # ========================================================
        # 2. GET LOADBOARD RECORD
        # ========================================================

        loadboard_tender = (
            db.query(Lane_Tender_Loadboard)
            .filter(
                Lane_Tender_Loadboard.id == id
            )
            .first()
        )

        if not loadboard_tender:
            raise HTTPException(
                status_code=404,
                detail="Tender loadboard record not found"
            )

        # ========================================================
        # 3. GET SELECTED TENDER
        # ========================================================

        selected_tender = (
            db.query(Lane_Tender_RFQ)
            .filter(
                Lane_Tender_RFQ.id == loadboard_tender.tender_id
            )
            .first()
        )

        if not selected_tender:
            raise HTTPException(
                status_code=404,
                detail="Tender not found"
            )

        # ========================================================
        # 4. DETERMINE TENDER FAMILY / ROOT TENDER
        #
        # If this tender is a child tender, move to its parent.
        # If it is already the parent, use itself.
        # ========================================================

        root_tender = selected_tender

        if getattr(selected_tender, "parent_tender_id", None):

            root_tender = (
                db.query(Lane_Tender_RFQ)
                .filter(
                    Lane_Tender_RFQ.id ==
                    selected_tender.parent_tender_id
                )
                .first()
            )

            if not root_tender:
                raise HTTPException(
                    status_code=404,
                    detail="Parent tender not found"
                )

        # ========================================================
        # 5. GET ALL SUB-TENDERS
        #
        # The parent itself is also included in the tender family.
        # ========================================================

        child_tenders = (
            db.query(Lane_Tender_RFQ)
            .filter(
                Lane_Tender_RFQ.parent_tender_id ==
                root_tender.id
            )
            .order_by(
                Lane_Tender_RFQ.id.asc()
            )
            .all()
        )

        # Parent + children
        tender_family = [root_tender] + child_tenders

        # Remove duplicates defensively
        unique_tenders = {}
        for t in tender_family:
            unique_tenders[t.id] = t

        tender_family = list(unique_tenders.values())

        # ========================================================
        # 6. GET SHIPPER / COMPANY
        # ========================================================

        client = (
            db.query(Corporation)
            .filter(
                Corporation.id == root_tender.client_id
            )
            .first()
        )

        shipper_information = {
            "company_id": (
                client.id
                if client
                else root_tender.client_id
            ),
            "legal_business_name": (
                client.legal_business_name
                if client
                else None
            )
        }

        # ========================================================
        # 7. HELPER FOR VOLUME CALCULATION
        # ========================================================

        def calculate_tender_volume(tender_id):

            profiles = (
                db.query(Lane_Tender_RFQ_Volume_Profile)
                .filter(
                    Lane_Tender_RFQ_Volume_Profile.tender_id ==
                    tender_id
                )
                .order_by(
                    Lane_Tender_RFQ_Volume_Profile.period_sequence.asc()
                )
                .all()
            )

            total_loads = sum(
                (profile.expected_loads or 0)
                for profile in profiles
            )

            return profiles, total_loads

        def get_tender_volume(tender_id):
            """
            Returns the total expected loads for one tender.
            """
            profiles = (
                db.query(Lane_Tender_RFQ_Volume_Profile)
                .filter(
                    Lane_Tender_RFQ_Volume_Profile.tender_id == tender_id
                )
                .all()
            )

            return sum(
                (profile.expected_loads or 0)
                for profile in profiles
            )


        # ------------------------------------------------------------
        # TOTAL FAMILY VOLUME
        # ------------------------------------------------------------

        total_estimated_movements = sum(
            get_tender_volume(t.id)
            for t in tender_family
        )


        # ------------------------------------------------------------
        # COLLECT ORIGINS / DESTINATIONS FROM ALL TENDERS
        # ------------------------------------------------------------

        origin_locations = []
        destination_regions = []

        for family_tender in tender_family:

            family_stops = (
                db.query(Lane_Tender_RFQ_Stop)
                .filter(
                    Lane_Tender_RFQ_Stop.tender_id == family_tender.id
                )
                .order_by(
                    Lane_Tender_RFQ_Stop.stop_sequence.asc()
                )
                .all()
            )

            if not family_stops:
                continue

            family_origin = family_stops[0]
            family_destination = family_stops[-1]

            # --------------------------------------------------------
            # ORIGIN
            # --------------------------------------------------------

            origin_value = getattr(
                family_origin,
                "city_province",
                None
            )

            if origin_value:
                origin_value = origin_value.strip()

                if origin_value not in origin_locations:
                    origin_locations.append(origin_value)

            # --------------------------------------------------------
            # DESTINATION REGION
            # --------------------------------------------------------

            destination_value = getattr(
                family_destination,
                "region",
                None
            )

            if destination_value:
                destination_value = destination_value.strip()

                if destination_value not in destination_regions:
                    destination_regions.append(destination_value)


        # ------------------------------------------------------------
        # CLIENT NAME
        # ------------------------------------------------------------

        client_name = (
            client.legal_business_name
            if client
            else "the Client"
        )


        # ------------------------------------------------------------
        # FORMAT ORIGINS
        # ------------------------------------------------------------

        if len(origin_locations) == 1:

            origin_text = origin_locations[0]

        elif len(origin_locations) == 2:

            origin_text = (
                f"{origin_locations[0]} and "
                f"{origin_locations[1]}"
            )

        elif len(origin_locations) > 2:

            origin_text = (
                ", ".join(origin_locations[:-1])
                + " and "
                + origin_locations[-1]
            )

        else:

            origin_text = "the Client's designated facilities"


        # ------------------------------------------------------------
        # FORMAT DESTINATIONS
        # ------------------------------------------------------------

        if len(destination_regions) == 1:

            destination_text = destination_regions[0]

        elif len(destination_regions) == 2:

            destination_text = (
                f"{destination_regions[0]} and "
                f"{destination_regions[1]}"
            )

        elif len(destination_regions) > 2:

            destination_text = (
                ", ".join(destination_regions[:-1])
                + " and "
                + destination_regions[-1]
            )

        else:

            destination_text = "approved destinations across the SADC region"


        # ------------------------------------------------------------
        # PAYMENT TERMS
        #
        # PRIMARY / ROOT TENDER ONLY
        # ------------------------------------------------------------

        payment_terms = getattr(
            root_tender,
            "payment_terms",
            None
        )

        if payment_terms:
            payment_terms_text = str(payment_terms)
        else:
            payment_terms_text = (
                "the applicable contractual payment terms"
            )


        # ------------------------------------------------------------
        # MOVEMENT WORDING
        # ------------------------------------------------------------

        movement_word = (
            "movement"
            if total_estimated_movements == 1
            else "movements"
        )


        # ------------------------------------------------------------
        # FINAL CORPORATE INVITATION
        # ------------------------------------------------------------

        tender_invitation = (
            "SADC FREIGHTLINK, as the appointed freight procurement "
            "and transportation partner acting on behalf of the Client, "
            "invites suitably qualified and compliant transport operators "
            "to participate in this Request for Quotation (RFQ). "
            
            f"The RFQ seeks competitive rates for an estimated "
            f"{total_estimated_movements:,} cross-border transportation "
            f"{movement_word} over the applicable contract period, "
            f"servicing freight originating from the Client's "
            f"{origin_text} facilities and destined for approved "
            f"locations across the SADC region. "
            
            f"The anticipated commercial payment term is "
            f"{payment_terms_text}, subject to the applicable contractual "
            "and invoicing requirements."
        )

        # ========================================================
        # 8. BUILD EACH FULL TENDER
        # ========================================================

        full_tenders = []

        combined_total_loads = 0
        combined_total_tonnage_kg = 0

        combined_cargoes = set()
        combined_load_types = set()
        combined_equipment = set()
        combined_corridors = []

        for tender in tender_family:

            # ====================================================
            # ROUTE / STOPS
            # ====================================================

            route_points = (
                db.query(Lane_Tender_RFQ_Stop)
                .filter(
                    Lane_Tender_RFQ_Stop.tender_id ==
                    tender.id
                )
                .order_by(
                    Lane_Tender_RFQ_Stop.stop_sequence.asc()
                )
                .all()
            )

            if not route_points:
                continue

            origin_stop = route_points[0]
            destination_stop = route_points[-1]
            intermediate_stops = route_points[1:-1]

            # ====================================================
            # STOP DEMURRAGE / TURNAROUND
            # ====================================================

            def build_stop(stop):

                turnaround = (
                    db.query(
                        Turnaround_Window_Demurrage_Protocals
                    )
                    .filter(
                        Turnaround_Window_Demurrage_Protocals.tender_id ==
                        tender.id,
                        Turnaround_Window_Demurrage_Protocals.stop_id ==
                        stop.id
                    )
                    .first()
                )

                return {
                    "stop_id": stop.id,
                    "stop_sequence": stop.stop_sequence,
                    "facility_name": getattr(
                        stop,
                        "facility_name",
                        None
                    ),
                    "address": stop.address,
                    "complete_address": getattr(
                        stop,
                        "complete_address",
                        None
                    ),
                    "city_province": getattr(
                        stop,
                        "city_province",
                        None
                    ),
                    "country": getattr(
                        stop,
                        "country",
                        None
                    ),
                    "region": getattr(
                        stop,
                        "region",
                        None
                    ),

                    "turnaround_and_demurrage": (
                        {
                            "demurrage_conditions":
                                turnaround.demurrage_conditions,

                            "loading_offloading_turnaround_hours":
                                turnaround.loading_offloading_turnaround_hours,

                            "free_demurrage_hours":
                                turnaround.free_demurrage_hours,

                            "demurrage_rate_per_hour":
                                turnaround.demurrage_rate_per_hour,

                            "maximum_demurrage_incursion_hours":
                                turnaround.maximum_demurrage_incursion_hours
                        }
                        if turnaround
                        else None
                    )
                }

            origin = build_stop(origin_stop)

            destination = build_stop(destination_stop)

            stops = [
                build_stop(stop)
                for stop in intermediate_stops
            ]

            # ====================================================
            # EQUIPMENT
            # ====================================================

            equipment_requirements = (
                db.query(
                    Lane_Tender_RFQ_Vehicle_Config
                )
                .filter(
                    Lane_Tender_RFQ_Vehicle_Config.tender_id ==
                    tender.id
                )
                .all()
            )

            equipment_response = []

            for equipment in equipment_requirements:

                equipment_response.append({
                    "configuration_type":
                        equipment.configuration_type,

                    "truck_type":
                        equipment.truck_type,

                    "equipment_type":
                        equipment.equipment_type,

                    "trailer_type":
                        equipment.trailer_type,

                    "trailer_length":
                        equipment.trailer_length
                })

                if equipment.equipment_type:
                    combined_equipment.add(
                        equipment.equipment_type
                    )

                if equipment.trailer_type:
                    combined_equipment.add(
                        equipment.trailer_type
                    )

            # ====================================================
            # VOLUME
            # ====================================================

            volume_profiles, tender_total_loads = (
                calculate_tender_volume(tender.id)
            )

            combined_total_loads += tender_total_loads

            shipment_weight = (
                tender.average_shipment_weight_kg or 0
            )

            combined_total_tonnage_kg += (
                shipment_weight * tender_total_loads
            )

            if tender.commodity:
                combined_cargoes.add(
                    tender.commodity
                )

            if tender.load_type:
                combined_load_types.add(
                    tender.load_type
                )

            # ====================================================
            # CORRIDOR
            # ====================================================

            origin_name = (
                origin_stop.city_province
                or origin_stop.address
            )

            destination_name = (
                destination_stop.city_province
                or destination_stop.address
            )

            corridor = (
                f"{origin_name} → {destination_name}"
            )

            combined_corridors.append(corridor)

            # ====================================================
            # CERTIFICATION REQUIREMENTS
            # ====================================================

            certifications = (
                db.query(
                    Carrier_Certification_Driver_Standards
                )
                .filter(
                    Carrier_Certification_Driver_Standards.tender_id ==
                    tender.id
                )
                .all()
            )

            certification_response = [
                {
                    "certification_name":
                        certification.certification_name,

                    "driver_qualification_security_directives":
                        certification.driver_qualification_security_directives,

                    "is_required":
                        certification.is_required
                }
                for certification in certifications
            ]

            # ====================================================
            # ESCORT POLICY
            # ====================================================

            escort_policy = (
                db.query(Escort_Policy)
                .filter(
                    Escort_Policy.tender_id ==
                    tender.id
                )
                .first()
            )

            escort_response = (
                {
                    "armed_escort_required":
                        escort_policy.armed_escort_required,

                    "escort_expense_responsible_party":
                        escort_policy.escort_expense_responsible_party
                }
                if escort_policy
                else None
            )

            # ====================================================
            # SLA / INCIDENT REPORTING
            # ====================================================

            sla_reporting = (
                db.query(Sla_incident_Reporting)
                .filter(
                    Sla_incident_Reporting.tender_id ==
                    tender.id
                )
                .first()
            )

            sla_response = (
                {
                    "incident_reporting_sla":
                        sla_reporting.incident_reporting_sla,

                    "service_level_agreement":
                        sla_reporting.service_level_agreement
                }
                if sla_reporting
                else None
            )

            # ====================================================
            # ACCESSORIALS
            # ====================================================

            accessorials = (
                db.query(
                    Lane_Tender_RFQ_Accessorial
                )
                .filter(
                    Lane_Tender_RFQ_Accessorial.tender_id ==
                    tender.id
                )
                .all()
            )

            accessorial_response = [
                {
                    "charge_type":
                        accessorial.charge_type,

                    "treatment":
                        accessorial.treatment,

                    "threshold_value":
                        accessorial.threshold_value,

                    "threshold_unit":
                        accessorial.threshold_unit,

                    "notes":
                        accessorial.notes
                }
                for accessorial in accessorials
            ]

            # ====================================================
            # CARRIER'S BIDS
            # ====================================================

            bids = (
                db.query(
                    Lane_Tender_RFQ_Bids
                )
                .filter(
                    Lane_Tender_RFQ_Bids.tender_id ==
                    tender.id,
                    Lane_Tender_RFQ_Bids.carrier_id ==
                    company_id
                )
                .all()
            )

            bid_response = [
                {
                    "bid_id": bid.id,

                    # Include whatever public/carrier-owned
                    # bid fields you have here.
                    "status": getattr(
                        bid,
                        "status",
                        None
                    ),

                    "submitted_at": getattr(
                        bid,
                        "created_at",
                        None
                    )
                }
                for bid in bids
            ]

            # ====================================================
            # VOLUME PROFILE RESPONSE
            # ====================================================

            volume_response = [
                {
                    "volume_entry_method":
                        profile.volume_entry_method,

                    "period_sequence":
                        profile.period_sequence,

                    "period_label":
                        profile.period_label,

                    "period_start_date":
                        profile.period_start_date,

                    "period_end_date":
                        profile.period_end_date,

                    "day_of_week":
                        profile.day_of_week,

                    "expected_loads":
                        profile.expected_loads
                }
                for profile in volume_profiles
            ]

            # ====================================================
            # BUILD COMPLETE TENDER
            # ====================================================

            full_tenders.append({

                # =================================================
                # IDENTITY / HIERARCHY
                # =================================================

                "tender_id": tender.id,

                "parent_tender_id": getattr(
                    tender,
                    "parent_tender_id",
                    None
                ),

                "is_parent_tender": (
                    tender.id == root_tender.id
                ),

                "tender_status": getattr(
                    tender,
                    "status",
                    None
                ),

                "published_at": getattr(
                    tender,
                    "published_at",
                    None
                ),

                "tender_title":
                    tender.tender_title,

                "tender_category":
                    tender.tender_category,

                "tender_length_category":
                    tender.tender_length_category,

                "business_unit":
                    getattr(
                        tender,
                        "business_unit",
                        None
                    ),

                "priority_level":
                    getattr(
                        tender,
                        "priority_level",
                        None
                    ),

                "customer_reference":
                    getattr(
                        tender,
                        "customer_reference",
                        None
                    ),

                # =================================================
                # SCOPE
                # =================================================

                "scope_description":
                    tender.scope_description,

                # =================================================
                # CONTRACT
                # =================================================

                "contract": {
                    "start_date":
                        tender.contract_start_date,

                    "end_date":
                        tender.contract_end_date
                },

                # =================================================
                # PROCUREMENT TIMELINES
                # =================================================

                "procurement_timeline": {

                    "issued_at":
                        getattr(
                            tender,
                            "published_at",
                            None
                        ),

                    "questions_deadline":
                        getattr(
                            tender,
                            "questions_deadline",
                            None
                        ),

                    "submission_deadline":
                        getattr(
                            tender,
                            "bid_closing_date",
                            None
                        )
                },

                # =================================================
                # ROUTING
                # =================================================

                "routing": {

                    "origin": origin,

                    "stops": stops,

                    "destination": destination,

                    "total_stops":
                        len(route_points),

                    "distance_km":
                        getattr(
                            tender,
                            "actual_distance_km",
                            None
                        ),

                    "polyline":
                        getattr(
                            tender,
                            "polyline",
                            None
                        )
                },

                # =================================================
                # CARGO
                # =================================================

                "cargo": {

                    "commodity":
                        tender.commodity,

                    "load_type":
                        tender.load_type,

                    "trip_type":
                        getattr(
                            tender,
                            "trip_type",
                            None
                        ),

                    "average_shipment_weight_kg":
                        tender.average_shipment_weight_kg,

                    "minimum_weight_bracket_kg":
                        tender.minimum_weight_bracket_kg,

                    "packaging_type":
                        tender.packaging_type,

                    "packaging_quantity":
                        tender.packaging_quantity,

                    "temperature_control":
                        tender.temperature_control,

                    "target_temperature_spec":
                        tender.target_temperature_spec,

                    "hazardous_materials":
                        tender.hazardous_materials,

                    "hazchem_classification":
                        tender.hazchem_classification,

                    "under_bond":
                        tender.under_bond,

                    "border_customs_responsibility":
                        tender.border_customs_responsibility,

                    "rib_requirements":
                        tender.rib_requirements
                },

                # =================================================
                # VOLUME
                # =================================================

                "volume": {

                    "entry_method":
                        tender.volume_entry_method,

                    "commitment":
                        tender.volume_commitment,

                    "total_expected_loads":
                        tender_total_loads,

                    "profiles":
                        volume_response
                },

                # =================================================
                # EQUIPMENT
                # =================================================

                "equipment_requirements": {

                    "allowed_configurations":
                        equipment_response,

                    "compliance": {

                        "tarpaulin_compliance_required":
                            tender.tarpaulin_compliance_required,

                        "corner_plates_required":
                            tender.corner_plates_required,

                        "chock_blocks_required":
                            tender.chock_blocks_required,

                        "ratchets_belts_required":
                            tender.ratchets_belts_required,

                        "other_equipment_requirements":
                            tender.other_equipment_requirements
                    }
                },

                # =================================================
                # DRIVER / CARRIER QUALIFICATION
                # =================================================

                "carrier_certification_driver_standards":
                    certification_response,

                # =================================================
                # ESCORT
                # =================================================

                "escort_policy":
                    escort_response,

                # =================================================
                # OPERATIONAL REQUIREMENTS
                # =================================================

                "operational_requirements": {

                    "subcontracting_policy":
                        tender.subcontracting_policy,

                    "vehicle_tracking_required":
                        tender.vehicle_tracking_required,

                    "all_time_hour_control_room":
                        tender.all_time_hour_control_room,

                    "driver_mobile_phone":
                        tender.driver_mobile_phone,

                    "clean_compliant_equipment":
                        tender.clean_compliant_equipment,

                    "pallet_management":
                        tender.pallet_management,

                    "pod_submission_local":
                        tender.pod_submission_local,

                    "pod_submission_long_haul":
                        tender.pod_submission_long_haul,

                    "pod_submission_cross_border":
                        tender.pod_submission_cross_border
                },

                # =================================================
                # DOCUMENTATION / SLA
                # =================================================

                "sla_and_reporting": {

                    "delivery_documentation_sla":
                        tender.delivery_documentation_sla,

                    "incident_reporting_sla":
                        (
                            sla_response["incident_reporting_sla"]
                            if sla_response
                            else None
                        ),

                    "service_level_agreement":
                        (
                            sla_response["service_level_agreement"]
                            if sla_response
                            else None
                        )
                },

                # =================================================
                # RISK / INSURANCE
                # =================================================

                "risk_and_insurance": {

                    "claims_risk_policy":
                        tender.claims_risk_policy,

                    "claims_risk_requirements":
                        tender.claims_risk_requirements,

                    "minimum_git_cover_amount":
                        tender.minimum_git_cover_amount,

                    "minimum_liability_cover_amount":
                        tender.minimum_liability_cover_amount,

                    "git_all_risk_required":
                        tender.git_all_risk_required,

                    "git_first_loss_required":
                        tender.git_first_loss_required,

                    "git_driver_fidelity_required":
                        tender.git_driver_fidelity_required
                },

                # =================================================
                # PRICING CONDITIONS
                #
                # IMPORTANT:
                # We deliberately DO NOT return:
                #
                # incumbent_transport_rate_per_shipment
                # incumbent_contract_rate
                # procurement_target_rate
                # =================================================

                "pricing_conditions": {

                    "pricing_basis":
                        tender.pricing_basis,

                    "rate_direction":
                        tender.rate_direction,

                    "vat_included":
                        tender.vat_included,

                    "rate_validity":
                        tender.rate_validity,

                    "rate_includes_fuel":
                        tender.rate_includes_fuel,

                    "rate_includes_driver":
                        tender.rate_includes_driver,

                    "rate_includes_maintenance":
                        tender.rate_includes_maintenance,

                    "rate_includes_insurance":
                        tender.rate_includes_insurance,

                    "rate_includes_tolls":
                        tender.rate_includes_tolls,

                    "rate_includes_border_charges":
                        getattr(
                            tender,
                            "rate_includes_border_charges",
                            None
                        ),

                    "rate_includes_empty_return":
                        tender.rate_includes_empty_return,

                    "rate_includes_waiting_time":
                        tender.rate_includes_waiting_time,

                    "rate_includes_loading_assistance":
                        tender.rate_includes_loading_assistance,

                    "rate_includes_offloading_assistance":
                        tender.rate_includes_offloading_assistance
                },

                # =================================================
                # FUEL
                # =================================================

                "fuel_terms": {

                    "fuel_treatment_type":
                        tender.fuel_treatment_type,

                    "fuel_review_period":
                        tender.fuel_review_period,

                    "fuel_component_percentage":
                        tender.fuel_component_percentage

                    # base_diesel_price intentionally excluded
                    # if you consider this procurement-sensitive.
                },

                # =================================================
                # COMMERCIAL TERMS
                # =================================================

                "commercial_terms": {

                    "payment_terms":
                        tender.payment_terms,

                    "invoice_submission_frequency":
                        tender.invoice_submission_frequency,

                    "invoice_submission_deadline":
                        tender.invoice_submission_deadline
                },

                # =================================================
                # EVALUATION
                # =================================================

                "evaluation_criteria": {

                    "price":
                        tender.evaluation_price_enabled,

                    "capacity":
                        tender.evaluation_capacity_enabled,

                    "service":
                        tender.evaluation_service_enabled,

                    "compliance":
                        tender.evaluation_compliance_enabled,

                    "flexibility":
                        tender.evaluation_flexibility_enabled
                },

                # =================================================
                # ACCESSORIALS
                # =================================================

                "accessorials":
                    accessorial_response,

                # =================================================
                # CARRIER PARTICIPATION
                # =================================================

                "carrier_participation": {

                    "has_submitted_bid":
                        len(bids) > 0,

                    "bids":
                        bid_response
                }
            })

        # ========================================================
        # 9. BUILD CORPORATE UNIFIED SUMMARY
        # ========================================================

        tender_count = len(full_tenders)

        # Remove duplicate corridors while preserving order
        unique_corridors = list(
            dict.fromkeys(combined_corridors)
        )

        # ========================================================
        # 10. GET MASTER LOADBOARD INFORMATION
        # ========================================================

        # Use the root loadboard record where available.
        root_loadboard = (
            db.query(Lane_Tender_Loadboard)
            .filter(
                Lane_Tender_Loadboard.tender_id ==
                root_tender.id
            )
            .first()
        )

        # ========================================================
        # 11. FINAL RESPONSE
        # ========================================================

        return {

            # ====================================================
            # CORPORATE SUMMARY
            # ====================================================

            "tender_summary": {

                "tender_id":
                    root_tender.id,

                "tender_invitation": {
                    "client": client_name,

                    "estimated_total_movements": total_estimated_movements,

                    "origin_locations": origin_locations,

                    "destination_regions": destination_regions,

                    "payment_terms": payment_terms,

                    "invitation_text": tender_invitation
                },

                "tender_title":
                    root_tender.tender_title,

                "status":
                    getattr(
                        root_loadboard,
                        "status",
                        getattr(
                            root_tender,
                            "status",
                            None
                        )
                    ),

                "shipper":
                    (
                        client.legal_business_name
                        if client
                        else None
                    ),

                "tender_category":
                    root_tender.tender_category,

                "tender_length_category":
                    root_tender.tender_length_category,

                "contract_start_date":
                    root_tender.contract_start_date,

                "contract_end_date":
                    root_tender.contract_end_date,

                "total_tenders":
                    tender_count,

                "total_routes":
                    tender_count,

                "total_combined_expected_loads":
                    combined_total_loads,

                "total_combined_tonnage_kg":
                    combined_total_tonnage_kg,

                "total_combined_tonnage_mt":
                    round(
                        combined_total_tonnage_kg / 1000,
                        2
                    ),

                "cargoes":
                    sorted(
                        list(combined_cargoes)
                    ),

                "load_types":
                    sorted(
                        list(combined_load_types)
                    ),

                "equipment_required":
                    sorted(
                        list(combined_equipment)
                    ),

                "corridors":
                    unique_corridors
            },

            # ====================================================
            # SHIPPER
            # ====================================================

            "shipper": shipper_information,

            # ====================================================
            # TENDER FAMILY
            # ====================================================

            "tender_family": {

                "root_tender_id":
                    root_tender.id,

                "requested_tender_id":
                    selected_tender.id,

                "requested_tender_is_parent":
                    selected_tender.id ==
                    root_tender.id,

                "total_tenders":
                    tender_count
            },

            # ====================================================
            # ALL FULL TENDERS
            # ====================================================

            "tenders":
                full_tenders
        }

    except HTTPException:
        raise

    except Exception as e:

        print(
            f"ERROR FETCHING FULL TENDER: {str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch tender: {str(e)}"
        )

#####################################Exchange Load Boards#############################################
@router.get("/carrier/ftl/exchange")
def get_ftl_exchange_loadboard(
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
        loads = db.query(Exchange_Ftl_Load_Board).filter(Exchange_Ftl_Load_Board.status == "Open").all()
        return {
            "exchanges": [{
                "id": load.exchange_id,
                "rate": load.shipment_rate,
                "trip_type": load.trip_type,
                "status": load.status,
                "end_time": load.exchange_end_time,
                "origin": load.origin_city_province,
                "pickup_date": load.pickup_date,
                "pickup_window": load.pickup_appointment,
                "destination": load.destination_city_province,
                "route": load.route_preview_embed,
                "eta_date": load.eta_date,
                "eta_window": load.eta_window,
                "provider": "SADC FREIGHTLINK",
                "distance": load.distance,
                "minimum_transit_time": load.estimated_transit_time,
                "truck": load.required_truck_type,
                "equipment": load.equipment_type,
                "trailer_type": load.trailer_type,
                "trailer_length": load.trailer_length,
                "minimum_weight_bracket": load.minimum_weight_bracket,
                "commodity": load.commodity,
                "hazardous_materials": load.hazardous_materials,
                "leading_bid_amount": load.leading_bid_amount,
                "allow_carrier_to_book_at_current_or_lower_offer_rate": load.allow_carrier_to_book_at_current_or_lower_offer_rate,
            } for load in loads]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/carrier/exchange-ftl-load/{id}")
def get_exchange_ftl_load_id(
    id: int,
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
    carrier = db.query(Carrier).filter(Carrier.id == company_id).first()
    if not carrier:
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active. Carrier accounts are required to preview loads")

    try:
        loadboard_shipment = db.query(Exchange_Ftl_Load_Board).filter(Exchange_Ftl_Load_Board.exchange_id == id).first()
        bids = db.query(Exchange_FTL_Shipment_Bid).filter(Exchange_FTL_Shipment_Bid.exchange_id == loadboard_shipment.exchange_id,
                                                            Exchange_FTL_Shipment_Bid.carrier_id == company_id).all()

        return {
            "ftl_exchange": {
                "id": loadboard_shipment.exchange_id,
                "shipment_type": loadboard_shipment.type,
                "trip_type": loadboard_shipment.trip_type,
                "load_type": loadboard_shipment.load_type,
                "required_truck_type": loadboard_shipment.required_truck_type,
                "equipment_type": loadboard_shipment.equipment_type,
                "trailer_type": loadboard_shipment.trailer_type,
                "trailer_length": loadboard_shipment.trailer_length,
                "minimum_weight_bracket": loadboard_shipment.minimum_weight_bracket,
                "shipment_weight": loadboard_shipment.shipment_weight,
                "commodity": loadboard_shipment.commodity,
                "distance": loadboard_shipment.distance,
                "estimated_transit_time": loadboard_shipment.estimated_transit_time,
                "origin": loadboard_shipment.origin_city_province,
                "destination": loadboard_shipment.destination_city_province,
                "route_preview_embed": loadboard_shipment.route_preview_embed,
                "pickup_date": loadboard_shipment.pickup_date,
                "priority_level": loadboard_shipment.priority_level,
                "customer_reference": loadboard_shipment.customer_reference_number,
                "payment_terms": loadboard_shipment.payment_terms,
                "minimum_git_cover_amount": loadboard_shipment.minimum_git_cover_amount,
                "minimum_liability_cover_amount": loadboard_shipment.minimum_liability_cover_amount,
                "packaging_quantity": loadboard_shipment.packaging_quantity,
                "packaging_type": loadboard_shipment.packaging_type,
                "temperature_control": loadboard_shipment.temperature_control,
                "hazardous_materials": loadboard_shipment.hazardous_materials,
                "pickup_number": loadboard_shipment.pickup_number,
                "pickup_notes": loadboard_shipment.pickup_notes,
                "delivery_number": loadboard_shipment.delivery_number,
                "delivery_notes": loadboard_shipment.delivery_notes,
                "allow_booking": loadboard_shipment.automatically_accept_lower_bid,
                "end_time": loadboard_shipment.exchange_end_time,

                "exchange_information": {
                    "exchange_offer": loadboard_shipment.shipment_rate,
                    "leading_bid": loadboard_shipment.leading_bid_amount,
                    "payment_terms": loadboard_shipment.payment_terms,
                    "rate_per_km": loadboard_shipment.rate_per_km,
                    "rate_per_ton": loadboard_shipment.rate_per_ton,
                    "your_bids": [{
                        "bid_amount": bid.bid_amount,
                        "bid_status": bid.status,
                        "submitted_at": bid.submitted_at,
                    } for bid in bids]
                },

                "pickup_facility": {
                    "facility_name": loadboard_shipment.pickup_facility_name,
                    "pickup_date": loadboard_shipment.pickup_date,
                    "time_window": loadboard_shipment.pickup_appointment,
                    "scheduling_type": loadboard_shipment.pickup_scheduling_type,
                    "contact_name": f"{loadboard_shipment.pickup_first_name} - {loadboard_shipment.pickup_last_name}",
                    "email": loadboard_shipment.pickup_email,
                    "contact_phone": loadboard_shipment.pickup_phone_number,
                    "notes": loadboard_shipment.pickup_notes,
                },

                "delivery_facility": {
                    "facility_name": loadboard_shipment.delivery_facility_name,
                    "eta_date": loadboard_shipment.eta_date,
                    "time_window": loadboard_shipment.delivery_appointment,
                    "eta_window": loadboard_shipment.eta_window,
                    "scheduling_type": loadboard_shipment.delivery_scheduling_type,
                    "contact_name": f"{loadboard_shipment.delivery_first_name} - {loadboard_shipment.delivery_last_name}",
                    "email": loadboard_shipment.delivery_email,
                    "contact_phone": loadboard_shipment.delivery_phone_number,
                    "notes": loadboard_shipment.delivery_notes,
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/exchange/ftl-loadboard/id/bid", status_code=status.HTTP_201_CREATED) #UnTested
def place_ftl_shipment_exchange_bid(
    bid_data: Exchange_FTL_Shipment_Bid_Create,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)):

    try:
        result = place_ftl_shipment_bid(
            db,
            bid_data,
            current_user=current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/carrier/exchange-ftl-lane-loadboard")
def exchange_ftl_lane_loadboard(
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
    carrier = db.query(Carrier).filter(Carrier.id == company_id).first()
    if not carrier:
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active. A carrier account is required in order to view shipments")

    try:
        loadboard_shipments = db.query(Exchange_Ftl_Lane_LoadBoard).filter(Exchange_Ftl_Lane_LoadBoard.status == "Open").all()

        return {
            "lanes": [{
                "id": loadboard_shipment.exchange_id,
                "status": loadboard_shipment.status,
                "trip_type": loadboard_shipment.trip_type,
                "load_type": loadboard_shipment.load_type,
                "origin": loadboard_shipment.origin_city_province,
                "destination": loadboard_shipment.destination_city_province,
                "distance": loadboard_shipment.distance,
                "route": loadboard_shipment.route_preview_embed,
                "truck_type": loadboard_shipment.required_truck_type,
                "equipment_type": loadboard_shipment.equipment_type,
                "trailer_type": loadboard_shipment.trailer_type,
                "trailer_length": loadboard_shipment.trailer_length,
                "minimum_weight_bracket": loadboard_shipment.minimum_weight_bracket,
                "commodity": loadboard_shipment.commodity,
                "packaging_type": loadboard_shipment.packaging_type,
                "average_shipment_weight": loadboard_shipment.average_shipment_weight,
                "start_date": loadboard_shipment.start_date,
                "end_date": loadboard_shipment.end_date,
                "frequency": loadboard_shipment.recurrence_frequency,
                "total_slots": loadboard_shipment.shipments_per_interval,
                "available_slots": loadboard_shipment.available_slots,
                "total_shipments_per_slot": loadboard_shipment.each_slot_size,
                "exchange_end_time": loadboard_shipment.exchange_end_time,
                "number_of_bidders": loadboard_shipment.number_of_bids_submitted,
                "per_slot_contract_offer": loadboard_shipment.per_shipment_offer_rate * loadboard_shipment.each_slot_size,
                "per_shipment_offer": loadboard_shipment.per_shipment_offer_rate,
            } for loadboard_shipment in loadboard_shipments]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/carrier/exchange-ftl-lane/{id}")
def exchange_ftl_lane(
    id: int,
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
    carrier = db.query(Carrier).filter(Carrier.id == company_id).first()
    if not carrier:
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")

    try:
        loadboard_lane = db.query(Exchange_Ftl_Lane_LoadBoard).filter(Exchange_Ftl_Lane_LoadBoard.exchange_id == id).first()
        bids = db.query(Exchange_FTL_Lane_Bid).filter(Exchange_FTL_Lane_Bid.exchange_id == loadboard_lane.exchange_id,
                                                        Exchange_FTL_Lane_Bid.carrier_id == company_id).all()

        return {
            "lane_information":{
                "id": loadboard_lane.exchange_id,
                "shipment_type": loadboard_lane.type,
                "trip_type": loadboard_lane.trip_type,
                "load_type": loadboard_lane.load_type,
                "required_truck_type": loadboard_lane.required_truck_type,
                "equipment_type": loadboard_lane.equipment_type,
                "trailer_type": loadboard_lane.trailer_type,
                "trailer_length": loadboard_lane.trailer_length,
                "minimum_weight_bracket": loadboard_lane.minimum_weight_bracket,
                "average_shipment_weight": loadboard_lane.average_shipment_weight,
                "commodity": loadboard_lane.commodity,
                "priority_level": loadboard_lane.priority_level,
                "customer_reference": loadboard_lane.customer_reference_number,
                "distance": loadboard_lane.distance,
                "estimated_transit_time": loadboard_lane.estimated_transit_time,
                "payment_terms": loadboard_lane.payment_terms,
                "route_preview_embed": loadboard_lane.route_preview_embed,
                "minimum_git_cover_amount": loadboard_lane.minimum_git_cover_amount,
                "minimum_liability_cover_amount": loadboard_lane.minimum_liability_cover_amount,
                "packaging_quantity": loadboard_lane.packaging_quantity,
                "packaging_type": loadboard_lane.packaging_type,
                "temperature_control": loadboard_lane.temperature_control,
                "hazardous_materials": loadboard_lane.hazardous_materials,
                "origin": loadboard_lane.origin_city_province,
                "destination": loadboard_lane.destination_city_province,
                "pickup_number": loadboard_lane.pickup_number,
                "delivery_number": loadboard_lane.delivery_number,
                "pickup_notes": loadboard_lane.pickup_notes,
                "delivery_notes": loadboard_lane.delivery_notes,
                "allow_booking": loadboard_lane.automatically_accept_lower_bid,
                "auction_status": loadboard_lane.status,

                "exchange_information": {
                    "per_shipment_offer_rate": loadboard_lane.per_shipment_offer_rate,
                    "per_slot_contract_offer_rate": loadboard_lane.contract_offer_rate / loadboard_lane.shipments_per_interval,
                    "per_shipment_leading_bid": loadboard_lane.leading_per_shipment_offer_bid_amount,
                    "per_slot_contract_leading_bid": loadboard_lane.leading_per_shipment_offer_bid_amount * loadboard_lane.each_slot_size if loadboard_lane.leading_per_shipment_offer_bid_amount else None,
                    "active_bidders": loadboard_lane.number_of_bids_submitted,
                    "auction_end_time": loadboard_lane.exchange_end_time,
                
                "your_bids": [{
                    "bid_id": bid.id,
                    "per_shipment_bid": bid.per_shipment_bid_amount,
                    "per_slot_contract_bid": bid.per_shipment_bid_amount * loadboard_lane.each_slot_size if bid.per_shipment_bid_amount else None,
                    "requested_slots": bid.requested_slots,
                    "bid_status": bid.status,
                    "submitted_at": bid.submitted_at,
                } for bid in bids]
                },

                "contract_details": {
                    "contract_start_date": loadboard_lane.start_date,
                    "contract_end_date": loadboard_lane.end_date,
                    "recurrence_frequency": loadboard_lane.recurrence_frequency,
                    "recurrence_days": loadboard_lane.recurrence_days,
                    "slots_per_interval": loadboard_lane.shipments_per_interval,
                    "available_slots": loadboard_lane.available_slots,
                    "total_shipments_per_slot": loadboard_lane.total_shipments / loadboard_lane.shipments_per_interval,
                    "payment_terms": loadboard_lane.payment_terms,
                    "shipment_schedule": loadboard_lane.shipment_dates,
                    "payment_schedule": loadboard_lane.payment_dates,
                },

                "pickup_facility": {
                    "facility_name": loadboard_lane.pickup_facility_name,
                    "time_window": loadboard_lane.pickup_appointment,
                    "scheduling_type": loadboard_lane.pickup_scheduling_type,
                    "contact_name": f"{loadboard_lane.pickup_first_name} - {loadboard_lane.pickup_last_name}",
                    "email": loadboard_lane.pickup_email,
                    "contact_phone": loadboard_lane.pickup_phone_number,
                    "notes": loadboard_lane.pickup_notes,
                },

                "delivery_facility": {
                    "facility_name": loadboard_lane.delivery_facility_name,
                    "time_window": loadboard_lane.delivery_appointment,
                    "scheduling_type": loadboard_lane.delivery_scheduling_type,
                    "contact_name": f"{loadboard_lane.delivery_first_name} - {loadboard_lane.delivery_last_name}",
                    "email": loadboard_lane.delivery_email,
                    "contact_phone": loadboard_lane.delivery_phone_number,
                    "notes": loadboard_lane.delivery_notes,
                }
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/exchange/ftl-lane-loadboard/bid", status_code=status.HTTP_201_CREATED) #UnTested
def place_ftl_lane_exchange_bid(
    bid_data: Exchange_FTL_Lane_Bid_Create,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        result = place_ftl_lane_bid(
            db,
            bid_data,
            current_user=current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/carrier/exchange-power-loadboard")
def exchange_power_loadboard(
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
    carrier = db.query(Carrier).filter(Carrier.id == company_id).first()
    if not carrier:
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")

    try:
        loadboard_shipments = (db.query(Exchange_Power_Load_Board).filter(Exchange_Power_Load_Board.status == "Open").all())

        results = []
        for loadboard_shipment in loadboard_shipments:
            trailer = loadboard_shipment.trailer  # thanks to relationship
        return {
            "power_shipments": [{
                "id": loadboard_shipment.exchange_id,
                "rate": loadboard_shipment.offer_rate,
                "trip_type": loadboard_shipment.trip_type,
                "origin": loadboard_shipment.origin_city_province,
                "pickup_date": loadboard_shipment.pickup_date,
                "pickup_window": loadboard_shipment.pickup_appointment,
                "route": loadboard_shipment.route_preview_embed,
                "destination": loadboard_shipment.destination_city_province,
                "eta_date": loadboard_shipment.eta_date,
                "eta_window": loadboard_shipment.eta_window,
                "provider": "SADC FREIGHTLINK",
                "distance": loadboard_shipment.distance,
                "transit_time": loadboard_shipment.estimated_transit_time,
                "truck_type": loadboard_shipment.required_truck_type,
                "axle_configuration": loadboard_shipment.axle_configuration,
                "minimum_weight_bracket": loadboard_shipment.minimum_weight_bracket,
                "equipment_type": trailer.equipment_type,
                "trailer_type": trailer.trailer_type,
                "trailer_length": trailer.trailer_length,
                "shipment_weight": loadboard_shipment.shipment_weight,
                "commodity": loadboard_shipment.commodity,
                "status": loadboard_shipment.status,
                "end_time": loadboard_shipment.exchange_end_time,
                "best bid": loadboard_shipment.leading_bid_amount,
                "allow_carrier_to_book_at_current_or_lower_offer_rate": loadboard_shipment.allow_carrier_to_book_at_current_or_lower_offer_rate,
            } for loadboard_shipment in loadboard_shipments]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/carrier/exchange-power-load/{id}")
def exchange_power_load(
    id: int,
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
    carrier = db.query(Carrier).filter(Carrier.id == company_id).first()
    if not carrier:
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")

    try:
        loadboard_shipment = db.query(Exchange_Power_Load_Board).filter(Exchange_Power_Load_Board.exchange_id == id).first()
        bids = db.query(Exchange_POWER_Shipment_Bid).filter(Exchange_POWER_Shipment_Bid.exchange_id == loadboard_shipment.exchange_id,
                                                            Exchange_POWER_Shipment_Bid.carrier_id == company_id).all()
        trailer = db.query(ShipperTrailer).filter(ShipperTrailer.id == loadboard_shipment.trailer_id).first()

        return {
            "power_shipment": {
                "id": loadboard_shipment.exchange_id,
                "shipment_type": loadboard_shipment.type,
                "trip_type": loadboard_shipment.trip_type,
                "load_type": loadboard_shipment.load_type,
                "origin": loadboard_shipment.origin_city_province,
                "destination": loadboard_shipment.destination_city_province,
                "distance": loadboard_shipment.distance,
                "estimated_transit_time": loadboard_shipment.estimated_transit_time,
                "route_preview_embed": loadboard_shipment.route_preview_embed,
                "required_truck_type": loadboard_shipment.required_truck_type,
                "axle_configuration": loadboard_shipment.axle_configuration,
                "minimum_weight_bracket": loadboard_shipment.minimum_weight_bracket,
                "minimum_git_cover_amount": loadboard_shipment.minimum_git_cover_amount,
                "minimum_liability_cover_amount": loadboard_shipment.minimum_liability_cover_amount,
                "is_trailer_loaded": loadboard_shipment.is_trailer_loaded,
                "shipment_weight": loadboard_shipment.shipment_weight,
                "commodity": loadboard_shipment.commodity,
                "temperature_control": loadboard_shipment.temperature_control,
                "hazardous_materials": loadboard_shipment.hazardous_materials,
                "packaging_quantity": loadboard_shipment.packaging_quantity,
                "packaging_type": loadboard_shipment.packaging_type,
                "pickup_number": loadboard_shipment.pickup_number,
                "pickup_notes": loadboard_shipment.pickup_notes,
                "delivery_number": loadboard_shipment.delivery_number,
                "delivery_notes": loadboard_shipment.delivery_notes,
                "trailer_return_notes": loadboard_shipment.trailer_return_notes,

                "trailer_information": {
                    "id": trailer.id,
                    "verification_status": trailer.is_verified,
                    "make": trailer.make,
                    "model": trailer.model,
                    "year": trailer.year,
                    "color": trailer.color,
                    "equipment_type": trailer.equipment_type,
                    "trailer_type": trailer.trailer_type,
                    "trailer_length": trailer.trailer_length,
                    "vin": trailer.vin,
                    "license_plate": trailer.license_plate,
                    "tare_weight": trailer.tare_weight,
                    "gvm_weight": trailer.gvm_weight,
                    "payload_capacity": trailer.payload_capacity,
                },

                "exchange_information": {
                    "exchange_offer": loadboard_shipment.offer_rate,
                    "leading_bid": loadboard_shipment.leading_bid_amount,
                    "payment_terms": loadboard_shipment.payment_terms,
                    "rate_per_km": loadboard_shipment.rate_per_km,
                    "rate_per_ton": loadboard_shipment.rate_per_ton,
                
                "your_bids": [{
                    "bid_amount": bid.bid_amount,
                    "bid_status": bid.status,
                    "submitted_at": bid.submitted_at,
                } for bid in bids]
                },

                "pickup_facility": {
                    "facility_name": loadboard_shipment.pickup_facility_name,
                    "pickup_date": loadboard_shipment.pickup_date,
                    "time_window": loadboard_shipment.pickup_appointment,
                    "scheduling_type": loadboard_shipment.pickup_scheduling_type,
                    "contact_name": f"{loadboard_shipment.pickup_first_name} - {loadboard_shipment.pickup_last_name}",
                    "email": loadboard_shipment.pickup_email,
                    "contact_phone": loadboard_shipment.pickup_phone_number,
                    "notes": loadboard_shipment.pickup_notes,
                },

                "delivery_facility": {
                    "facility_name": loadboard_shipment.delivery_facility_name,
                    "eta_date": loadboard_shipment.eta_date,
                    "time_window": loadboard_shipment.delivery_appointment,
                    "eta_window": loadboard_shipment.eta_window,
                    "scheduling_type": loadboard_shipment.delivery_scheduling_type,
                    "contact_name": f"{loadboard_shipment.delivery_first_name} - {loadboard_shipment.delivery_last_name}",
                    "email": loadboard_shipment.delivery_email,
                    "contact_phone": loadboard_shipment.delivery_phone_number,
                    "notes": loadboard_shipment.delivery_notes,
                }
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/carrier/exchange/power-loadboard/id/bid", status_code=status.HTTP_201_CREATED) #UnTested
def place_power_shipment_exchange_bid(
    bid_data: Exchange_POWER_Shipment_Bid_Create,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)):

    try:
        result = place_power_shipment_bid(
            db,
            bid_data,
            current_user=current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.get("/exchange/ftl-loadboard/id/all-bids", response_model=List[Exchange_FTL_Exchange_Loadboard_BidResponse]) #UnTested
def get_all_ftl_load_exchange_bids(
    bid_data: IndividualLoadboardShipmentRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    carrier = db.query(Carrier).filter(
        Carrier.id == company_id).first()
    if not carrier:
        raise ValueError("Carrier Not found")
        
    try:
        # Query all records from the "dedicated_lanes_loadboard" table
        bids = db.query(Exchange_FTL_Shipment_Bid).filter(Exchange_FTL_Shipment_Bid.exchange_id == bid_data.id).all()
        return bids
    except Exception as e:
        return {"error": str(e)}
    

###########################   ONCE-OFF POWER   #############################################
@router.get("/exchange/power-loadboard/id/all-bids", response_model=List[Exchange_Power_Exchange_Loadboard_BidResponse]) #UnTested
def get_all_power_load_exchange_bids(
    bid_data: IndividualLoadboardShipmentRequest,
    db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    carrier = db.query(Carrier).filter(
        Carrier.id == company_id).first()
    if not carrier:
        raise ValueError("Carrier Not found")
        
    try:
        # Query all records from the "dedicated_lanes_loadboard" table
        bids = db.query(Exchange_POWER_Shipment_Bid).filter(Exchange_POWER_Shipment_Bid.exchange_id == bid_data.id).all()
        return bids
    except Exception as e:
        return {"error": str(e)}
    

@router.get("/public/shipment-loadboard")
def public_get_shipments_loadboard(
    db: Session = Depends(get_db),
):
    try:
        loadboards = db.query(Shipment_Auction_Loadboard).filter(
            Shipment_Auction_Loadboard.is_visible_to_carriers == True,
            Shipment_Auction_Loadboard.status == "Active"
        ).all()

        response = []

        for loadboard in loadboards:
            auction_id = loadboard.auction_id

            auction = db.query(Client_Shipment_Auction).filter(
                Client_Shipment_Auction.id == auction_id
            ).first()
            if not auction:
                continue

            client = db.query(Corporation).filter(
                Corporation.id == auction.client_id
            ).first()

            route_points = db.query(Client_Shipment_Auction_Stop).filter(
                Client_Shipment_Auction_Stop.auction_id == auction_id
            ).order_by(
                Client_Shipment_Auction_Stop.stop_sequence.asc()
            ).all()

            origin = next(
                (stop for stop in route_points if stop.stop_type == "Origin"),
                None
            )
            destination = next(
                (stop for stop in route_points if stop.stop_type == "Destination"),
                None
            )
            intermediate_stops = [
                stop for stop in route_points
                if stop.stop_type == "Intermediate"
            ]

            if not origin or not destination:
                continue

            pickup_window = None
            if origin.operating_start_time and origin.operating_end_time:
                pickup_window = f"{origin.operating_start_time} - {origin.operating_end_time}"

            delivery_window = None
            if destination.operating_start_time and destination.operating_end_time:
                delivery_window = f"{destination.operating_start_time} - {destination.operating_end_time}"

            vehicle_configurations = db.query(
                Client_Shipment_Auction_Vehicle_Requirement
            ).filter(
                Client_Shipment_Auction_Vehicle_Requirement.auction_id == auction_id
            ).all()

            requirements = [
                {
                    "configuration_type": config.configuration_type,
                    "truck_type": config.truck_type,
                    "equipment_type": config.equipment_type,
                    "trailer_type": config.trailer_type,
                    "trailer_length": config.trailer_length
                }
                for config in vehicle_configurations
            ]

            response.append({
                "id": loadboard.auction_id,
                "trip_type": loadboard.trip_type,
                "client": client.legal_business_name if client else None,
                "closing_date": loadboard.auction_closing_date,
                "route": {
                    "origin": {
                        "pickup": origin.complete_address or origin.address,
                        "facility_name": origin.facility_name or None,
                        "pickup_date": loadboard.pickup_date,
                        "pickup_window": pickup_window
                    },
                    "destination": {
                        "delivery": destination.complete_address or destination.address,
                        "facility_name": destination.facility_name or None,
                        "eta_date": loadboard.eta_date,
                        "delivery_window": delivery_window
                    },
                    "distance": loadboard.distance,
                    "minimum_transit_time": loadboard.estimated_transit_time,
                    "stops": len(intermediate_stops) if intermediate_stops else None,
                    "polyline": loadboard.polyline
                },
                "commodity": loadboard.commodity,
                "shipment_weight": loadboard.shipment_weight,
                "hazardous_materials": {
                    "hazardous": loadboard.hazardous_materials,
                    "hazchem_classification": loadboard.hazchem_classification if loadboard.hazchem_classification else None
                },
                "required_equipment_specification": requirements,
                "number_of_trucks_required": loadboard.number_of_trucks_required,
                "slot_remaining": loadboard.slots_remaining,
                "rate": {
                    "rate_basis": loadboard.pricing_basis,
                    "benchmark_rate": loadboard.benchmark_rate,
                    "benchmark_service_fee": loadboard.benchmark_rate_service_fee,
                    "book_now_rate": loadboard.book_now_rate if loadboard.book_now_rate else None,
                    "vat_included": loadboard.vat_included,
                    "bidding_allowed": loadboard.bidding_activated,
                    "bidding_direction": loadboard.rate_direction
                }
            })

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve shipment loadboard: {str(e)}"
        )


@router.get("/public-shipment-loadboard/{id}")
def public_get_loadboard_shipment(
    id: int,
    db: Session = Depends(get_db),
):
    try:
        load = db.query(Shipment_Auction_Loadboard).filter(
            Shipment_Auction_Loadboard.auction_id == id,
            Shipment_Auction_Loadboard.is_visible_to_carriers == True
        ).first()
        if not load:
            raise HTTPException(status_code=404, detail="Loadboard shipment not found or not available")
        auction = db.query(Client_Shipment_Auction).filter(
            Client_Shipment_Auction.id == load.auction_id
        ).first()
        if not auction:
            raise HTTPException(status_code=404, detail="Auction not found")
            
        client = db.query(Corporation).filter(
            Corporation.id == auction.client_id
        ).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        route_points = db.query(Client_Shipment_Auction_Stop).filter(
            Client_Shipment_Auction_Stop.auction_id == auction.id
        ).order_by(
            Client_Shipment_Auction_Stop.stop_sequence.asc()
        ).all()
        if not route_points:
            raise HTTPException(status_code=404, detail="Route information not found")
        vehicle_configurations = db.query(
            Client_Shipment_Auction_Vehicle_Requirement
        ).filter(
            Client_Shipment_Auction_Vehicle_Requirement.auction_id == auction.id
        ).all()
        origin = next(
            (stop for stop in route_points if stop.stop_type == "Origin"),
            None
        )
        destination = next(
            (stop for stop in route_points if stop.stop_type == "Destination"),
            None
        )
        intermediate_stops = [
            stop for stop in route_points
            if stop.stop_type == "Intermediate"
        ]
        if not origin:
            raise HTTPException(status_code=500, detail="Origin stop not found")
        if not destination:
            raise HTTPException(status_code=500, detail="Destination stop not found")
        return {
            "load_information": {
                "id": load.auction_id,
                "client": client.legal_business_name,
                "closing_date": load.auction_closing_date,
                "trip_type": load.trip_type,
                "load_type": load.load_type,
                "priority_level": load.priority_level,
                "payment_terms": load.payment_terms,
                "pickup_date": load.pickup_date,
                "number_of_trucks_required": load.number_of_trucks_required,
                "remaining_slots": load.slots_remaining,
                "route": {
                    "origin": origin.city_province,
                    "stops": [
                        {
                            "location": stop.city_province,
                        }
                        for stop in intermediate_stops
                    ],
                    "destination": destination.city_province,
                    "distance": load.distance,
                    "transit_time": load.estimated_transit_time,
                    "eta_date": getattr(load, "eta_date", None),
                    "polyline": load.polyline,
                    "stop_count": len(intermediate_stops),
                },
                "exchange_and_bidding": {
                    "rules": {
                        "rate_basis": load.pricing_basis,
                        "vat_included": load.vat_included,
                        "bidding_allowed": load.bidding_activated,
                        "bidding_direction": load.rate_direction,
                    },
                    "rates": {
                        "benchmark_rate": load.benchmark_rate,
                        "benchmark_rate_service_fee": load.benchmark_rate_service_fee,
                        "book_now_rate": load.book_now_rate,
                    },
                    "rates_inclusive_of": {
                        "fuel": load.rate_includes_fuel,
                        "driver": load.rate_includes_driver,
                        "maintenance": load.rate_includes_maintenance,
                        "insurance": load.rate_includes_insurance,
                        "tolls": load.rate_includes_tolls,
                        "border_fees_and_duty": load.rate_includes_border_charges,
                        "empty_return": load.rate_includes_empty_return,
                        "waiting_detention_time": load.rate_includes_waiting_time,
                        "loading_assistance": load.rate_includes_loading_assistance,
                        "offloading_assistance": load.rate_includes_offloading_assistance,
                    },
                },
                "equipment": {
                    "accepted_vehicle_configs": [
                        {
                            "config_type": config.configuration_type,
                            "truck_type": config.truck_type,
                            "equipment_type": config.equipment_type,
                            "trailer_type": config.trailer_type,
                            "trailer_length": config.trailer_length,
                            "is_required": config.is_required,
                        }
                        for config in vehicle_configurations
                    ],
                    "equipment_compliance": {
                        "tarpaulin_compliance_required": load.tarpaulin_compliance_required,
                        "corner_plates_required": load.corner_plates_required,
                        "chock_blocks_required": load.chock_blocks_required,
                        "ratchets_belts_required": load.ratchets_belts_required,
                        "other_equipment_requirements": load.other_equipment_requirements,
                    },
                },
                "cargo": {
                    "commodity": load.commodity,
                    "weight": load.shipment_weight,
                    "packaging_type": load.packaging_type,
                    "packaging_quantity": load.packaging_quantity,
                    "under_bond": load.under_bond,
                    "hazardous": {
                        "is_hazardous": load.hazardous_materials,
                        "hazchem_classification": getattr(load, "hazchem_classification", None),
                    },
                },
                "insurance_requirements": {
                    "minimum_git_cover_amount": load.minimum_git_cover_amount,
                    "minimum_liability_cover_amount": load.minimum_liability_cover_amount,
                    "git_all_risk_required": load.git_all_risk_required,
                    "git_first_loss_required": load.git_first_loss_required,
                    "git_driver_fidelity_required": load.git_driver_fidelity_required,
                },
                "operational_requirements": {
                    "vehicle_tracking_required": load.vehicle_tracking_required,
                    "all_time_hour_control_room": load.all_time_hour_control_room,
                    "driver_mobile_phone": load.driver_mobile_phone,
                    "clean_compliant_equipment": load.clean_compliant_equipment,
                    "pallet_management_chep": load.pallet_management,
                    "pod_submission_local": load.pod_submission_local,
                    "pod_submission_long_haul": load.pod_submission_long_haul,
                    "pod_submission_cross_border": load.pod_submission_cross_border,
                },
                "facilities": [
                    {
                        "sequence": facility.stop_sequence,
                        "type": facility.stop_type,
                        "name": facility.facility_name,
                        "location": facility.city_province,
                        "country": facility.country,
                        "scheduling_type": facility.scheduling_type,
                        "operations_window": f"{facility.operating_start_time} - {facility.operating_end_time}",
                        "operating_days": {
                            "monday": facility.open_monday,
                            "tuesday": facility.open_tuesday,
                            "wednesday": facility.open_wednesday,
                            "thursday": facility.open_thursday,
                            "friday": facility.open_friday,
                            "saturday": facility.open_saturday,
                            "sunday": facility.open_sunday,
                        },
                    }
                    for facility in route_points
                ],
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))