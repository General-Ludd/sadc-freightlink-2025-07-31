from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException
import uuid
from models.Exchange.dedicated_ftl_lane import Lane_Tender_RFQ, Lane_Tender_RFQ_Stop, Lane_Tender_RFQ_Vehicle_Config, Lane_Tender_RFQ_Volume_Profile, Lane_Tender_RFQ_Accessorial
from models.Exchange.auction import Lane_Tender_RFQ_Bids
from models.spot_bookings.dedicated_lane_ftl_shipment import Client_Lane, Lane_Stop, Lane_Vehicle_Config, Lane_Volume_Profile, Lane_Accessorial
from models.brokerage.finance import Dedicated_Lane_BrokerageLedger

def award_tender_bid(
    db: Session,
    tender_id: int,
    bid_id: int,
    current_user: dict
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
        db.query(Lane_Tender_RFQ_Bids)
        .filter(
            Lane_Tender_RFQ_Bids.id == bid_id,
            Lane_Tender_RFQ_Bids.tender_id == tender_id
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

    if not bid.slots_per_interval or bid.slots_per_interval <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Bid does not contain a valid "
                "slots_per_interval value"
            )
        )

    if not bid.bid_per_shipment or bid.bid_per_shipment <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Bid does not contain a valid "
                "bid_per_shipment"
            )
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
        db.query(Lane_Tender_RFQ_Bids)
        .filter(
            Lane_Tender_RFQ_Bids.tender_id == tender_id,
            Lane_Tender_RFQ_Bids.status == "Awarded"
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
    # 15. CALCULATE BID RATE
    # ============================================================

    bid_rate = Decimal(
        str(bid.bid_per_shipment)
    )

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

        # IMPORTANT:
        # Required by Client_Lane model.
        awarded_carrier_id=bid.carrier_id,

        lane_title=tender.tender_title,
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

        lane_title=tender.tender_title,
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

    try:
        db.commit()

    except Exception:
        db.rollback()
        raise

    # ============================================================
    # 35. REFRESH OBJECTS
    # ============================================================

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
