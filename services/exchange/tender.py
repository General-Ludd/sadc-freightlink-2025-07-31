from datetime import date, datetime, time
from fastapi import HTTPException
from sqlalchemy.orm import Session
from models.Exchange.dedicated_ftl_lane import (
    Lane_Tender_RFQ,
    Lane_Tender_Stop,
    Lane_Tender_Vehicle_Config,
    Lane_Tender_Volume_Profile,
    Lane_Tender_Accessorial,
)
from models.brokerage.loadboard import Lane_Tender_Loadboard

from schemas.exchange_bookings.dedicated_ftl_lane import TenderCreate

def create_tender_and_publish(
    db: Session,
    tender_data: TenderCreate,
    current_user: dict
):
    try:

        # ========================================================
        # 1. VALIDATE CONTRACT DATES
        # ========================================================

        if tender_data.contract_end_date < tender_data.contract_start_date:
            raise HTTPException(
                status_code=400,
                detail="Contract end date cannot be before contract start date."
            )


        # ========================================================
        # 2. VALIDATE TENDER CLOSING DATE
        # ========================================================

        contract_start_datetime = datetime.combine(
            tender_data.contract_start_date,
            time.min
        )

        if tender_data.tender_closing_date <= contract_start_datetime:
            raise HTTPException(
                status_code=400,
                detail="Tender closing date must be before the contract start date."
            )
        # ========================================================
        # 3. VALIDATE QUESTIONS DEADLINE
        # ========================================================

        if tender_data.questions_deadline:

            if tender_data.questions_deadline >= tender_data.tender_closing_date:
                raise HTTPException(
                    status_code=400,
                    detail="Questions deadline must be before the tender closing date."
                )

        # ========================================================
        # 4. VALIDATE VOLUME PROFILES
        # ========================================================

        for profile in tender_data.volume_profiles:

            if profile.period_start_date and profile.period_end_date:

                if profile.period_end_date < profile.period_start_date:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Volume profile period {profile.period_sequence} "
                            "has an invalid date range."
                        )
                    )

        # ========================================================
        # 5. VALIDATE STOP SEQUENCES
        # ========================================================

        stop_sequences = [
            stop.stop_sequence
            for stop in tender_data.stops
        ]

        if len(stop_sequences) != len(set(stop_sequences)):
            raise HTTPException(
                status_code=400,
                detail="Tender stop sequences must be unique."
            )

        # ========================================================
        # 6. CALCULATE / VERIFY DISTANCE
        # ========================================================

        calculated_distance_km = calculate_tender_distance(
            origin_address=tender_data.origin_address,
            destination_address=tender_data.destination_address,
        )

        if not calculated_distance_km or calculated_distance_km <= 0:
            raise HTTPException(
                status_code=400,
                detail="Unable to calculate a valid route distance."
            )

        # ========================================================
        # 7. GET CLIENT PAYMENT TERMS
        # ========================================================

        payment_terms = get_client_payment_terms(
            db=db,
            client_id=tender_data.client_id,
        )

        # ========================================================
        # 8. CREATE MASTER TENDER
        # ========================================================

        tender = Lane_Tender_RFQ(
            client_id=tender_data.client_id,

            is_sub_tender=False,
            parent_tender_id=None,

            # ----------------------------------------------------
            # SECTION 1
            # ----------------------------------------------------

            tender_title=tender_data.tender_title,
            scope_description=tender_data.scope_description,
            business_unit=tender_data.business_unit,
            cost_centre_project_code=tender_data.cost_centre_project_code,
            tender_length_category=tender_data.tender_length_category,
            tender_category=tender_data.tender_category,

            contract_start_date=tender_data.contract_start_date,
            contract_end_date=tender_data.contract_end_date,

            origin_address=tender_data.origin_address,
            destination_address=tender_data.destination_address,

            border_customs_responsibility=(
                tender_data.border_customs_responsibility
            ),

            estimated_distance_km=tender_data.estimated_distance_km if tender_data.estimated_distance_km else calculated_distance_km,
            actual_distance_km=calculated_distance_km,

            priority_level=tender_data.priority_level,
            load_type=tender_data.load_type,

            customer_reference=tender_data.customer_reference,

            # ----------------------------------------------------
            # SECTION 2
            # ----------------------------------------------------

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
            target_temperature_spec=tender_data.target_temperature_spec,

            hazardous_materials=tender_data.hazardous_materials,
            hazchem_classification=tender_data.hazchem_classification,

            under_bond=tender_data.under_bond,
            rib_requirements=tender_data.rib_requirements,

            minimum_git_cover_amount=(
                tender_data.minimum_git_cover_amount
            ),

            minimum_liability_cover_amount=(
                tender_data.minimum_liability_cover_amount
            ),

            # ----------------------------------------------------
            # SECTION 3
            # ----------------------------------------------------

            volume_entry_method=tender_data.volume_entry_method,
            volume_commitment=tender_data.volume_commitment,

            # ----------------------------------------------------
            # SECTION 4
            # ----------------------------------------------------

            pricing_basis=tender_data.pricing_basis,
            incumbent_transport_rate_per_shipment=tender_data.incumbent_transport_rate_per_shipment,
            procurement_target_rate=(
                tender_data.procurement_target_rate
            ),
            rate_direction=tender_data.rate_direction,

            # ----------------------------------------------------
            # RATE INCLUDES
            # ----------------------------------------------------

            rate_includes_fuel=tender_data.rate_includes_fuel,
            rate_includes_driver=tender_data.rate_includes_driver,
            rate_includes_maintenance=(
                tender_data.rate_includes_maintenance
            ),
            rate_includes_insurance=(
                tender_data.rate_includes_insurance
            ),
            rate_includes_tolls=tender_data.rate_includes_tolls,
            rate_includes_border_charges=tender_data.rate_includes_border_charges,
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

            # ----------------------------------------------------
            # FUEL
            # ----------------------------------------------------

            fuel_treatment_type=tender_data.fuel_treatment_type,
            base_diesel_price=tender_data.base_diesel_price,
            fuel_review_period=tender_data.fuel_review_period,
            fuel_component_percentage=(
                tender_data.fuel_component_percentage
            ),

            # ----------------------------------------------------
            # VAT / RATE VALIDITY
            # ----------------------------------------------------

            vat_treatment=tender_data.vat_treatment,
            rate_validity=tender_data.rate_validity,

            # ----------------------------------------------------
            # PAYMENT TERMS
            # ----------------------------------------------------

            payment_terms=payment_terms,
            custom_payment_terms=None,

            # ----------------------------------------------------
            # INVOICING
            # ----------------------------------------------------

            invoice_submission_frequency=None,
            invoice_submission_deadline=None,

            # ----------------------------------------------------
            # TENDER PROCESS
            # ----------------------------------------------------

            tender_closing_date=tender_data.tender_closing_date,
            questions_deadline=tender_data.questions_deadline,

            # ----------------------------------------------------
            # OPERATIONAL
            # ----------------------------------------------------

            vehicle_tracking_required=(
                tender_data.vehicle_tracking_required
            ),

            all_time_hour_control_room=(
                tender_data.all_time_hour_control_room
            ),

            driver_mobile_phone=tender_data.driver_mobile_phone,

            clean_compliant_equipment=(
                tender_data.clean_compliant_equipment
            ),

            pallet_management=tender_data.pallet_management,

            pod_submission_local=tender_data.pod_submission_local,
            pod_submission_long_haul=(
                tender_data.pod_submission_long_haul
            ),
            pod_submission_cross_border=(
                tender_data.pod_submission_cross_border
            ),

            subcontracting_policy=(
                tender_data.subcontracting_policy
            ),

            # ----------------------------------------------------
            # DOCUMENTATION / RISK
            # ----------------------------------------------------

            delivery_documentation_sla=(
                tender_data.delivery_documentation_sla
            ),

            claims_risk_policy=tender_data.claims_risk_policy,

            claims_risk_requirements=(
                tender_data.claims_risk_requirements
            ),

            # ----------------------------------------------------
            # INSURANCE
            # ----------------------------------------------------

            git_all_risk_required=(
                tender_data.git_all_risk_required
            ),

            git_first_loss_required=(
                tender_data.git_first_loss_required
            ),

            git_driver_fidelity_required=(
                tender_data.git_driver_fidelity_required
            ),

            # ----------------------------------------------------
            # EQUIPMENT COMPLIANCE
            # ----------------------------------------------------

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

            # ----------------------------------------------------
            # EVALUATION
            # ----------------------------------------------------

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

            # ----------------------------------------------------
            # STATUS
            # ----------------------------------------------------

            status="draft",
        )

        db.add(tender)

        db.flush()

        # ========================================================
        # 9. CREATE STOPS
        # ========================================================

        for stop_data in tender_data.stops:

            stop = Lane_Tender_Stop(
                tender_id=tender.id,
                stop_sequence=stop_data.stop_sequence,
                address=stop_data.address,
            )

            db.add(stop)

        # ========================================================
        # 10. CREATE VEHICLE CONFIGURATIONS
        # ========================================================

        for vehicle_data in tender_data.vehicle_configurations:

            vehicle_config = Lane_Tender_Vehicle_Config(
                tender_id=tender.id,
                configuration_type=(
                    vehicle_data.configuration_type
                ),
                truck_type=vehicle_data.truck_type,
                equipment_type=vehicle_data.equipment_type,
                trailer_type=vehicle_data.trailer_type,
                trailer_length=vehicle_data.trailer_length,
                is_active=True,
            )

            db.add(vehicle_config)

        # ========================================================
        # 11. CREATE VOLUME PROFILES
        # ========================================================

        for volume_data in tender_data.volume_profiles:

            volume_profile = Lane_Tender_Volume_Profile(
                tender_id=tender.id,
                volume_entry_method=(
                    volume_data.volume_entry_method
                ),
                period_sequence=volume_data.period_sequence,
                period_label=volume_data.period_label,
                period_start_date=volume_data.period_start_date,
                period_end_date=volume_data.period_end_date,
                day_of_week=volume_data.day_of_week,
                expected_loads=volume_data.expected_loads,
            )

            db.add(volume_profile)

        # ========================================================
        # 12. CREATE ACCESSORIALS
        # ========================================================

        for accessorial_data in tender_data.accessorials:

            accessorial = Lane_Tender_Accessorial(
                tender_id=tender.id,
                charge_type=accessorial_data.charge_type,
                treatment=accessorial_data.treatment,
                threshold_value=accessorial_data.threshold_value,
                threshold_unit=accessorial_data.threshold_unit,
                notes=accessorial_data.notes,
            )

            db.add(accessorial)

        # ========================================================
        # 13. FLUSH CHILD RECORDS
        # ========================================================

        db.flush()

        # ========================================================
        # 14. CREATE LOADBOARD
        # ========================================================

        loadboard = Lane_Tender_Loadboard(
            tender_id=tender.id,

            status="open",

            published_at=datetime.utcnow(),
            bid_opening_date=datetime.utcnow(),

            bid_closing_date=tender.tender_closing_date,
            questions_deadline=tender.questions_deadline,

            # ----------------------------------------------------
            # TENDER IDENTITY
            # ----------------------------------------------------

            tender_title=tender.tender_title,
            tender_category=tender.tender_category,
            tender_length_category=tender.tender_length_category,
            scope_description=tender.scope_description,

            # ----------------------------------------------------
            # CONTRACT
            # ----------------------------------------------------

            contract_start_date=tender.contract_start_date,
            contract_end_date=tender.contract_end_date,

            # ----------------------------------------------------
            # ROUTING
            # ----------------------------------------------------

            origin_address=tender.origin_address,
            origin_city_province=tender.origin_city_province,
            origin_country=tender.origin_country,
            origin_region=tender.origin_region,

            destination_address=tender.destination_address,
            destination_city_province=tender.destination_city_province,
            destination_country=tender.destination_country,
            destination_region=tender.destination_region,

            estimated_distance_km=tender.estimated_distance_km,
            actual_distance_km=tender.actual_distance_km,

            border_customs_responsibility=(
                tender.border_customs_responsibility
            ),

            # ----------------------------------------------------
            # CARGO
            # ----------------------------------------------------

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

            temperature_control=tender.temperature_control,
            target_temperature_spec=tender.target_temperature_spec,

            hazardous_materials=tender.hazardous_materials,
            hazchem_classification=tender.hazchem_classification,

            under_bond=tender.under_bond,

            # ----------------------------------------------------
            # VOLUME
            # ----------------------------------------------------

            volume_entry_method=tender.volume_entry_method,
            volume_commitment=tender.volume_commitment,

            # ----------------------------------------------------
            # PRICING
            # ----------------------------------------------------

            pricing_basis=tender.pricing_basis,
            rate_direction=tender.rate_direction,

            # ----------------------------------------------------
            # RATE INCLUSIONS
            # ----------------------------------------------------

            rate_includes_fuel=tender.rate_includes_fuel,
            rate_includes_driver=tender.rate_includes_driver,
            rate_includes_maintenance=(
                tender.rate_includes_maintenance
            ),
            rate_includes_insurance=(
                tender.rate_includes_insurance
            ),
            rate_includes_tolls=tender.rate_includes_tolls,
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

            # ----------------------------------------------------
            # FUEL
            # ----------------------------------------------------

            fuel_treatment_type=tender.fuel_treatment_type,
            base_diesel_price=tender.base_diesel_price,
            fuel_review_period=tender.fuel_review_period,
            fuel_component_percentage=(
                tender.fuel_component_percentage
            ),

            # ----------------------------------------------------
            # COMMERCIAL
            # ----------------------------------------------------

            vat_treatment=tender.vat_treatment,
            rate_validity=tender.rate_validity,

            payment_terms=tender.payment_terms,
            custom_payment_terms=tender.custom_payment_terms,

            invoice_submission_frequency=(
                tender.invoice_submission_frequency
            ),

            invoice_submission_deadline=(
                tender.invoice_submission_deadline
            ),

            # ----------------------------------------------------
            # OPERATIONS
            # ----------------------------------------------------

            vehicle_tracking_required=(
                tender.vehicle_tracking_required
            ),

            all_time_hour_control_room=(
                tender.all_time_hour_control_room
            ),

            driver_mobile_phone=tender.driver_mobile_phone,

            clean_compliant_equipment=(
                tender.clean_compliant_equipment
            ),

            pallet_management=tender.pallet_management,

            pod_submission_local=tender.pod_submission_local,
            pod_submission_long_haul=(
                tender.pod_submission_long_haul
            ),
            pod_submission_cross_border=(
                tender.pod_submission_cross_border
            ),

            subcontracting_policy=(
                tender.subcontracting_policy
            ),

            # ----------------------------------------------------
            # DOCUMENTATION
            # ----------------------------------------------------

            delivery_documentation_sla=(
                tender.delivery_documentation_sla
            ),

            claims_risk_policy=tender.claims_risk_policy,

            claims_risk_requirements=(
                tender.claims_risk_requirements
            ),

            # ----------------------------------------------------
            # INSURANCE
            # ----------------------------------------------------

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

            # ----------------------------------------------------
            # EQUIPMENT
            # ----------------------------------------------------

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

            # ----------------------------------------------------
            # EVALUATION
            # ----------------------------------------------------

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

            # ----------------------------------------------------
            # DISPLAY
            # ----------------------------------------------------

            is_featured=False,
            is_visible_to_carriers=True,
        )

        db.add(loadboard)

        # ========================================================
        # 15. PUBLISH MASTER TENDER
        # ========================================================

        tender.status = "published"

        # ========================================================
        # 16. FINAL FLUSH
        # ========================================================

        db.flush()

        # ========================================================
        # 17. COMMIT ENTIRE TRANSACTION
        # ========================================================

        db.commit()

        # ========================================================
        # 18. REFRESH
        # ========================================================

        db.refresh(tender)
        db.refresh(loadboard)

        # ========================================================
        # 19. RETURN
        # ========================================================

        return tender

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to create and publish tender: {str(e)}"
        )