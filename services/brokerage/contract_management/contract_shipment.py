from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

import uuid


# =============================================================================
# CREATE CONTRACT SUB-SHIPMENTS
# =============================================================================

def create_contract_sub_shipments(
    db: Session,
    tender_id: int,
    requested_trucks: int,
    pickup_date: date,
    current_user: dict,
    customer_reference: Optional[str] = None,
    shipment_weight: Optional[int] = None,
    commodity: Optional[str] = None,
    booking_reference: Optional[str] = None,
    notes: Optional[str] = None,
    booking_operational_data: Optional[dict] = None,
) -> dict:
    """
    Create contract-based shipment records from a tender.

    FLOW:

        Tender
           ↓
        Client_Lane contracts
           ↓
        Contract Allocation Engine
           ↓
        Allocated Client_Lane / Carrier_Lane slots
           ↓
        Client_Shipment
           ↓
        Carrier_Shipment

    IMPORTANT:

    - The allocation engine decides which contracts receive the shipment.
    - This function does NOT independently choose carriers.
    - One allocated slot creates:
          1 Client_Shipment
          1 Carrier_Shipment
    - Client_Shipment uses the client's awarded contract rate.
    - Carrier_Shipment uses:
          client contract rate - contract service fee
    - Shipment documents are NOT required during booking.
    - Contract addresses cannot be changed during booking.
    - Facility operational information may be supplied/updated during booking.
    """

    # =========================================================================
    # 1. VALIDATE REQUEST
    # =========================================================================

    if requested_trucks <= 0:
        raise HTTPException(
            status_code=400,
            detail="Number of trucks must be greater than zero"
        )

    if not pickup_date:
        raise HTTPException(
            status_code=400,
            detail="Pickup date is required"
        )

    # =========================================================================
    # 2. VALIDATE CURRENT USER
    # =========================================================================

    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a client company"
        )

    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="Authenticated user ID is missing"
        )

    # =========================================================================
    # 3. LOCK TENDER
    # =========================================================================

    tender = (
        db.query(Lane_Tender_RFQ)
        .filter(
            Lane_Tender_RFQ.id == tender_id
        )
        .with_for_update()
        .first()
    )

    if not tender:
        raise HTTPException(
            status_code=404,
            detail="Tender not found"
        )

    # =========================================================================
    # 4. VALIDATE TENDER CLIENT
    # =========================================================================

    if tender.client_id != company_id:
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to book against this tender"
        )

    # =========================================================================
    # 5. VALIDATE TENDER STATUS
    # =========================================================================

    allowed_tender_statuses = {
        "Awarded",
        "Partially Awarded",
        "Active"
    }

    if tender.status not in allowed_tender_statuses:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Tender cannot accept contract shipments "
                f"while in status '{tender.status}'"
            )
        )

    # =========================================================================
    # 6. VALIDATE PICKUP DATE AGAINST TENDER / CONTRACT PERIOD
    # =========================================================================

    if (
        getattr(tender, "contract_start_date", None)
        and pickup_date < tender.contract_start_date
    ):
        raise HTTPException(
            status_code=400,
            detail="Pickup date is before the tender contract start date"
        )

    if (
        getattr(tender, "contract_end_date", None)
        and pickup_date > tender.contract_end_date
    ):
        raise HTTPException(
            status_code=400,
            detail="Pickup date is after the tender contract end date"
        )

    # =========================================================================
    # 7. CALL CONTRACT DISTRIBUTION / ALLOCATION ENGINE
    # =========================================================================
    #
    # THIS FUNCTION MUST BE YOUR PREVIOUSLY CREATED INDEPENDENT
    # CONTRACT ALLOCATION FUNCTION.
    #
    # It determines:
    #
    #   Client_Lane A → 5 slots
    #   Client_Lane B → 2 slots
    #   Client_Lane C → 3 slots
    #
    # based on contractual obligations and shipment history.
    #
    # It must NOT create shipments.
    #
    # =========================================================================

    allocation_result = allocate_contract_shipment_slots(
        db=db,
        tender_id=tender_id,
        requested_slots=requested_trucks,
        pickup_date=pickup_date,
    )

    if not allocation_result:
        raise HTTPException(
            status_code=400,
            detail="No contract capacity is available for this booking"
        )

    # =========================================================================
    # 8. VALIDATE ALLOCATION RESULT
    # =========================================================================

    total_allocated_slots = sum(
        int(item.get("allocated_slots", 0))
        for item in allocation_result
    )

    if total_allocated_slots != requested_trucks:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Contract allocation could only allocate "
                f"{total_allocated_slots} of the requested "
                f"{requested_trucks} trucks"
            )
        )

    # =========================================================================
    # 9. PREPARE RESULT COLLECTIONS
    # =========================================================================

    created_client_shipments = []
    created_carrier_shipments = []

    # =========================================================================
    # 10. PROCESS EACH CONTRACT ALLOCATION
    # =========================================================================

    for allocation in allocation_result:

        client_lane_id = allocation.get("client_lane_id")
        carrier_lane_id = allocation.get("carrier_lane_id")
        allocated_slots = int(
            allocation.get("allocated_slots", 0)
        )

        if allocated_slots <= 0:
            continue

        # =====================================================================
        # 11. LOCK CLIENT CONTRACT
        # =====================================================================

        client_lane = (
            db.query(Client_Lane)
            .filter(
                Client_Lane.id == client_lane_id,
                Client_Lane.tender_id == tender_id,
                Client_Lane.client_id == company_id
            )
            .with_for_update()
            .first()
        )

        if not client_lane:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Client contract {client_lane_id} "
                    f"was not found for tender {tender_id}"
                )
            )

        # =====================================================================
        # 12. LOCK CARRIER CONTRACT
        # =====================================================================

        carrier_lane = (
            db.query(Carrier_Lane)
            .filter(
                Carrier_Lane.id == carrier_lane_id,
                Carrier_Lane.client_lane_id == client_lane.id,
                Carrier_Lane.tender_id == tender_id
            )
            .with_for_update()
            .first()
        )

        if not carrier_lane:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Carrier contract {carrier_lane_id} "
                    f"was not found for client contract "
                    f"{client_lane.id}"
                )
            )

        # =====================================================================
        # 13. VALIDATE CONTRACT STATUS
        # =====================================================================

        if client_lane.contract_status not in {
            "Awarded",
            "Active"
        }:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Client contract {client_lane.id} "
                    f"is not active for shipment booking"
                )
            )

        if carrier_lane.contract_status not in {
            "Awarded",
            "Active"
        }:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Carrier contract {carrier_lane.id} "
                    f"is not active for shipment booking"
                )
            )

        # =====================================================================
        # 14. VALIDATE CONTRACT DATE
        # =====================================================================

        if (
            client_lane.contract_start_date
            and pickup_date < client_lane.contract_start_date
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Pickup date is before the start of "
                    f"client contract {client_lane.id}"
                )
            )

        if (
            client_lane.contract_end_date
            and pickup_date > client_lane.contract_end_date
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Pickup date is after the end of "
                    f"client contract {client_lane.id}"
                )
            )

        # =====================================================================
        # 15. CONTRACT RATE
        # =====================================================================

        client_rate = client_lane.awarded_rate_per_shipment

        if client_rate is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Client contract {client_lane.id} "
                    f"does not have an awarded shipment rate"
                )
            )

        client_rate = Decimal(str(client_rate))

        if client_rate <= Decimal("0"):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Client contract {client_lane.id} "
                    f"has an invalid awarded shipment rate"
                )
            )

        # =====================================================================
        # 16. SERVICE FEE
        # =====================================================================

        service_fee = getattr(
            client_lane,
            "contract_service_fee",
            None
        )

        if service_fee is None:
            service_fee = Decimal("0.00")
        else:
            service_fee = Decimal(str(service_fee))

        if service_fee < Decimal("0"):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Client contract {client_lane.id} "
                    f"has an invalid contract service fee"
                )
            )

        # =====================================================================
        # 17. CALCULATE CARRIER RATE
        # =====================================================================

        carrier_rate = client_rate - service_fee

        if carrier_rate < Decimal("0"):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Contract service fee exceeds the awarded "
                    f"shipment rate on client contract "
                    f"{client_lane.id}"
                )
            )

        # =====================================================================
        # 18. LOAD CONTRACT STOPS
        # =====================================================================
        #
        # IMPORTANT:
        #
        # The booking user cannot change the contractual addresses.
        #
        # We therefore fetch the contract's existing stops and use those
        # addresses as the authoritative shipment route.
        #
        # Facility operational information can be overridden below by
        # booking-specific information.
        #
        # =====================================================================

        contract_stops = (
            db.query(Lane_Stop)
            .filter(
                Lane_Stop.lane_id == client_lane.id
            )
            .order_by(
                Lane_Stop.stop_sequence.asc()
            )
            .all()
        )

        if not contract_stops:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Client contract {client_lane.id} "
                    f"has no lane stops configured"
                )
            )

        # =====================================================================
        # 19. LOAD VEHICLE CONFIGURATION
        # =====================================================================

        vehicle_configs = (
            db.query(Lane_Vehicle_Config)
            .filter(
                Lane_Vehicle_Config.lane_id == client_lane.id,
                Lane_Vehicle_Config.is_active == True
            )
            .all()
        )

        if not vehicle_configs:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Client contract {client_lane.id} "
                    f"has no active vehicle configuration"
                )
            )

        # =====================================================================
        # 20. DETERMINE SHIPMENT-SPECIFIC VALUES
        # =====================================================================

        final_weight = (
            shipment_weight
            if shipment_weight is not None
            else client_lane.average_shipment_weight_kg
        )

        final_commodity = (
            commodity
            if commodity is not None
            else client_lane.commodity
        )

        final_customer_reference = (
            customer_reference
            if customer_reference
            else None
        )

        # =====================================================================
        # 21. VALIDATE SHIPMENT-SPECIFIC WEIGHT
        # =====================================================================

        if final_weight is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Shipment weight must be provided because "
                    f"contract {client_lane.id} has no default weight"
                )
            )

        if (
            client_lane.minimum_weight_bracket_kg
            and final_weight < client_lane.minimum_weight_bracket_kg
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Shipment weight {final_weight}kg is below "
                    f"the contractual minimum weight bracket of "
                    f"{client_lane.minimum_weight_bracket_kg}kg"
                )
            )

        # =====================================================================
        # 22. CREATE INDIVIDUAL SHIPMENTS
        # =====================================================================

        for slot_number in range(allocated_slots):

            unique_reference = (
                f"SFL-{tender_id}-"
                f"{client_lane.id}-"
                f"{uuid.uuid4().hex[:10].upper()}"
            )

            # =================================================================
            # 23. CLIENT SHIPMENT
            # =================================================================

            client_shipment = Client_Shipment(

                # -------------------------------------------------------------
                # LINKAGE
                # -------------------------------------------------------------

                is_subshipment=True,

                auction_id=None,

                client_lane_id=client_lane.id,

                carrier_lane_id=carrier_lane.id,

                booking_source="Tender Contract",

                # -------------------------------------------------------------
                # REFERENCES
                # -------------------------------------------------------------

                shipment_reference=unique_reference,

                booking_reference=(
                    booking_reference
                    if booking_reference
                    else None
                ),

                # -------------------------------------------------------------
                # CORE COMMERCIAL
                # -------------------------------------------------------------

                trip_type=(
                    getattr(client_lane, "trip_type", None)
                    or getattr(tender, "trip_type", None)
                ),

                load_type=client_lane.load_type,

                client_id=client_lane.client_id,

                client_user_id=user_id,

                rate=client_rate,

                pricing_basis=client_lane.pricing_basis,

                vat_included=(
                    client_lane.vat_included
                    if client_lane.vat_included is not None
                    else False
                ),

                payment_terms=client_lane.payment_terms,

                # -------------------------------------------------------------
                # BOOKING INFORMATION
                # -------------------------------------------------------------

                pickup_date=pickup_date,

                priority_level=client_lane.priority_level,

                customer_reference_number=(
                    final_customer_reference
                ),

                shipment_weight=final_weight,

                commodity=final_commodity,

                # -------------------------------------------------------------
                # CONTRACT CARGO REQUIREMENTS
                # -------------------------------------------------------------

                temperature_control=(
                    client_lane.temperature_control
                ),

                target_temperature_spec=(
                    client_lane.target_temperature_spec
                ),

                hazardous_materials=(
                    client_lane.hazardous_materials
                ),

                hazchem_classification=(
                    client_lane.hazchem_classification
                ),

                under_bond=client_lane.under_bond,

                rib_requirements=client_lane.rib_requirements,

                packaging_quantity=(
                    client_lane.packaging_quantity
                ),

                packaging_type=(
                    client_lane.packaging_type
                ),

                # -------------------------------------------------------------
                # ROUTING
                # -------------------------------------------------------------

                distance=client_lane.actual_distance_km,

                estimated_transit_time=None,

                eta_date=None,

                eta_window=None,

                route_preview_embed=None,

                polyline=client_lane.polyline,

                # -------------------------------------------------------------
                # STATUS
                # -------------------------------------------------------------

                status="Booked",

                trip_status="Schedule",

                # -------------------------------------------------------------
                # CARRIER ASSIGNMENT
                # -------------------------------------------------------------

                carrier_id=carrier_lane.carrier_id,

                vehicle_id=None,

                driver_id=None,

                # -------------------------------------------------------------
                # RATE INCLUSIONS
                # -------------------------------------------------------------

                rate_includes_fuel=(
                    client_lane.rate_includes_fuel
                ),

                rate_includes_driver=(
                    client_lane.rate_includes_driver
                ),

                rate_includes_maintenance=(
                    client_lane.rate_includes_maintenance
                ),

                rate_includes_insurance=(
                    client_lane.rate_includes_insurance
                ),

                rate_includes_tolls=(
                    client_lane.rate_includes_tolls
                ),

                rate_includes_border_charges=(
                    client_lane.rate_includes_border_charges
                ),

                rate_includes_empty_return=(
                    client_lane.rate_includes_empty_return
                ),

                rate_includes_waiting_time=(
                    client_lane.rate_includes_waiting_time
                ),

                rate_includes_loading_assistance=(
                    client_lane.rate_includes_loading_assistance
                ),

                rate_includes_offloading_assistance=(
                    client_lane.rate_includes_offloading_assistance
                ),

                # -------------------------------------------------------------
                # OPERATIONAL REQUIREMENTS
                # -------------------------------------------------------------

                minimum_weight_bracket_kg=(
                    client_lane.minimum_weight_bracket_kg
                ),

                vehicle_tracking_required=(
                    client_lane.vehicle_tracking_required
                ),

                all_time_hour_control_room=(
                    client_lane.all_time_hour_control_room
                ),

                driver_mobile_phone=(
                    client_lane.driver_mobile_phone
                ),

                clean_compliant_equipment=(
                    client_lane.clean_compliant_equipment
                ),

                pallet_management=(
                    client_lane.pallet_management
                ),

                pod_submission_local=(
                    client_lane.pod_submission_local
                ),

                pod_submission_long_haul=(
                    client_lane.pod_submission_long_haul
                ),

                pod_submission_cross_border=(
                    client_lane.pod_submission_cross_border
                ),

                # -------------------------------------------------------------
                # INSURANCE
                # -------------------------------------------------------------

                minimum_git_cover_amount=(
                    client_lane.minimum_git_cover_amount
                ),

                minimum_liability_cover_amount=(
                    client_lane.minimum_liability_cover_amount
                ),

                git_all_risk_required=(
                    client_lane.git_all_risk_required
                ),

                git_first_loss_required=(
                    client_lane.git_first_loss_required
                ),

                git_driver_fidelity_required=(
                    client_lane.git_driver_fidelity_required
                ),

                # -------------------------------------------------------------
                # EQUIPMENT
                # -------------------------------------------------------------

                tarpaulin_compliance_required=(
                    client_lane.tarpaulin_compliance_required
                ),

                corner_plates_required=(
                    client_lane.corner_plates_required
                ),

                chock_blocks_required=(
                    client_lane.chock_blocks_required
                ),

                ratchets_belts_required=(
                    client_lane.ratchets_belts_required
                ),

                other_equipment_requirements=(
                    client_lane.other_equipment_requirements
                )
            )

            db.add(client_shipment)

            # ================================================================
            # FLUSH CLIENT SHIPMENT
            # ================================================================

            db.flush()

            # ================================================================
            # 24. CREATE CLIENT SHIPMENT STOPS
            # ================================================================

            for contract_stop in contract_stops:

                stop_data = {
                    "shipment_id": client_shipment.id,
                    "stop_sequence": contract_stop.stop_sequence,
                    "stop_type": contract_stop.stop_type,

                    # CONTRACT-LOCKED ROUTING
                    "address": contract_stop.address,
                    "complete_address": (
                        contract_stop.complete_address
                    ),
                    "city_province": (
                        contract_stop.city_province
                    ),
                    "country": contract_stop.country,
                    "region": contract_stop.region,
                    "latitude": contract_stop.latitude,
                    "longitude": contract_stop.longitude,

                    # FACILITY
                    "facility_name": (
                        contract_stop.facility_name
                    ),
                    "scheduling_type": (
                        contract_stop.scheduling_type
                    ),
                    "operating_start_time": (
                        contract_stop.operating_start_time
                    ),
                    "operating_end_time": (
                        contract_stop.operating_end_time
                    ),

                    # WEEKDAYS
                    "open_monday": contract_stop.open_monday,
                    "open_tuesday": contract_stop.open_tuesday,
                    "open_wednesday": contract_stop.open_wednesday,
                    "open_thursday": contract_stop.open_thursday,
                    "open_friday": contract_stop.open_friday,
                    "open_saturday": contract_stop.open_saturday,
                    "open_sunday": contract_stop.open_sunday,

                    # CONTACT
                    "contact_first_name": (
                        contract_stop.contact_first_name
                    ),
                    "contact_last_name": (
                        contract_stop.contact_last_name
                    ),
                    "contact_phone_number": (
                        contract_stop.contact_phone_number
                    ),
                    "contact_email": (
                        contract_stop.contact_email
                    ),

                    # BOOKING INFORMATION
                    "reference_number": (
                        contract_stop.reference_number
                    ),
                    "notes": notes,
                }

                # =============================================================
                # APPLY BOOKING-SPECIFIC FACILITY INFORMATION
                # =============================================================
                #
                # booking_operational_data may contain values such as:
                #
                # {
                #     "0": {
                #         "scheduling_type": "Appointment",
                #         "operating_start_time": "06:00",
                #         "operating_end_time": "16:00"
                #     }
                # }
                #
                # Address fields are NEVER accepted here.
                #
                # =============================================================

                if booking_operational_data:

                    sequence_key = str(
                        contract_stop.stop_sequence
                    )

                    stop_override = (
                        booking_operational_data.get(
                            sequence_key,
                            {}
                        )
                    )

                    allowed_facility_fields = {
                        "scheduling_type",
                        "operating_start_time",
                        "operating_end_time",
                        "open_monday",
                        "open_tuesday",
                        "open_wednesday",
                        "open_thursday",
                        "open_friday",
                        "open_saturday",
                        "open_sunday",
                        "contact_first_name",
                        "contact_last_name",
                        "contact_phone_number",
                        "contact_email",
                        "reference_number",
                        "notes",
                    }

                    for field, value in stop_override.items():

                        if field in allowed_facility_fields:

                            stop_data[field] = value

                shipment_stop = Client_Shipment_Stop(
                    **stop_data
                )

                db.add(shipment_stop)

            # =================================================================
            # 25. CREATE CLIENT SHIPMENT VEHICLE REQUIREMENTS
            # =================================================================

            for config in vehicle_configs:

                shipment_vehicle_config = (
                    Client_Shipment_Vehicle_Requirement(
                        shipment_id=client_shipment.id,

                        configuration_type=(
                            config.configuration_type
                        ),

                        truck_type=config.truck_type,

                        equipment_type=(
                            config.equipment_type
                        ),

                        trailer_type=(
                            config.trailer_type
                        ),

                        trailer_length=(
                            config.trailer_length
                        ),

                        is_required=(
                            config.is_active
                        )
                    )
                )

                db.add(shipment_vehicle_config)

            # =================================================================
            # 26. CREATE CARRIER SHIPMENT
            # =================================================================
            #
            # IMPORTANT:
            #
            # Carrier shipment commercial rate is NOT the client's rate.
            #
            # It is:
            #
            #     awarded client rate
            #             -
            #       contract service fee
            #
            # =================================================================

            carrier_shipment = Carrier_Shipment(

                # -------------------------------------------------------------
                # LINKAGE
                # -------------------------------------------------------------

                client_shipment_id=client_shipment.id,

                is_subshipment=True,

                auction_id=None,

                client_id=client_lane.client_id,

                carrier_lane_id=carrier_lane.id,

                client_lane_id=client_lane.id,

                booking_source="Tender Contract",

                # -------------------------------------------------------------
                # REFERENCES
                # -------------------------------------------------------------

                shipment_reference=unique_reference,

                booking_reference=(
                    booking_reference
                    if booking_reference
                    else None
                ),

                # -------------------------------------------------------------
                # CORE
                # -------------------------------------------------------------

                trip_type=(
                    getattr(client_lane, "trip_type", None)
                    or getattr(tender, "trip_type", None)
                ),

                load_type=client_lane.load_type,

                carrier_id=carrier_lane.carrier_id,

                carrier_user_id=carrier_lane.bidder_user_id,

                # -------------------------------------------------------------
                # COMMERCIAL
                # -------------------------------------------------------------

                rate=carrier_rate,

                service_fee=service_fee,

                pricing_basis=client_lane.pricing_basis,

                vat_included=(
                    client_lane.vat_included
                    if client_lane.vat_included is not None
                    else False
                ),

                payment_terms=carrier_lane.payment_terms,

                # -------------------------------------------------------------
                # BOOKING
                # -------------------------------------------------------------

                pickup_date=pickup_date,

                priority_level=client_lane.priority_level,

                customer_reference_number=(
                    final_customer_reference
                ),

                shipment_weight=final_weight,

                commodity=final_commodity,

                # -------------------------------------------------------------
                # CARGO
                # -------------------------------------------------------------

                temperature_control=(
                    client_lane.temperature_control
                ),

                target_temperature_spec=(
                    client_lane.target_temperature_spec
                ),

                hazardous_materials=(
                    client_lane.hazardous_materials
                ),

                hazchem_classification=(
                    client_lane.hazchem_classification
                ),

                under_bond=client_lane.under_bond,

                rib_requirements=client_lane.rib_requirements,

                packaging_quantity=(
                    client_lane.packaging_quantity
                ),

                packaging_type=(
                    client_lane.packaging_type
                ),

                # -------------------------------------------------------------
                # ROUTING
                # -------------------------------------------------------------

                distance=client_lane.actual_distance_km,

                estimated_transit_time=None,

                eta_date=None,

                eta_window=None,

                route_preview_embed=None,

                polyline=client_lane.polyline,

                # -------------------------------------------------------------
                # STATUS
                # -------------------------------------------------------------

                status="Booked",

                trip_status="Scheduled",

                # -------------------------------------------------------------
                # TRACKING
                # -------------------------------------------------------------

                live_location=None,

                vehicle_id=None,

                driver_id=None,

                # -------------------------------------------------------------
                # RATE INCLUSIONS
                # -------------------------------------------------------------

                rate_includes_fuel=(
                    client_lane.rate_includes_fuel
                ),

                rate_includes_driver=(
                    client_lane.rate_includes_driver
                ),

                rate_includes_maintenance=(
                    client_lane.rate_includes_maintenance
                ),

                rate_includes_insurance=(
                    client_lane.rate_includes_insurance
                ),

                rate_includes_tolls=(
                    client_lane.rate_includes_tolls
                ),

                rate_includes_border_charges=(
                    client_lane.rate_includes_border_charges
                ),

                rate_includes_empty_return=(
                    client_lane.rate_includes_empty_return
                ),

                rate_includes_waiting_time=(
                    client_lane.rate_includes_waiting_time
                ),

                rate_includes_loading_assistance=(
                    client_lane.rate_includes_loading_assistance
                ),

                rate_includes_offloading_assistance=(
                    client_lane.rate_includes_offloading_assistance
                ),

                # -------------------------------------------------------------
                # OPERATIONAL
                # -------------------------------------------------------------

                minimum_weight_bracket_kg=(
                    client_lane.minimum_weight_bracket_kg
                ),

                vehicle_tracking_required=(
                    client_lane.vehicle_tracking_required
                ),

                all_time_hour_control_room=(
                    client_lane.all_time_hour_control_room
                ),

                driver_mobile_phone=(
                    client_lane.driver_mobile_phone
                ),

                clean_compliant_equipment=(
                    client_lane.clean_compliant_equipment
                ),

                pallet_management=(
                    client_lane.pallet_management
                ),

                pod_submission_local=(
                    client_lane.pod_submission_local
                ),

                pod_submission_long_haul=(
                    client_lane.pod_submission_long_haul
                ),

                pod_submission_cross_border=(
                    client_lane.pod_submission_cross_border
                ),

                # -------------------------------------------------------------
                # INSURANCE
                # -------------------------------------------------------------

                minimum_git_cover_amount=(
                    client_lane.minimum_git_cover_amount
                ),

                minimum_liability_cover_amount=(
                    client_lane.minimum_liability_cover_amount
                ),

                git_all_risk_required=(
                    client_lane.git_all_risk_required
                ),

                git_first_loss_required=(
                    client_lane.git_first_loss_required
                ),

                git_driver_fidelity_required=(
                    client_lane.git_driver_fidelity_required
                ),

                # -------------------------------------------------------------
                # EQUIPMENT
                # -------------------------------------------------------------

                tarpaulin_compliance_required=(
                    client_lane.tarpaulin_compliance_required
                ),

                corner_plates_required=(
                    client_lane.corner_plates_required
                ),

                chock_blocks_required=(
                    client_lane.chock_blocks_required
                ),

                ratchets_belts_required=(
                    client_lane.ratchets_belts_required
                ),

                other_equipment_requirements=(
                    client_lane.other_equipment_requirements
                )
            )

            db.add(carrier_shipment)

            # =================================================================
            # FLUSH CARRIER SHIPMENT
            # =================================================================

            db.flush()

            # =================================================================
            # 27. STORE RESULT
            # =================================================================

            created_client_shipments.append({
                "id": client_shipment.id,
                "shipment_reference": (
                    client_shipment.shipment_reference
                ),
                "client_lane_id": client_lane.id,
                "carrier_lane_id": carrier_lane.id,
                "carrier_id": carrier_lane.carrier_id,
                "rate": str(client_rate),
            })

            created_carrier_shipments.append({
                "id": carrier_shipment.id,
                "shipment_reference": (
                    carrier_shipment.shipment_reference
                ),
                "client_shipment_id": (
                    client_shipment.id
                ),
                "client_lane_id": client_lane.id,
                "carrier_lane_id": carrier_lane.id,
                "carrier_id": carrier_lane.carrier_id,
                "rate": str(carrier_rate),
                "service_fee": str(service_fee),
            })

    # =========================================================================
    # 28. FINAL VALIDATION
    # =========================================================================

    if (
        len(created_client_shipments)
        != requested_trucks
    ):
        raise HTTPException(
            status_code=500,
            detail=(
                "Shipment creation mismatch: the number of "
                "client shipments created does not match "
                "the requested number of trucks"
            )
        )

    if (
        len(created_carrier_shipments)
        != requested_trucks
    ):
        raise HTTPException(
            status_code=500,
            detail=(
                "Shipment creation mismatch: the number of "
                "carrier shipments created does not match "
                "the requested number of trucks"
            )
        )

    # =========================================================================
    # 29. COMMIT EVERYTHING AS ONE TRANSACTION
    # =========================================================================

    try:

        db.commit()

    except Exception as exc:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Contract shipment booking failed. "
                "No shipment records were committed."
            )
        ) from exc

    # =========================================================================
    # 30. RETURN RESULT
    # =========================================================================

    return {
        "success": True,

        "message": (
            f"{requested_trucks} contract shipment(s) "
            f"created successfully"
        ),

        "tender_id": tender.id,

        "requested_trucks": requested_trucks,

        "allocated_trucks": total_allocated_slots,

        "client_shipments_created": len(
            created_client_shipments
        ),

        "carrier_shipments_created": len(
            created_carrier_shipments
        ),

        "client_shipments": created_client_shipments,

        "carrier_shipments": created_carrier_shipments,
    }