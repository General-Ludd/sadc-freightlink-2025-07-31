from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException
import uuid
from models.Exchange.dedicated_ftl_lane import Lane_Tender_RFQ, Lane_Tender_RFQ_Stop, Lane_Tender_RFQ_Vehicle_Config, Lane_Tender_RFQ_Volume_Profile, Lane_Tender_RFQ_Accessorial
from models.Exchange.bidding import Lane_Tender_Bid
from models.spot_bookings.dedicated_lane_ftl_shipment import Client_Lane, Lane_Stop, Lane_Vehicle_Config, Lane_Volume_Profile, Lane_Accessorial
from models.brokerage.finance import Dedicated_Lane_BrokerageLedger

ELIGIBLE_BID_STATUSES = {
    "Submitted",
    "Leading",
    "Under-Evaluation"
}


def _has_positive_bid_amount(value) -> bool:
    if value is None:
        return False

    try:
        return Decimal(str(value)) > 0
    except Exception:
        return False


def _calculate_award_rate(
    tender,
    bid,
    award_rate_type: str
) -> Decimal:

    award_rate_type = award_rate_type.upper()

    if award_rate_type not in {"MAIN", "SECONDARY"}:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid award rate type: {award_rate_type}"
        )

    if award_rate_type == "MAIN":

        raw_amount = bid.main_bid_amount
        stored_rate = getattr(
            bid,
            "main_rate_per_shipment",
            None
        )

    else:

        raw_amount = bid.secondary_bid_amount
        stored_rate = getattr(
            bid,
            "secondary_rate_per_shipment",
            None
        )

    if raw_amount is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{award_rate_type} bid does not contain "
                "a bid amount."
            )
        )

    # Prefer the rate already calculated during bid submission.
    if stored_rate is not None:
        rate = Decimal(str(stored_rate))

    else:

        amount = Decimal(str(raw_amount))

        if tender.pricing_basis == "Rate per Ton":

            tons = (
                Decimal(
                    str(
                        tender.average_shipment_weight_kg
                        or 0
                    )
                )
                / Decimal("1000")
            )

            if tons <= 0:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Tender does not contain a valid "
                        "average shipment weight."
                    )
                )

            rate = amount * tons

        elif tender.pricing_basis == "Rate per Km":

            distance = Decimal(
                str(
                    tender.actual_distance_km
                    or 0
                )
            )

            if distance <= 0:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Tender does not contain a valid "
                        "actual distance."
                    )
                )

            rate = amount * distance

        else:

            # Rate per Load / Shipment / Trip
            rate = amount

    if rate <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{award_rate_type} award rate must "
                "be greater than zero."
            )
        )

    return rate


def _get_remaining_tender_capacity(
    db: Session,
    tender_id: int
):

    volume_profiles = (
        db.query(
            Lane_Tender_RFQ_Volume_Profile
        )
        .filter(
            Lane_Tender_RFQ_Volume_Profile.tender_id
            == tender_id
        )
        .order_by(
            Lane_Tender_RFQ_Volume_Profile.period_sequence
        )
        .all()
    )

    if not volume_profiles:
        return 0, 0

    required_slots_per_interval = max(
        profile.expected_loads or 0
        for profile in volume_profiles
    )

    awarded_bids = (
        db.query(Lane_Tender_Bid)
        .filter(
            Lane_Tender_Bid.tender_id == tender_id,
            Lane_Tender_Bid.status == "Awarded"
        )
        .with_for_update()
        .all()
    )

    currently_awarded = sum(
        b.slots_per_interval or 0
        for b in awarded_bids
    )

    remaining = max(
        required_slots_per_interval
        - currently_awarded,
        0
    )

    return (
        required_slots_per_interval,
        remaining
    )


def _find_existing_carrier_award(
    db: Session,
    tender_id: int,
    carrier_id: int
):

    return (
        db.query(Carrier_Lane)
        .filter(
            Carrier_Lane.tender_id == tender_id,
            Carrier_Lane.carrier_id == carrier_id
        )
        .with_for_update()
        .first()
    )


def _find_submission_bid(
    db: Session,
    tender_id: int,
    carrier_id: int,
    submission_id: str
):

    return (
        db.query(Lane_Tender_Bid)
        .filter(
            Lane_Tender_Bid.tender_id == tender_id,
            Lane_Tender_Bid.carrier_id == carrier_id,
            Lane_Tender_Bid.submission_id == submission_id
        )
        .order_by(
            Lane_Tender_Bid.id.desc()
        )
        .with_for_update()
        .first()
    )

def _build_bundle_award_plan(
    db: Session,
    selected_tender,
    selected_bid
):

    # ------------------------------------------------------------
    # NOT A BUNDLE
    # ------------------------------------------------------------

    if not selected_tender.bundle_id:

        if not _has_positive_bid_amount(
            selected_bid.main_bid_amount
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Independent tender must have "
                    "a valid main bid."
                )
            )

        return [
            {
                "tender": selected_tender,
                "bid": selected_bid,
                "award_type": "MAIN"
            }
        ], None


    # ------------------------------------------------------------
    # LOCK BUNDLE
    # ------------------------------------------------------------

    bundle = (
        db.query(Lane_Tender_Bundle)
        .filter(
            Lane_Tender_Bundle.id
            == selected_tender.bundle_id
        )
        .with_for_update()
        .first()
    )

    if not bundle:
        raise HTTPException(
            status_code=500,
            detail=(
                "Tender references a bundle that "
                "does not exist."
            )
        )


    # ------------------------------------------------------------
    # LOAD AND LOCK ALL BUNDLE STAGES
    # ------------------------------------------------------------

    stages = (
        db.query(Lane_Tender_RFQ)
        .filter(
            Lane_Tender_RFQ.bundle_id == bundle.id
        )
        .order_by(
            Lane_Tender_RFQ.bundle_trip_sequence
        )
        .with_for_update()
        .all()
    )

    if len(stages) < 2:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Bundle {bundle.bundle_reference} "
                "does not contain enough stages."
            )
        )


    stage_sequences = [
        stage.bundle_trip_sequence
        for stage in stages
    ]

    expected_sequences = list(
        range(1, len(stages) + 1)
    )

    if stage_sequences != expected_sequences:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Bundle {bundle.bundle_reference} "
                "has invalid stage sequencing."
            )
        )


    selected_stage_sequence = (
        selected_tender.bundle_trip_sequence
    )

    last_stage_sequence = stages[-1].bundle_trip_sequence


    # ------------------------------------------------------------
    # TERMINAL STAGE
    #
    # C in A -> B -> C
    #
    # C only has MAIN.
    # ------------------------------------------------------------

    if selected_stage_sequence == last_stage_sequence:

        if not _has_positive_bid_amount(
            selected_bid.main_bid_amount
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "The final bundle stage must contain "
                    "a valid main bid."
                )
            )

        return [
            {
                "tender": selected_tender,
                "bid": selected_bid,
                "award_type": "MAIN"
            }
        ], bundle


    # ------------------------------------------------------------
    # CURRENT STAGE IS NOT THE FINAL STAGE
    #
    # Example:
    #
    # A -> B -> C
    #
    # A MAIN is only valid if B and C can also be awarded
    # to this carrier.
    # ------------------------------------------------------------

    downstream_plan = []
    main_chain_possible = True

    later_stages = [
        stage
        for stage in stages
        if stage.bundle_trip_sequence
        > selected_stage_sequence
    ]


    for stage in later_stages:

        # --------------------------------------------------------
        # Already awarded to this carrier?
        #
        # Then this downstream stage already satisfies
        # the bundle continuity requirement.
        # --------------------------------------------------------

        existing_award = _find_existing_carrier_award(
            db=db,
            tender_id=stage.id,
            carrier_id=selected_bid.carrier_id
        )

        if existing_award:
            continue


        # --------------------------------------------------------
        # The downstream lane must still have capacity.
        # --------------------------------------------------------

        required_capacity, remaining_capacity = (
            _get_remaining_tender_capacity(
                db=db,
                tender_id=stage.id
            )
        )

        if remaining_capacity <= 0:
            main_chain_possible = False
            break


        # --------------------------------------------------------
        # Find the same carrier's bid from the SAME submission.
        #
        # This is important because create_tender_bid()
        # gives all bundle bids in one submission the same
        # submission_id.
        # --------------------------------------------------------

        downstream_bid = _find_submission_bid(
            db=db,
            tender_id=stage.id,
            carrier_id=selected_bid.carrier_id,
            submission_id=selected_bid.submission_id
        )

        if not downstream_bid:
            main_chain_possible = False
            break


        if downstream_bid.status not in ELIGIBLE_BID_STATUSES:
            main_chain_possible = False
            break


        if not downstream_bid.slots_per_interval:
            main_chain_possible = False
            break


        if downstream_bid.slots_per_interval <= 0:
            main_chain_possible = False
            break


        # --------------------------------------------------------
        # Every downstream stage must be MAIN-capable.
        #
        # Example:
        #
        # A MAIN requires B MAIN, which requires C MAIN.
        #
        # A MAIN must not be created merely because B has a
        # SECONDARY price.
        # --------------------------------------------------------

        if not _has_positive_bid_amount(
            downstream_bid.main_bid_amount
        ):
            main_chain_possible = False
            break


        _calculate_award_rate(
            tender=stage,
            bid=downstream_bid,
            award_rate_type="MAIN"
        )


        downstream_plan.append(
            {
                "tender": stage,
                "bid": downstream_bid,
                "award_type": "MAIN"
            }
        )


    # ------------------------------------------------------------
    # MAIN BUNDLE AWARD IS AVAILABLE
    # ------------------------------------------------------------

    if (
        _has_positive_bid_amount(
            selected_bid.main_bid_amount
        )
        and main_chain_possible
    ):

        return (
            [
                {
                    "tender": selected_tender,
                    "bid": selected_bid,
                    "award_type": "MAIN"
                }
            ]
            + downstream_plan,
            bundle
        )


    # ------------------------------------------------------------
    # MAIN BUNDLE CANNOT BE HONOURED
    #
    # Use SECONDARY as standalone fallback.
    # ------------------------------------------------------------

    if _has_positive_bid_amount(
        selected_bid.secondary_bid_amount
    ):

        return [
            {
                "tender": selected_tender,
                "bid": selected_bid,
                "award_type": "SECONDARY"
            }
        ], bundle


    raise HTTPException(
        status_code=400,
        detail=(
            f"Carrier cannot be awarded tender "
            f"{selected_tender.id} at its main bundle rate "
            "because the downstream bundle cannot be "
            "completed, and no secondary bid was supplied."
        )
    )

#######################################################################################################################################################
#######################################################################################################################################################
#################################################################Award Single Tender###################################################################
#######################################################################################################################################################
#######################################################################################################################################################
def _award_single_tender_bid(
    db: Session,
    tender_id: int,
    bid_id: int,
    current_user: dict,
    award_rate_type: str = "MAIN",
    commit: bool = True
):
    # ============================================================
    # 1. LOCK AND LOAD TENDER
    # ============================================================

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

    # ============================================================
    # 2. VALIDATE TENDER STATUS
    # ============================================================

    if tender.status == "Awarded":
        raise HTTPException(
            status_code=400,
            detail="Tender has already been fully awarded"
        )

    if not tender.is_active:
        raise HTTPException(
            status_code=400,
            detail="Tender is not active and cannot receive an award"
        )

    # ============================================================
    # 3. LOAD AND LOCK BID
    # ============================================================

    bid = (
        db.query(Lane_Tender_Bid)
        .filter(
            Lane_Tender_Bid.id == bid_id,
            Lane_Tender_Bid.tender_id == tender_id
        )
        .with_for_update()
        .first()
    )

    if not bid:
        raise HTTPException(
            status_code=404,
            detail="Bid not found for this tender"
        )

    # ============================================================
    # 4. VALIDATE BID STATUS
    # ============================================================

    if bid.status not in [
        "Submitted",
        "Leading",
        "Under-Review"
    ]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Bid cannot be awarded from status "
                f"'{bid.status}'"
            )
        )

    # ============================================================
    # 5. VALIDATE BID VALUES
    # ============================================================

    selected_bid_amount = (
        bid.main_bid_amount
        if award_rate_type.upper() == "MAIN"
        else bid.secondary_bid_amount
    )

    if not _has_positive_bid_amount(
        selected_bid_amount
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{award_rate_type.upper()} bid does not "
                "contain a valid bid amount."
            )
        )

    bid_rate = _calculate_award_rate(
        tender=tender,
        bid=bid,
        award_rate_type=award_rate_type
    )

    # ============================================================
    # 6. CHECK IF THIS CARRIER ALREADY HAS AN AWARDED LANE
    # ============================================================

    existing_award = (
        db.query(Carrier_Lane)
        .filter(
            Carrier_Lane.tender_id == tender_id,
            Carrier_Lane.carrier_id == bid.carrier_id
        )
        .first()
    )

    if existing_award:
        raise HTTPException(
            status_code=409,
            detail=(
                "This carrier already has an awarded "
                "lane for this tender"
            )
        )

    # ============================================================
    # 7. LOAD TENDER VOLUME PROFILES
    # ============================================================

    volume_profiles = (
        db.query(Lane_Tender_RFQ_Volume_Profile)
        .filter(
            Lane_Tender_RFQ_Volume_Profile.tender_id == tender_id
        )
        .order_by(
            Lane_Tender_RFQ_Volume_Profile.period_sequence
        )
        .all()
    )

    if not volume_profiles:
        raise HTTPException(
            status_code=400,
            detail="Tender has no volume profile"
        )

    # ============================================================
    # 8. DETERMINE NUMBER OF INTERVALS
    # ============================================================

    number_of_intervals = len(volume_profiles)

    if number_of_intervals <= 0:
        raise HTTPException(
            status_code=400,
            detail="Tender has no valid volume intervals"
        )

    # ============================================================
    # 9. DETERMINE REQUIRED PEAK CAPACITY
    #
    # Tender capacity is currently based on the peak interval.
    # ============================================================

    required_slots_per_interval = max(
        profile.expected_loads or 0
        for profile in volume_profiles
    )

    if required_slots_per_interval <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Tender volume profile contains no "
                "required shipment capacity"
            )
        )

    # ============================================================
    # 10. FIND ALREADY AWARDED BIDS
    #
    # IMPORTANT:
    # Awarded bids MUST use status == "Awarded".
    # ============================================================

    awarded_bids = (
        db.query(Lane_Tender_Bid)
        .filter(
            Lane_Tender_Bid.tender_id == tender_id,
            Lane_Tender_Bid.status == "Awarded"
        )
        .with_for_update()
        .all()
    )

    # ============================================================
    # 11. CALCULATE CURRENTLY AWARDED CAPACITY
    #
    # This represents slots PER INTERVAL.
    # ============================================================

    currently_awarded_slots_per_interval = sum(
        b.slots_per_interval or 0
        for b in awarded_bids
    )

    # ============================================================
    # 12. DETERMINE REMAINING CAPACITY
    # ============================================================

    remaining_slots_per_interval = max(
        required_slots_per_interval
        - currently_awarded_slots_per_interval,
        0
    )

    if remaining_slots_per_interval <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Tender has already satisfied its "
                "required slots per interval"
            )
        )

    # ============================================================
    # 13. DETERMINE ACTUAL AWARDED CAPACITY
    #
    # Example:
    #
    # Required = 10
    # Already awarded = 7
    # New bid = 5
    #
    # Actual award = 3
    # ============================================================

    awarded_slots_per_interval = min(
        bid.slots_per_interval,
        remaining_slots_per_interval
    )

    if awarded_slots_per_interval <= 0:
        raise HTTPException(
            status_code=400,
            detail="No remaining capacity available for this bid"
        )

    # ============================================================
    # 14. CALCULATE TOTAL CONTRACT SLOTS
    #
    # Awarded slots per interval × number of intervals
    # ============================================================

    total_contract_slots = (
        awarded_slots_per_interval
        * number_of_intervals
    )

    # ============================================================
    # 15. BID RATE
    #
    # Already calculated during Section 5 according to
    # MAIN or SECONDARY award type.
    # ============================================================

    # ============================================================
    # 16. CALCULATE TOTAL CONTRACT VALUE
    # ============================================================

    contract_rate = (
        bid_rate
        * Decimal(total_contract_slots)
    )

    # ============================================================
    # 17. CALCULATE PROCUREMENT SAVINGS
    # ============================================================

    incumbent_rate = Decimal(
        str(
            tender.incumbent_transport_rate_per_shipment
            or 0
        )
    )

    rate_savings = (
        incumbent_rate
        - bid_rate
    )

    contract_savings = (
        rate_savings
        * Decimal(total_contract_slots)
    )

    # ============================================================
    # 18. GENERATE CLIENT LANE REFERENCE
    # ============================================================

    client_lane_reference = (
        f"LANE-{tender.id}-"
        f"{uuid.uuid4().hex[:8].upper()}"
    )

    # ============================================================
    # 19. CREATE CLIENT / SHIPPER LANE
    # ============================================================

    client_lane = Client_Lane(
        tender_id=tender.id,
        client_id=tender.client_id,
        publisher_user_id=tender.publisher_user_id,
        # ========================================================
        # BUNDLE LINEAGE
        # ========================================================
        bundle_id=getattr(tender, "bundle_id", None),
        bundle_reference=getattr(tender, "bundle_reference", None),
        bundle_role=getattr(tender, "bundle_role", None),
        bundle_trip_sequence=getattr(tender, "bundle_trip_sequence", None),
        # IMPORTANT:
        # Required by Client_Lane model.
        awarded_carrier_id=bid.carrier_id,

        lane_title=tender.tender_title,
        lane_commitment_type=tender.lane_commitment_type,
        lane_length_category=tender.tender_length_category,
        lane_category=tender.tender_category,
        scope_description=tender.scope_description,
        business_unit=tender.business_unit,
        cost_centre_project_code=tender.cost_centre_project_code,

        parent_lane_id=None,
        lane_reference=client_lane_reference,

        contract_status="Awarded",

        contract_start_date=tender.contract_start_date,
        contract_end_date=tender.contract_end_date,

        actual_distance_km=tender.actual_distance_km,
        polyline=tender.polyline,

        # ========================================================
        # ROUTING
        # ========================================================

        origin_address=tender.origin_address,
        complete_origin_address=tender.complete_origin_address,
        origin_city_province=tender.origin_city_province,
        origin_country=tender.origin_country,
        origin_region=tender.origin_region,

        destination_address=tender.destination_address,
        complete_destination_address=tender.complete_destination_address,
        destination_city_province=tender.destination_city_province,
        destination_country=tender.destination_country,
        destination_region=tender.destination_region,

        border_customs_responsibility=(
            tender.border_customs_responsibility
        ),

        priority_level=tender.priority_level,
        load_type=tender.load_type,
        customer_reference=tender.customer_reference,

        # ========================================================
        # CARGO
        # ========================================================

        commodity=tender.commodity,
        average_shipment_weight_kg=(
            tender.average_shipment_weight_kg
        ),
        minimum_weight_bracket_kg=(
            tender.minimum_weight_bracket_kg
        ),
        packaging_type=tender.packaging_type,
        packaging_quantity=tender.packaging_quantity,
        temperature_control=tender.temperature_control,
        target_temperature_spec=tender.target_temperature_spec,
        hazardous_materials=tender.hazardous_materials,
        hazchem_classification=tender.hazchem_classification,
        under_bond=tender.under_bond,
        rib_requirements=tender.rib_requirements,

        # ========================================================
        # COMMERCIAL
        # ========================================================

        pricing_basis=tender.pricing_basis,

        incumbent_transport_rate_per_shipment=(
            tender.incumbent_transport_rate_per_shipment
        ),

        incumbent_contract_rate=(
            tender.incumbent_contract_rate
        ),

        procurement_target_rate=(
            tender.procurement_target_rate
        ),

        procurement_target_contract_rate=(
            tender.procurement_target_contract_rate
        ),

        awarded_rate_per_shipment=bid_rate,
        awarded_contract_rate=contract_rate,
        awarded_rate_per_shipment_savings=rate_savings,
        awarded_savings_contract_value=contract_savings,

        vat_included=tender.vat_included,
        rate_validity=tender.rate_validity,

        # ========================================================
        # RATE INCLUSIONS
        # ========================================================

        rate_includes_fuel=tender.rate_includes_fuel,
        rate_includes_driver=tender.rate_includes_driver,
        rate_includes_maintenance=(
            tender.rate_includes_maintenance
        ),
        rate_includes_insurance=(
            tender.rate_includes_insurance
        ),
        rate_includes_tolls=tender.rate_includes_tolls,
        rate_includes_border_charges=(
            tender.rate_includes_border_charges
        ),
        rate_includes_empty_return=(
            tender.rate_includes_empty_return
        ),
        rate_includes_waiting_time=(
            tender.rate_includes_waiting_time
        ),
        rate_includes_loading_assistance=(
            tender.rate_includes_loading_assistance
        ),
        rate_includes_offloading_assistance=(
            tender.rate_includes_offloading_assistance
        ),

        # ========================================================
        # PAYMENT
        # ========================================================

        payment_terms=tender.payment_terms,
        invoice_submission_frequency=(
            tender.invoice_submission_frequency
        ),
        invoice_submission_deadline=(
            tender.invoice_submission_deadline
        ),

        # ========================================================
        # INSURANCE
        # ========================================================

        minimum_git_cover_amount=(
            tender.minimum_git_cover_amount
        ),
        minimum_liability_cover_amount=(
            tender.minimum_liability_cover_amount
        ),

        git_all_risk_required=(
            tender.git_all_risk_required
        ),
        git_first_loss_required=(
            tender.git_first_loss_required
        ),
        git_driver_fidelity_required=(
            tender.git_driver_fidelity_required
        ),

        # ========================================================
        # DOCUMENTATION / RISK
        # ========================================================

        delivery_documentation_sla=(
            tender.delivery_documentation_sla
        ),
        claims_risk_policy=tender.claims_risk_policy,
        claims_risk_requirements=(
            tender.claims_risk_requirements
        ),

        # ========================================================
        # OPERATIONAL REQUIREMENTS
        # ========================================================

        vehicle_tracking_required=(
            tender.vehicle_tracking_required
        ),
        all_time_hour_control_room=(
            tender.all_time_hour_control_room
        ),
        driver_mobile_phone=(
            tender.driver_mobile_phone
        ),
        clean_compliant_equipment=(
            tender.clean_compliant_equipment
        ),
        pallet_management=tender.pallet_management,

        pod_submission_local=(
            tender.pod_submission_local
        ),
        pod_submission_long_haul=(
            tender.pod_submission_long_haul
        ),
        pod_submission_cross_border=(
            tender.pod_submission_cross_border
        ),

        subcontracting_policy=(
            tender.subcontracting_policy
        ),

        # ========================================================
        # EQUIPMENT COMPLIANCE
        # ========================================================

        tarpaulin_compliance_required=(
            tender.tarpaulin_compliance_required
        ),
        corner_plates_required=(
            tender.corner_plates_required
        ),
        chock_blocks_required=(
            tender.chock_blocks_required
        ),
        ratchets_belts_required=(
            tender.ratchets_belts_required
        ),
        other_equipment_requirements=(
            tender.other_equipment_requirements
        )
    )

    db.add(client_lane)
    db.flush()

    # ============================================================
    # 20. LOAD TENDER STOPS
    #
    # We only copy fields that actually exist on the tender stop.
    # The client can complete operational facility information
    # after award.
    # ============================================================

    tender_stops = (
        db.query(Lane_Tender_RFQ_Stop)
        .filter(
            Lane_Tender_RFQ_Stop.tender_id == tender.id
        )
        .order_by(
            Lane_Tender_RFQ_Stop.stop_sequence
        )
        .all()
    )

    for stop in tender_stops:
        db.add(
            Lane_Stop(
                lane_id=client_lane.id,
                stop_sequence=stop.stop_sequence,
                stop_type=stop.stop_type,
                facility_name=stop.facility_name,
                address=stop.address,
                complete_address=stop.complete_address,
                city_province=stop.city_province,
                country=stop.country,
                region=stop.region
            )
        )

    # ============================================================
    # 21. CREATE CLIENT LANE VEHICLE CONFIGURATIONS
    # ============================================================

    tender_configs = (
        db.query(Lane_Tender_RFQ_Vehicle_Config)
        .filter(
            Lane_Tender_RFQ_Vehicle_Config.tender_id == tender.id
        )
        .all()
    )

    for config in tender_configs:
        db.add(
            Lane_Vehicle_Config(
                lane_id=client_lane.id,
                configuration_type=config.configuration_type,
                truck_type=config.truck_type,
                equipment_type=config.equipment_type,
                trailer_type=config.trailer_type,
                trailer_length=config.trailer_length,
                is_active=config.is_active
            )
        )

    # ============================================================
    # 22. CREATE CLIENT LANE VOLUME PROFILES
    # ============================================================

    for profile in volume_profiles:
        db.add(
            Lane_Volume_Profile(
                lane_id=client_lane.id,
                volume_entry_method=profile.volume_entry_method,
                period_sequence=profile.period_sequence,
                period_label=profile.period_label,
                period_start_date=profile.period_start_date,
                period_end_date=profile.period_end_date,
                day_of_week=profile.day_of_week,
                expected_loads=profile.expected_loads
            )
        )

    # ============================================================
    # 23. CREATE CLIENT LANE ACCESSORIALS
    # ============================================================

    tender_accessorials = (
        db.query(Lane_Tender_RFQ_Accessorial)
        .filter(
            Lane_Tender_RFQ_Accessorial.tender_id == tender.id
        )
        .all()
    )

    for accessorial in tender_accessorials:
        db.add(
            Lane_Accessorial(
                lane_id=client_lane.id,
                charge_type=accessorial.charge_type,
                treatment=accessorial.treatment,
                threshold_value=accessorial.threshold_value,
                threshold_unit=accessorial.threshold_unit,
                notes=accessorial.notes
            )
        )

    # ============================================================
    # 24. GENERATE CARRIER LANE REFERENCE
    # ============================================================

    carrier_lane_reference = (
        f"CLANE-{tender.id}-"
        f"{bid.carrier_id}-"
        f"{uuid.uuid4().hex[:8].upper()}"
    )

    # ============================================================
    # 25. CREATE CARRIER LANE
    # ============================================================

    carrier_lane = Carrier_Lane(
        tender_id=tender.id,
        client_lane_id=client_lane.id,
        carrier_id=bid.carrier_id,
        bidder_user_id=bid.bidder_user_id,

        # ========================================================
        # BUNDLE LINEAGE
        # ========================================================
        bundle_id=getattr(tender, "bundle_id", None),
        bundle_reference=getattr(tender, "bundle_reference", None),
        bundle_role=getattr(tender, "bundle_role", None),
        bundle_trip_sequence=getattr(tender, "bundle_trip_sequence", None),

        lane_title=tender.tender_title,
        lane_commitment_type=tender.lane_commitment_type,
        lane_length_category=tender.tender_length_category,
        lane_category=tender.tender_category,
        scope_description=tender.scope_description,
        business_unit=tender.business_unit,
        cost_centre_project_code=tender.cost_centre_project_code,

        parent_lane_id=None,
        lane_reference=carrier_lane_reference,

        contract_status="Awarded",

        contract_start_date=tender.contract_start_date,
        contract_end_date=tender.contract_end_date,

        actual_distance_km=tender.actual_distance_km,
        polyline=tender.polyline,

        # ========================================================
        # CARGO
        # ========================================================

        commodity=tender.commodity,
        average_shipment_weight_kg=(
            tender.average_shipment_weight_kg
        ),
        minimum_weight_bracket_kg=(
            tender.minimum_weight_bracket_kg
        ),
        packaging_type=tender.packaging_type,
        packaging_quantity=tender.packaging_quantity,
        temperature_control=tender.temperature_control,
        target_temperature_spec=tender.target_temperature_spec,
        hazardous_materials=tender.hazardous_materials,
        hazchem_classification=tender.hazchem_classification,
        under_bond=tender.under_bond,
        rib_requirements=tender.rib_requirements,

        # ========================================================
        # VOLUME / CAPACITY
        #
        # IMPORTANT:
        # This carrier only receives the capacity actually
        # awarded to it.
        # ========================================================

        volume_entry_method=(
            tender.volume_entry_method
        ),
        volume_commitment=(
            tender.volume_commitment
        ),

        # ========================================================
        # COMMERCIAL
        # ========================================================

        pricing_basis=tender.pricing_basis,
        rate=bid_rate,
        award_rate_type=award_rate_type,
        contract_rate=contract_rate,

        slots_per_interval=awarded_slots_per_interval,
        total_slots=total_contract_slots,

        vat_included=tender.vat_included,
        rate_validity=tender.rate_validity,

        # ========================================================
        # RATE INCLUSIONS
        # ========================================================

        rate_includes_fuel=tender.rate_includes_fuel,
        rate_includes_driver=tender.rate_includes_driver,
        rate_includes_maintenance=(
            tender.rate_includes_maintenance
        ),
        rate_includes_insurance=(
            tender.rate_includes_insurance
        ),
        rate_includes_tolls=tender.rate_includes_tolls,
        rate_includes_border_charges=(
            tender.rate_includes_border_charges
        ),
        rate_includes_empty_return=(
            tender.rate_includes_empty_return
        ),
        rate_includes_waiting_time=(
            tender.rate_includes_waiting_time
        ),
        rate_includes_loading_assistance=(
            tender.rate_includes_loading_assistance
        ),
        rate_includes_offloading_assistance=(
            tender.rate_includes_offloading_assistance
        ),

        # ========================================================
        # PAYMENT
        # ========================================================

        payment_terms=tender.payment_terms,
        invoice_submission_frequency=(
            tender.invoice_submission_frequency
        ),
        invoice_submission_deadline=(
            tender.invoice_submission_deadline
        ),

        # ========================================================
        # ROUTING
        # ========================================================

        origin_address=tender.origin_address,
        complete_origin_address=(
            tender.complete_origin_address
        ),
        origin_city_province=(
            tender.origin_city_province
        ),
        origin_country=tender.origin_country,
        origin_region=tender.origin_region,

        destination_address=tender.destination_address,
        complete_destination_address=(
            tender.complete_destination_address
        ),
        destination_city_province=(
            tender.destination_city_province
        ),
        destination_country=tender.destination_country,
        destination_region=tender.destination_region,

        # ========================================================
        # INSURANCE
        # ========================================================

        minimum_git_cover_amount=(
            tender.minimum_git_cover_amount
        ),
        minimum_liability_cover_amount=(
            tender.minimum_liability_cover_amount
        ),

        git_all_risk_required=(
            tender.git_all_risk_required
        ),
        git_first_loss_required=(
            tender.git_first_loss_required
        ),
        git_driver_fidelity_required=(
            tender.git_driver_fidelity_required
        ),

        # ========================================================
        # DOCUMENTATION / RISK
        # ========================================================

        delivery_documentation_sla=(
            tender.delivery_documentation_sla
        ),
        claims_risk_policy=tender.claims_risk_policy,
        claims_risk_requirements=(
            tender.claims_risk_requirements
        ),

        # ========================================================
        # OPERATIONAL REQUIREMENTS
        # ========================================================

        vehicle_tracking_required=(
            tender.vehicle_tracking_required
        ),
        all_time_hour_control_room=(
            tender.all_time_hour_control_room
        ),
        driver_mobile_phone=(
            tender.driver_mobile_phone
        ),
        clean_compliant_equipment=(
            tender.clean_compliant_equipment
        ),
        pallet_management=tender.pallet_management,

        pod_submission_local=(
            tender.pod_submission_local
        ),
        pod_submission_long_haul=(
            tender.pod_submission_long_haul
        ),
        pod_submission_cross_border=(
            tender.pod_submission_cross_border
        ),

        subcontracting_policy=(
            tender.subcontracting_policy
        ),

        # ========================================================
        # EQUIPMENT COMPLIANCE
        # ========================================================

        tarpaulin_compliance_required=(
            tender.tarpaulin_compliance_required
        ),
        corner_plates_required=(
            tender.corner_plates_required
        ),
        chock_blocks_required=(
            tender.chock_blocks_required
        ),
        ratchets_belts_required=(
            tender.ratchets_belts_required
        ),
        other_equipment_requirements=(
            tender.other_equipment_requirements
        )
    )

    db.add(carrier_lane)
    db.flush()

    # ============================================================
    # 26. CREATE CARRIER LANE STOPS
    #
    # Same tender-stop data only.
    # Carrier does not receive operational facility fields that
    # do not exist on the tender stop.
    # ============================================================

    for stop in tender_stops:
        db.add(
            Lane_Stop(
                lane_id=carrier_lane.id,
                stop_sequence=stop.stop_sequence,
                stop_type=stop.stop_type,
                facility_name=stop.facility_name,
                address=stop.address,
                complete_address=stop.complete_address,
                city_province=stop.city_province,
                country=stop.country,
                region=stop.region
            )
        )

    # ============================================================
    # 27. CREATE CARRIER LANE VEHICLE CONFIGURATIONS
    # ============================================================

    for config in tender_configs:
        db.add(
            Lane_Vehicle_Config(
                lane_id=carrier_lane.id,
                configuration_type=config.configuration_type,
                truck_type=config.truck_type,
                equipment_type=config.equipment_type,
                trailer_type=config.trailer_type,
                trailer_length=config.trailer_length,
                is_active=config.is_active
            )
        )

    # ============================================================
    # 28. CREATE CARRIER LANE VOLUME PROFILES
    # ============================================================

    for profile in volume_profiles:
        db.add(
            Lane_Volume_Profile(
                lane_id=carrier_lane.id,
                volume_entry_method=profile.volume_entry_method,
                period_sequence=profile.period_sequence,
                period_label=profile.period_label,
                period_start_date=profile.period_start_date,
                period_end_date=profile.period_end_date,
                day_of_week=profile.day_of_week,
                expected_loads=profile.expected_loads
            )
        )

    # ============================================================
    # 29. CREATE CARRIER LANE ACCESSORIALS
    # ============================================================

    for accessorial in tender_accessorials:
        db.add(
            Lane_Accessorial(
                lane_id=carrier_lane.id,
                charge_type=accessorial.charge_type,
                treatment=accessorial.treatment,
                threshold_value=accessorial.threshold_value,
                threshold_unit=accessorial.threshold_unit,
                notes=accessorial.notes
            )
        )

    # ============================================================
    # 30. UPDATE BID STATUS
    #
    # IMPORTANT:
    # Use "Awarded" consistently because capacity calculations
    # search for Awarded bids.
    # ============================================================

    bid.status = "Awarded"

    # ============================================================
    # 31. CALCULATE TOTAL AWARDED CAPACITY
    # ============================================================

    total_awarded_slots_per_interval = (
        currently_awarded_slots_per_interval
        + awarded_slots_per_interval
    )

    remaining_slots_per_interval = max(
        required_slots_per_interval
        - total_awarded_slots_per_interval,
        0
    )

    # ============================================================
    # 32. UPDATE TENDER STATUS
    # ============================================================

    if remaining_slots_per_interval == 0:
        tender.status = "Awarded"
        tender.is_active = False
    else:
        tender.status = "Partially Awarded"
        tender.is_active = True

    # ============================================================
    # 33. CREATE BROKERAGE LEDGER
    #
    # LEFT STRUCTURALLY UNCHANGED AS REQUESTED.
    # ============================================================

    def calculate_commission(bid_rate: float) -> int:
        if bid_rate <= 12500:
            return 200
        elif bid_rate <= 18000:
            return 400
        elif bid_rate <= 24000:
            return 600
        else:
            return 850

    shipper = (
        db.query(Corporation)
        .filter(
            Corporation.id == tender.client_id
        )
        .first()
    )

    if shipper:
        commission_fee = calculate_commission(bid_rate)

        brokerage_ledger = Dedicated_Lane_BrokerageLedger(
            tender_id=tender.id,
            client_lane_id=client_lane.id,
            shipper_company_id=client_lane.client_id,
            shipper_company_name=shipper.legal_business_name,
            shipper_company_registration_number=(
                shipper.business_registration_number
            ),
            shipper_company_country_of_incorporation=(
                shipper.country_of_incorporation
            ),
            payment_terms=client_lane.payment_terms,
            contract_booking_amount=contract_rate,
            contract_platform_commission=(
                commission_fee * total_contract_slots
            ),
            contract_true_platform_earnings=(
                commission_fee * total_contract_slots
            ),
            contract_carrier_payable=(
                contract_rate
                - (
                    commission_fee
                    * total_contract_slots
                )
            ),
            contract_amount_paid=0,
            carrier_payable_paid=0,
            platform_commission_generated=0,

            total_shipments=total_contract_slots,
            booking_amount_per_shipment=bid_rate,
            platform_commission_per_shipment=commission_fee,
            true_platform_earnings_per_shipment=commission_fee,
            carrier_payable_per_shipment=(
                bid_rate - commission_fee
            ),
            num_shipments_completed=0,
            total_slots_assigned=awarded_slots_per_interval,
            shipments_per_slot=number_of_intervals,
        )

        db.add(brokerage_ledger)

    # ============================================================
    # 34. COMMIT EVERYTHING AS ONE TRANSACTION
    # ============================================================

    if commit:

        try:
            db.commit()

        except Exception:
            db.rollback()
            raise

    # ============================================================
    # 35. REFRESH OBJECTS
    # ============================================================

    if commit:

        db.refresh(client_lane)
        db.refresh(carrier_lane)
        db.refresh(tender)
        db.refresh(bid)

    # ============================================================
    # 36. RETURN AWARD RESULT
    # ============================================================

    return {
        "success": True,

        "message": (
            "Bid awarded and tender fully awarded"
            if tender.status == "Awarded"
            else "Bid awarded and tender partially awarded"
        ),

        "tender_id": tender.id,
        "tender_status": tender.status,

        "bid_id": bid.id,
        "bid_status": bid.status,

        "client_lane_id": client_lane.id,
        "carrier_lane_id": carrier_lane.id,

        "carrier_id": bid.carrier_id,

        "number_of_intervals": number_of_intervals,

        "required_slots_per_interval": (
            required_slots_per_interval
        ),

        "previously_awarded_slots_per_interval": (
            currently_awarded_slots_per_interval
        ),

        "bid_slots_per_interval": (
            bid.slots_per_interval
        ),

        "awarded_slots_per_interval": (
            awarded_slots_per_interval
        ),

        "total_awarded_slots_per_interval": (
            total_awarded_slots_per_interval
        ),

        "remaining_slots_per_interval": (
            remaining_slots_per_interval
        ),

        "total_contract_slots": (
            total_contract_slots
        ),

        "rate_per_shipment": str(
            bid_rate
        ),

        "contract_rate": str(
            contract_rate
        ),

        "rate_savings_per_shipment": str(
            rate_savings
        ),

        "contract_savings": str(
            contract_savings
        )
    }



#######################################################################################################################################################
#######################################################################################################################################################
#################################################################Award Tender Bid######################################################################
#######################################################################################################################################################
#######################################################################################################################################################
def award_tender_bid(
    db: Session,
    tender_id: int,
    bid_id: int,
    current_user: dict
):

    try:

        # ========================================================
        # 1. LOAD TENDER
        # ========================================================

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


        # ========================================================
        # 2. LOCK BUNDLE FIRST
        #
        # Prevent concurrent awards on different stages
        # of the same bundle.
        # ========================================================

        bundle = None

        if tender.bundle_id:

            bundle = (
                db.query(Lane_Tender_Bundle)
                .filter(
                    Lane_Tender_Bundle.id
                    == tender.bundle_id
                )
                .with_for_update()
                .first()
            )

            if not bundle:
                raise HTTPException(
                    status_code=500,
                    detail=(
                        "Tender references a bundle "
                        "that does not exist."
                    )
                )

            (
                db.query(Lane_Tender_RFQ)
                .filter(
                    Lane_Tender_RFQ.bundle_id
                    == bundle.id
                )
                .with_for_update()
                .all()
            )


        # ========================================================
        # 3. LOCK SELECTED TENDER
        # ========================================================

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


        # ========================================================
        # 4. VALIDATE TENDER
        # ========================================================

        if tender.status == "Awarded":
            raise HTTPException(
                status_code=400,
                detail=(
                    "Tender has already been "
                    "fully awarded."
                )
            )

        if not tender.is_active:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Tender is not active and cannot "
                    "receive an award."
                )
            )


        # ========================================================
        # 5. LOAD AND LOCK SELECTED BID
        # ========================================================

        bid = (
            db.query(Lane_Tender_Bid)
            .filter(
                Lane_Tender_Bid.id == bid_id,
                Lane_Tender_Bid.tender_id == tender_id
            )
            .with_for_update()
            .first()
        )

        if not bid:
            raise HTTPException(
                status_code=404,
                detail="Bid not found for this tender"
            )


        # ========================================================
        # 6. VALIDATE BID STATUS
        # ========================================================

        if bid.status not in ELIGIBLE_BID_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Bid cannot be awarded from status "
                    f"'{bid.status}'"
                )
            )


        # ========================================================
        # 7. VALIDATE BID CAPACITY
        # ========================================================

        if (
            not bid.slots_per_interval
            or bid.slots_per_interval <= 0
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Bid does not contain a valid "
                    "slots_per_interval value."
                )
            )


        # ========================================================
        # 8. BUILD AWARD PLAN
        # ========================================================

        award_plan, bundle = (
            _build_bundle_award_plan(
                db=db,
                selected_tender=tender,
                selected_bid=bid
            )
        )


        # ========================================================
        # 9. EXECUTE AWARD PLAN
        #
        # Each tender is still awarded by your original
        # single-lane award engine.
        # ========================================================

        award_results = []

        for award_item in award_plan:

            plan_tender = award_item["tender"]
            plan_bid = award_item["bid"]
            award_type = award_item["award_type"]


            # ----------------------------------------------------
            # Do not award the same tender/carrier twice.
            # ----------------------------------------------------

            existing_award = (
                db.query(Carrier_Lane)
                .filter(
                    Carrier_Lane.tender_id
                    == plan_tender.id,
                    Carrier_Lane.carrier_id
                    == plan_bid.carrier_id
                )
                .first()
            )

            if existing_award:
                continue


            result = _award_single_tender_bid(
                db=db,
                tender_id=plan_tender.id,
                bid_id=plan_bid.id,
                current_user=current_user,
                award_rate_type=award_type,
                commit=False
            )

            result["award_type"] = award_type

            award_results.append(result)


        # ========================================================
        # 10. UPDATE BUNDLE STATUS
        # ========================================================

        bundle_summary = None

        if bundle:

            bundle_tenders = (
                db.query(Lane_Tender_RFQ)
                .filter(
                    Lane_Tender_RFQ.bundle_id
                    == bundle.id
                )
                .order_by(
                    Lane_Tender_RFQ.bundle_trip_sequence
                )
                .all()
            )

            all_awarded = all(
                stage.status == "Awarded"
                for stage in bundle_tenders
            )

            bundle.status = (
                "Awarded"
                if all_awarded
                else "Partially Awarded"
            )

            bundle_summary = {
                "bundle_id": bundle.id,
                "bundle_reference": (
                    bundle.bundle_reference
                ),
                "bundle_status": bundle.status,
                "stage_count": len(
                    bundle_tenders
                )
            }


        # ========================================================
        # 11. COMMIT ENTIRE AWARD TRANSACTION
        # ========================================================

        db.commit()


        # ========================================================
        # 12. RETURN RESULT
        # ========================================================

        return {
            "success": True,

            "message": (
                "Bundle award completed."
                if bundle and len(award_results) > 1
                else "Tender award completed."
            ),

            "tender_id": tender.id,

            "bundle": bundle_summary,

            "awards_created": len(
                award_results
            ),

            "awards": award_results
        }


    except HTTPException:

        db.rollback()
        raise

    except Exception:

        db.rollback()
        raise