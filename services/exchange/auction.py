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


from decimal import Decimal
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

# Make sure these are imported from your actual model locations
# from models.client_shipment import Client_Shipment
# from models.client_shipment_stop import Client_Shipment_Stop
# from models.client_shipment_vehicle_requirement import Client_Shipment_Vehicle_Requirement
# from models.carrier_shipment import Carrier_Shipment
# from models.auction import Client_Shipment_Auction
# from models.auction_stop import Client_Shipment_Auction_Stop
# from models.auction_vehicle_requirement import Client_Shipment_Auction_Vehicle_Requirement
# from models.auction_bid import Shipment_Auction_Bid
# from services.commission import calculate_commission


def accept_auction_bid(
    auction_id: int,
    bid_id: int,
    db: Session,
    current_user: dict
):
    """
    Accept a carrier bid on a shipment auction.

    Creates:
        - Client Shipment(s)
        - Client Shipment Stop(s)
        - Client Shipment Vehicle Requirement(s)
        - Carrier Shipment(s)

    All records are created inside one database transaction.
    If anything fails, the entire transaction is rolled back.
    """

    # ============================================================
    # 1. AUTHENTICATION
    # ============================================================

    company_id = current_user.get("company_id")
    user_id = current_user.get("id")

    if company_id is None:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    if user_id is None:
        raise HTTPException(
            status_code=400,
            detail="User ID missing from authentication token"
        )

    try:

        # ========================================================
        # 2. LOAD AUCTION
        # ========================================================

        auction = (
            db.query(Client_Shipment_Auction)
            .filter(
                Client_Shipment_Auction.id == auction_id
            )
            .first()
        )

        if auction is None:
            raise HTTPException(
                status_code=404,
                detail=f"Auction {auction_id} not found"
            )

        # ========================================================
        # 3. VALIDATE AUCTION
        # ========================================================

        if auction.slots_remaining is None:
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Auction {auction.id} has no slots_remaining value. "
                    "The auction record is invalid."
                )
            )

        if auction.slots_remaining <= 0:
            auction.slots_remaining = 0
            auction.status = "Closed"

            raise HTTPException(
                status_code=403,
                detail=(
                    "Sorry, the auction has closed and all available "
                    "slots have already been awarded."
                )
            )

        # ========================================================
        # 4. LOAD BID
        # ========================================================

        bid = (
            db.query(Shipment_Auction_Bid)
            .filter(
                Shipment_Auction_Bid.id == bid_id,
                Shipment_Auction_Bid.auction_id == auction.id
            )
            .first()
        )

        if bid is None:
            raise HTTPException(
                status_code=404,
                detail=f"Bid {bid_id} not found for auction {auction_id}"
            )

        # ========================================================
        # 5. VALIDATE BID
        # ========================================================

        if bid.status == "Rejected":
            raise HTTPException(
                status_code=403,
                detail="This bid has already been rejected."
            )

        if bid.status == "Outbidded":
            raise HTTPException(
                status_code=403,
                detail="This bid has been outbidded and cannot be accepted."
            )

        if bid.status == "Under-Review":
            raise HTTPException(
                status_code=403,
                detail="This bid is currently under review."
            )

        if bid.rate is None:
            raise HTTPException(
                status_code=400,
                detail="Cannot accept bid because the bid rate is missing."
            )

        if bid.number_of_loads is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Cannot accept bid because the number of loads "
                    "requested by the carrier is missing."
                )
            )

        if bid.number_of_loads <= 0:
            raise HTTPException(
                status_code=400,
                detail="Bid number_of_loads must be greater than zero."
            )

        if bid.carrier_id is None:
            raise HTTPException(
                status_code=400,
                detail="Cannot accept bid because carrier_id is missing."
            )

        # ========================================================
        # 6. DETERMINE NUMBER OF LOADS
        # ========================================================

        number_to_assign = min(
            int(bid.number_of_loads),
            int(auction.slots_remaining)
        )

        if number_to_assign <= 0:
            raise HTTPException(
                status_code=400,
                detail="No loads are available to assign."
            )

        # ========================================================
        # 7. LOAD AUCTION STOPS
        # ========================================================

        auction_stops = (
            db.query(Client_Shipment_Auction_Stop)
            .filter(
                Client_Shipment_Auction_Stop.auction_id == auction.id
            )
            .order_by(
                Client_Shipment_Auction_Stop.stop_sequence.asc()
            )
            .all()
        )

        if not auction_stops:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Auction {auction.id} has no routing stops. "
                    "At least one origin and destination are required."
                )
            )

        # ========================================================
        # 8. LOAD VEHICLE REQUIREMENTS
        # ========================================================

        auction_requirements = (
            db.query(Client_Shipment_Auction_Vehicle_Requirement)
            .filter(
                Client_Shipment_Auction_Vehicle_Requirement.auction_id
                == auction.id
            )
            .all()
        )

        # ========================================================
        # 9. COMMISSION
        # ========================================================

        commission_result = calculate_commission(
            db=db,
            shipment_rate=Decimal(str(bid.rate))
        )

        if commission_result is None:
            raise HTTPException(
                status_code=500,
                detail="Commission calculation returned no result."
            )

        service_fee = commission_result.get("commission")

        if service_fee is None:
            raise HTTPException(
                status_code=500,
                detail="Commission calculation returned no commission value."
            )

        # ========================================================
        # 10. TRACK CREATED SHIPMENTS
        # ========================================================

        created_shipments = []

        # ========================================================
        # 11. CREATE EACH AWARDED LOAD
        # ========================================================

        for load_number in range(1, number_to_assign + 1):

            # ----------------------------------------------------
            # 11A. CREATE CLIENT SHIPMENT
            # ----------------------------------------------------

            client_shipment = Client_Shipment(
                is_subshipment=False,

                auction_id=auction.id,

                booking_source="Shipment Exchange",

                shipment_reference=auction.shipment_reference,

                booking_reference=auction.booking_reference,

                trip_type=auction.trip_type,

                load_type=auction.load_type,

                client_id=auction.client_id,

                client_user_id=auction.client_user_id,

                rate=bid.rate,

                pricing_basis=auction.pricing_basis,

                vat_included=auction.vat_included,

                payment_terms=auction.payment_terms,

                pickup_date=auction.pickup_date,

                priority_level=auction.priority_level,

                customer_reference_number=auction.customer_reference_number,

                shipment_weight=auction.shipment_weight,

                commodity=auction.commodity,

                temperature_control=auction.temperature_control,

                target_temperature_spec=auction.target_temperature_spec,

                hazardous_materials=(
                    auction.hazardous_materials
                    if auction.hazardous_materials is not None
                    else False
                ),

                hazchem_classification=auction.hazchem_classification,

                under_bond=(
                    auction.under_bond
                    if auction.under_bond is not None
                    else False
                ),

                rib_requirements=(
                    auction.rib_requirements
                    if auction.rib_requirements is not None
                    else False
                ),

                packaging_quantity=auction.packaging_quantity,

                packaging_type=auction.packaging_type,

                distance=auction.distance,

                estimated_transit_time=auction.estimated_transit_time,

                eta_date=auction.eta_date,

                eta_window=None,

                route_preview_embed=auction.route_preview_embed,

                polyline=auction.polyline,

                status="Booked",

                trip_status="Schedule",

                carrier_id=bid.carrier_id,

                rate_includes_fuel=(
                    auction.rate_includes_fuel
                    if auction.rate_includes_fuel is not None
                    else False
                ),

                rate_includes_driver=(
                    auction.rate_includes_driver
                    if auction.rate_includes_driver is not None
                    else False
                ),

                rate_includes_maintenance=(
                    auction.rate_includes_maintenance
                    if auction.rate_includes_maintenance is not None
                    else False
                ),

                rate_includes_insurance=(
                    auction.rate_includes_insurance
                    if auction.rate_includes_insurance is not None
                    else False
                ),

                rate_includes_tolls=(
                    auction.rate_includes_tolls
                    if auction.rate_includes_tolls is not None
                    else False
                ),

                rate_includes_border_charges=(
                    auction.rate_includes_border_charges
                    if auction.rate_includes_border_charges is not None
                    else False
                ),

                rate_includes_empty_return=(
                    auction.rate_includes_empty_return
                    if auction.rate_includes_empty_return is not None
                    else False
                ),

                rate_includes_waiting_time=(
                    auction.rate_includes_waiting_time
                    if auction.rate_includes_waiting_time is not None
                    else False
                ),

                rate_includes_loading_assistance=(
                    auction.rate_includes_loading_assistance
                    if auction.rate_includes_loading_assistance is not None
                    else False
                ),

                rate_includes_offloading_assistance=(
                    auction.rate_includes_offloading_assistance
                    if auction.rate_includes_offloading_assistance is not None
                    else False
                ),

                minimum_weight_bracket_kg=(
                    auction.minimum_weight_bracket
                    if auction.minimum_weight_bracket is not None
                    else 0
                ),

                vehicle_tracking_required=(
                    auction.vehicle_tracking_required
                    if auction.vehicle_tracking_required is not None
                    else False
                ),

                all_time_hour_control_room=(
                    auction.all_time_hour_control_room
                    if auction.all_time_hour_control_room is not None
                    else False
                ),

                driver_mobile_phone=(
                    auction.driver_mobile_phone
                    if auction.driver_mobile_phone is not None
                    else False
                ),

                clean_compliant_equipment=(
                    auction.clean_compliant_equipment
                    if auction.clean_compliant_equipment is not None
                    else False
                ),

                pallet_management=(
                    auction.pallet_management
                    if auction.pallet_management is not None
                    else False
                ),

                pod_submission_local=auction.pod_submission_local,

                pod_submission_long_haul=auction.pod_submission_long_haul,

                pod_submission_cross_border=auction.pod_submission_cross_border,

                minimum_git_cover_amount=auction.minimum_git_cover_amount,

                minimum_liability_cover_amount=auction.minimum_liability_cover_amount,

                git_all_risk_required=(
                    auction.git_all_risk_required
                    if auction.git_all_risk_required is not None
                    else False
                ),

                git_first_loss_required=(
                    auction.git_first_loss_required
                    if auction.git_first_loss_required is not None
                    else False
                ),

                git_driver_fidelity_required=(
                    auction.git_driver_fidelity_required
                    if auction.git_driver_fidelity_required is not None
                    else False
                ),

                tarpaulin_compliance_required=(
                    auction.tarpaulin_compliance_required
                    if auction.tarpaulin_compliance_required is not None
                    else False
                ),

                corner_plates_required=(
                    auction.corner_plates_required
                    if auction.corner_plates_required is not None
                    else False
                ),

                chock_blocks_required=(
                    auction.chock_blocks_required
                    if auction.chock_blocks_required is not None
                    else False
                ),

                ratchets_belts_required=(
                    auction.ratchets_belts_required
                    if auction.ratchets_belts_required is not None
                    else False
                ),

                other_equipment_requirements=(
                    auction.other_equipment_requirements
                )
            )

            db.add(client_shipment)

            # IMPORTANT:
            # Flush ONLY this shipment so we obtain its ID.
            db.flush()

            if client_shipment.id is None:
                raise RuntimeError(
                    "Client shipment was created but no database ID was returned."
                )

            client_shipment_id = client_shipment.id

            # ----------------------------------------------------
            # 11B. CREATE STOPS
            # ----------------------------------------------------

            # ----------------------------------------------------
            # 11C. CREATE VEHICLE REQUIREMENTS
            # ----------------------------------------------------

            for requirement in auction_requirements:

                # These are NOT nullable in the destination table.
                if requirement.configuration_type is None:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Auction vehicle requirement is missing "
                            "configuration_type."
                        )
                    )

                if requirement.truck_type is None:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Auction vehicle requirement is missing "
                            "truck_type."
                        )
                    )

                if requirement.equipment_type is None:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Auction vehicle requirement is missing "
                            "equipment_type."
                        )
                    )

                shipment_requirement = Client_Shipment_Vehicle_Requirement(
                    shipment_id=client_shipment_id,

                    configuration_type=requirement.configuration_type,

                    truck_type=requirement.truck_type,

                    equipment_type=requirement.equipment_type,

                    trailer_type=requirement.trailer_type,

                    trailer_length=requirement.trailer_length,
                )

                db.add(shipment_requirement)

            db.flush()

            # ----------------------------------------------------
            # 11D. CREATE CARRIER SHIPMENT
            # ----------------------------------------------------

            carrier_reference = (
                f"EX-{auction.id}-"
                f"{bid.carrier_id}-"
                f"{uuid.uuid4().hex[:8].upper()}"
            )

            carrier_shipment = Carrier_Shipment(
                is_subshipment=False,

                auction_id=auction.id,

                booking_source="Shipment Exchange",

                shipment_reference=carrier_reference,

                booking_reference=auction.booking_reference,

                trip_type=auction.trip_type,

                load_type=auction.load_type,

                carrier_id=bid.carrier_id,

                carrier_user_id=bid.bidder_user_id,

                rate=bid.rate,

                service_fee=service_fee,

                pricing_basis=auction.pricing_basis,

                vat_included=auction.vat_included,

                payment_terms=auction.payment_terms,

                pickup_date=auction.pickup_date,

                priority_level=auction.priority_level,

                customer_reference_number=auction.customer_reference_number,

                shipment_weight=auction.shipment_weight,

                commodity=auction.commodity,

                temperature_control=auction.temperature_control,

                target_temperature_spec=auction.target_temperature_spec,

                hazardous_materials=(
                    auction.hazardous_materials
                    if auction.hazardous_materials is not None
                    else False
                ),

                hazchem_classification=auction.hazchem_classification,

                under_bond=(
                    auction.under_bond
                    if auction.under_bond is not None
                    else False
                ),

                rib_requirements=(
                    auction.rib_requirements
                    if auction.rib_requirements is not None
                    else False
                ),

                packaging_quantity=auction.packaging_quantity,

                packaging_type=auction.packaging_type,

                distance=auction.distance,

                estimated_transit_time=auction.estimated_transit_time,

                eta_date=auction.eta_date,

                eta_window=None,

                route_preview_embed=auction.route_preview_embed,

                polyline=auction.polyline,

                status="Booked",

                trip_status="Schedule",

                vehicle_id=None,

                driver_id=None,

                rate_includes_fuel=(
                    auction.rate_includes_fuel
                    if auction.rate_includes_fuel is not None
                    else False
                ),

                rate_includes_driver=(
                    auction.rate_includes_driver
                    if auction.rate_includes_driver is not None
                    else False
                ),

                rate_includes_maintenance=(
                    auction.rate_includes_maintenance
                    if auction.rate_includes_maintenance is not None
                    else False
                ),

                rate_includes_insurance=(
                    auction.rate_includes_insurance
                    if auction.rate_includes_insurance is not None
                    else False
                ),

                rate_includes_tolls=(
                    auction.rate_includes_tolls
                    if auction.rate_includes_tolls is not None
                    else False
                ),

                rate_includes_border_charges=(
                    auction.rate_includes_border_charges
                    if auction.rate_includes_border_charges is not None
                    else False
                ),

                rate_includes_empty_return=(
                    auction.rate_includes_empty_return
                    if auction.rate_includes_empty_return is not None
                    else False
                ),

                rate_includes_waiting_time=(
                    auction.rate_includes_waiting_time
                    if auction.rate_includes_waiting_time is not None
                    else False
                ),

                rate_includes_loading_assistance=(
                    auction.rate_includes_loading_assistance
                    if auction.rate_includes_loading_assistance is not None
                    else False
                ),

                rate_includes_offloading_assistance=(
                    auction.rate_includes_offloading_assistance
                    if auction.rate_includes_offloading_assistance is not None
                    else False
                ),

                minimum_weight_bracket_kg=(
                    auction.minimum_weight_bracket
                    if auction.minimum_weight_bracket is not None
                    else 0
                ),

                vehicle_tracking_required=(
                    auction.vehicle_tracking_required
                    if auction.vehicle_tracking_required is not None
                    else False
                ),

                all_time_hour_control_room=(
                    auction.all_time_hour_control_room
                    if auction.all_time_hour_control_room is not None
                    else False
                ),

                driver_mobile_phone=(
                    auction.driver_mobile_phone
                    if auction.driver_mobile_phone is not None
                    else False
                ),

                clean_compliant_equipment=(
                    auction.clean_compliant_equipment
                    if auction.clean_compliant_equipment is not None
                    else False
                ),

                pallet_management=(
                    auction.pallet_management
                    if auction.pallet_management is not None
                    else False
                ),

                pod_submission_local=auction.pod_submission_local,

                pod_submission_long_haul=auction.pod_submission_long_haul,

                pod_submission_cross_border=auction.pod_submission_cross_border,

                minimum_git_cover_amount=auction.minimum_git_cover_amount,

                minimum_liability_cover_amount=auction.minimum_liability_cover_amount,

                git_all_risk_required=(
                    auction.git_all_risk_required
                    if auction.git_all_risk_required is not None
                    else False
                ),

                git_first_loss_required=(
                    auction.git_first_loss_required
                    if auction.git_first_loss_required is not None
                    else False
                ),

                git_driver_fidelity_required=(
                    auction.git_driver_fidelity_required
                    if auction.git_driver_fidelity_required is not None
                    else False
                ),

                tarpaulin_compliance_required=(
                    auction.tarpaulin_compliance_required
                    if auction.tarpaulin_compliance_required is not None
                    else False
                ),

                corner_plates_required=(
                    auction.corner_plates_required
                    if auction.corner_plates_required is not None
                    else False
                ),

                chock_blocks_required=(
                    auction.chock_blocks_required
                    if auction.chock_blocks_required is not None
                    else False
                ),

                ratchets_belts_required=(
                    auction.ratchets_belts_required
                    if auction.ratchets_belts_required is not None
                    else False
                ),

                other_equipment_requirements=(
                    auction.other_equipment_requirements
                )
            )

            db.add(carrier_shipment)

            db.flush()

            if carrier_shipment.id is None:
                raise RuntimeError(
                    "Carrier shipment was created but no database ID was returned."
                )

            carrier_shipment_id = carrier_shipment.id

            # ----------------------------------------------------
            # 11E. LINK CREATED RECORDS
            # ----------------------------------------------------

            created_shipments.append({
                "load_number": load_number,
                "client_shipment_id": client_shipment_id,
                "carrier_shipment_id": carrier_shipment_id
            })

        # ========================================================
        # 12. UPDATE AUCTION
        # ========================================================

        auction.slots_remaining = (
            int(auction.slots_remaining) - number_to_assign
        )

        if auction.slots_remaining <= 0:
            auction.slots_remaining = 0
            auction.status = "Closed"

        # ========================================================
        # 13. UPDATE BID
        # ========================================================

        bid.status = "Accepted"

        # ========================================================
        # 14. FINAL COMMIT
        # ========================================================

        db.commit()

        # ========================================================
        # 15. RETURN SUCCESS
        # ========================================================

        return {
            "message": "Bid awarded successfully",

            "auction_id": auction.id,

            "bid_id": bid.id,

            "carrier_id": bid.carrier_id,

            "requested_loads": bid.number_of_loads,

            "assigned_loads": number_to_assign,

            "slots_remaining": auction.slots_remaining,

            "auction_status": auction.status,

            "bid_status": bid.status,

            "rate": float(bid.rate),

            "service_fee": float(service_fee),

            "combined_rate": float(
                bid.rate * number_to_assign
            ),

            "created_shipments": created_shipments
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:

        db.rollback()

        import traceback

        print("=" * 100)
        print("ERROR ACCEPTING AUCTION BID")
        print(f"ERROR TYPE: {type(e).__name__}")
        print(f"ERROR: {str(e)}")
        print("FULL TRACEBACK:")
        traceback.print_exc()
        print("=" * 100)

        raise HTTPException(
            status_code=500,
            detail=(
                f"Failed to accept auction bid: "
                f"{type(e).__name__}: {str(e)}"
            )
        )


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