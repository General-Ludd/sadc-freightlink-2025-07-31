from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException


def allocate_contract_shipment_slot(
    db: Session,
    tender_id: int,
    booking_date: date,
    requested_slots: int = 1
):
    """
    Determines which awarded carrier contract(s) should receive
    shipment slot(s) for a new contract shipment booking.

    IMPORTANT:
    - Does NOT create Client_Shipment.
    - Does NOT create Carrier_Shipment.
    - Does NOT modify shipment records.
    - Only determines the contractual carrier allocation.
    - Intended to be called by create_contract_sub_shipment().

    Allocation principle:

        1. Load all awarded Client_Lanes for the tender.
        2. Load each lane's volume profile.
        3. Determine tender expected volume for the booking period.
        4. Determine each carrier contract's contractual capacity.
        5. Determine how many shipments each contract has already
           received.
        6. Calculate contractual utilization.
        7. Prefer contracts that are furthest behind their
           contractual allocation.
        8. Return the selected Client_Lane / Carrier_Lane.

    Example:

        Tender peak = 13

        Carrier A = 5
        Carrier B = 2
        Carrier C = 2
        Carrier D = 3
        Carrier E = 1

        Total = 13
    """

    # ============================================================
    # 1. VALIDATE REQUEST
    # ============================================================

    if not tender_id:
        raise HTTPException(
            status_code=400,
            detail="Tender ID is required"
        )

    if not booking_date:
        raise HTTPException(
            status_code=400,
            detail="Booking date is required"
        )

    if requested_slots <= 0:
        raise HTTPException(
            status_code=400,
            detail="requested_slots must be greater than zero"
        )

    # ============================================================
    # 2. LOAD TENDER
    # ============================================================

    tender = (
        db.query(Lane_Tender_RFQ)
        .filter(
            Lane_Tender_RFQ.id == tender_id
        )
        .first()
    )

    if not tender:
        raise HTTPException(
            status_code=404,
            detail="Tender not found"
        )

    # ============================================================
    # 3. LOAD ALL CLIENT LANES CREATED FROM THIS TENDER
    #
    # Each Client_Lane represents one awarded carrier contract.
    # ============================================================

    client_lanes = (
        db.query(Client_Lane)
        .filter(
            Client_Lane.tender_id == tender_id,
            Client_Lane.contract_status.in_(
                ["Awarded", "Active"]
            )
        )
        .order_by(
            Client_Lane.id
        )
        .all()
    )

    if not client_lanes:
        raise HTTPException(
            status_code=404,
            detail=(
                "No awarded client lane contracts were found "
                "for this tender"
            )
        )

    # ============================================================
    # 4. DETERMINE TENDER VOLUME PROFILE
    #
    # The tender's volume profile tells us how many loads are
    # expected for the booking period.
    #
    # We first attempt exact date-range matching.
    # Then day-of-week matching.
    # Then a single general profile.
    # ============================================================

    tender_profiles = (
        db.query(Lane_Tender_RFQ_Volume_Profile)
        .filter(
            Lane_Tender_RFQ_Volume_Profile.tender_id == tender_id
        )
        .order_by(
            Lane_Tender_RFQ_Volume_Profile.period_sequence
        )
        .all()
    )

    if not tender_profiles:
        raise HTTPException(
            status_code=400,
            detail="Tender has no volume profiles"
        )

    matching_profile = None

    # ------------------------------------------------------------
    # 4A. Exact date-range profile
    # ------------------------------------------------------------

    for profile in tender_profiles:

        if (
            profile.period_start_date
            and profile.period_end_date
            and profile.period_start_date
            <= booking_date
            <= profile.period_end_date
        ):
            matching_profile = profile
            break

    # ------------------------------------------------------------
    # 4B. Day-of-week profile
    # ------------------------------------------------------------

    if matching_profile is None:

        booking_day = booking_date.strftime("%A").lower()

        for profile in tender_profiles:

            if not profile.day_of_week:
                continue

            profile_day = (
                profile.day_of_week
                .strip()
                .lower()
            )

            if profile_day == booking_day:
                matching_profile = profile
                break

    # ------------------------------------------------------------
    # 4C. Single/general profile
    # ------------------------------------------------------------

    if matching_profile is None and len(tender_profiles) == 1:
        matching_profile = tender_profiles[0]

    # ------------------------------------------------------------
    # 4D. Fail if no volume profile can determine today's demand
    # ------------------------------------------------------------

    if matching_profile is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "No volume profile could be matched to "
                f"booking date {booking_date}"
            )
        )

    tender_expected_loads = (
        matching_profile.expected_loads or 0
    )

    if tender_expected_loads <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "The matched tender volume profile has "
                "no expected loads"
            )
        )

    # ============================================================
    # 5. DETERMINE PEAK TENDER CAPACITY
    #
    # This is used to calculate each carrier's proportional
    # contractual share.
    # ============================================================

    tender_peak_slots = max(
        profile.expected_loads or 0
        for profile in tender_profiles
    )

    if tender_peak_slots <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Tender has no valid peak slot capacity"
            )
        )

    # ============================================================
    # 6. BUILD CONTRACT UTILIZATION DATA
    # ============================================================

    contract_candidates = []

    for client_lane in client_lanes:

        # --------------------------------------------------------
        # Find corresponding carrier lane
        # --------------------------------------------------------

        carrier_lane = (
            db.query(Carrier_Lane)
            .filter(
                Carrier_Lane.client_lane_id == client_lane.id,
                Carrier_Lane.tender_id == tender_id,
                Carrier_Lane.contract_status.in_(
                    ["Awarded", "Active"]
                )
            )
            .first()
        )

        if not carrier_lane:
            continue

        # --------------------------------------------------------
        # Carrier's contractual peak capacity
        # --------------------------------------------------------

        contractual_slots_per_interval = (
            carrier_lane.slots_per_interval or 0
        )

        if contractual_slots_per_interval <= 0:
            continue

        # --------------------------------------------------------
        # Carrier's contractual total capacity
        # --------------------------------------------------------

        contractual_total_slots = (
            carrier_lane.total_slots or 0
        )

        if contractual_total_slots <= 0:
            continue

        # --------------------------------------------------------
        # Determine this carrier's proportional share
        # of the tender peak capacity.
        # --------------------------------------------------------

        contractual_share = (
            Decimal(contractual_slots_per_interval)
            / Decimal(tender_peak_slots)
        )

        # --------------------------------------------------------
        # Calculate expected loads for this carrier for the
        # current booking period.
        #
        # Example:
        #
        # Tender peak = 13
        # Carrier = 5
        # Today's volume = 4
        #
        # 4 × (5 / 13) = 1.538
        #
        # We retain the decimal value for utilization
        # calculations rather than rounding too early.
        # --------------------------------------------------------

        expected_contract_loads = (
            Decimal(tender_expected_loads)
            * contractual_share
        )

        # --------------------------------------------------------
        # Fetch all shipments already created against this
        # Client_Lane.
        #
        # The shipment itself is NOT created here.
        # --------------------------------------------------------

        existing_shipments = (
            db.query(Client_Shipment)
            .filter(
                Client_Shipment.lane_id == client_lane.id
            )
            .all()
        )

        total_shipments_awarded = len(
            existing_shipments
        )

        # --------------------------------------------------------
        # Count shipments completed / created during the
        # contract's current period up to the booking date.
        #
        # We use shipment dates where available.
        # --------------------------------------------------------

        period_shipments = 0

        for shipment in existing_shipments:

            shipment_date = getattr(
                shipment,
                "pickup_date",
                None
            )

            if shipment_date is None:
                shipment_date = getattr(
                    shipment,
                    "scheduled_pickup_date",
                    None
                )

            if shipment_date is None:
                continue

            if hasattr(shipment_date, "date"):
                shipment_date = shipment_date.date()

            if shipment_date <= booking_date:
                period_shipments += 1

        # --------------------------------------------------------
        # Calculate lifetime contractual utilization.
        # --------------------------------------------------------

        utilization_ratio = (
            Decimal(total_shipments_awarded)
            / Decimal(contractual_total_slots)
        )

        # --------------------------------------------------------
        # Calculate how much of the contract remains.
        # --------------------------------------------------------

        remaining_contract_slots = max(
            contractual_total_slots
            - total_shipments_awarded,
            0
        )

        # --------------------------------------------------------
        # Calculate how far behind the carrier currently is
        # relative to its proportional share of the tender.
        #
        # This becomes the primary allocation signal.
        # --------------------------------------------------------

        expected_total_contract_loads = (
            Decimal(tender_expected_loads)
            * contractual_share
        )

        utilization_gap = (
            expected_total_contract_loads
            - Decimal(period_shipments)
        )

        # --------------------------------------------------------
        # Calculate today's proportional target.
        # --------------------------------------------------------

        todays_target = expected_contract_loads

        # --------------------------------------------------------
        # Store candidate
        # --------------------------------------------------------

        contract_candidates.append(
            {
                "client_lane": client_lane,
                "carrier_lane": carrier_lane,

                "carrier_id": carrier_lane.carrier_id,

                "contractual_slots_per_interval": (
                    contractual_slots_per_interval
                ),

                "contractual_total_slots": (
                    contractual_total_slots
                ),

                "contractual_share": (
                    contractual_share
                ),

                "expected_contract_loads": (
                    expected_contract_loads
                ),

                "today_target": (
                    todays_target
                ),

                "total_shipments_awarded": (
                    total_shipments_awarded
                ),

                "period_shipments": (
                    period_shipments
                ),

                "remaining_contract_slots": (
                    remaining_contract_slots
                ),

                "utilization_ratio": (
                    utilization_ratio
                ),

                "utilization_gap": (
                    utilization_gap
                )
            }
        )

    # ============================================================
    # 7. VALIDATE CONTRACT CANDIDATES
    # ============================================================

    if not contract_candidates:
        raise HTTPException(
            status_code=400,
            detail=(
                "No active carrier contracts with valid "
                "capacity were found for this tender"
            )
        )

    # ============================================================
    # 8. REMOVE CONTRACTS THAT HAVE EXHAUSTED THEIR CAPACITY
    # ============================================================

    available_candidates = [
        candidate
        for candidate in contract_candidates
        if candidate["remaining_contract_slots"] > 0
    ]

    if not available_candidates:
        raise HTTPException(
            status_code=409,
            detail=(
                "All carrier contracts have reached their "
                "contractual shipment capacity"
            )
        )

    # ============================================================
    # 9. SORT CONTRACTS BY CONTRACTUAL UTILIZATION GAP
    #
    # The contract furthest behind its expected utilization
    # gets priority.
    #
    # Secondary priority:
    #   lower utilization ratio.
    #
    # Third priority:
    #   larger contractual capacity.
    #
    # Final priority:
    #   lower lane ID for deterministic behavior.
    # ============================================================

    available_candidates.sort(
        key=lambda candidate: (
            -candidate["utilization_gap"],
            candidate["utilization_ratio"],
            -candidate["contractual_slots_per_interval"],
            candidate["client_lane"].id
        )
    )

    # ============================================================
    # 10. ALLOCATE REQUESTED SLOTS
    #
    # For now the function supports requested_slots > 1 by
    # repeatedly allocating one slot at a time.
    #
    # This is important because the allocation engine can
    # eventually be used for bulk bookings.
    # ============================================================

    allocations = []

    remaining_slots_to_allocate = requested_slots

    while remaining_slots_to_allocate > 0:

        # --------------------------------------------------------
        # Re-sort after each allocation.
        # --------------------------------------------------------

        available_candidates.sort(
            key=lambda candidate: (
                -candidate["utilization_gap"],
                candidate["utilization_ratio"],
                -candidate["contractual_slots_per_interval"],
                candidate["client_lane"].id
            )
        )

        selected = available_candidates[0]

        # --------------------------------------------------------
        # Record allocation.
        # --------------------------------------------------------

        allocations.append(
            {
                "client_lane_id": (
                    selected["client_lane"].id
                ),

                "carrier_lane_id": (
                    selected["carrier_lane"].id
                ),

                "carrier_id": (
                    selected["carrier_id"]
                ),

                "allocated_slots": 1,

                "contractual_slots_per_interval": (
                    selected[
                        "contractual_slots_per_interval"
                    ]
                ),

                "contractual_total_slots": (
                    selected[
                        "contractual_total_slots"
                    ]
                ),

                "shipments_already_awarded": (
                    selected[
                        "total_shipments_awarded"
                    ]
                ),

                "remaining_contract_slots_before": (
                    selected[
                        "remaining_contract_slots"
                    ]
                ),

                "expected_contract_loads": str(
                    selected[
                        "expected_contract_loads"
                    ]
                ),

                "utilization_gap_before": str(
                    selected[
                        "utilization_gap"
                    ]
                )
            }
        )

        # --------------------------------------------------------
        # Simulate this allocation so the next slot can be
        # assigned against the updated contractual position.
        # --------------------------------------------------------

        selected["total_shipments_awarded"] += 1

        selected["period_shipments"] += 1

        selected["remaining_contract_slots"] = max(
            selected["remaining_contract_slots"] - 1,
            0
        )

        selected["utilization_ratio"] = (
            Decimal(
                selected["total_shipments_awarded"]
            )
            / Decimal(
                selected["contractual_total_slots"]
            )
        )

        selected["utilization_gap"] = (
            selected["expected_contract_loads"]
            - Decimal(
                selected["period_shipments"]
            )
        )

        # --------------------------------------------------------
        # Remove exhausted contract.
        # --------------------------------------------------------

        if selected["remaining_contract_slots"] <= 0:

            available_candidates.remove(
                selected
            )

            if (
                remaining_slots_to_allocate > 1
                and not available_candidates
            ):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Requested shipment slots exceed "
                        "the remaining contractual capacity "
                        "of all awarded carrier contracts"
                    )
                )

        remaining_slots_to_allocate -= 1

    # ============================================================
    # 11. DETERMINE PRIMARY ALLOCATION
    # ============================================================

    primary_allocation = allocations[0]

    # ============================================================
    # 12. RETURN ALLOCATION DECISION
    #
    # NO DATABASE RECORD IS CREATED.
    # ============================================================

    return {
        "success": True,

        "allocation_type": (
            "Contract Tender Allocation"
        ),

        "tender_id": tender_id,

        "booking_date": (
            booking_date.isoformat()
        ),

        "matched_volume_profile_id": (
            matching_profile.id
        ),

        "matched_volume_profile_sequence": (
            matching_profile.period_sequence
        ),

        "matched_volume_profile_label": (
            matching_profile.period_label
        ),

        "tender_expected_loads": (
            tender_expected_loads
        ),

        "tender_peak_slots": (
            tender_peak_slots
        ),

        "requested_slots": (
            requested_slots
        ),

        "primary_client_lane_id": (
            primary_allocation[
                "client_lane_id"
            ]
        ),

        "primary_carrier_lane_id": (
            primary_allocation[
                "carrier_lane_id"
            ]
        ),

        "primary_carrier_id": (
            primary_allocation[
                "carrier_id"
            ]
        ),

        "allocations": allocations,

        "contracts_evaluated": len(
            contract_candidates
        )
    }
