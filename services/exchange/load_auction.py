from datetime import date, datetime, time, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session
from schemas.exchange_bookings.ftl_shipment import (
    ShipmentBatchCreate,
    ClientShipmentAuctionCreate,
    ClientShipmentAuctionVehicleRequirementCreate,
    ClientShipmentAuctionStopCreate,
)
from models.Exchange.ftl_shipment import (
    Client_Shipment_Auction_Bundle,
    Client_Shipment_Auction,
    Client_Shipment_Auction_Stop,
    Client_Shipment_Auction_Vehicle_Requirement,
)
from models.brokerage.finance import FinancialAccounts
from models.shipper import Corporation
from models.brokerage.loadboard import Shipment_Auction_Loadboard
from utils.google_maps import AddressInput, RouteETAInput, calculate_distance, get_eta_and_polyline
from uuid import uuid4
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
    waypoints = []

    if stops:
        sorted_stops = sorted(
            stops,
            key=lambda stop: stop.stop_sequence
        )

        waypoints = [
            stop.address.strip()
            for stop in sorted_stops
            if stop.address and stop.address.strip()
        ]

    route_input = AddressInput(
        origin_address=origin_address,
        destination_address=destination_address,
        waypoints=waypoints
    )

    result = calculate_distance(route_input)

    # calculate_distance() may return the distance
    # directly as a float.
    if isinstance(result, (int, float)):
        return float(result)

    # Or it may return a dictionary.
    if isinstance(result, dict):
        distance_km = result.get("distance")

        if distance_km is None:
            raise HTTPException(
                status_code=400,
                detail="Google Maps did not return a route distance."
            )

        return float(distance_km)

    raise HTTPException(
        status_code=500,
        detail="Unexpected response from distance calculation service."
    )


def create_single_shipment_auction(
    db: Session,
    auction_data: ClientShipmentAuctionCreate,
    shipper,
    financial_account,
    user_id: int,
    bundle_context: dict | None = None
):
    """
    Create ONE Client Shipment Auction.

    This function does NOT commit the database.

    It is intentionally reusable so that the batch creator
    can create any number of independent or bundled auctions
    inside one database transaction.
    """

    # ============================================================
    # 1. VALIDATE STOP SEQUENCES
    # ============================================================

    sorted_stops = sorted(
        auction_data.stops,
        key=lambda s: s.stop_sequence
    )

    stop_sequences = [
        stop.stop_sequence
        for stop in sorted_stops
    ]

    expected_sequences = list(
        range(1, len(sorted_stops) + 1)
    )

    if stop_sequences != expected_sequences:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Shipment {auction_data.shipment_reference}: "
                "Intermediate stop sequences must be "
                "consecutive starting from 1."
            )
        )

    # ============================================================
    # 2. CALCULATE COMPLETE ROUTE
    # ============================================================

    try:

        distance_data = calculate_auction_distance(
            origin_address=auction_data.origin.address,
            destination_address=auction_data.destination.address,
            stops=sorted_stops
        )

    except HTTPException as e:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Shipment "
                f"{auction_data.shipment_reference}: "
                f"Google Maps routing calculation failed: "
                f"{e.detail}"
            )
        )

    distance_km = distance_data.get("distance")

    estimated_transit_time = distance_data.get(
        "duration"
    )

    route_preview_embed = distance_data.get(
        "google_maps_embed_url"
    )

    polyline = distance_data.get(
        "polyline"
    )

    if distance_km is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Shipment "
                f"{auction_data.shipment_reference}: "
                "Google Maps did not return a valid "
                "route distance."
            )
        )

    # ============================================================
    # 3. ORIGIN GEO INFORMATION
    # ============================================================

    complete_origin_address = distance_data.get(
        "complete_origin_address",
        auction_data.origin.address
    )

    origin_city_province = distance_data.get(
        "origin_city_province"
    )

    origin_country = distance_data.get(
        "origin_country"
    )

    origin_region = distance_data.get(
        "origin_region"
    )

    origin_latitude = distance_data.get(
        "origin_latitude"
    )

    origin_longitude = distance_data.get(
        "origin_longitude"
    )

    # ============================================================
    # 4. DESTINATION GEO INFORMATION
    # ============================================================

    complete_destination_address = distance_data.get(
        "complete_destination_address",
        auction_data.destination.address
    )

    destination_city_province = distance_data.get(
        "destination_city_province"
    )

    destination_country = distance_data.get(
        "destination_country"
    )

    destination_region = distance_data.get(
        "destination_region"
    )

    destination_latitude = distance_data.get(
        "destination_latitude"
    )

    destination_longitude = distance_data.get(
        "destination_longitude"
    )

    # ============================================================
    # 5. INTERMEDIATE STOP GEO INFORMATION
    # ============================================================

    calculated_stops = []

    for index, stop_data in enumerate(
        sorted_stops,
        start=1
    ):

        calculated_stops.append(
            {
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

                "latitude": distance_data.get(
                    f"stop_{index}_latitude"
                ),

                "longitude": distance_data.get(
                    f"stop_{index}_longitude"
                ),
            }
        )

    # ============================================================
    # 6. ETA / POLYLINE
    # ============================================================

    try:

        trip_data = get_eta_and_polyline(
            RouteETAInput(
                origin_address=(
                    auction_data.origin.address
                ),

                destination_address=(
                    auction_data.destination.address
                ),

                start_date=auction_data.pickup_date,

                start_time=(
                    auction_data.origin.operating_end_time
                ),
            )
        )

        eta_date = trip_data.get(
            "eta_date"
        )

        eta_window = trip_data.get(
            "eta_window"
        )

        eta_polyline = trip_data.get(
            "polyline"
        )

        if eta_polyline:
            polyline = eta_polyline

    except HTTPException as e:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Shipment "
                f"{auction_data.shipment_reference}: "
                f"Trip information calculation failed: "
                f"{e.detail}"
            )
        )

    # ============================================================
    # 7. NORMALIZE AUCTION CLOSING DATE
    # ============================================================

    auction_closing_date = (
        auction_data.auction_closing_date
    )

    if auction_closing_date.tzinfo is None:

        auction_closing_date = (
            auction_closing_date.replace(
                tzinfo=timezone.utc
            )
        )

    else:

        auction_closing_date = (
            auction_closing_date.astimezone(
                timezone.utc
            )
        )

    # ============================================================
    # 8. BUNDLE CONTEXT
    # ============================================================

    bundle_id = None
    bundle_reference = None
    bundle_trip_sequence = None
    bundle_role = None

    if bundle_context:

        bundle_id = bundle_context.get(
            "bundle_id"
        )

        bundle_reference = bundle_context.get(
            "bundle_reference"
        )

        bundle_trip_sequence = bundle_context.get(
            "stage_sequence"
        )

        bundle_role = bundle_context.get(
            "stage_role"
        )

    # ============================================================
    # 9. CREATE AUCTION
    # ============================================================

    auction = Client_Shipment_Auction(

        client_id=shipper.id,
        client_user_id=user_id,

        # --------------------------------------------------------
        # BUNDLE RELATIONSHIP
        # --------------------------------------------------------

        bundle_id=bundle_id,
        bundle_reference=bundle_reference,
        bundle_trip_sequence=bundle_trip_sequence,
        bundle_role=bundle_role,

        # --------------------------------------------------------
        # SHIPMENT
        # --------------------------------------------------------

        shipment_reference=(
            auction_data.shipment_reference
        ),

        booking_reference=(
            auction_data.booking_reference
        ),

        trip_type=auction_data.trip_type,

        load_type=auction_data.load_type,

        number_of_trucks_required=(
            auction_data.number_of_trucks_required
        ),

        slots_remaining=(
            auction_data.number_of_trucks_required
        ),

        payment_terms=(
            financial_account.payment_terms
        ),

        pickup_date=auction_data.pickup_date,

        priority_level=(
            auction_data.priority_level
        ),

        customer_reference_number=(
            auction_data.customer_reference_number
        ),

        shipment_weight=(
            auction_data.shipment_weight
        ),

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

        hazchem_classification=(
            auction_data.hazchem_classification
        ),

        under_bond=auction_data.under_bond,

        rib_requirements=(
            auction_data.rib_requirements
        ),

        packaging_quantity=(
            auction_data.packaging_quantity
        ),

        packaging_type=(
            auction_data.packaging_type
        ),

        # --------------------------------------------------------
        # ROUTING
        # --------------------------------------------------------

        distance=distance_km,

        estimated_transit_time=(
            estimated_transit_time
        ),

        eta_date=eta_date,

        route_preview_embed=(
            route_preview_embed
        ),

        polyline=polyline,

        # --------------------------------------------------------
        # RATE INCLUDES
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # EXCHANGE & BIDDING
        # --------------------------------------------------------

        auction_closing_date=(
            auction_closing_date
        ),

        pricing_basis=(
            auction_data.pricing_basis
        ),

        vat_included=(
            auction_data.vat_included
        ),

        book_now_rate=(
            auction_data.book_now_rate
        ),

        procurement_target_rate=(
            auction_data.procurement_target_rate
        ),

        bidding_activated=(
            auction_data.bidding_activated
        ),

        rate_direction=(
            auction_data.rate_direction
        ),

        # --------------------------------------------------------
        # OPERATIONAL REQUIREMENTS
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # INSURANCE
        # --------------------------------------------------------

        minimum_git_cover_amount=(
            auction_data.minimum_git_cover_amount
        ),

        minimum_liability_cover_amount=(
            auction_data.minimum_liability_cover_amount
        ),

        minimum_weight_bracket=(
            auction_data.minimum_weight_bracket
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

        # --------------------------------------------------------
        # EQUIPMENT
        # --------------------------------------------------------

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

        status="Active"
    )

    db.add(auction)

    db.flush()

    # ============================================================
    # 10. CREATE ORIGIN STOP
    # ============================================================

    origin_stop = Client_Shipment_Auction_Stop(

        auction_id=auction.id,

        stop_sequence=0,
        stop_type="Origin",

        address=auction_data.origin.address,

        complete_address=(
            complete_origin_address
        ),

        city_province=(
            origin_city_province
        ),

        country=origin_country,
        region=origin_region,

        latitude=origin_latitude,
        longitude=origin_longitude,

        facility_name=(
            auction_data.origin.facility_name
        ),

        scheduling_type=(
            auction_data.origin.scheduling_type.value
        ),

        operating_start_time=(
            auction_data.origin.operating_start_time
        ),

        operating_end_time=(
            auction_data.origin.operating_end_time
        ),

        open_monday=(
            auction_data.origin.open_monday
        ),

        open_tuesday=(
            auction_data.origin.open_tuesday
        ),

        open_wednesday=(
            auction_data.origin.open_wednesday
        ),

        open_thursday=(
            auction_data.origin.open_thursday
        ),

        open_friday=(
            auction_data.origin.open_friday
        ),

        open_saturday=(
            auction_data.origin.open_saturday
        ),

        open_sunday=(
            auction_data.origin.open_sunday
        ),

        reference_number=(
            auction_data.origin.reference_number
        ),

        notes=(
            auction_data.origin.notes
        ),

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
        )
    )

    db.add(origin_stop)

    # ============================================================
    # 11. CREATE INTERMEDIATE STOPS
    # ============================================================

    for stop_data, stop_geo in zip(
        sorted_stops,
        calculated_stops
    ):

        inter_stop = (
            Client_Shipment_Auction_Stop(

                auction_id=auction.id,

                stop_sequence=(
                    stop_data.stop_sequence
                ),

                stop_type="Intermediate",

                address=stop_data.address,

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

                facility_name=(
                    stop_data.facility_name
                ),

                scheduling_type=(
                    stop_data.scheduling_type.value
                ),

                operating_start_time=(
                    stop_data.operating_start_time
                ),

                operating_end_time=(
                    stop_data.operating_end_time
                ),

                open_monday=(
                    stop_data.open_monday
                ),

                open_tuesday=(
                    stop_data.open_tuesday
                ),

                open_wednesday=(
                    stop_data.open_wednesday
                ),

                open_thursday=(
                    stop_data.open_thursday
                ),

                open_friday=(
                    stop_data.open_friday
                ),

                open_saturday=(
                    stop_data.open_saturday
                ),

                open_sunday=(
                    stop_data.open_sunday
                ),

                reference_number=(
                    stop_data.reference_number
                ),

                notes=(
                    stop_data.notes
                ),

                contact_first_name=(
                    stop_data.contact.first_name
                    if stop_data.contact
                    else None
                ),

                contact_last_name=(
                    stop_data.contact.last_name
                    if stop_data.contact
                    else None
                ),

                contact_phone_number=(
                    stop_data.contact.phone_number
                    if stop_data.contact
                    else None
                ),

                contact_email=(
                    stop_data.contact.email
                    if stop_data.contact
                    else None
                )
            )
        )

        db.add(inter_stop)

    # ============================================================
    # 12. CREATE DESTINATION STOP
    # ============================================================

    destination_stop = (
        Client_Shipment_Auction_Stop(

            auction_id=auction.id,

            stop_sequence=(
                len(sorted_stops) + 1
            ),

            stop_type="Destination",

            address=(
                auction_data.destination.address
            ),

            complete_address=(
                complete_destination_address
            ),

            city_province=(
                destination_city_province
            ),

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

            open_monday=(
                auction_data.destination.open_monday
            ),

            open_tuesday=(
                auction_data.destination.open_tuesday
            ),

            open_wednesday=(
                auction_data.destination.open_wednesday
            ),

            open_thursday=(
                auction_data.destination.open_thursday
            ),

            open_friday=(
                auction_data.destination.open_friday
            ),

            open_saturday=(
                auction_data.destination.open_saturday
            ),

            open_sunday=(
                auction_data.destination.open_sunday
            ),

            reference_number=(
                auction_data.destination.reference_number
            ),

            notes=(
                auction_data.destination.notes
            ),

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
            )
        )
    )

    db.add(destination_stop)

    # ============================================================
    # 13. VEHICLE REQUIREMENTS
    # ============================================================

    for vehicle_data in (
        auction_data.vehicle_configurations
    ):

        vehicle_config = (
            Client_Shipment_Auction_Vehicle_Requirement(

                auction_id=auction.id,

                configuration_type=(
                    vehicle_data.configuration_type
                ),

                truck_type=(
                    vehicle_data.truck_type
                ),

                equipment_type=(
                    vehicle_data.equipment_type
                ),

                trailer_type=(
                    vehicle_data.trailer_type
                ),

                trailer_length=(
                    vehicle_data.trailer_length
                ),

                is_required=True
            )
        )

        db.add(vehicle_config)

    # ============================================================
    # 14. SERVICE FEE
    # ============================================================

    service_fee_data = calculate_service_fee(

        pricing_basis=(
            auction_data.pricing_basis
        ),

        benchmark_rate=(
            auction_data.procurement_target_rate
        ),

        distance=distance_km,

        shipment_weight=(
            auction_data.shipment_weight
        )
    )

    # ============================================================
    # 15. CREATE LOADBOARD ENTRY
    # ============================================================

    loadboard = Shipment_Auction_Loadboard(

        auction_id=auction.id,

        trip_type=auction_data.trip_type,

        load_type=auction_data.load_type,

        number_of_trucks_required=(
            auction_data.number_of_trucks_required
        ),

        slots_remaining=(
            auction_data.number_of_trucks_required
        ),

        payment_terms=(
            financial_account.payment_terms
        ),

        pickup_date=auction_data.pickup_date,

        priority_level=(
            auction_data.priority_level
        ),

        shipment_weight=(
            auction_data.shipment_weight
        ),

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

        hazchem_classification=(
            auction_data.hazchem_classification
        ),

        under_bond=auction_data.under_bond,

        rib_requirements=(
            auction_data.rib_requirements
        ),

        packaging_quantity=(
            auction_data.packaging_quantity
        ),

        packaging_type=(
            auction_data.packaging_type
        ),

        distance=distance_km,

        estimated_transit_time=(
            estimated_transit_time
        ),

        eta_date=eta_date,

        polyline=polyline,

        status="Active",

        # --------------------------------------------------------
        # RATE INCLUDES
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # EXCHANGE & BIDDING
        # --------------------------------------------------------

        auction_closing_date=(
            auction_closing_date
        ),

        pricing_basis=(
            auction_data.pricing_basis
        ),

        vat_included=(
            auction_data.vat_included
        ),

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

        # --------------------------------------------------------
        # OPERATIONAL REQUIREMENTS
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # INSURANCE
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # EQUIPMENT COMPLIANCE
        # --------------------------------------------------------

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
        )
    )

    db.add(loadboard)

    # ============================================================
    # 16. FLUSH
    # ============================================================

    db.flush()

    return {
        "auction": auction,
        "loadboard": loadboard,
        "service_fee": service_fee_data
    }

###################################################################################################################################################################
###################################################################################################################################################################
########################################################################Create Shipment Batch######################################################################
###################################################################################################################################################################
###################################################################################################################################################################
def create_shipment_batch(
    db: Session,
    batch_data: ShipmentBatchCreate,
    current_user: dict
):
    """
    Create any number of shipment auctions in one request.

    Supports:

        1. Independent auctions
        2. Round-trip bundles
        3. Multi-stage bundles
        4. Any combination of the above

    There is intentionally no business-level maximum
    on the number of auctions in a batch.

    The entire operation commits as ONE transaction.
    """

    try:

        # ========================================================
        # 1. AUTHENTICATE USER
        # ========================================================

        assert (
            "company_id" in current_user
        ), "Missing company_id in current_user"

        company_id = current_user.get(
            "company_id"
        )

        user_id = current_user.get(
            "id"
        )

        if not company_id:

            raise HTTPException(
                status_code=400,
                detail=(
                    "User does not belong "
                    "to a company."
                )
            )

        # ========================================================
        # 2. VALIDATE BATCH
        # ========================================================

        if not batch_data.auctions:

            raise HTTPException(
                status_code=400,
                detail=(
                    "At least one shipment auction "
                    "is required."
                )
            )

        # ========================================================
        # 3. VALIDATE AUCTION REFERENCES
        # ========================================================

        auction_lookup = {}

        for auction_data in batch_data.auctions:

            shipment_ref = (
                auction_data.shipment_reference
            )

            if shipment_ref in auction_lookup:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Duplicate shipment reference "
                        f"'{shipment_ref}' found in "
                        "the batch."
                    )
                )

            auction_lookup[shipment_ref] = (
                auction_data
            )

        # ========================================================
        # 4. VALIDATE BUNDLE REFERENCES
        # ========================================================

        bundle_lookup = {}

        for bundle_data in batch_data.bundles:

            client_bundle_ref = (
                bundle_data.client_bundle_ref
            )

            if client_bundle_ref in bundle_lookup:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Duplicate bundle reference "
                        f"'{client_bundle_ref}' found "
                        "in the batch."
                    )
                )

            bundle_lookup[
                client_bundle_ref
            ] = bundle_data

        # ========================================================
        # 5. VALIDATE BUNDLES
        # ========================================================

        auction_bundle_assignments = {}

        created_bundle_contexts = {}

        for bundle_data in batch_data.bundles:

            # ----------------------------------------------------
            # Bundle type
            # ----------------------------------------------------

            bundle_type = (
                bundle_data.bundle_type
                .strip()
                .upper()
            )

            if bundle_type not in {
                "ROUND_TRIP",
                "MULTI_STAGE"
            }:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Bundle "
                        f"{bundle_data.client_bundle_ref}: "
                        f"Unsupported bundle type "
                        f"'{bundle_data.bundle_type}'. "
                        "Supported types are "
                        "ROUND_TRIP and MULTI_STAGE."
                    )
                )

            # ----------------------------------------------------
            # Minimum stages
            # ----------------------------------------------------

            if len(bundle_data.stages) < 2:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Bundle "
                        f"{bundle_data.client_bundle_ref}: "
                        "A bundle must contain at least "
                        "2 stages."
                    )
                )

            # ----------------------------------------------------
            # ROUND TRIP must contain exactly 2 stages
            # ----------------------------------------------------

            if (
                bundle_type == "ROUND_TRIP"
                and len(bundle_data.stages) != 2
            ):

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Bundle "
                        f"{bundle_data.client_bundle_ref}: "
                        "A ROUND_TRIP bundle must contain "
                        "exactly 2 stages."
                    )
                )

            # ----------------------------------------------------
            # Validate stage sequences
            # ----------------------------------------------------

            stage_sequences = sorted(
                stage.stage_sequence
                for stage in bundle_data.stages
            )

            expected_sequences = list(
                range(
                    1,
                    len(bundle_data.stages) + 1
                )
            )

            if stage_sequences != expected_sequences:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Bundle "
                        f"{bundle_data.client_bundle_ref}: "
                        "Stage sequences must be consecutive "
                        "starting from 1."
                    )
                )

            # ----------------------------------------------------
            # Validate duplicate stage sequences
            # ----------------------------------------------------

            if len(stage_sequences) != len(
                set(stage_sequences)
            ):

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Bundle "
                        f"{bundle_data.client_bundle_ref}: "
                        "Duplicate stage sequence detected."
                    )
                )

            # ----------------------------------------------------
            # Validate each stage
            # ----------------------------------------------------

            for stage in bundle_data.stages:

                auction_ref = stage.auction_ref

                if auction_ref not in auction_lookup:

                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Bundle "
                            f"{bundle_data.client_bundle_ref}: "
                            f"Auction reference "
                            f"'{auction_ref}' does not exist "
                            "in this batch."
                        )
                    )

                if auction_ref in (
                    auction_bundle_assignments
                ):

                    existing_bundle = (
                        auction_bundle_assignments[
                            auction_ref
                        ]["client_bundle_ref"]
                    )

                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Auction "
                            f"'{auction_ref}' is already "
                            f"assigned to bundle "
                            f"'{existing_bundle}' and "
                            "cannot belong to multiple "
                            "bundles."
                        )
                    )

                if stage.stage_sequence < 1:

                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Bundle "
                            f"{bundle_data.client_bundle_ref}: "
                            "Stage sequence must start "
                            "at 1."
                        )
                    )

                stage_role = (
                    stage.stage_role
                    .strip()
                    .upper()
                )

                if not stage_role:

                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Bundle "
                            f"{bundle_data.client_bundle_ref}: "
                            "Stage role cannot be empty."
                        )
                    )

                auction_bundle_assignments[
                    auction_ref
                ] = {
                    "client_bundle_ref": (
                        bundle_data.client_bundle_ref
                    ),

                    "stage_sequence": (
                        stage.stage_sequence
                    ),

                    "stage_role": stage_role
                }

        # ========================================================
        # 6. VALIDATE SHIPPER
        # ========================================================

        shipper = (
            db.query(Corporation)
            .filter(
                Corporation.id == company_id
            )
            .first()
        )

        if not shipper:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Shipper account not found "
                    "or not active."
                )
            )

        if not shipper.is_verified:

            raise HTTPException(
                status_code=403,
                detail=(
                    "Shipper account is not verified. "
                    "Please await verification to create "
                    "a shipment exchange."
                )
            )

        if shipper.status != "Active":

            raise HTTPException(
                status_code=403,
                detail=(
                    "Shipper account is not active. "
                    "Please await account activation "
                    "to create a shipment exchange."
                )
            )

        # ========================================================
        # 7. VALIDATE FINANCIAL ACCOUNT
        # ========================================================

        financial_account = (
            db.query(FinancialAccounts)
            .filter(
                FinancialAccounts.id == shipper.id
            )
            .first()
        )

        if not financial_account:

            raise HTTPException(
                status_code=404,
                detail=(
                    "Financial account not found."
                )
            )

        if not financial_account.is_verified:

            raise HTTPException(
                status_code=403,
                detail=(
                    "Financial account is not verified. "
                    "Please await verification to create "
                    "and finance a shipment exchange."
                )
            )

        if financial_account.status != "Active":

            raise HTTPException(
                status_code=403,
                detail=(
                    "Financial account is not active. "
                    "Please await activation to create "
                    "and finance a shipment exchange."
                )
            )

        # ========================================================
        # 8. CREATE BUNDLES
        # ========================================================

        created_bundles = {}

        for bundle_data in batch_data.bundles:

            bundle_reference = (
                f"BND-{uuid4().hex[:12].upper()}"
            )

            bundle = Client_Shipment_Auction_Bundle(

                client_id=shipper.id,

                bundle_reference=bundle_reference,

                bundle_type=(
                    bundle_data.bundle_type
                    .strip()
                    .upper()
                ),

                stage_count=len(
                    bundle_data.stages
                ),

                status="Active",

                created_by_user_id=user_id
            )

            db.add(bundle)

            db.flush()

            created_bundles[
                bundle_data.client_bundle_ref
            ] = bundle

            created_bundle_contexts[
                bundle_data.client_bundle_ref
            ] = {
                "bundle_id": bundle.id,
                "bundle_reference": bundle.bundle_reference
            }

        # ========================================================
        # 9. CREATE ALL AUCTIONS
        # ========================================================

        created_auctions = []

        for auction_data in batch_data.auctions:

            shipment_ref = (
                auction_data.shipment_reference
            )

            bundle_context = None

            assignment = (
                auction_bundle_assignments.get(
                    shipment_ref
                )
            )

            if assignment:

                client_bundle_ref = (
                    assignment[
                        "client_bundle_ref"
                    ]
                )

                bundle_base = (
                    created_bundle_contexts[
                        client_bundle_ref
                    ]
                )

                bundle_context = {
                    "bundle_id": (
                        bundle_base["bundle_id"]
                    ),

                    "bundle_reference": (
                        bundle_base[
                            "bundle_reference"
                        ]
                    ),

                    "stage_sequence": (
                        assignment[
                            "stage_sequence"
                        ]
                    ),

                    "stage_role": (
                        assignment[
                            "stage_role"
                        ]
                    )
                }

            result = create_single_shipment_auction(

                db=db,

                auction_data=auction_data,

                shipper=shipper,

                financial_account=financial_account,

                user_id=user_id,

                bundle_context=bundle_context
            )

            created_auctions.append(
                {
                    "auction_data": auction_data,
                    "auction": result["auction"],
                    "loadboard": result["loadboard"],
                    "service_fee": result[
                        "service_fee"
                    ],
                    "bundle_context": bundle_context
                }
            )

        # ========================================================
        # 10. COMMIT EVERYTHING
        # ========================================================

        db.commit()

        # ========================================================
        # 11. REFRESH
        # ========================================================

        for item in created_auctions:

            db.refresh(
                item["auction"]
            )

            db.refresh(
                item["loadboard"]
            )

        for bundle in created_bundles.values():

            db.refresh(bundle)

        # ========================================================
        # 12. RETURN RESPONSE
        # ========================================================

        return {
            "success": True,

            "message": (
                "Shipment auction created successfully."
                if len(created_auctions) == 1
                else "Shipment auction batch created successfully."
            ),

            "auction_count": len(
                created_auctions
            ),

            "bundle_count": len(
                created_bundles
            ),

            "bundles": [

                {
                    "client_bundle_ref": (
                        client_bundle_ref
                    ),

                    "bundle_id": bundle.id,

                    "bundle_reference": (
                        bundle.bundle_reference
                    ),

                    "bundle_type": (
                        bundle.bundle_type
                    ),

                    "stage_count": (
                        bundle.stage_count
                    ),

                    "status": bundle.status
                }

                for client_bundle_ref, bundle
                in created_bundles.items()
            ],

            "auctions": [

                {
                    "shipment_reference": (
                        item[
                            "auction_data"
                        ].shipment_reference
                    ),

                    "auction_id": (
                        item[
                            "auction"
                        ].id
                    ),

                    "loadboard_id": (
                        item[
                            "loadboard"
                        ].id
                    ),

                    "bundle_id": (
                        item[
                            "auction"
                        ].bundle_id
                    ),

                    "bundle_reference": (
                        item[
                            "auction"
                        ].bundle_reference
                    ),

                    "bundle_trip_sequence": (
                        item[
                            "auction"
                        ].bundle_trip_sequence
                    ),

                    "bundle_role": (
                        item[
                            "auction"
                        ].bundle_role
                    ),

                    "status": (
                        item[
                            "auction"
                        ].status
                    )
                }

                for item in created_auctions
            ]
        }

    except HTTPException:

        db.rollback()
        raise

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to create shipment auction "
                f"batch: {str(e)}"
            )
        )