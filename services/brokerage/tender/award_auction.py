from fastapi import HTTPException
from sqlalchemy.orm import Session

def award_shipment_bid(
    db: Session,
    auction_id: int,
    bid_id: int,
    current_user: dict
):
    # ============================================================
    # 1. LOCK AND LOAD AUCTION
    # ============================================================

    auction = (
        db.query(Client_Shipment_Auction)
        .filter(
            Client_Shipment_Auction.id == auction_id
        )
        .with_for_update()
        .first()
    )

    if not auction:
        raise HTTPException(
            status_code=404,
            detail="Shipment auction not found"
        )

    # ============================================================
    # 2. VALIDATE AUCTION STATUS
    # ============================================================

    if auction.status not in ["Active", "Partially Awarded"]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Auction cannot be awarded from status "
                f"'{auction.status}'"
            )
        )

    # ============================================================
    # 3. VALIDATE REMAINING SLOTS
    # ============================================================

    if not auction.slots_remaining or auction.slots_remaining <= 0:
        raise HTTPException(
            status_code=400,
            detail="This auction has no remaining slots"
        )

    # ============================================================
    # 4. LOCK AND LOAD BID
    # ============================================================

    bid = (
        db.query(Shipment_Auction_Bid)
        .filter(
            Shipment_Auction_Bid.id == bid_id,
            Shipment_Auction_Bid.auction_id == auction_id
        )
        .with_for_update()
        .first()
    )

    if not bid:
        raise HTTPException(
            status_code=404,
            detail="Bid not found for this auction"
        )

    # ============================================================
    # 5. VALIDATE BID STATUS
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
    # 6. VALIDATE BID QUANTITY
    # ============================================================

    if not bid.number_of_loads or bid.number_of_loads <= 0:
        raise HTTPException(
            status_code=400,
            detail="Bid does not contain a valid number of slots"
        )

    awarded_slots = bid.number_of_loads

    if awarded_slots > auction.slots_remaining:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Bid requests {awarded_slots} slots, "
                f"but only {auction.slots_remaining} slots "
                f"remain on the auction"
            )
        )

    # ============================================================
    # 7. VALIDATE BID RATE
    # ============================================================

    if bid.rate is None:
        raise HTTPException(
            status_code=400,
            detail="Bid does not contain a valid rate"
        )

    # ============================================================
    # 8. VALIDATE CARRIER USER
    # ============================================================

    if not bid.bidder_user_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "Bid does not contain a bidder user ID. "
                "Cannot create carrier shipment."
            )
        )

    # ============================================================
    # 9. LOAD AUCTION STOPS
    # ============================================================

    auction_stops = (
        db.query(Client_Shipment_Auction_Stop)
        .filter(
            Client_Shipment_Auction_Stop.auction_id == auction.id
        )
        .order_by(
            Client_Shipment_Auction_Stop.stop_sequence
        )
        .all()
    )

    if not auction_stops:
        raise HTTPException(
            status_code=400,
            detail="Auction has no configured shipment stops"
        )

    # ============================================================
    # 10. LOAD AUCTION VEHICLE REQUIREMENTS
    # ============================================================

    auction_vehicle_requirements = (
        db.query(Client_Shipment_Auction_Vehicle_Requirement)
        .filter(
            Client_Shipment_Auction_Vehicle_Requirement.auction_id
            == auction.id
        )
        .all()
    )

    if not auction_vehicle_requirements:
        raise HTTPException(
            status_code=400,
            detail=(
                "Auction has no configured vehicle requirements"
            )
        )

    # ============================================================
    # 11. DETERMINE FIRST SHIPMENT SLOT NUMBER
    # ============================================================

    existing_shipments = (
        db.query(Client_Shipment)
        .filter(
            Client_Shipment.auction_id == auction.id
        )
        .count()
    )

    first_slot_number = existing_shipments + 1

    created_client_shipments = []
    created_carrier_shipments = []

    # ============================================================
    # 12. CREATE SHIPMENTS FOR EVERY AWARDED SLOT
    # ============================================================

    for slot_index in range(awarded_slots):

        slot_number = first_slot_number + slot_index

        # --------------------------------------------------------
        # Generate unique references
        # --------------------------------------------------------

        shipment_reference = (
            f"{auction.shipment_reference}-S{slot_number:03d}"
        )

        booking_reference = (
            f"{auction.booking_reference or auction.id}"
            f"-S{slot_number:03d}"
        )

        # ========================================================
        # 12A. CREATE CLIENT SHIPMENT
        # ========================================================

        client_shipment = Client_Shipment(
            tracking_status=None,
            is_subshipment=False,

            auction_id=auction.id,

            booking_source="Auction",

            shipment_reference=shipment_reference,
            booking_reference=booking_reference,

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

            customer_reference_number=(
                auction.customer_reference_number
            ),

            shipment_weight=auction.shipment_weight,
            commodity=auction.commodity,

            temperature_control=auction.temperature_control,
            target_temperature_spec=(
                auction.target_temperature_spec
            ),

            hazardous_materials=auction.hazardous_materials,
            hazchem_classification=(
                auction.hazchem_classification
            ),

            under_bond=auction.under_bond,
            rib_requirements=auction.rib_requirements,

            packaging_quantity=auction.packaging_quantity,
            packaging_type=auction.packaging_type,

            distance=auction.distance,

            estimated_transit_time=(
                auction.estimated_transit_time
            ),

            eta_date=auction.eta_date,

            route_preview_embed=auction.route_preview_embed,
            polyline=auction.polyline,

            status="Booked",
            trip_status="Schedule",

            # ----------------------------------------------------
            # RATE INCLUSIONS
            # ----------------------------------------------------

            rate_includes_fuel=auction.rate_includes_fuel,
            rate_includes_driver=auction.rate_includes_driver,
            rate_includes_maintenance=(
                auction.rate_includes_maintenance
            ),
            rate_includes_insurance=(
                auction.rate_includes_insurance
            ),
            rate_includes_tolls=auction.rate_includes_tolls,
            rate_includes_border_charges=(
                auction.rate_includes_border_charges
            ),
            rate_includes_empty_return=(
                auction.rate_includes_empty_return
            ),
            rate_includes_waiting_time=(
                auction.rate_includes_waiting_time
            ),
            rate_includes_loading_assistance=(
                auction.rate_includes_loading_assistance
            ),
            rate_includes_offloading_assistance=(
                auction.rate_includes_offloading_assistance
            ),

            # ----------------------------------------------------
            # OPERATIONAL REQUIREMENTS
            # ----------------------------------------------------

            minimum_weight_bracket_kg=(
                auction.minimum_weight_bracket
            ),

            vehicle_tracking_required=(
                auction.vehicle_tracking_required
            ),
            all_time_hour_control_room=(
                auction.all_time_hour_control_room
            ),
            driver_mobile_phone=(
                auction.driver_mobile_phone
            ),
            clean_compliant_equipment=(
                auction.clean_compliant_equipment
            ),
            pallet_management=auction.pallet_management,

            pod_submission_local=(
                auction.pod_submission_local
            ),
            pod_submission_long_haul=(
                auction.pod_submission_long_haul
            ),
            pod_submission_cross_border=(
                auction.pod_submission_cross_border
            ),

            # ----------------------------------------------------
            # INSURANCE
            # ----------------------------------------------------

            minimum_git_cover_amount=(
                auction.minimum_git_cover_amount
            ),
            minimum_liability_cover_amount=(
                auction.minimum_liability_cover_amount
            ),

            git_all_risk_required=(
                auction.git_all_risk_required
            ),
            git_first_loss_required=(
                auction.git_first_loss_required
            ),
            git_driver_fidelity_required=(
                auction.git_driver_fidelity_required
            ),

            # ----------------------------------------------------
            # EQUIPMENT COMPLIANCE
            # ----------------------------------------------------

            tarpaulin_compliance_required=(
                auction.tarpaulin_compliance_required
            ),
            corner_plates_required=(
                auction.corner_plates_required
            ),
            chock_blocks_required=(
                auction.chock_blocks_required
            ),
            ratchets_belts_required=(
                auction.ratchets_belts_required
            ),
            other_equipment_requirements=(
                auction.other_equipment_requirements
            ),

            # ----------------------------------------------------
            # ASSIGN CARRIER
            # ----------------------------------------------------

            carrier_id=bid.carrier_id,
        )

        db.add(client_shipment)

        # We need the Client Shipment ID before creating
        # the Carrier Shipment.
        db.flush()

        # ========================================================
        # 12B. COPY STOPS
        # ========================================================

        for auction_stop in auction_stops:

            shipment_stop = Client_Shipment_Stop(
                shipment_id=client_shipment.id,

                stop_sequence=auction_stop.stop_sequence,
                stop_type=auction_stop.stop_type,

                address=auction_stop.address,
                complete_address=(
                    auction_stop.complete_address
                ),
                city_province=(
                    auction_stop.city_province
                ),
                country=auction_stop.country,
                region=auction_stop.region,

                latitude=auction_stop.latitude,
                longitude=auction_stop.longitude,

                facility_name=auction_stop.facility_name,

                scheduling_type=(
                    auction_stop.scheduling_type
                ),

                operating_start_time=(
                    auction_stop.operating_start_time
                ),
                operating_end_time=(
                    auction_stop.operating_end_time
                ),

                open_monday=auction_stop.open_monday,
                open_tuesday=auction_stop.open_tuesday,
                open_wednesday=auction_stop.open_wednesday,
                open_thursday=auction_stop.open_thursday,
                open_friday=auction_stop.open_friday,
                open_saturday=auction_stop.open_saturday,
                open_sunday=auction_stop.open_sunday,

                contact_first_name=(
                    auction_stop.contact_first_name
                ),
                contact_last_name=(
                    auction_stop.contact_last_name
                ),
                contact_phone_number=(
                    auction_stop.contact_phone_number
                ),
                contact_email=(
                    auction_stop.contact_email
                ),

                reference_number=(
                    auction_stop.reference_number
                ),

                notes=auction_stop.notes,
            )

            db.add(shipment_stop)

        # ========================================================
        # 12C. COPY VEHICLE REQUIREMENTS
        # ========================================================

        for auction_requirement in auction_vehicle_requirements:

            shipment_requirement = (
                Client_Shipment_Vehicle_Requirement(
                    shipment_id=client_shipment.id,

                    configuration_type=(
                        auction_requirement.configuration_type
                    ),
                    truck_type=(
                        auction_requirement.truck_type
                    ),
                    equipment_type=(
                        auction_requirement.equipment_type
                    ),
                    trailer_type=(
                        auction_requirement.trailer_type
                    ),
                    trailer_length=(
                        auction_requirement.trailer_length
                    ),
                    is_required=(
                        auction_requirement.is_required
                    ),
                )
            )

            db.add(shipment_requirement)

        # ========================================================
        # 12D. CREATE CARRIER SHIPMENT
        # ========================================================

        carrier_shipment = Carrier_Shipment(

            # Critical relationship
            client_shipment_id=client_shipment.id,

            tracking_status=None,
            is_subshipment=False,

            auction_id=auction.id,

            client_id=auction.client_id,

            carrier_lane_id=None,
            client_lane_id=None,

            booking_source="Auction",

            shipment_reference=shipment_reference,
            booking_reference=booking_reference,

            trip_type=auction.trip_type,
            load_type=auction.load_type,

            carrier_id=bid.carrier_id,
            carrier_user_id=bid.bidder_user_id,

            rate=bid.rate,

            # Service fee can be populated by your
            # existing fee calculation logic.
            service_fee=None,

            pricing_basis=auction.pricing_basis,
            vat_included=auction.vat_included,
            payment_terms=auction.payment_terms,

            pickup_date=auction.pickup_date,
            priority_level=auction.priority_level,

            customer_reference_number=(
                auction.customer_reference_number
            ),

            shipment_weight=auction.shipment_weight,
            commodity=auction.commodity,

            temperature_control=auction.temperature_control,
            target_temperature_spec=(
                auction.target_temperature_spec
            ),

            hazardous_materials=auction.hazardous_materials,
            hazchem_classification=(
                auction.hazchem_classification
            ),

            under_bond=auction.under_bond,
            rib_requirements=auction.rib_requirements,

            packaging_quantity=auction.packaging_quantity,
            packaging_type=auction.packaging_type,

            distance=auction.distance,

            estimated_transit_time=(
                auction.estimated_transit_time
            ),

            eta_date=auction.eta_date,

            route_preview_embed=auction.route_preview_embed,
            polyline=auction.polyline,

            status="Booked",
            trip_status="Scheduled",

            # ----------------------------------------------------
            # RATE INCLUSIONS
            # ----------------------------------------------------

            rate_includes_fuel=auction.rate_includes_fuel,
            rate_includes_driver=auction.rate_includes_driver,
            rate_includes_maintenance=(
                auction.rate_includes_maintenance
            ),
            rate_includes_insurance=(
                auction.rate_includes_insurance
            ),
            rate_includes_tolls=auction.rate_includes_tolls,
            rate_includes_border_charges=(
                auction.rate_includes_border_charges
            ),
            rate_includes_empty_return=(
                auction.rate_includes_empty_return
            ),
            rate_includes_waiting_time=(
                auction.rate_includes_waiting_time
            ),
            rate_includes_loading_assistance=(
                auction.rate_includes_loading_assistance
            ),
            rate_includes_offloading_assistance=(
                auction.rate_includes_offloading_assistance
            ),

            # ----------------------------------------------------
            # OPERATIONAL REQUIREMENTS
            # ----------------------------------------------------

            minimum_weight_bracket_kg=(
                auction.minimum_weight_bracket
            ),

            vehicle_tracking_required=(
                auction.vehicle_tracking_required
            ),
            all_time_hour_control_room=(
                auction.all_time_hour_control_room
            ),
            driver_mobile_phone=(
                auction.driver_mobile_phone
            ),
            clean_compliant_equipment=(
                auction.clean_compliant_equipment
            ),
            pallet_management=auction.pallet_management,

            pod_submission_local=(
                auction.pod_submission_local
            ),
            pod_submission_long_haul=(
                auction.pod_submission_long_haul
            ),
            pod_submission_cross_border=(
                auction.pod_submission_cross_border
            ),

            # ----------------------------------------------------
            # INSURANCE
            # ----------------------------------------------------

            minimum_git_cover_amount=(
                auction.minimum_git_cover_amount
            ),
            minimum_liability_cover_amount=(
                auction.minimum_liability_cover_amount
            ),

            git_all_risk_required=(
                auction.git_all_risk_required
            ),
            git_first_loss_required=(
                auction.git_first_loss_required
            ),
            git_driver_fidelity_required=(
                auction.git_driver_fidelity_required
            ),

            # ----------------------------------------------------
            # EQUIPMENT
            # ----------------------------------------------------

            tarpaulin_compliance_required=(
                auction.tarpaulin_compliance_required
            ),
            corner_plates_required=(
                auction.corner_plates_required
            ),
            chock_blocks_required=(
                auction.chock_blocks_required
            ),
            ratchets_belts_required=(
                auction.ratchets_belts_required
            ),
            other_equipment_requirements=(
                auction.other_equipment_requirements
            ),
        )

        db.add(carrier_shipment)

        created_client_shipments.append(client_shipment)
        created_carrier_shipments.append(carrier_shipment)

    # ============================================================
    # 13. UPDATE REMAINING AUCTION SLOTS
    # ============================================================

    auction.slots_remaining = (
        auction.slots_remaining - awarded_slots
    )

    # ============================================================
    # 14. UPDATE AUCTION STATUS
    # ============================================================

    if auction.slots_remaining == 0:

        auction.status = "Awarded"

    else:

        auction.status = "Partially Awarded"

    # ============================================================
    # 15. UPDATE BID STATUS
    # ============================================================

    bid.status = "Awarded"

    # ============================================================
    # 16. FLUSH EVERYTHING
    # ============================================================

    db.flush()

    # ============================================================
    # 17. COMMIT
    # ============================================================

    db.commit()

    # ============================================================
    # 18. RETURN RESULT
    # ============================================================

    return {
        "success": True,
        "message": (
            f"Successfully awarded {awarded_slots} "
            f"shipment slot(s) to {bid.carrier_name}"
        ),
        "auction_id": auction.id,
        "bid_id": bid.id,
        "carrier_id": bid.carrier_id,
        "awarded_slots": awarded_slots,
        "slots_remaining": auction.slots_remaining,
        "auction_status": auction.status,
        "bid_status": bid.status,
        "client_shipment_ids": [
            shipment.id
            for shipment in created_client_shipments
        ],
        "carrier_shipment_ids": [
            shipment.id
            for shipment in created_carrier_shipments
        ],
    }