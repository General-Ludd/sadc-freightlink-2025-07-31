

def award_shipment_bid(
    db: Session,
    auction_id: int,
    bid_id: int,
    current_user: dict
):
    # ============================================================
    # 1. LOCK AND LOAD TENDER
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
            detail="Load exchange not found"
        )

    # ============================================================
    # 2. LOAD AND LOCK BID
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
            detail="Bid not found for this tender"
        )

    # ============================================================
    # 3. VALIDATE BID STATUS
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
    # 4. VALIDATE BID VALUES
    # ============================================================

    client_shipment = Client_Shipment(
        is_subshipment=False,
        auction_id=auction.id,
        booking_source="Auction",
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
        hazardous_materials=auction.hazardous_materials,
        under_bond=auction.under_bond,
        rib_requirements=auction.rib_requirements,
        packaging_quantity=auction.packaging_quantity,
        packaging_type=auction.packaging_type,
        distance=auction.distance,
        estimated_transit_time=auction.estimated_transit_time,
        route_preview_embed=auction.route_preview_embed,
        polyline=auction.polyline,
        rate_includes_fuel=auction.rate_includes_fuel,
        rate_includes_driver=auction.rate_includes_driver,
        rate_includes_maintenance=auction.rate_includes_maintenance,
        rate_includes_insurance=auction.rate_includes_insurance,
        rate_includes_tolls=auction.rate_includes_tolls,
        rate_includes_border_charges=auction.rate_includes_border_charges,
        rate_includes_empty_return=auction.rate_includes_empty_return,
        rate_includes_waiting_time=auction.rate_includes_waiting_time,
        rate_includes_loading_assistance=auction.rate_includes_loading_assistance,
        rate_includes_offloading_assistance=auction.rate_includes_offloading_assistance,
        vehicle_tracking_required=auction.vehicle_tracking_required,
        all_time_hour_control_room=auction.all_time_hour_control_room,
        driver_mobile_phone=auction.driver_mobile_phone,
        clean_compliant_equipment=auction.clean_compliant_equipment,
        pallet_management=auction.pallet_management,
        pod_submission_local=auction.pod_submission_local,
        pod_submission_long_haul=auction.pod_submission_long_haul,
        pod_submission_cross_border=auction.pod_submission_cross_border,
        minimum_git_cover_amount=auction.minimum_git_cover_amount,
        minimum_liability_cover_amount=auction.minimum_liability_cover_amount,
        git_all_risk_required=auction.git_all_risk_required,
        git_first_loss_required=auction.git_first_loss_required,
        git_driver_fidelity_required=auction.git_driver_fidelity_required,
        tarpaulin_compliance_required=auction.tarpaulin_compliance_required,
        corner_plates_required=auction.corner_plates_required,
        chock_blocks_required=auction.chock_blocks_required,
        ratchets_belts_required=auction.ratchets_belts_required,
        other_equipment_requirements=auction.other_equipment_requirements,
    )
    db.add(client_shipment)

    # ============================================================
    # 18. CREATE CLIENT LANE STOPS
    # ============================================================

    auction_stops = (
        db.query(Lane_Tender_RFQ_Stop)
        .filter(
            Lane_Tender_RFQ_Stop.tender_id == tender.id
        )
        .order_by(
            Lane_Tender_RFQ_Stop.stop_sequence
        )
        .all()
    )