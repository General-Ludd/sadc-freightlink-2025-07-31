from typing import List
from fastapi import HTTPException
from sqlalchemy.orm import Session
from models.spot_bookings.shipment_facility import ShipmentFacility
import uuid
from models.Exchange.dedicated_ftl_lane import FTL_Lane_Exchange
from models.Exchange.ftl_shipment import FTL_SHIPMENT_EXCHANGE, Client_Shipment_Auction, Client_Shipment_Auction_Stop, Client_Shipment_Auction_Vehicle_Requirement
from models.spot_bookings.ftl_shipment import Client_Shipment, Client_Shipment_Stop, Client_Shipment_Vehicle_Requirement
from models.brokerage.assigned_shipments import Carrier_Shipment
from models.Exchange.auction import Exchange_FTL_Lane_Bid, Exchange_FTL_Shipment_Bid, Exchange_POWER_Shipment_Bid, Shipment_Auction_Bid
from models.Exchange.power_shipment import POWER_SHIPMENT_EXCHANGE
from models.brokerage.assigned_shipments import Carrier_Shipment
from models.brokerage.assigned_lanes import Assigned_Ftl_Lanes
from models.brokerage.assigned_shipments import Assigned_Power_Shipments, Assigned_Spot_Ftl_Shipments
from models.brokerage.finance import BrokerageLedger, CarrierFinancialAccounts, Dedicated_Lane_BrokerageLedger, Lane_Slot_Ledger, Exchange_Lane_Slot_Assignment, FinancialAccounts, Interim_Invoice, Lane_Interim_Invoice, Lane_Invoice, Load_Invoice, PlatformCommission
from models.brokerage.loadboards.exchange_loadboards import Exchange_Ftl_Lane_LoadBoard, Exchange_Ftl_Load_Board, Exchange_Power_Load_Board
from models.brokerage.loadboard import Shipment_Auction_Loadboard
from models.carrier import Carrier, Carrier_Profile, Carrier_Notification
from models.shipper import Corporation, Client_Notification
from models.spot_bookings.dedicated_lane_ftl_shipment import Client_Lane
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT, Client_Shipment, Client_Shipment_Stop, Client_Shipment_Vehicle_Requirement
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from models.vehicle import Vehicle
from schemas.exchange_bookings.auction import Accept_Bid, Exchange_FTL_Lane_Bid_Create, Exchange_FTL_Shipment_Bid_Create, Exchange_POWER_Shipment_Bid_Create, Create_Tender_Bid, Create_Shipment_Bid
from services.brokerage.carrier_loadboard_service import calculate_rates
from services.brokerage.commission import calculate_commission
from utils.billing import BillingEngine
from fastapi import HTTPException, Depends, Request
from sqlalchemy.orm import Session
import pytz
from datetime import datetime
from utils.sast_datetime import format_datetime_sast
from utils.google_maps import AddressInput, RouteETAInput, calculate_distance, get_eta_and_polyline

##############################################################################################################################################
##############################################################################################################################################
##############################################################################################################################################
##############################################################################################################################################

def place_auction_bid(
    id: int,
    bid_data: Create_Shipment_Bid,
    db: Session,
    current_user: dict,
):
    company_id = current_user.get("company_id")
    user_id = current_user.get("id")

    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")

    if not user_id:
        raise HTTPException(status_code=400, detail="User ID missing from authentication token")

    try:
        auction = db.query(Client_Shipment_Auction).filter(
            Client_Shipment_Auction.id == id,
            Client_Shipment_Auction.status == "Active"
        ).first()

        if not auction:
            raise HTTPException(status_code=404, detail="Load not found or bidding is closed")

        if auction.status != "Active":
            raise HTTPException(status_code=400, detail=f"Load is not accepting bids. Current status: {auction.status}")

        auction_loadboard = db.query(Shipment_Auction_Loadboard).filter(
            Shipment_Auction_Loadboard.auction_id == auction.id,
            Shipment_Auction_Loadboard.is_visible_to_carriers == True
        ).first()

        if not auction_loadboard:
            raise HTTPException(status_code=404, detail="Load is not available on the carrier loadboard")

        carrier = db.query(Carrier).filter(
            Carrier.id == company_id
        ).first()

        if not carrier:
            raise HTTPException(status_code=404, detail="Carrier not found")

        if not carrier.is_verified:
            raise HTTPException(status_code=403, detail="Carrier company account not verified, please request account verification")

        if carrier.status != "Active":
            raise HTTPException(status_code=403, detail="Carrier account is not Active, please request account activation")

        if carrier.git_cover_amount is None or carrier.git_cover_amount < auction.minimum_git_cover_amount:
            raise HTTPException(status_code=400, detail=f"Carrier GIT cover amount of 'R{carrier.git_cover_amount or 0}' does not satisfy the shipments's required minimum of 'R{auction.minimum_git_cover_amount}'")

        if carrier.liability_insurance_cover_amount is None or carrier.liability_insurance_cover_amount < auction.minimum_liability_cover_amount:
            raise HTTPException(status_code=400, detail=f"Carrier liability cover amount 'R{carrier.liability_insurance_cover_amount or 0}' does not satisfy the shipments's required minimum of 'R{auction.minimum_liability_cover_amount}'")

        carrier_profile = db.query(Carrier_Profile).filter(
            Carrier_Profile.carrier_id == carrier.id
        ).first()

        if not carrier_profile:
            raise HTTPException(status_code=400, detail="Carrier profile not found. Please complete your fleet profile before bidding.")

        fleet_fields = [
            "rigid_tautliners",
            "triaxle_tautliners",
            "superlink_tautliners",
            "rigid_flatbeds",
            "triaxle_flatbeds",
            "superlink_flatbeds",
            "rigid_flatbeds_with_twistlocks",
            "triaxle_flatbeds_with_twistlocks",
            "superlink_flatbeds_with_twistlocks",
            "rigid_dropsides",
            "triaxle_dropside",
            "superlink_dropside",
            "triaxle_skeletals",
            "superlink_skeletals",
            "rigid_pantechs",
            "triaxle_pantechs",
            "triaxle_side_tippers",
            "superlink_side_tippers",
            "low_beds",
            "rigid_end_tipper",
            "triaxle_end_tipper"
        ]

        fleet_size = sum((getattr(carrier_profile, field) or 0) for field in fleet_fields)

        if fleet_size <= 0:
            raise HTTPException(status_code=400, detail="Carrier fleet profile contains no vehicles")

        if bid_data.rate is None:
            raise HTTPException(status_code=400, detail="Bid per shipment is required")

        if bid_data.rate <= 0:
            raise HTTPException(status_code=400, detail="Bid per shipment must be greater than zero")

        existing_bid = db.query(Shipment_Auction_Bid).filter(
            Shipment_Auction_Bid.auction_id == auction.id,
            Shipment_Auction_Bid.carrier_id == carrier.id
        ).first()

        if existing_bid:
            raise HTTPException(status_code=400, detail="You have already placed a bid on this load exchange")

        bid = Shipment_Auction_Bid(
            auction_id=auction.id,
            carrier_id=carrier.id,
            bidder_user_id=user_id,
            carrier_name=carrier.legal_business_name,
            fleet_size=fleet_size,
            primary_lanes=carrier_profile.primary_routes,
            rate=bid_data.rate,
            number_of_loads=bid_data.number_of_loads,
            lead_time=bid_data.lead_time,
            bid_notes=bid_data.bid_notes,
            status="Submitted"
        )

        db.add(bid)
        db.commit()
        db.refresh(bid)

        return {
            "message": "Load exchange bid submitted successfully",
            "bid_id": bid.id,
            "auction_id": auction.id,
            "carrier_id": carrier.id,
            "rate": float(bid.rate),
            "number_of_loads": bid.number_of_loads,
            "lead_time": bid.lead_time,
            "status": bid.status
        }

    except HTTPException:
        # Re-raise standard HTTP exceptions safely 
        raise
    except Exception as e:
        # FIXED: Roll back the DB session instead of bid_data
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

from sqlalchemy import nullslast # Ensure this is imported at the top of your file


def accept_auction_bid(
    auction_id: int,
    bid_id: int,
    db: Session,
    current_user: dict
):
    company_id = current_user.get("company_id")
    user_id = current_user.get("id")

    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")

    if not user_id:
        raise HTTPException(status_code=400, detail="User ID missing from authentication token")

    try:
        auction = db.query(Client_Shipment_Auction).filter(
            Client_Shipment_Auction.id == auction_id
        ).first()

        if not auction:
            raise HTTPException(status_code=404, detail="Auction not found")

        if auction.slots_remaining == 0:
            auction.slots_remaining = 0
            auction.status = "Closed"
            raise HTTPException(status_code=403, detail="Sorry, the auction has closed and all slots have been awarded")

        bid = db.query(Shipment_Auction_Bid).filter(
            Shipment_Auction_Bid.id == bid_id,
            Shipment_Auction_Bid.auction_id == auction.id
        ).first()

        if not bid:
            raise HTTPException(status_code=404, detail="Bid not found")

        if bid.status == "Withdrawn":
            raise HTTPException(
                status_code=403,
                detail=f"Unfortunately the selected bid cannot be awarded as it has been withdrawn by the carrier {bid.carrier_name}"
            )

        number_to_assign = min(
            bid.number_of_loads,
            auction.slots_remaining
        )

        # 1. Fetch raw underlying data properties instead of handling relationship links
        stops_facilities = db.query(Client_Shipment_Auction_Stop).filter(
            Client_Shipment_Auction_Stop.auction_id == auction.id
        ).all()
        
        configs = db.query(Client_Shipment_Auction_Vehicle_Requirement).filter(
            Client_Shipment_Auction_Vehicle_Requirement.auction_id == auction.id
        ).all()

        commission_result = calculate_commission(
            db,
            bid.rate
        )
        service_fee = commission_result["commission"]

        created_shipments_summary = []

        # Raw storage lists to hold data structures for direct table copying
        stops_payload = []
        requirements_payload = []

        for assignment_number in range(number_to_assign):

            # 2. Add Parent Client Shipment Row
            client_shipment = Client_Shipment(
                is_subshipment=False,
                auction_id=auction.id,
                booking_source="Shipment Exchange",
                shipment_reference=auction.shipment_reference if auction.shipment_reference else None,
                booking_reference=auction.booking_reference if auction.booking_reference else None,
                trip_type=auction.trip_type,
                load_type=auction.load_type,
                client_id=company_id,
                client_user_id=user_id,
                rate=bid.rate,
                pricing_basis=auction.pricing_basis,
                vat_included=auction.vat_included,
                payment_terms=auction.payment_terms,
                pickup_date=auction.pickup_date,
                priority_level=auction.priority_level,
                customer_reference_number=auction.customer_reference_number if auction.customer_reference_number else None,
                shipment_weight=auction.shipment_weight,
                commodity=auction.commodity,
                temperature_control=auction.temperature_control,
                target_temperature_spec=auction.target_temperature_spec if auction.target_temperature_spec else None,
                hazardous_materials=auction.hazardous_materials,
                hazchem_classification=auction.hazchem_classification if auction.hazchem_classification else None,
                under_bond=auction.under_bond,
                rib_requirements=auction.rib_requirements,
                packaging_quantity=auction.packaging_quantity,
                packaging_type=auction.packaging_type,
                distance=auction.distance,
                rate_includes_fuel=auction.rate_includes_fuel,
                rate_includes_driver=auction.rate_includes_driver,
                rate_includes_maintenance=auction.rate_includes_maintenance,
                rate_includes_insurance=auction.rate_includes_insurance,
                rate_includes_tolls=auction.rate_includes_tolls,
                rate_includes_border_charges=auction.rate_includes_border_charges,
                rate_includes_empty_return=auction.rate_includes_empty_return,
                rate_includes_waiting_time=auction.rate_includes_waiting_time,
                rate_includes_loading_assistance=auction.rate_includes_loading_assistance,
                rate_includes_offloading_assistance=auction.rate_includes_offloading_assistance,
                minimum_weight_bracket_kg=auction.minimum_weight_bracket,
                vehicle_tracking_required=auction.vehicle_tracking_required,
                all_time_hour_control_room=auction.all_time_hour_control_room,
                driver_mobile_phone=auction.driver_mobile_phone,
                clean_compliant_equipment=auction.clean_compliant_equipment,
                pallet_management=auction.pallet_management,
                pod_submission_local=auction.pod_submission_local,
                pod_submission_long_haul=auction.pod_submission_long_haul,
                pod_submission_cross_border=auction.pod_submission_cross_border,
                minimum_git_cover_amount=auction.minimum_git_cover_amount,
                minimum_liability_cover_amount=auction.minimum_liability_cover_amount,
                git_all_risk_required=auction.git_all_risk_required,
                git_first_loss_required=auction.git_first_loss_required,
                git_driver_fidelity_required=auction.git_driver_fidelity_required,
                tarpaulin_compliance_required=auction.tarpaulin_compliance_required,
                corner_plates_required=auction.corner_plates_required,
                chock_blocks_required=auction.chock_blocks_required,
                ratchets_belts_required=auction.ratchets_belts_required,
                other_equipment_requirements=auction.other_equipment_requirements
            )
            db.add(client_shipment)
            db.flush() # Only flushes the high-level parent shipment row to allocate its auto-increment ID

            for i, stop in enumerate(stops_facilities):
                # Fallback to current system timestamp if arrival/departure times are not yet populated
                db.add(
                    Client_Shipment_Stop(
                        shipment_id=client_shipment.id,
                        stop_sequence=stop.stop_sequence,
                        stop_type=stop.stop_type,
                        address=stop.address,
                        complete_address=stop.complete_address,
                        city_province=stop.city_province,
                        country=stop.country,
                        region=stop.region,
                        latitude=stop.latitude,
                        longitude=stop.longitude,
                        facility_name=stop.facility_name,
                        scheduling_type=stop.scheduling_type,
                        operating_start_time=stop.operating_start_time,
                        operating_end_time=stop.operating_end_time,
                        open_monday=stop.open_monday,
                        open_tuesday=stop.open_tuesday,
                        open_wednesday=stop.open_wednesday,
                        open_thursday=stop.open_thursday,
                        open_friday=stop.open_friday,
                        open_saturday=stop.open_saturday,
                        open_sunday=stop.open_sunday,
                        contact_first_name=stop.contact_first_name,
                        contact_last_name=stop.contact_last_name,
                        contact_phone_number=stop.contact_phone_number,
                        contact_email=stop.contact_email,
                        reference_number=stop.reference_number,
                        notes=stop.notes,
                    )
                )

            for config in configs:
                db.add(
                    Client_Shipment_Vehicle_Requirement(
                        shipment_id=client_shipment.id,
                        # Fallback applied here to finish the truncated function safely
                        configuration_type=config.configuration_type,
                        truck_type=config.truck_type,
                        equipment_type=config.equipment_type,
                        trailer_type=config.trailer_type,
                        trailer_length=config.trailer_type,
                        is_required=True,
                    )
                )

            # 3. Add Parent Carrier Shipment Row
            safe_carrier_id = bid.carrier_id if bid.carrier_id is not None else "UNKNOWN"
            carrier_shipment_reference = f"EX-{auction.id}-{safe_carrier_id}-{uuid.uuid4().hex[:8].upper()}"

            carrier_shipment = Carrier_Shipment(
                is_subshipment=False,
                auction_id=auction.id,
                booking_source="Shipment Exchange",
                shipment_reference=carrier_shipment_reference,
                booking_reference=auction.booking_reference,
                trip_type=auction.trip_type,
                load_type=auction.load_type,
                carrier_id=bid.carrier_id,
                carrier_user_id=bid.bidder_user_id,
                rate=bid.rate,
                service_fee=0,
                pricing_basis=auction.pricing_basis,
                vat_included=auction.vat_included,
                payment_terms=auction.payment_terms,
                pickup_date=auction.pickup_date,
                priority_level=auction.priority_level,
                customer_reference_number=auction.customer_reference_number,
                shipment_weight=auction.shipment_weight,
                commodity=auction.commodity,
                temperature_control=auction.temperature_control,
                target_temperature_spec=auction.target_temperature_spec if auction.target_temperature_spec else None,
                hazardous_materials=auction.hazardous_materials,
                hazchem_classification=auction.hazchem_classification if auction.hazchem_classification else None,
                under_bond=auction.under_bond,
                rib_requirements=auction.rib_requirements,
                packaging_quantity=auction.packaging_quantity,
                packaging_type=auction.packaging_type,
                distance=auction.distance,
                rate_includes_fuel=auction.rate_includes_fuel,
                rate_includes_driver=auction.rate_includes_driver,
                rate_includes_maintenance=auction.rate_includes_maintenance,
                rate_includes_insurance=auction.rate_includes_insurance,
                rate_includes_tolls=auction.rate_includes_tolls,
                rate_includes_border_charges=auction.rate_includes_border_charges,
                rate_includes_empty_return=auction.rate_includes_empty_return,
                rate_includes_waiting_time=auction.rate_includes_waiting_time,
                rate_includes_loading_assistance=auction.rate_includes_loading_assistance,
                rate_includes_offloading_assistance=auction.rate_includes_offloading_assistance,
                minimum_weight_bracket_kg=auction.minimum_weight_bracket,
                vehicle_tracking_required=auction.vehicle_tracking_required,
                all_time_hour_control_room=auction.all_time_hour_control_room,
                driver_mobile_phone=auction.driver_mobile_phone,
                clean_compliant_equipment=auction.clean_compliant_equipment,
                pallet_management=auction.pallet_management,
                pod_submission_local=auction.pod_submission_local,
                pod_submission_long_haul=auction.pod_submission_long_haul,
                pod_submission_cross_border=auction.pod_submission_cross_border,
                minimum_git_cover_amount=auction.minimum_git_cover_amount,
                minimum_liability_cover_amount=auction.minimum_liability_cover_amount,
                git_all_risk_required=auction.git_all_risk_required,
                git_first_loss_required=auction.git_first_loss_required,
                git_driver_fidelity_required=auction.git_driver_fidelity_required,
                tarpaulin_compliance_required=auction.tarpaulin_compliance_required,
                corner_plates_required=auction.corner_plates_required,
                chock_blocks_required=auction.chock_blocks_required,
                ratchets_belts_required=auction.ratchets_belts_required,
                other_equipment_requirements=auction.other_equipment_requirements
            )

            db.add(carrier_shipment)
            db.flush()

            created_shipments.append({
                "client_shipment_id": client_shipment.id,
                "carrier_shipment_id": carrier_shipment.id
            })

        auction.slots_remaining -= number_to_assign

        if auction.slots_remaining <= 0:
            auction.slots_remaining = 0
            auction.status = "Closed"

        bid.status = "Awarded"

        db.commit()

        return {
            "message": "Bid awarded successfully",
            "auction_id": auction.id,
            "bid_id": bid.id,
            "carrier_id": bid.carrier_id,
            "requested_loads": bid.number_of_loads,
            "assigned_loads": number_to_assign,
            "slots_remaining": auction.slots_remaining,
            "auction_status": auction.status,
            "rate": bid.rate,
            "combined_rate": (bid.rate * number_to_assign),
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        print(f"ERROR ACCEPTING AUCTION BID: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def place_tender_bid(
    db: Session,
    bid_data: Create_Tender_Bid,
    current_user: dict
):
    # ============================================================
    # 1. CURRENT USER
    # ============================================================

    company_id = current_user.get("company_id")
    user_id = current_user.get("id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="User ID missing from authentication token"
        )

    # ============================================================
    # 2. GET ACTIVE TENDER
    # ============================================================

    tender = db.query(Lane_Tender_RFQ).filter(
        Lane_Tender_RFQ.id == bid_data.tender_id,
        Lane_Tender_RFQ.is_active == True
    ).first()

    if not tender:
        raise HTTPException(
            status_code=404,
            detail="Tender not found or bidding is closed"
        )

    if tender.status != "Active":
        raise HTTPException(
            status_code=400,
            detail=f"Tender is not accepting bids. Current status: {tender.status}"
        )

    # ============================================================
    # 3. VERIFY TENDER LOADBOARD
    # ============================================================

    tender_loadboard = db.query(Lane_Tender_Loadboard).filter(
        Lane_Tender_Loadboard.tender_id == tender.id,
        Lane_Tender_Loadboard.is_visible_to_carrier == True
    ).first()

    if not tender_loadboard:
        raise HTTPException(
            status_code=404,
            detail="Tender is not available on the carrier loadboard"
        )

    # ============================================================
    # 4. GET CARRIER
    # ============================================================

    carrier = db.query(Carrier).filter(
        Carrier.id == company_id
    ).first()

    if not carrier:
        raise HTTPException(
            status_code=404,
            detail="Carrier not found"
        )

    if not carrier.is_verified:
        raise HTTPException(
            status_code=403,
            detail=(
                "Carrier company account not verified, "
                "please request account verification"
            )
        )

    if carrier.status != "Active":
        raise HTTPException(
            status_code=403,
            detail=(
                "Carrier account is not Active, "
                "please request account activation."
            )
        )

    # ============================================================
    # 5. VALIDATE CARRIER INSURANCE
    # ============================================================

    if (
        carrier.git_cover_amount is None
        or carrier.git_cover_amount < tender.minimum_git_cover_amount
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Carrier GIT cover amount of "
                f"'R{carrier.git_cover_amount or 0}' does not satisfy "
                f"the tender's required minimum of "
                f"'R{tender.minimum_git_cover_amount}'"
            )
        )

    if (
        carrier.liability_insurance_cover_amount is None
        or carrier.liability_insurance_cover_amount
        < tender.minimum_liability_cover_amount
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Carrier liability cover amount "
                f"'R{carrier.liability_insurance_cover_amount or 0}' "
                f"does not satisfy the tender's required minimum of "
                f"'R{tender.minimum_liability_cover_amount}'"
            )
        )

    # ============================================================
    # 6. GET CARRIER PROFILE
    # ============================================================

    carrier_profile = db.query(Carrier_Profile).filter(
        Carrier_Profile.carrier_id == carrier.id
    ).first()

    if not carrier_profile:
        raise HTTPException(
            status_code=400,
            detail="Carrier profile not found. Please complete your fleet profile before bidding."
        )

    # ============================================================
    # 7. CALCULATE FLEET SIZE
    # ============================================================

    fleet_fields = [
        "rigid_tautliners",
        "triaxle_tautliners",
        "superlink_tautliners",
        "rigid_flatbeds",
        "triaxle_flatbeds",
        "superlink_flatbeds",
        "rigid_flatbeds_with_twistlocks",
        "triaxle_flatbeds_with_twistlocks",
        "superlink_flatbeds_with_twistlocks",
        "rigid_dropsides",
        "triaxle_dropside",
        "superlink_dropside",
        "triaxle_skeletals",
        "superlink_skeletals",
        "rigid_pantechs",
        "triaxle_pantechs",
        "triaxle_side_tippers",
        "superlink_side_tippers",
        "low_beds",
        "rigid_end_tipper",
        "triaxle_end_tipper"
    ]

    fleet_size = sum(
        (getattr(carrier_profile, field) or 0)
        for field in fleet_fields
    )

    if fleet_size <= 0:
        raise HTTPException(
            status_code=400,
            detail="Carrier fleet profile contains no vehicles"
        )

    # ============================================================
    # 8. VALIDATE BID RATE
    # ============================================================

    if bid_data.bid_per_shipment is None:
        raise HTTPException(
            status_code=400,
            detail="Bid per shipment is required"
        )

    if bid_data.bid_per_shipment <= 0:
        raise HTTPException(
            status_code=400,
            detail="Bid per shipment must be greater than zero"
        )

    # ============================================================
    # 9. VALIDATE SLOTS PER INTERVAL
    # ============================================================

    if bid_data.slots_per_interval is None:
        raise HTTPException(
            status_code=400,
            detail="Slots per interval is required"
        )

    if bid_data.slots_per_interval <= 0:
        raise HTTPException(
            status_code=400,
            detail="Slots per interval must be greater than zero"
        )

    # ============================================================
    # 10. GET VOLUME PROFILES
    # ============================================================

    volume_profiles = db.query(
        Lane_Tender_RFQ_Volume_Profile
    ).filter(
        Lane_Tender_RFQ_Volume_Profile.tender_id == tender.id
    ).order_by(
        Lane_Tender_RFQ_Volume_Profile.period_sequence
    ).all()

    if not volume_profiles:
        raise HTTPException(
            status_code=400,
            detail="Tender does not contain a volume profile"
        )

    # ============================================================
    # 11. DETERMINE NUMBER OF CONTRACT INTERVALS
    # ============================================================

    number_of_intervals = len(volume_profiles)

    # ============================================================
    # 12. CALCULATE PER-SLOT SIZE
    #
    # Example:
    #
    # 4 weekly volume profiles
    # 2 slots per interval
    #
    # 2 × 4 = 8
    #
    # Therefore this bid represents 8 total contract slots.
    # ============================================================

    per_slot_size = (
        bid_data.slots_per_interval
        * number_of_intervals
    )

    if per_slot_size <= 0:
        raise HTTPException(
            status_code=400,
            detail="Unable to calculate contract slot size"
        )

    # ============================================================
    # 13. CALCULATE TOTAL CONTRACT BID
    #
    # Example:
    #
    # R10,000 per shipment
    # × 8 contract slots
    # = R80,000
    # ============================================================

    total_contract_bid = (
        bid_data.bid_per_shipment
        * per_slot_size
    )

    # ============================================================
    # 14. CREATE BID
    # ============================================================

    bid = Lane_Tender_RFQ_Bids(
        tender_id=tender.id,
        carrier_id=carrier.id,
        bidder_user_id=user_id,
        carrier_name=carrier.legal_business_name,
        fleet_size=fleet_size,
        primary_lanes=carrier_profile.primary_routes,
        bid_per_shipment=bid_data.bid_per_shipment,
        slots_per_interval=bid_data.slots_per_interval,
        per_slot_size=per_slot_size,
        bid_notes=bid_data.bid_notes,
        status="Submitted"
    )

    # ============================================================
    # 15. SAVE
    # ============================================================

    db.add(bid)
    db.commit()
    db.refresh(bid)

    # ============================================================
    # 16. RESPONSE
    # ============================================================

    return {
        "message": "Tender bid submitted successfully",
        "bid_id": bid.id,
        "tender_id": tender.id,
        "carrier_id": carrier.id,
        "bid_per_shipment": float(bid.bid_per_shipment),
        "slots_per_interval": bid.slots_per_interval,
        "number_of_intervals": number_of_intervals,
        "per_slot_size": bid.per_slot_size,
        "total_contract_bid": float(total_contract_bid),
        "fleet_size": fleet_size,
        "status": bid.status
    }