from fastapi import HTTPException
from sqlalchemy.orm import Session
from models.Exchange.dedicated_ftl_lane import Lane_Tender_RFQ, Lane_Tender_RFQ_Volume_Profile
from models.Exchange.bidding import  Lane_Tender_Bid
from models.carrier import Carrier, Carrier_Profile
from schemas.exchange_bookings.bidding import TenderBidCreate
from uuid import uuid4

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
        )
        db.add(db_bid)
        created_bids.append(db_bid)
    
    db.commit()
    for bid in created_bids:
        db.refresh(bid)

    return {"status": "success", "submission_id": submission_id, "bids_created": len(created_bids)}
