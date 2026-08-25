from datetime import date, datetime, time, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session
from schemas.exchange_bookings.ftl_shipment import (
    ClientShipmentAuctionCreate,
    ClientShipmentAuctionVehicleRequirementCreate,
    ClientShipmentAuctionStopCreate,
)
from models.Exchange.ftl_shipment import (
    Client_Shipment_Auction,
    Client_Shipment_Auction_Stop,
    Client_Shipment_Auction_Vehicle_Requirement,
)
from models.brokerage.finance import FinancialAccounts
from models.shipper import Corporation
from models.brokerage.loadboard import Shipment_Auction_Loadboard
from utils.google_maps import AddressInput, RouteETAInput, calculate_distance, get_eta_and_polyline
from decimal import Decimal


def calculate_service_fee(
    pricing_basis,
    benchmark_rate,
    distance=None,
    shipment_weight=None
):
    """
    Calculate SADC FREIGHTLINK service fee based on the
    calculated shipment benchmark value.

    Pricing basis:
        - Rate Per Load
        - Fixed Trip Rate
        - Rate per Container
        - Rate per KM
        - Rate per Ton

    Service fee:
        <= R12,500  -> R200
        <= R18,000  -> R400
        <= R24,000  -> R600
        >  R24,000  -> R850
    """

    if benchmark_rate is None:
        raise ValueError("Benchmark rate is required.")

    benchmark_rate = Decimal(str(benchmark_rate))

    if benchmark_rate < 0:
        raise ValueError("Benchmark rate cannot be negative.")

    pricing_basis = str(pricing_basis).strip().lower()

    # ============================================================
    # CALCULATE ACTUAL SHIPMENT VALUE
    # ============================================================

    if pricing_basis in {
        "rate per load",
        "fixed trip rate",
        "rate per container"
    }:
        calculated_rate = benchmark_rate

    elif pricing_basis == "rate per km":

        if distance is None:
            raise ValueError(
                "Distance is required when pricing basis is Rate per KM."
            )

        distance = Decimal(str(distance))

        if distance < 0:
            raise ValueError("Distance cannot be negative.")

        calculated_rate = benchmark_rate * distance

    elif pricing_basis in {
        "rate per ton",
        "rate per tonne"
    }:

        if shipment_weight is None:
            raise ValueError(
                "Shipment weight is required when pricing basis is Rate per Ton."
            )

        shipment_weight = Decimal(str(shipment_weight))

        if shipment_weight < 0:
            raise ValueError("Shipment weight cannot be negative.")

        # Shipment weight is stored in KG.
        # Convert KG -> TON.
        shipment_weight_tons = shipment_weight / Decimal("1000")

        calculated_rate = benchmark_rate * shipment_weight_tons

    else:
        raise ValueError(
            f"Unsupported pricing basis: {pricing_basis}"
        )

    # ============================================================
    # CALCULATE SERVICE FEE
    # ============================================================

    if calculated_rate <= Decimal("12500"):
        service_fee = Decimal("200")

    elif calculated_rate <= Decimal("18000"):
        service_fee = Decimal("400")

    elif calculated_rate <= Decimal("24000"):
        service_fee = Decimal("600")

    else:
        service_fee = Decimal("850")

    return {
        "benchmark_rate": benchmark_rate,
        "calculated_rate": calculated_rate,
        "service_fee": service_fee,
        "pricing_basis": pricing_basis
    }

def calculate_auction_distance(
    origin_address: str,
    destination_address: str,
    stops=None
):
    """
    Calculate the complete tender route distance using:

    Origin
        ↓
    Stop 1
        ↓
    Stop 2
        ↓
    ...
        ↓
    Destination

    Uses the existing calculate_distance() function.
    """

    # ---------------------------------------------------------
    # Build waypoint list from tender stops
    # ---------------------------------------------------------

    waypoints = []

    if stops:
        # Sort stops by stop_sequence
        sorted_stops = sorted(
            stops,
            key=lambda stop: stop.stop_sequence
        )

        waypoints = [
            stop.address.strip()
            for stop in sorted_stops
            if stop.address and stop.address.strip()
        ]

    # ---------------------------------------------------------
    # Build AddressInput for existing distance function
    # ---------------------------------------------------------

    route_input = AddressInput(
        origin_address=origin_address,
        destination_address=destination_address,
        waypoints=waypoints
    )

    # ---------------------------------------------------------
    # Call existing Google Maps distance function
    # ---------------------------------------------------------

    result = calculate_distance(route_input)

    # ---------------------------------------------------------
    # Extract calculated distance
    # ---------------------------------------------------------

    distance_km = result.get("distance")

    if distance_km is None:
        raise HTTPException(
            status_code=400,
            detail="Google Maps did not return a route distance."
        )

    return distance_km


def create_auction_and_publish(
    db: Session,
    auction_data: ClientShipmentAuctionCreate,
    current_user: dict
):
    try:

        # ============================================================
        # STEP 1 — AUTHENTICATE / VALIDATE SHIPPER
        # ============================================================

        assert "company_id" in current_user, "Missing company_id in current_user"

        print(f"current_user: {current_user}")

        company_id = current_user.get("company_id")
        user_id = current_user.get("id")

        if not company_id:
            raise HTTPException(
                status_code=400,
                detail="User does not belong to a company."
            )

        shipper = (
            db.query(Corporation)
            .filter(Corporation.id == company_id)
            .first()
        )

        if not shipper:
            raise HTTPException(
                status_code=400,
                detail="Shipper account not found or not active."
            )

        if not shipper.is_verified:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Shipper account is not verified. "
                    "Please await verification to create a shipment exchange."
                )
            )

        if shipper.status != "Active":
            raise HTTPException(
                status_code=403,
                detail=(
                    "Shipper account is not active. "
                    "Please await account activation to create a shipment exchange."
                )
            )

        # ============================================================
        # STEP 2 — RETRIEVE FINANCIAL ACCOUNT
        # ============================================================

        financial_account = (
            db.query(FinancialAccounts)
            .filter(FinancialAccounts.id == shipper.id)
            .first()
        )

        if not financial_account:
            raise HTTPException(
                status_code=404,
                detail="Financial account not found."
            )

        if not financial_account.is_verified:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Financial account is not verified. "
                    "Please await verification to create and finance "
                    "a shipment exchange."
                )
            )

        if financial_account.status != "Active":
            raise HTTPException(
                status_code=403,
                detail=(
                    "Financial account is not active. "
                    "Please await activation to create and finance "
                    "a shipment exchange."
                )
            )

        # ========================================================
        # 6. VALIDATE STOP SEQUENCES
        # ========================================================
        sorted_stops = sorted(
            auction_data.stops,
            key=lambda s: s.stop_sequence
        )
        stop_sequences = [stop.stop_sequence for stop in sorted_stops]
        expected_sequences = list(range(1, len(sorted_stops) + 1))
        if stop_sequences != expected_sequences:
            raise HTTPException(
                status_code=400,
                detail="Tender intermediate stop sequences must be consecutive starting from 1."
            )

        # ========================================================
        # 7. BUILD GOOGLE MAPS WAYPOINTS
        # ========================================================
        waypoints = [
            stop.address.strip()
            for stop in sorted_stops
            if stop.address and stop.address.strip()
        ]

        # ========================================================
        # 8. CALCULATE COMPLETE ROUTE
        # ========================================================
        try:
            distance_data = calculate_distance(
                AddressInput(
                    origin_address=auction_data.origin.address,
                    destination_address=auction_data.destination.address,
                    waypoints=waypoints
                )
            )
        except HTTPException as e:
            raise HTTPException(
                status_code=500,
                detail=f"Google Maps routing calculation failed: {e.detail}"
            )

        if not isinstance(distance_data, dict):
            raise HTTPException(
                status_code=500,
                detail="Google Maps routing calculation returned an invalid response."
            )

        distance_km = distance_data.get("distance")
        estimated_transit_time = distance_data.get("duration")
        route_preview_embed = distance_data.get("google_maps_embed_url")

        if distance_km is None:
            raise HTTPException(
                status_code=400,
                detail="Google Maps did not return a valid route distance."
            )

        # ========================================================
        # 9. EXTRACT ORIGIN GEO INFORMATION
        # ========================================================
        complete_origin_address = distance_data.get(
            "complete_origin_address",
            auction_data.origin.address
        )
        origin_city_province = distance_data.get("origin_city_province")
        origin_country = distance_data.get("origin_country")
        origin_region = distance_data.get("origin_region")
        
        # 💻 Added coordinates extraction
        origin_latitude = distance_data.get("origin_latitude")
        origin_longitude = distance_data.get("origin_longitude")

        # ========================================================
        # 10. EXTRACT DESTINATION GEO INFORMATION
        # ========================================================
        complete_destination_address = distance_data.get(
            "complete_destination_address",
            auction_data.destination.address
        )
        destination_city_province = distance_data.get("destination_city_province")
        destination_country = distance_data.get("destination_country")
        destination_region = distance_data.get("destination_region")
        
        # 💻 Added coordinates extraction
        destination_latitude = distance_data.get("destination_latitude")
        destination_longitude = distance_data.get("destination_longitude")

        # ========================================================
        # 11. EXTRACT INTERMEDIATE STOP GEO INFORMATION
        # ========================================================
        calculated_stops = []

        for index, stop_data in enumerate(sorted_stops, start=1):
            calculated_stops.append({
                "complete_address": distance_data.get(
                    f"complete_stop_{index}_address",
                    stop_data.address
                ),
                "city_province": distance_data.get(
                    f"stop_{index}_city_province"
                ),
                "country": distance_data.get(
                    f"stop_{index}_country"
                ),
                "region": distance_data.get(
                    f"stop_{index}_region"
                ),
                # 💻 Added coordinates extraction per sequence index
                "latitude": distance_data.get(
                    f"stop_{index}_latitude"
                ),
                "longitude": distance_data.get(
                    f"stop_{index}_longitude"
                ),
            })

        # Step 2: get ETA Date, ETA Window, Polylines
        try:
            trip_data = get_eta_and_polyline(RouteETAInput(
                origin_address=auction_data.origin.address,
                destination_address=auction_data.destination.address,
                start_date=auction_data.pickup_date,
                start_time=auction_data.origin.operating_end_time,
            ))
            eta_date = trip_data["eta_date"]  # Distance in kilometers
            eta_window = trip_data["eta_window"]  # Transit time as text
            polyline = trip_data["polyline"]
        except HTTPException as e:
            raise HTTPException(status_code=500, detail=f"Trip info calculation failed: {e.detail}")
    
        def safe_str(val):
            return val.value if hasattr(val, "value") else str(val)
        # ============================================================
        # STEP 10 — NORMALIZE AUCTION CLOSING DATE TO UTC
        # ============================================================

        auction_closing_date = auction_data.auction_closing_date

        if auction_closing_date.tzinfo is None:
            auction_closing_date = auction_closing_date.replace(
                tzinfo=timezone.utc
            )
        else:
            auction_closing_date = (
                auction_closing_date.astimezone(timezone.utc)
            )

        # ============================================================
        # STEP 11 — CREATE MASTER AUCTION
        # ============================================================

        auction = Client_Shipment_Auction(
            client_id=shipper.id,
            client_user_id=user_id,

            shipment_reference=auction_data.shipment_reference,
            booking_reference=auction_data.booking_reference,

            trip_type=auction_data.trip_type,
            load_type=auction_data.load_type,

            payment_terms=financial_account.payment_terms,

            pickup_date=auction_data.pickup_date,
            priority_level=auction_data.priority_level,

            customer_reference_number=(
                auction_data.customer_reference_number
            ),

            shipment_weight=auction_data.shipment_weight,
            commodity=auction_data.commodity,

            temperature_control=(
                auction_data.temperature_control
            ),

            target_temperature_spec=(
                auction_data.target_temperature_spec
            ),

            hazardous_materials=(
                auction_data.hazardous_materials
            ),
            hazchem_classification=auction_data.hazchem_classification,

            under_bond=auction_data.under_bond,
            rib_requirements=auction_data.rib_requirements,

            packaging_quantity=(
                auction_data.packaging_quantity
            ),

            packaging_type=auction_data.packaging_type,

            distance=distance_km,
            estimated_transit_time=estimated_transit_time,
            eta_date=eta_date,
            polyline=polyline,

            # ========================================================
            # RATE INCLUDES
            # ========================================================

            rate_includes_fuel=auction_data.rate_includes_fuel,
            rate_includes_driver=auction_data.rate_includes_driver,
            rate_includes_maintenance=(
                auction_data.rate_includes_maintenance
            ),
            rate_includes_insurance=(
                auction_data.rate_includes_insurance
            ),
            rate_includes_tolls=auction_data.rate_includes_tolls,
            rate_includes_border_charges=(
                auction_data.rate_includes_border_charges
            ),
            rate_includes_empty_return=(
                auction_data.rate_includes_empty_return
            ),
            rate_includes_waiting_time=(
                auction_data.rate_includes_waiting_time
            ),
            rate_includes_loading_assistance=(
                auction_data.rate_includes_loading_assistance
            ),
            rate_includes_offloading_assistance=(
                auction_data.rate_includes_offloading_assistance
            ),

            # ========================================================
            # EXCHANGE & BIDDING
            # ========================================================

            auction_closing_date=auction_closing_date,

            pricing_basis=auction_data.pricing_basis,

            vat_included=auction_data.vat_included,

            book_now_rate=auction_data.book_now_rate,

            procurement_target_rate=(
                auction_data.procurement_target_rate
            ),

            rate_direction=auction_data.rate_direction,

            # ========================================================
            # OPERATIONAL REQUIREMENTS
            # ========================================================

            vehicle_tracking_required=(
                auction_data.vehicle_tracking_required
            ),

            all_time_hour_control_room=(
                auction_data.all_time_hour_control_room
            ),

            driver_mobile_phone=(
                auction_data.driver_mobile_phone
            ),

            clean_compliant_equipment=(
                auction_data.clean_compliant_equipment
            ),

            pallet_management=(
                auction_data.pallet_management
            ),

            pod_submission_local=(
                auction_data.pod_submission_local
            ),

            pod_submission_long_haul=(
                auction_data.pod_submission_long_haul
            ),

            pod_submission_cross_border=(
                auction_data.pod_submission_cross_border
            ),

            # ========================================================
            # INSURANCE REQUIREMENTS
            # ========================================================

            minimum_git_cover_amount=(
                auction_data.minimum_git_cover_amount
            ),

            minimum_liability_cover_amount=(
                auction_data.minimum_liability_cover_amount
            ),

            git_all_risk_required=(
                auction_data.git_all_risk_required
            ),

            git_first_loss_required=(
                auction_data.git_first_loss_required
            ),

            git_driver_fidelity_required=(
                auction_data.git_driver_fidelity_required
            ),

            # ========================================================
            # EQUIPMENT COMPLIANCE
            # ========================================================

            tarpaulin_compliance_required=(
                auction_data.tarpaulin_compliance_required
            ),

            corner_plates_required=(
                auction_data.corner_plates_required
            ),

            chock_blocks_required=(
                auction_data.chock_blocks_required
            ),

            ratchets_belts_required=(
                auction_data.ratchets_belts_required
            ),

            other_equipment_requirements=(
                auction_data.other_equipment_requirements
            ),
        )

        db.add(auction)

        # Generate auction.id
        db.flush()

        # ============================================================
        # STEP 12 — CREATE ORIGIN STOP
        # ============================================================

        origin_stop = Client_Shipment_Auction_Stop(
            auction_id=auction.id,

            stop_sequence=0,
            stop_type="Origin",

            address=auction_data.origin.address,

            complete_address=complete_origin_address,
            city_province=origin_city_province,
            country=origin_country,
            region=origin_region,

            latitude=origin_latitude,
            longitude=origin_longitude,

            facility_name=auction_data.origin.facility_name,

            scheduling_type=(
                auction_data.origin.scheduling_type.value
            ),

            operating_start_time=(
                auction_data.origin.operating_start_time
            ),

            operating_end_time=(
                auction_data.origin.operating_end_time
            ),

            open_monday=auction_data.origin.open_monday,
            open_tuesday=auction_data.origin.open_tuesday,
            open_wednesday=auction_data.origin.open_wednesday,
            open_thursday=auction_data.origin.open_thursday,
            open_friday=auction_data.origin.open_friday,
            open_saturday=auction_data.origin.open_saturday,
            open_sunday=auction_data.origin.open_sunday,

            reference_number=(
                auction_data.origin.reference_number
            ),

            notes=auction_data.origin.notes,

            contact_first_name=(
                auction_data.origin.contact.first_name
                if auction_data.origin.contact
                else None
            ),

            contact_last_name=(
                auction_data.origin.contact.last_name
                if auction_data.origin.contact
                else None
            ),

            contact_phone_number=(
                auction_data.origin.contact.phone_number
                if auction_data.origin.contact
                else None
            ),

            contact_email=(
                auction_data.origin.contact.email
                if auction_data.origin.contact
                else None
            ),
        )

        db.add(origin_stop)

        # ============================================================
        # STEP 13 — CREATE INTERMEDIATE STOPS
        # ============================================================

        for stop_p, stop_geo in zip(
            auction_data.stops,
            calculated_stops
        ):

            inter_stop = Client_Shipment_Auction_Stop(
                auction_id=auction.id,

                stop_sequence=stop_p.stop_sequence,
                stop_type="Intermediate",

                # Original client address
                address=stop_p.address,

                # Google verified address
                complete_address=(
                    stop_geo["complete_address"]
                ),

                city_province=(
                    stop_geo["city_province"]
                ),

                country=stop_geo["country"],
                region=stop_geo["region"],

                latitude=stop_geo["latitude"],
                longitude=stop_geo["longitude"],

                # Facility
                facility_name=stop_p.facility_name,

                scheduling_type=(
                    stop_p.scheduling_type.value
                ),

                operating_start_time=(
                    stop_p.operating_start_time
                ),

                operating_end_time=(
                    stop_p.operating_end_time
                ),

                open_monday=stop_p.open_monday,
                open_tuesday=stop_p.open_tuesday,
                open_wednesday=stop_p.open_wednesday,
                open_thursday=stop_p.open_thursday,
                open_friday=stop_p.open_friday,
                open_saturday=stop_p.open_saturday,
                open_sunday=stop_p.open_sunday,

                reference_number=(
                    stop_p.reference_number
                ),

                notes=stop_p.notes,

                contact_first_name=(
                    stop_p.contact.first_name
                    if stop_p.contact
                    else None
                ),

                contact_last_name=(
                    stop_p.contact.last_name
                    if stop_p.contact
                    else None
                ),

                contact_phone_number=(
                    stop_p.contact.phone_number
                    if stop_p.contact
                    else None
                ),

                contact_email=(
                    stop_p.contact.email
                    if stop_p.contact
                    else None
                ),
            )

            db.add(inter_stop)

        # ============================================================
        # STEP 14 — CREATE DESTINATION STOP
        # ============================================================

        destination_stop = Client_Shipment_Auction_Stop(
            auction_id=auction.id,

            stop_sequence=len(auction_data.stops) + 1,
            stop_type="Destination",

            address=auction_data.destination.address,

            complete_address=complete_destination_address,
            city_province=destination_city_province,
            country=destination_country,
            region=destination_region,

            latitude=destination_latitude,
            longitude=destination_longitude,

            facility_name=(
                auction_data.destination.facility_name
            ),

            scheduling_type=(
                auction_data.destination.scheduling_type.value
            ),

            operating_start_time=(
                auction_data.destination.operating_start_time
            ),

            operating_end_time=(
                auction_data.destination.operating_end_time
            ),

            open_monday=auction_data.destination.open_monday,
            open_tuesday=auction_data.destination.open_tuesday,
            open_wednesday=auction_data.destination.open_wednesday,
            open_thursday=auction_data.destination.open_thursday,
            open_friday=auction_data.destination.open_friday,
            open_saturday=auction_data.destination.open_saturday,
            open_sunday=auction_data.destination.open_sunday,

            reference_number=(
                auction_data.destination.reference_number
            ),

            notes=auction_data.destination.notes,

            contact_first_name=(
                auction_data.destination.contact.first_name
                if auction_data.destination.contact
                else None
            ),

            contact_last_name=(
                auction_data.destination.contact.last_name
                if auction_data.destination.contact
                else None
            ),

            contact_phone_number=(
                auction_data.destination.contact.phone_number
                if auction_data.destination.contact
                else None
            ),

            contact_email=(
                auction_data.destination.contact.email
                if auction_data.destination.contact
                else None
            ),
        )

        db.add(destination_stop)

        # ============================================================
        # STEP 15 — CREATE VEHICLE REQUIREMENTS
        # ============================================================

        for vehicle_data in auction_data.vehicle_configurations:

            vehicle_config = (
                Client_Shipment_Auction_Vehicle_Requirement(
                    auction_id=auction.id,

                    configuration_type=(
                        vehicle_data.configuration_type
                    ),

                    truck_type=vehicle_data.truck_type,
                    equipment_type=vehicle_data.equipment_type,
                    trailer_type=vehicle_data.trailer_type,
                    trailer_length=vehicle_data.trailer_length,

                    is_required=True,
                )
            )

            db.add(vehicle_config)

        # ============================================================
        # STEP 16 — CALCULATE SERVICE FEE
        # ============================================================

        service_fee_data = calculate_service_fee(
            pricing_basis=auction_data.pricing_basis,
            benchmark_rate=(
                auction_data.procurement_target_rate
            ),
            distance=distance_km,
            shipment_weight=auction_data.shipment_weight
        )

        # ============================================================
        # STEP 17 — CREATE LOADBOARD ENTRY
        # ============================================================

        loadboard = Shipment_Auction_Loadboard(

            auction_id=auction.id,

            trip_type=auction_data.trip_type,
            load_type=auction_data.load_type,

            payment_terms=financial_account.payment_terms,

            pickup_date=auction_data.pickup_date,
            priority_level=auction_data.priority_level,

            customer_reference_number=(
                auction_data.customer_reference_number
            ),

            shipment_weight=auction_data.shipment_weight,
            commodity=auction_data.commodity,

            temperature_control=(
                auction_data.temperature_control
            ),

            target_temperature_spec=(
                auction_data.target_temperature_spec
            ),

            hazardous_materials=(
                auction_data.hazardous_materials
            ),
            hazchem_classification=auction_data.hazchem_classification,

            under_bond=auction_data.under_bond,
            rib_requirements=auction_data.rib_requirements,

            packaging_quantity=(
                auction_data.packaging_quantity
            ),

            packaging_type=auction_data.packaging_type,

            # IMPORTANT:
            # Use the calculated route distance, not
            # auction_data.distance.
            distance=distance_km,

            estimated_transit_time=(
                estimated_transit_time
            ),
            eta_date=eta_date,

            polyline=polyline,

            status="Active",

            # ========================================================
            # RATE INCLUDES
            # ========================================================

            rate_includes_fuel=(
                auction_data.rate_includes_fuel
            ),

            rate_includes_driver=(
                auction_data.rate_includes_driver
            ),

            rate_includes_maintenance=(
                auction_data.rate_includes_maintenance
            ),

            rate_includes_insurance=(
                auction_data.rate_includes_insurance
            ),

            rate_includes_tolls=(
                auction_data.rate_includes_tolls
            ),

            rate_includes_border_charges=(
                auction_data.rate_includes_border_charges
            ),

            rate_includes_empty_return=(
                auction_data.rate_includes_empty_return
            ),

            rate_includes_waiting_time=(
                auction_data.rate_includes_waiting_time
            ),

            rate_includes_loading_assistance=(
                auction_data.rate_includes_loading_assistance
            ),

            rate_includes_offloading_assistance=(
                auction_data.rate_includes_offloading_assistance
            ),

            # ========================================================
            # EXCHANGE & BIDDING
            # ========================================================

            auction_closing_date=auction_closing_date,

            pricing_basis=auction_data.pricing_basis,

            vat_included=auction_data.vat_included,

            benchmark_rate=(
                auction_data.procurement_target_rate
            ),

            benchmark_rate_service_fee=(
                service_fee_data["service_fee"]
            ),

            book_now_rate=(
                auction_data.book_now_rate
            ),

            rate_direction=(
                auction_data.rate_direction
            ),

            # ========================================================
            # OPERATIONAL REQUIREMENTS
            # ========================================================

            vehicle_tracking_required=(
                auction_data.vehicle_tracking_required
            ),

            all_time_hour_control_room=(
                auction_data.all_time_hour_control_room
            ),

            driver_mobile_phone=(
                auction_data.driver_mobile_phone
            ),

            clean_compliant_equipment=(
                auction_data.clean_compliant_equipment
            ),

            pallet_management=(
                auction_data.pallet_management
            ),

            pod_submission_local=(
                auction_data.pod_submission_local
            ),

            pod_submission_long_haul=(
                auction_data.pod_submission_long_haul
            ),

            pod_submission_cross_border=(
                auction_data.pod_submission_cross_border
            ),

            # ========================================================
            # INSURANCE REQUIREMENTS
            # ========================================================

            minimum_git_cover_amount=(
                auction_data.minimum_git_cover_amount
            ),

            minimum_liability_cover_amount=(
                auction_data.minimum_liability_cover_amount
            ),

            git_all_risk_required=(
                auction_data.git_all_risk_required
            ),

            git_first_loss_required=(
                auction_data.git_first_loss_required
            ),

            git_driver_fidelity_required=(
                auction_data.git_driver_fidelity_required
            ),

            # ========================================================
            # EQUIPMENT COMPLIANCE
            # ========================================================

            tarpaulin_compliance_required=(
                auction_data.tarpaulin_compliance_required
            ),

            corner_plates_required=(
                auction_data.corner_plates_required
            ),

            chock_blocks_required=(
                auction_data.chock_blocks_required
            ),

            ratchets_belts_required=(
                auction_data.ratchets_belts_required
            ),

            other_equipment_requirements=(
                auction_data.other_equipment_requirements
            ),
        )

        db.add(loadboard)

        # ============================================================
        # STEP 18 — ACTIVATE AUCTION
        # ============================================================

        auction.status = "Active"

        # ============================================================
        # STEP 19 — FINAL DATABASE FLUSH
        # ============================================================

        db.flush()

        # ============================================================
        # STEP 20 — COMMIT EVERYTHING AT ONCE
        # ============================================================

        db.commit()

        # ============================================================
        # STEP 21 — REFRESH OBJECTS
        # ============================================================

        db.refresh(auction)
        db.refresh(loadboard)

        return {
            "auction_id": auction.id
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                f"Failed to create and publish auction: {str(e)}"
            )
        )