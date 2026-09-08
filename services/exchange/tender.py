from datetime import date, datetime, time, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session
from models.Exchange.dedicated_ftl_lane import (
    Lane_Tender_RFQ,
    Lane_Tender_RFQ_Stop,
    Lane_Tender_RFQ_Vehicle_Config,
    Lane_Tender_RFQ_Volume_Profile,
    Lane_Tender_RFQ_Accessorial,
    Turnaround_Window_Demurrage_Protocals,
    Carrier_Certification_Driver_Standards,
    Escort_Policy,
    Sla_incident_Reporting,
)
from models.brokerage.loadboard import Lane_Tender_Loadboard
from models.brokerage.finance import FinancialAccounts
from models.shipper import Corporation
from utils.google_maps import AddressInput, RouteETAInput, calculate_distance, get_eta_and_polyline

from schemas.exchange_bookings.dedicated_ftl_lane import TenderCreate, TenderBatchCreate

def calculate_tender_distance(
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

def create_tender_and_publish(
    db: Session,
    batch_data: TenderBatchCreate,
    current_user: dict
):
    try:

        # ========================================================
        # 0. VALIDATE BATCH
        # ========================================================

        if not batch_data.tenders:
            raise HTTPException(
                status_code=400,
                detail="At least one tender is required."
            )

        if len(batch_data.tenders) > 50:
            raise HTTPException(
                status_code=400,
                detail="A maximum of 50 tenders can be created in one batch."
            )

        # ========================================================
        # 1. VALIDATE USER / SHIPPER ACCOUNT ONCE
        # ========================================================

        assert "company_id" in current_user, \
            "Missing company_id in current_user"

        print(f"current_user: {current_user}")

        company_id = current_user.get("company_id")
        user_id = current_user.get("id")

        if not company_id:
            raise HTTPException(
                status_code=400,
                detail="User does not belong to a company"
            )

        shipper = db.query(Corporation).filter(
            Corporation.id == company_id
        ).first()

        if not shipper:
            raise HTTPException(
                status_code=400,
                detail="Shipper account not found or not active."
            )

        if not shipper.is_verified:
            raise HTTPException(
                status_code=403,
                detail="Shipper account is not verified. "
                       "Please await verification to create a shipment exchange."
            )

        if shipper.status != "Active":
            raise HTTPException(
                status_code=403,
                detail="Shipper account is not active. "
                       "Please await account activation to create a shipment exchange."
            )

        financial_account = db.query(FinancialAccounts).filter(
            FinancialAccounts.id == shipper.id
        ).first()

        if not financial_account:
            raise HTTPException(
                status_code=404,
                detail="Financial account not found."
            )

        if not financial_account.is_verified:
            raise HTTPException(
                status_code=403,
                detail="Financial account is not verified. "
                       "Please await verification to create and finance a shipment exchange."
            )

        if financial_account.status != "Active":
            raise HTTPException(
                status_code=403,
                detail="Financial account is not active. "
                       "Please await activation to create and finance a shipment exchange."
            )

        # ========================================================
        # 2. CREATE ALL TENDERS
        # ========================================================

        created_tenders = []

        master_tender = None

        for index, tender_data in enumerate(batch_data.tenders):

            # ----------------------------------------------------
            # FIRST ROUTE = MASTER TENDER
            # ----------------------------------------------------

            if index == 0:

                is_sub_tender = False
                parent_tender_id = None

            # ----------------------------------------------------
            # ALL OTHER ROUTES = SUB-TENDERS
            # ----------------------------------------------------

            else:

                is_sub_tender = True
                parent_tender_id = master_tender.id

            # ====================================================
            # 3. VALIDATE CONTRACT DATES
            # ====================================================

            if tender_data.contract_end_date < tender_data.contract_start_date:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Tender {index + 1}: "
                        "Contract end date cannot be before the contract start date."
                    )
                )

            # ====================================================
            # 4. NORMALIZE TENDER CLOSING DATE
            # ====================================================

            tender_closing_date = tender_data.tender_closing_date

            if tender_closing_date.tzinfo is None:
                tender_closing_date = tender_closing_date.replace(
                    tzinfo=timezone.utc
                )
            else:
                tender_closing_date = tender_closing_date.astimezone(
                    timezone.utc
                )

            # ====================================================
            # 5. VALIDATE TENDER CLOSING DATE
            # ====================================================

            contract_start_datetime = datetime.combine(
                tender_data.contract_start_date,
                time.min,
                tzinfo=timezone.utc
            )

            if tender_closing_date >= contract_start_datetime:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Tender {index + 1}: "
                        "Tender closing date must be before "
                        "the contract start date."
                    )
                )

            # ====================================================
            # 6. NORMALIZE QUESTIONS DEADLINE
            # ====================================================

            questions_deadline = tender_data.questions_deadline

            if questions_deadline is not None:

                if questions_deadline.tzinfo is None:
                    questions_deadline = questions_deadline.replace(
                        tzinfo=timezone.utc
                    )
                else:
                    questions_deadline = questions_deadline.astimezone(
                        timezone.utc
                    )

                if questions_deadline >= tender_closing_date:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Tender {index + 1}: "
                            "Questions deadline must be before "
                            "the tender closing date."
                        )
                    )

            # ====================================================
            # 7. VALIDATE VOLUME PROFILES
            # ====================================================

            for profile in tender_data.volume_profiles:

                if (
                    profile.period_start_date
                    and profile.period_end_date
                ):

                    if profile.period_end_date < profile.period_start_date:

                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Tender {index + 1}: "
                                f"Volume profile period "
                                f"{profile.period_sequence} "
                                "has an invalid date range."
                            )
                        )

            # ====================================================
            # 8. CALCULATE TOTAL EXPECTED LOADS
            # ====================================================

            total_expected_loads = sum(
                profile.expected_loads
                for profile in tender_data.volume_profiles
            )

            # ====================================================
            # 9. CALCULATE PROCUREMENT TARGET CONTRACT RATE
            # ====================================================

            procurement_target_contract_rate = (
                tender_data.procurement_target_rate
                * total_expected_loads
            )

            # ====================================================
            # 10. VALIDATE STOP SEQUENCES
            # ====================================================

            sorted_stops = sorted(
                tender_data.stops,
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
                        f"Tender {index + 1}: "
                        "Tender intermediate stop sequences "
                        "must be consecutive starting from 1."
                    )
                )

            # ====================================================
            # 11. BUILD GOOGLE MAPS WAYPOINTS
            # ====================================================

            waypoints = [
                stop.address.strip()
                for stop in sorted_stops
                if stop.address and stop.address.strip()
            ]

            # ====================================================
            # 12. CALCULATE COMPLETE ROUTE
            # ====================================================

            try:

                distance_data = calculate_distance(
                    AddressInput(
                        origin_address=tender_data.origin.address,
                        destination_address=tender_data.destination.address,
                        waypoints=waypoints
                    )
                )

            except HTTPException as e:

                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"Tender {index + 1}: "
                        f"Google Maps routing calculation failed: "
                        f"{e.detail}"
                    )
                )

            if not isinstance(distance_data, dict):

                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"Tender {index + 1}: "
                        "Google Maps routing calculation "
                        "returned an invalid response."
                    )
                )

            distance_km = distance_data.get("distance")

            estimated_transit_time = distance_data.get(
                "duration"
            )

            route_preview_embed = distance_data.get(
                "google_maps_embed_url"
            )

            if distance_km is None:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Tender {index + 1}: "
                        "Google Maps did not return a valid route distance."
                    )
                )

            # ====================================================
            # 13. EXTRACT ORIGIN GEO INFORMATION
            # ====================================================

            complete_origin_address = distance_data.get(
                "complete_origin_address",
                tender_data.origin.address
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

            # ====================================================
            # 14. EXTRACT DESTINATION GEO INFORMATION
            # ====================================================

            complete_destination_address = distance_data.get(
                "complete_destination_address",
                tender_data.destination.address
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

            # ====================================================
            # 15. EXTRACT INTERMEDIATE STOP GEO INFORMATION
            # ====================================================

            calculated_stops = []

            for stop_index, stop_data in enumerate(
                sorted_stops,
                start=1
            ):

                calculated_stops.append({
                    "complete_address": distance_data.get(
                        f"complete_stop_{stop_index}_address",
                        stop_data.address
                    ),
                    "city_province": distance_data.get(
                        f"stop_{stop_index}_city_province"
                    ),
                    "country": distance_data.get(
                        f"stop_{stop_index}_country"
                    ),
                    "region": distance_data.get(
                        f"stop_{stop_index}_region"
                    ),
                })

            # ====================================================
            # 16. CREATE TENDER
            # ====================================================

            tender = Lane_Tender_RFQ(

                client_id=shipper.id,
                publisher_user_id=user_id,

                # HIERARCHY
                is_sub_tender=is_sub_tender,
                parent_tender_id=parent_tender_id,

                # BASIC
                tender_title=tender_data.tender_title,
                scope_description=tender_data.scope_description,
                business_unit=tender_data.business_unit,
                cost_centre_project_code=(
                    tender_data.cost_centre_project_code
                ),
                tender_length_category=(
                    tender_data.tender_length_category
                ),
                tender_category=tender_data.tender_category,

                # CONTRACT
                contract_start_date=(
                    tender_data.contract_start_date
                ),
                contract_end_date=(
                    tender_data.contract_end_date
                ),

                # ROUTING
                border_customs_responsibility=(
                    tender_data.border_customs_responsibility
                ),

                estimated_distance_km=(
                    tender_data.estimated_distance_km
                    or distance_km
                ),

                actual_distance_km=distance_km,

                polyline=distance_data.get("polyline"),

                priority_level=tender_data.priority_level,
                load_type=tender_data.load_type,

                # IMPORTANT
                trip_type=tender_data.trip_type,

                customer_reference=(
                    tender_data.customer_reference
                ),

                # CARGO
                commodity=tender_data.commodity,
                average_shipment_weight_kg=(
                    tender_data.average_shipment_weight_kg
                ),
                minimum_weight_bracket_kg=(
                    tender_data.minimum_weight_bracket_kg
                ),
                packaging_type=tender_data.packaging_type,
                packaging_quantity=tender_data.packaging_quantity,
                temperature_control=tender_data.temperature_control,
                target_temperature_spec=(
                    tender_data.target_temperature_spec
                ),
                hazardous_materials=(
                    tender_data.hazardous_materials
                ),
                hazchem_classification=(
                    tender_data.hazchem_classification
                ),
                under_bond=tender_data.under_bond,
                rib_requirements=tender_data.rib_requirements,

                minimum_git_cover_amount=(
                    tender_data.minimum_git_cover_amount
                ),

                minimum_liability_cover_amount=(
                    tender_data.minimum_liability_cover_amount
                ),

                # VOLUME
                volume_entry_method=(
                    tender_data.volume_entry_method
                ),
                volume_commitment=(
                    tender_data.volume_commitment
                ),

                # PRICING
                pricing_basis=tender_data.pricing_basis,

                incumbent_transport_rate_per_shipment=(
                    tender_data.incumbent_transport_rate_per_shipment
                ),

                incumbent_contract_rate=(
                    tender_data.incumbent_contract_rate
                ),

                procurement_target_rate=(
                    tender_data.procurement_target_rate
                ),

                procurement_target_contract_rate=(
                    procurement_target_contract_rate
                ),

                rate_direction=tender_data.rate_direction,

                # RATE INCLUSIONS
                rate_includes_fuel=(
                    tender_data.rate_includes_fuel
                ),
                rate_includes_driver=(
                    tender_data.rate_includes_driver
                ),
                rate_includes_maintenance=(
                    tender_data.rate_includes_maintenance
                ),
                rate_includes_insurance=(
                    tender_data.rate_includes_insurance
                ),
                rate_includes_tolls=(
                    tender_data.rate_includes_tolls
                ),
                rate_includes_border_charges=(
                    tender_data.rate_includes_border_charges
                ),
                rate_includes_empty_return=(
                    tender_data.rate_includes_empty_return
                ),
                rate_includes_waiting_time=(
                    tender_data.rate_includes_waiting_time
                ),
                rate_includes_loading_assistance=(
                    tender_data.rate_includes_loading_assistance
                ),
                rate_includes_offloading_assistance=(
                    tender_data.rate_includes_offloading_assistance
                ),

                # FUEL
                fuel_treatment_type=(
                    tender_data.fuel_treatment_type
                ),
                base_diesel_price=(
                    tender_data.base_diesel_price
                ),
                fuel_review_period=(
                    tender_data.fuel_review_period
                ),
                fuel_component_percentage=(
                    tender_data.fuel_component_percentage
                ),

                vat_included=tender_data.vat_included,
                rate_validity=tender_data.rate_validity,

                # PAYMENT
                payment_terms=financial_account.payment_terms,
                custom_payment_terms=None,
                invoice_submission_frequency=None,
                invoice_submission_deadline=None,

                # TENDER PROCESS
                tender_closing_date=tender_closing_date,
                questions_deadline=questions_deadline,

                # OPERATIONS
                vehicle_tracking_required=(
                    tender_data.vehicle_tracking_required
                ),
                all_time_hour_control_room=(
                    tender_data.all_time_hour_control_room
                ),
                driver_mobile_phone=(
                    tender_data.driver_mobile_phone
                ),
                clean_compliant_equipment=(
                    tender_data.clean_compliant_equipment
                ),
                pallet_management=(
                    tender_data.pallet_management
                ),

                pod_submission_local=(
                    tender_data.pod_submission_local
                ),
                pod_submission_long_haul=(
                    tender_data.pod_submission_long_haul
                ),
                pod_submission_cross_border=(
                    tender_data.pod_submission_cross_border
                ),

                subcontracting_policy=(
                    tender_data.subcontracting_policy
                ),

                # DOCUMENTATION / RISK
                delivery_documentation_sla=(
                    tender_data.delivery_documentation_sla
                ),
                claims_risk_policy=(
                    tender_data.claims_risk_policy
                ),
                claims_risk_requirements=(
                    tender_data.claims_risk_requirements
                ),

                # INSURANCE
                git_all_risk_required=(
                    tender_data.git_all_risk_required
                ),
                git_first_loss_required=(
                    tender_data.git_first_loss_required
                ),
                git_driver_fidelity_required=(
                    tender_data.git_driver_fidelity_required
                ),

                # EQUIPMENT
                tarpaulin_compliance_required=(
                    tender_data.tarpaulin_compliance_required
                ),
                corner_plates_required=(
                    tender_data.corner_plates_required
                ),
                chock_blocks_required=(
                    tender_data.chock_blocks_required
                ),
                ratchets_belts_required=(
                    tender_data.ratchets_belts_required
                ),
                other_equipment_requirements=(
                    tender_data.other_equipment_requirements
                ),

                # BID EVALUATION
                evaluation_price_enabled=(
                    tender_data.evaluation_price_enabled
                ),
                evaluation_capacity_enabled=(
                    tender_data.evaluation_capacity_enabled
                ),
                evaluation_service_enabled=(
                    tender_data.evaluation_service_enabled
                ),
                evaluation_compliance_enabled=(
                    tender_data.evaluation_compliance_enabled
                ),
                evaluation_flexibility_enabled=(
                    tender_data.evaluation_flexibility_enabled
                ),

                status="Draft"
            )

            db.add(tender)
            db.flush()

            # First tender becomes master
            if index == 0:
                master_tender = tender

            # ====================================================
            # 17. CREATE ORIGIN STOP
            # ====================================================

            origin_stop = Lane_Tender_RFQ_Stop(
                tender_id=tender.id,
                stop_sequence=0,
                stop_type="Origin",
                facility_name=tender_data.origin.facility_name,
                address=tender_data.origin.address,
                complete_address=complete_origin_address,
                city_province=origin_city_province,
                country=origin_country,
                region=origin_region
            )

            db.add(origin_stop)


            # ====================================================
            # 18. CREATE INTERMEDIATE STOPS
            # ====================================================

            created_intermediate_stops = []

            for stop_data, geo_data in zip(
                sorted_stops,
                calculated_stops
            ):

                intermediate_stop = Lane_Tender_RFQ_Stop(
                    tender_id=tender.id,
                    stop_sequence=stop_data.stop_sequence,
                    stop_type="Intermediate",
                    facility_name=stop_data.facility_name,
                    address=stop_data.address,
                    complete_address=geo_data["complete_address"],
                    city_province=geo_data["city_province"],
                    country=geo_data["country"],
                    region=geo_data["region"]
                )

                db.add(intermediate_stop)

                created_intermediate_stops.append(
                    (stop_data, intermediate_stop)
                )


            # ====================================================
            # 19. CREATE DESTINATION STOP
            # ====================================================

            destination_stop = Lane_Tender_RFQ_Stop(
                tender_id=tender.id,
                stop_sequence=len(sorted_stops) + 1,
                stop_type="Destination",
                facility_name=tender_data.destination.facility_name,
                address=tender_data.destination.address,
                complete_address=complete_destination_address,
                city_province=destination_city_province,
                country=destination_country,
                region=destination_region
            )

            db.add(destination_stop)


            # ====================================================
            # 20. FLUSH STOPS
            # ====================================================

            db.flush()

            # ====================================================
            # 21. CREATE TURNAROUND / DEMURRAGE PROTOCOLS
            # ====================================================

            # ----------------------------------------------------
            # ORIGIN
            # ----------------------------------------------------

            if (
                tender_data.origin.turnaround_window_demurrage_protocol
                is not None
            ):

                demurrage_data = (
                    tender_data
                    .origin
                    .turnaround_window_demurrage_protocol
                )

                turnaround_protocol = Turnaround_Window_Demurrage_Protocals(
                    tender_id=tender.id,
                    stop_id=origin_stop.id,
                    demurrage_conditions=(
                        demurrage_data.demurrage_conditions
                    ),
                    loading_offloading_turnaround_hours=(
                        demurrage_data.loading_offloading_turnaround_hours
                    ),
                    free_demurrage_hours=(
                        demurrage_data.free_demurrage_hours
                    ),
                    demurrage_rate_per_hour=(
                        demurrage_data.demurrage_rate_per_hour
                    ),
                    maximum_demurrage_incursion_hours=(
                        demurrage_data.maximum_demurrage_incursion_hours
                    )
                )

                db.add(turnaround_protocol)


            # ----------------------------------------------------
            # INTERMEDIATE STOPS
            # ----------------------------------------------------

            for stop_data, created_stop in created_intermediate_stops:

                if (
                    stop_data.turnaround_window_demurrage_protocol
                    is None
                ):
                    continue

                demurrage_data = (
                    stop_data
                    .turnaround_window_demurrage_protocol
                )

                turnaround_protocol = Turnaround_Window_Demurrage_Protocals(
                    tender_id=tender.id,
                    stop_id=created_stop.id,
                    demurrage_conditions=(
                        demurrage_data.demurrage_conditions
                    ),
                    loading_offloading_turnaround_hours=(
                        demurrage_data.loading_offloading_turnaround_hours
                    ),
                    free_demurrage_hours=(
                        demurrage_data.free_demurrage_hours
                    ),
                    demurrage_rate_per_hour=(
                        demurrage_data.demurrage_rate_per_hour
                    ),
                    maximum_demurrage_incursion_hours=(
                        demurrage_data.maximum_demurrage_incursion_hours
                    )
                )

                db.add(turnaround_protocol)


            # ----------------------------------------------------
            # DESTINATION
            # ----------------------------------------------------

            if (
                tender_data.destination.turnaround_window_demurrage_protocol
                is not None
            ):

                demurrage_data = (
                    tender_data
                    .destination
                    .turnaround_window_demurrage_protocol
                )

                turnaround_protocol = Turnaround_Window_Demurrage_Protocals(
                    tender_id=tender.id,
                    stop_id=destination_stop.id,
                    demurrage_conditions=(
                        demurrage_data.demurrage_conditions
                    ),
                    loading_offloading_turnaround_hours=(
                        demurrage_data.loading_offloading_turnaround_hours
                    ),
                    free_demurrage_hours=(
                        demurrage_data.free_demurrage_hours
                    ),
                    demurrage_rate_per_hour=(
                        demurrage_data.demurrage_rate_per_hour
                    ),
                    maximum_demurrage_incursion_hours=(
                        demurrage_data.maximum_demurrage_incursion_hours
                    )
                )

                db.add(turnaround_protocol)

                # ====================================================
                # 22. CREATE CARRIER CERTIFICATIONS / DRIVER STANDARDS
                # ====================================================

                for certification_data in (
                    tender_data.carrier_certification_driver_standards
                ):

                    certification = Carrier_Certification_Driver_Standards(
                        tender_id=tender.id,
                        certification_name=(
                            certification_data.certification_name
                        ),
                        driver_qualification_security_directives=(
                            certification_data
                            .driver_qualification_security_directives
                        ),
                        is_required=True
                    )

                    db.add(certification)

                # ====================================================
                # 23. CREATE ESCORT POLICY
                # ====================================================

                if tender_data.escort_policy is not None:

                    escort_policy = Escort_Policy(
                        tender_id=tender.id,
                        armed_escort_required=(
                            tender_data
                            .escort_policy
                            .armed_escort_required
                        ),
                        escort_expense_responsible_party=(
                            tender_data
                            .escort_policy
                            .escort_expense_responsible_party
                        )
                    )

                    db.add(escort_policy)

            # ====================================================
            # 24. CREATE SLA / INCIDENT REPORTING POLICY
            # ====================================================

            if tender_data.sla_reporting is not None:

                sla_reporting = Sla_incident_Reporting(
                    tender_id=tender.id,
                    incident_reporting_sla=(
                        tender_data
                        .sla_reporting
                        .incident_reporting_sla
                    ),
                    service_level_agreement=(
                        tender_data
                        .sla_reporting
                        .service_level_agreement
                    )
                )

                db.add(sla_reporting)

            # ====================================================
            # 25. CREATE VEHICLE CONFIGURATIONS
            # ====================================================

            for vehicle_data in tender_data.vehicle_configurations:

                vehicle_config = Lane_Tender_RFQ_Vehicle_Config(
                    tender_id=tender.id,
                    configuration_type=(
                        vehicle_data.configuration_type
                    ),
                    truck_type=vehicle_data.truck_type,
                    equipment_type=vehicle_data.equipment_type,
                    trailer_type=vehicle_data.trailer_type,
                    trailer_length=vehicle_data.trailer_length,
                    is_active=True
                )

                db.add(vehicle_config)

            # ====================================================
            # 26. CREATE VOLUME PROFILES
            # ====================================================

            for volume_data in tender_data.volume_profiles:

                volume_profile = Lane_Tender_RFQ_Volume_Profile(
                    tender_id=tender.id,
                    volume_entry_method=(
                        volume_data.volume_entry_method
                    ),
                    period_sequence=(
                        volume_data.period_sequence
                    ),
                    period_label=volume_data.period_label,
                    period_start_date=(
                        volume_data.period_start_date
                    ),
                    period_end_date=(
                        volume_data.period_end_date
                    ),
                    day_of_week=volume_data.day_of_week,
                    expected_loads=volume_data.expected_loads
                )

                db.add(volume_profile)

            # ====================================================
            # 27. CREATE ACCESSORIALS
            # ====================================================

            for accessorial_data in tender_data.accessorials:

                accessorial = Lane_Tender_RFQ_Accessorial(
                    tender_id=tender.id,
                    charge_type=(
                        accessorial_data.charge_type
                    ),
                    treatment=(
                        accessorial_data.treatment
                    ),
                    threshold_value=(
                        accessorial_data.threshold_value
                    ),
                    threshold_unit=(
                        accessorial_data.threshold_unit
                    ),
                    notes=accessorial_data.notes
                )

                db.add(accessorial)

            db.flush()

            # ====================================================
            # 28. CREATE LOADBOARD
            # ====================================================

            loadboard = Lane_Tender_Loadboard(
                tender_id=tender.id,
                status="open",
                published_at=datetime.utcnow(),
                bid_opening_date=datetime.utcnow(),
                bid_closing_date=tender.tender_closing_date,
                questions_deadline=tender.questions_deadline,

                tender_title=tender.tender_title,
                tender_category=tender.tender_category,
                tender_length_category=(
                    tender.tender_length_category
                ),
                scope_description=tender.scope_description,

                contract_start_date=(
                    tender.contract_start_date
                ),
                contract_end_date=(
                    tender.contract_end_date
                ),

                estimated_distance_km=(
                    tender.estimated_distance_km
                ),
                actual_distance_km=(
                    tender.actual_distance_km
                ),

                polyline=tender.polyline,

                border_customs_responsibility=(
                    tender.border_customs_responsibility
                ),

                commodity=tender.commodity,
                load_type=tender.load_type,

                average_shipment_weight_kg=(
                    tender.average_shipment_weight_kg
                ),

                minimum_weight_bracket_kg=(
                    tender.minimum_weight_bracket_kg
                ),

                packaging_type=tender.packaging_type,
                packaging_quantity=tender.packaging_quantity,

                temperature_control=(
                    tender.temperature_control
                ),

                target_temperature_spec=(
                    tender.target_temperature_spec
                ),

                hazardous_materials=(
                    tender.hazardous_materials
                ),

                hazchem_classification=(
                    tender.hazchem_classification
                ),

                under_bond=tender.under_bond,

                volume_entry_method=(
                    tender.volume_entry_method
                ),

                volume_commitment=(
                    tender.volume_commitment
                ),

                pricing_basis=tender.pricing_basis,
                rate_direction=tender.rate_direction,

                rate_includes_fuel=(
                    tender.rate_includes_fuel
                ),
                rate_includes_driver=(
                    tender.rate_includes_driver
                ),
                rate_includes_maintenance=(
                    tender.rate_includes_maintenance
                ),
                rate_includes_insurance=(
                    tender.rate_includes_insurance
                ),
                rate_includes_tolls=(
                    tender.rate_includes_tolls
                ),
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

                fuel_treatment_type=(
                    tender.fuel_treatment_type
                ),
                base_diesel_price=(
                    tender.base_diesel_price
                ),
                fuel_review_period=(
                    tender.fuel_review_period
                ),
                fuel_component_percentage=(
                    tender.fuel_component_percentage
                ),

                vat_included=tender.vat_included,
                rate_validity=tender.rate_validity,

                payment_terms=financial_account.payment_terms,

                custom_payment_terms=(
                    tender.custom_payment_terms
                ),

                invoice_submission_frequency=(
                    tender.invoice_submission_frequency
                ),

                invoice_submission_deadline=(
                    tender.invoice_submission_deadline
                ),

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
                pallet_management=(
                    tender.pallet_management
                ),

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

                delivery_documentation_sla=(
                    tender.delivery_documentation_sla
                ),
                claims_risk_policy=(
                    tender.claims_risk_policy
                ),
                claims_risk_requirements=(
                    tender.claims_risk_requirements
                ),

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
                ),

                evaluation_price_enabled=(
                    tender.evaluation_price_enabled
                ),
                evaluation_capacity_enabled=(
                    tender.evaluation_capacity_enabled
                ),
                evaluation_service_enabled=(
                    tender.evaluation_service_enabled
                ),
                evaluation_compliance_enabled=(
                    tender.evaluation_compliance_enabled
                ),
                evaluation_flexibility_enabled=(
                    tender.evaluation_flexibility_enabled
                ),

                is_featured=False,
                is_visible_to_carriers=True
            )

            db.add(loadboard)

            # ====================================================
            # 29. ACTIVATE TENDER
            # ====================================================

            tender.status = "Active"

            db.flush()

            # ====================================================
            # 30. STORE RESULT
            # ====================================================

            created_tenders.append({
                "tender": tender,
                "loadboard": loadboard
            })

        # ========================================================
        # 31. ONE COMMIT FOR ENTIRE BATCH
        # ========================================================

        db.commit()

        # ========================================================
        # 32. REFRESH RESULTS
        # ========================================================

        for item in created_tenders:
            db.refresh(item["tender"])
            db.refresh(item["loadboard"])

        # ========================================================
        # 33. RESPONSE
        # ========================================================

        return {
            "success": True,
            "message": (
                "Tender created successfully."
                if len(created_tenders) == 1
                else "Tender batch created successfully."
            ),
            "master_tender_id": master_tender.id,
            "tender_count": len(created_tenders),
            "tenders": [
                {
                    "tender_id": item["tender"].id,
                    "loadboard_id": item["loadboard"].id,
                    "is_sub_tender": item["tender"].is_sub_tender,
                    "parent_tender_id": item["tender"].parent_tender_id,
                    "status": item["tender"].status
                }
                for item in created_tenders
            ]
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to create tender batch: {str(e)}"
        )

