from fastapi import HTTPException
from sqlalchemy.orm import Session
from models.Exchange.dedicated_ftl_lane import Lane_Tender_RFQ, Lane_Tender_RFQ_Volume_Profile
from models.Exchange.bidding import  Lane_Tender_Bid
from models.carrier import Carrier, Carrier_Profile
from schemas.exchange_bookings.bidding import TenderBidCreate, Create_Shipment_Bid
from uuid import uuid4

def create_shipment_bid(
    db: Session,
    bid_data: Create_Shipment_Bid,
    current_user: dict
):
    company_id = current_user.get("company_id")
    user_id = current_user.get("id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    if not bid_data.bids:
        raise HTTPException(
            status_code=400,
            detail="At least one auction bid is required."
        )

    # ---------------------------------------------------------
    # CARRIER
    # ---------------------------------------------------------

    carrier = db.query(Carrier).filter(
        Carrier.id == company_id
    ).first()

    if not carrier:
        raise HTTPException(
            status_code=404,
            detail="Carrier not found"
        )

    carrier_profile = db.query(Carrier_Profile).filter(
        Carrier_Profile.carrier_id == carrier.id
    ).first()

    if not carrier_profile:
        raise HTTPException(
            status_code=400,
            detail="Carrier profile not found."
        )

    # ---------------------------------------------------------
    # FLEET INFORMATION
    # ---------------------------------------------------------

    fleet_fields = [
        "rigid_tautliners",
        "triaxle_tautliners",
        "superlink_tautliners",
        "rigid_flatbeds",
        "triaxle_flatbeds",
        "superlink_flatbeds",
        "rigid_flatbeds_with_twistlocks",
        "triaxle_flatbeds_with_twistlocks",
        "superlink_flatbeds_with_twistlocks",
        "rigid_dropsides",
        "triaxle_dropside",
        "superlink_dropside",
        "triaxle_skeletals",
        "superlink_skeletals",
        "rigid_pantechs",
        "triaxle_pantechs",
        "triaxle_side_tippers",
        "superlink_side_tippers",
        "low_beds",
        "rigid_end_tipper",
        "triaxle_end_tipper"
    ]

    fleet_size = sum(
        (getattr(carrier_profile, field) or 0)
        for field in fleet_fields
    )

    # ---------------------------------------------------------
    # VALIDATE DUPLICATE AUCTION IDS
    # ---------------------------------------------------------

    auction_ids = [
        bid.auction_id
        for bid in bid_data.bids
    ]

    if len(auction_ids) != len(set(auction_ids)):
        raise HTTPException(
            status_code=400,
            detail="The same auction cannot be bid on more than once in one submission."
        )

    # ---------------------------------------------------------
    # LOAD AUCTIONS
    # ---------------------------------------------------------

    auctions = db.query(Client_Shipment_Auction).filter(
        Client_Shipment_Auction.id.in_(auction_ids)
    ).all()

    auction_map = {
        auction.id: auction
        for auction in auctions
    }

    if len(auctions) != len(set(auction_ids)):
        missing_ids = [
            auction_id
            for auction_id in auction_ids
            if auction_id not in auction_map
        ]

        raise HTTPException(
            status_code=404,
            detail=f"One or more auctions not found: {missing_ids}"
        )

    # ---------------------------------------------------------
    # VALIDATE AUCTION STATUS / CLOSING TIME
    # ---------------------------------------------------------

    now = datetime.now(timezone.utc)

    for auction in auctions:

        if auction.status != "Active":
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Auction {auction.id} is not active "
                    f"and cannot receive bids."
                )
            )

        if not auction.bidding_activated:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Bidding is not activated for auction "
                    f"{auction.id}."
                )
            )

        if auction.auction_closing_date:

            closing_date = auction.auction_closing_date

            if closing_date.tzinfo is None:
                closing_date = closing_date.replace(
                    tzinfo=timezone.utc
                )

            if closing_date <= now:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Auction {auction.id} has already closed."
                    )
                )

    # ---------------------------------------------------------
    # BUNDLE VALIDATION
    #
    # Each bundled auction remains an independent auction.
    # However, if a carrier submits a bid on one stage of a
    # bundle, the complete bundle must be submitted together.
    # ---------------------------------------------------------

    submitted_auction_ids = set(auction_ids)

    bundles = {}

    for auction in auctions:

        if not auction.bundle_id:
            continue

        if auction.bundle_id not in bundles:
            bundles[auction.bundle_id] = []

        bundles[auction.bundle_id].append(auction)

    for bundle_id, submitted_bundle_auctions in bundles.items():

        all_bundle_auctions = db.query(
            Client_Shipment_Auction
        ).filter(
            Client_Shipment_Auction.bundle_id == bundle_id
        ).order_by(
            Client_Shipment_Auction.bundle_stage_sequence
        ).all()

        if not all_bundle_auctions:
            raise HTTPException(
                status_code=400,
                detail=f"Shipment bundle {bundle_id} could not be found."
            )

        all_bundle_auction_ids = {
            auction.id
            for auction in all_bundle_auctions
        }

        missing_bundle_auctions = (
            all_bundle_auction_ids - submitted_auction_ids
        )

        if missing_bundle_auctions:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"This is a bundled shipment. "
                    f"All bundle stages must be submitted together. "
                    f"Missing auction IDs: "
                    f"{sorted(missing_bundle_auctions)}"
                )
            )

    # ---------------------------------------------------------
    # SUBMISSION ID
    #
    # One submission can contain:
    # - one independent auction
    # - several independent auctions
    # - all stages of a shipment bundle
    # ---------------------------------------------------------

    submission_id = str(uuid4())

    created_bids = []

    # ---------------------------------------------------------
    # CREATE BID RECORDS
    # ---------------------------------------------------------

    for bid in bid_data.bids:

        auction = auction_map.get(bid.auction_id)

        if not auction:
            raise HTTPException(
                status_code=404,
                detail=f"Auction {bid.auction_id} not found."
            )

        # -----------------------------------------------------
        # NUMBER OF LOADS
        # -----------------------------------------------------

        if bid.number_of_loads > auction.slots_remaining:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Auction {auction.id} only has "
                    f"{auction.slots_remaining} slots remaining. "
                    f"Bid requested {bid.number_of_loads} loads."
                )
            )

        # -----------------------------------------------------
        # NORMALIZE PRICING BASIS
        # -----------------------------------------------------

        pricing_basis = (
            str(auction.pricing_basis)
            .strip()
            .lower()
        )

        distance = (
            Decimal(str(auction.distance))
            if auction.distance is not None
            else None
        )

        shipment_weight = (
            Decimal(str(auction.shipment_weight))
            if auction.shipment_weight is not None
            else None
        )

        main_rate_per_shipment = None
        secondary_rate_per_shipment = None

        total_main_rate = None
        total_secondary_rate = None

        # -----------------------------------------------------
        # MAIN RATE
        # -----------------------------------------------------

        if bid.main_rate is not None:

            main_rate = Decimal(str(bid.main_rate))

            if pricing_basis in {
                "rate per load",
                "fixed trip rate",
                "rate per shipment",
                "rate per container"
            }:
                main_rate_per_shipment = main_rate

            elif pricing_basis == "rate per km":

                if distance is None:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Auction {auction.id} does not have "
                            f"a calculated distance required for "
                            f"Rate per KM bidding."
                        )
                    )

                main_rate_per_shipment = (
                    main_rate * distance
                )

            elif pricing_basis in {
                "rate per ton",
                "rate per tonne"
            }:

                if shipment_weight is None:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Auction {auction.id} does not have "
                            f"a shipment weight required for "
                            f"Rate per Ton bidding."
                        )
                    )

                shipment_weight_tons = (
                    shipment_weight / Decimal("1000")
                )

                main_rate_per_shipment = (
                    main_rate * shipment_weight_tons
                )

            else:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Unsupported pricing basis "
                        f"'{auction.pricing_basis}' "
                        f"for auction {auction.id}."
                    )
                )

            total_main_rate = (
                main_rate_per_shipment *
                bid.number_of_loads
            )

        # -----------------------------------------------------
        # SECONDARY RATE
        # -----------------------------------------------------

        if bid.secondary_rate is not None:

            secondary_rate = Decimal(
                str(bid.secondary_rate)
            )

            if pricing_basis in {
                "rate per load",
                "fixed trip rate",
                "rate per shipment",
                "rate per container"
            }:
                secondary_rate_per_shipment = secondary_rate

            elif pricing_basis == "rate per km":

                if distance is None:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Auction {auction.id} does not have "
                            f"a calculated distance required for "
                            f"Rate per KM bidding."
                        )
                    )

                secondary_rate_per_shipment = (
                    secondary_rate * distance
                )

            elif pricing_basis in {
                "rate per ton",
                "rate per tonne"
            }:

                if shipment_weight is None:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Auction {auction.id} does not have "
                            f"a shipment weight required for "
                            f"Rate per Ton bidding."
                        )
                    )

                shipment_weight_tons = (
                    shipment_weight / Decimal("1000")
                )

                secondary_rate_per_shipment = (
                    secondary_rate * shipment_weight_tons
                )

            else:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Unsupported pricing basis "
                        f"'{auction.pricing_basis}' "
                        f"for auction {auction.id}."
                    )
                )

            total_secondary_rate = (
                secondary_rate_per_shipment *
                bid.number_of_loads
            )

        # -----------------------------------------------------
        # CREATE DATABASE BID
        # -----------------------------------------------------

        db_bid = Shipment_Auction_Bid(
            auction_id=auction.id,
            carrier_id=company_id,
            bidder_user_id=user_id,
            carrier_name=carrier.legal_business_name,
            fleet_size=fleet_size,
            primary_lanes=carrier_profile.primary_routes,
            rate_basis=auction.pricing_basis,
            main_rate=(
                Decimal(str(bid.main_rate))
                if bid.main_rate is not None
                else None
            ),
            main_rate_per_shipment=main_rate_per_shipment,
            total_main_rate=total_main_rate,
            secondary_rate=(
                Decimal(str(bid.secondary_rate))
                if bid.secondary_rate is not None
                else None
            ),
            secondary_rate_per_shipment=(
                secondary_rate_per_shipment
            ),
            total_secondary_rate=(
                total_secondary_rate
            ),
            number_of_loads=bid.number_of_loads,
            lead_time=bid.lead_time,
            bid_notes=bid.bid_notes,

            status="Submitted",
            is_active=True
        )

        db.add(db_bid)
        created_bids.append(db_bid)

    # ---------------------------------------------------------
    # COMMIT
    # ---------------------------------------------------------

    db.commit()

    for bid in created_bids:
        db.refresh(bid)

    return {
        "status": "success",
        "submission_id": submission_id,
        "bids_created": len(created_bids),
        "auction_ids": [
            bid.auction_id
            for bid in created_bids
        ]
    }


def create_tender_bid(
    db: Session,
    bid_data: TenderBidCreate,
    current_user: dict
):
    company_id = current_user.get("company_id")
    user_id = current_user.get("id")

    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")

    submission_id = str(uuid4())
    
    carrier = db.query(Carrier).filter(Carrier.id == company_id).first()
    if not carrier:
        raise HTTPException(status_code=404, detail="Carrier not found")

    carrier_profile = db.query(Carrier_Profile).filter(Carrier_Profile.carrier_id == carrier.id).first()
    if not carrier_profile:
        raise HTTPException(status_code=400, detail="Carrier profile not found.")

    fleet_fields = ["rigid_tautliners", "triaxle_tautliners", "superlink_tautliners", "rigid_flatbeds", "triaxle_flatbeds", "superlink_flatbeds", "rigid_flatbeds_with_twistlocks", "triaxle_flatbeds_with_twistlocks", "superlink_flatbeds_with_twistlocks", "rigid_dropsides", "triaxle_dropside", "superlink_dropside", "triaxle_skeletals", "superlink_skeletals", "rigid_pantechs", "triaxle_pantechs", "triaxle_side_tippers", "superlink_side_tippers", "low_beds", "rigid_end_tipper", "triaxle_end_tipper"]
    fleet_size = sum((getattr(carrier_profile, field) or 0) for field in fleet_fields)

    tender_ids = [bid.tender_id for bid in bid_data.bids]
    tenders = db.query(Lane_Tender_RFQ).filter(Lane_Tender_RFQ.id.in_(tender_ids)).all()
    tender_map = {tender.id: tender for tender in tenders}

    if len(tenders) != len(set(tender_ids)):
        raise HTTPException(status_code=404, detail="One or more tenders not found.")

    bids_by_bundle = {}
    for bid in bid_data.bids:
        tender = tender_map.get(bid.tender_id)
        bundle_ref = tender.bundle_reference or 'independent'
        if bundle_ref not in bids_by_bundle:
            bids_by_bundle[bundle_ref] = []
        bids_by_bundle[bundle_ref].append(bid)

    for bundle_ref, bids in bids_by_bundle.items():
        if bundle_ref == 'independent':
            continue
        sorted_bids = sorted(bids, key=lambda b: tender_map[b.tender_id].bundle_stage_sequence)
        for i, bid in enumerate(sorted_bids):
            if bid.main_bid_amount is not None and i + 1 >= len(sorted_bids):
                raise HTTPException(status_code=400, detail=f"Main bid on tender {bid.tender_id} requires a bid on the next leg.")

    created_bids = []
    for bid in bid_data.bids:
        tender = tender_map.get(bid.tender_id)
        
        volume_profiles = db.query(Lane_Tender_RFQ_Volume_Profile).filter(Lane_Tender_RFQ_Volume_Profile.tender_id == tender.id).all()
        number_of_intervals = len(volume_profiles) if volume_profiles else 0
        per_slot_size = bid.slots_per_interval * number_of_intervals

        main_rate_per_shipment = None
        secondary_rate_per_shipment = None
        main_per_slot_contract_bid = None
        main_total_contract_bid = None
        secondary_per_slot_contract_bid = None
        secondary_total_contract_bid = None

        if tender.pricing_basis == "Rate per Ton":
            tons = tender.average_shipment_weight_kg / 1000
            if bid.main_bid_amount:
                main_rate_per_shipment = bid.main_bid_amount * tons
                main_per_slot_contract_bid = main_rate_per_shipment * per_slot_size
                main_total_contract_bid = main_per_slot_contract_bid * bid.slots_per_interval
            if bid.secondary_bid_amount:
                secondary_rate_per_shipment = bid.secondary_bid_amount * tons
                secondary_per_slot_contract_bid = secondary_rate_per_shipment * per_slot_size
                secondary_total_contract_bid = secondary_per_slot_contract_bid * bid.slots_per_interval
        elif tender.pricing_basis == "Rate per Km":
            if bid.main_bid_amount:
                main_rate_per_shipment = bid.main_bid_amount * tender.actual_distance_km
                main_per_slot_contract_bid = main_rate_per_shipment * per_slot_size
                main_total_contract_bid = main_per_slot_contract_bid * bid.slots_per_interval
            if bid.secondary_bid_amount:
                secondary_rate_per_shipment = bid.secondary_bid_amount * tender.actual_distance_km
                secondary_per_slot_contract_bid = secondary_rate_per_shipment * per_slot_size
                secondary_total_contract_bid = secondary_per_slot_contract_bid * bid.slots_per_interval
        else: # Rate Per Load, Rate per Shipment, Rate per Trip
            if bid.main_bid_amount:
                main_rate_per_shipment = bid.main_bid_amount
                main_per_slot_contract_bid = main_rate_per_shipment * per_slot_size
                main_total_contract_bid = main_per_slot_contract_bid * bid.slots_per_interval
            if bid.secondary_bid_amount:
                secondary_rate_per_shipment = bid.secondary_bid_amount
                secondary_per_slot_contract_bid = secondary_rate_per_shipment * per_slot_size
                secondary_total_contract_bid = secondary_per_slot_contract_bid * bid.slots_per_interval

        db_bid = Lane_Tender_Bid(
            tender_id=bid.tender_id,
            carrier_id=company_id,
            user_id=user_id,
            submission_id=submission_id,
            carrier_name=carrier.legal_business_name,
            fleet_size=fleet_size,
            primary_lanes=carrier_profile.primary_routes,
            rate_basis=tender.pricing_basis,
            main_bid_amount=bid.main_bid_amount,
            secondary_bid_amount=bid.secondary_bid_amount,
            main_rate_per_shipment=main_rate_per_shipment,
            secondary_rate_per_shipment=secondary_rate_per_shipment,
            slots_per_interval=bid.slots_per_interval,
            number_of_intervals=number_of_intervals,
            per_slot_size=per_slot_size,
            main_per_slot_contract_bid=main_per_slot_contract_bid,
            main_total_contract_bid=main_total_contract_bid,
            secondary_per_slot_contract_bid=secondary_per_slot_contract_bid,
            secondary_total_contract_bid=secondary_total_contract_bid,
            bid_notes=bid.notes,
            status="Submitted"
        )
        db.add(db_bid)
        created_bids.append(db_bid)
    
    db.commit()
    for bid in created_bids:
        db.refresh(bid)

    return {"status": "success", "submission_id": submission_id, "bids_created": len(created_bids)}
