from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.Exchange.auction import Exchange_FTL_Shipment_Bid, Exchange_FTL_Lane_Bid, Exchange_POWER_Shipment_Bid
from models.brokerage.loadboards.exchange_loadboards import Exchange_Ftl_Load_Board, Exchange_Ftl_Lane_LoadBoard
from models.carrier import Carrier
from schemas.brokerage.loadboard import IndividualLoadboardShipmentRequest
from schemas.brokerage.exchange_loadboards import Exchange_Ftl_Load_Board_Response, Exchange_Ftl_Loadboard_Summary_Response
from schemas.exchange_bookings.auction import Exchange_FTL_Lane_Bid_Create, Exchange_FTL_Shipment_Bid_Create, Exchange_FTL_Exchange_Loadboard_BidResponse, Exchange_POWER_Shipment_Bid_Create, Exchange_Power_Exchange_Loadboard_BidResponse
from schemas.exchange_bookings.ftl_shipment import Exchange_Ftl_Shipments_Summary_Response
from services.exchange.auction import place_ftl_lane_bid, place_ftl_shipment_bid, place_power_shipment_bid
from utils.auth import get_current_user

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

#####################################Exchange Load Boards#############################################
@router.get("/carrier/ftl/exchange")
def get_ftl_exchange_loadboard(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        loads = db.query(Exchange_Ftl_Load_Board).filter(Exchange_Ftl_Load_Board.status == "Open").all()
        return {
            "exchanges": [{
                "id": load.exchange_id,
                "rate": load.shipment_rate,
                "trip_type": load.trip_type,
                "status": load.status,
                "end_time": load.exchange_end_time,
                "origin": load.origin_city_province,
                "pickup_date": load.pickup_date,
                "pickup_window": load.pickup_appointment,
                "destination": load.destination_city_province,
                "route": load.route_preview_embed,
                "eta_date": load.eta_date,
                "eta_window": load.eta_window,
                "provider": "SADC FREIGHTLINK",
                "distance": load.distance,
                "minimum_transit_time": load.estimated_transit_time,
                "truck": load.required_truck_type,
                "equipment": load.equipment_type,
                "trailer_type": load.trailer_type,
                "trailer_length": load.trailer_length,
                "minimum_weight_bracket": load.minimum_weight_bracket,
                "commodity": load.commodity,
                "hazardous_materials": load.hazardous_materials,
                "leading_bid_amount": load.leading_bid_amount,
                "allow_carrier_to_book_at_current_or_lower_offer_rate": load.allow_carrier_to_book_at_current_or_lower_offer_rate,
            } for load in loads]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/carrier/exchange-ftl-load/{id}")
def get_exchange_ftl_load_id(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    carrier = db.query(Carrier).filter(Carrier.id == company_id).first()
    if not carrier:
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active. Carrier accounts are required to preview loads")

    try:
        loadboard_shipment = db.query(Exchange_Ftl_Load_Board).filter(Exchange_Ftl_Load_Board.exchange_id == id).first()
        bids = db.query(Exchange_FTL_Shipment_Bid).filter(Exchange_FTL_Shipment_Bid.exchange_id == loadboard_shipment.exchange_id,
                                                            Exchange_FTL_Shipment_Bid.carrier_id == company_id).all()

        return {
            "ftl_exchange": {
                "id": loadboard_shipment.exchange_id,
                "shipment_type": loadboard_shipment.type,
                "trip_type": loadboard_shipment.trip_type,
                "load_type": loadboard_shipment.load_type,
                "required_truck_type": loadboard_shipment.required_truck_type,
                "equipment_type": loadboard_shipment.equipment_type,
                "trailer_type": loadboard_shipment.trailer_type,
                "trailer_length": loadboard_shipment.trailer_length,
                "minimum_weight_bracket": loadboard_shipment.minimum_weight_bracket,
                "shipment_weight": loadboard_shipment.shipment_weight,
                "commodity": loadboard_shipment.commodity,
                "distance": loadboard_shipment.distance,
                "estimated_transit_time": loadboard_shipment.estimated_transit_time,
                "origin": loadboard_shipment.origin_city_province,
                "destination": loadboard_shipment.destination_city_province,
                "route_preview_embed": loadboard_shipment.route_preview_embed,
                "pickup_date": loadboard_shipment.pickup_date,
                "priority_level": loadboard_shipment.priority_level,
                "customer_reference": loadboard_shipment.customer_reference_number,
                "payment_terms": loadboard_shipment.payment_terms,
                "minimum_git_cover_amount": loadboard_shipment.minimum_git_cover_amount,
                "minimum_liability_cover_amount": loadboard_shipment.minimum_liability_cover_amount,
                "packaging_quantity": loadboard_shipment.packaging_quantity,
                "packaging_type": loadboard_shipment.packaging_type,
                "temperature_control": loadboard_shipment.temperature_control,
                "hazardous_materials": loadboard_shipment.hazardous_materials,
                "pickup_number": loadboard_shipment.pickup_number,
                "pickup_notes": loadboard_shipment.pickup_notes,
                "delivery_number": loadboard_shipment.delivery_number,
                "delivery_notes": loadboard_shipment.delivery_notes,
                "allow_booking": loadboard_shipment.automatically_accept_lower_bid,
                "end_time": loadboard_shipment.exchange_end_time,

                "exchange_information": {
                    "exchange_offer": loadboard_shipment.shipment_rate,
                    "leading_bid": loadboard_shipment.leading_bid_amount,
                    "payment_terms": loadboard_shipment.payment_terms,
                    "rate_per_km": loadboard_shipment.rate_per_km,
                    "rate_per_ton": loadboard_shipment.rate_per_ton,
                    "your_bids": [{
                        "bid_amount": bid.bid_amount,
                        "bid_status": bid.status,
                        "submitted_at": bid.submitted_at,
                    } for bid in bids]
                },

                "pickup_facility": {
                    "facility_name": loadboard_shipment.pickup_facility_name,
                    "pickup_date": loadboard_shipment.pickup_date,
                    "time_window": loadboard_shipment.pickup_appointment,
                    "scheduling_type": loadboard_shipment.pickup_scheduling_type,
                    "contact_name": f"{loadboard_shipment.pickup_first_name} - {loadboard_shipment.pickup_last_name}",
                    "email": loadboard_shipment.pickup_email,
                    "contact_phone": loadboard_shipment.pickup_phone_number,
                    "notes": loadboard_shipment.pickup_notes,
                },

                "delivery_facility": {
                    "facility_name": loadboard_shipment.delivery_facility_name,
                    "eta_date": loadboard_shipment.eta_date,
                    "time_window": loadboard_shipment.delivery_appointment,
                    "eta_window": loadboard_shipment.eta_window,
                    "scheduling_type": loadboard_shipment.delivery_scheduling_type,
                    "contact_name": f"{loadboard_shipment.delivery_first_name} - {loadboard_shipment.delivery_last_name}",
                    "email": loadboard_shipment.delivery_email,
                    "contact_phone": loadboard_shipment.delivery_phone_number,
                    "notes": loadboard_shipment.delivery_notes,
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/exchange/ftl-loadboard/id/bid", status_code=status.HTTP_201_CREATED) #UnTested
def place_ftl_shipment_exchange_bid(
    bid_data: Exchange_FTL_Shipment_Bid_Create,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)):

    try:
        result = place_ftl_shipment_bid(
            db,
            bid_data,
            current_user=current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/carrier/exchange-ftl-lane-loadboard")
def exchange_ftl_lane_loadboard(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    carrier = db.query(Carrier).filter(Carrier.id == company_id).first()
    if not carrier:
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active. A carrier account is required in order to view shipments")

    try:
        loadboard_shipments = db.query(Exchange_Ftl_Lane_LoadBoard).filter(Exchange_Ftl_Lane_LoadBoard.status == "Open").all()

        return {
            "lanes": [{
                "id": loadboard_shipment.exchange_id,
                "status": loadboard_shipment.status,
                "trip_type": loadboard_shipment.trip_type,
                "load_type": loadboard_shipment.load_type,
                "origin": loadboard_shipment.origin_city_province,
                "destination": loadboard_shipment.destination_city_province,
                "distance": loadboard_shipment.distance,
                "route": loadboard_shipment.route_preview_embed,
                "truck_type": loadboard_shipment.required_truck_type,
                "equipment_type": loadboard_shipment.equipment_type,
                "trailer_type": loadboard_shipment.trailer_type,
                "trailer_length": loadboard_shipment.trailer_length,
                "minimum_weight_bracket": loadboard_shipment.minimum_weight_bracket,
                "commodity": loadboard_shipment.commodity,
                "packaging_type": loadboard_shipment.packaging_type,
                "average_shipment_weight": loadboard_shipment.average_shipment_weight,
                "start_date": loadboard_shipment.start_date,
                "end_date": loadboard_shipment.end_date,
                "frequency": loadboard_shipment.recurrence_frequency,
                "shipments_per_interval": loadboard_shipment.shipments_per_interval,
                "total_shipments": loadboard_shipment.total_shipments,
                "exchange_end_time": loadboard_shipment.exchange_end_time,
                "number_of_bidders": loadboard_shipment.number_of_bids_submitted,
                "opening_contract_offer": loadboard_shipment.contract_offer_rate,
                "opening_per_shipment_offer": loadboard_shipment.per_shipment_offer_rate,
            } for loadboard_shipment in loadboard_shipments]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/carrier/exchange-ftl-lane/{id}")
def exchange_ftl_lane(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    carrier = db.query(Carrier).filter(Carrier.id == company_id).first()
    if not carrier:
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")

    try:
        loadboard_lane = db.query(Exchange_Ftl_Lane_LoadBoard).filter(Exchange_Ftl_Lane_LoadBoard.exchange_id == id).first()
        bids = db.query(Exchange_FTL_Lane_Bid).filter(Exchange_FTL_Lane_Bid.exchange_id == loadboard_lane.exchange_id,
                                                        Exchange_FTL_Lane_Bid.carrier_id == company_id).all()

        return {
            "lane_information":{
                "id": loadboard_lane.exchange_id,
                "shipment_type": loadboard_lane.type,
                "trip_type": loadboard_lane.trip_type,
                "load_type": loadboard_lane.load_type,
                "required_truck_type": loadboard_lane.required_truck_type,
                "equipment_type": loadboard_lane.equipment_type,
                "trailer_type": loadboard_lane.trailer_type,
                "trailer_length": loadboard_lane.trailer_length,
                "minimum_weight_bracket": loadboard_lane.minimum_weight_bracket,
                "average_shipment_weight": loadboard_lane.average_shipment_weight,
                "commodity": loadboard_lane.commodity,
                "priority_level": loadboard_lane.priority_level,
                "customer_reference": loadboard_lane.customer_reference_number,
                "distance": loadboard_lane.distance,
                "estimated_transit_time": loadboard_lane.estimated_transit_time,
                "payment_terms": loadboard_lane.payment_terms,
                "route_preview_embed": loadboard_lane.route_preview_embed,
                "minimum_git_cover_amount": loadboard_lane.minimum_git_cover_amount,
                "minimum_liability_cover_amount": loadboard_lane.minimum_liability_cover_amount,
                "packaging_quantity": loadboard_lane.packaging_quantity,
                "packaging_type": loadboard_lane.packaging_type,
                "temperature_control": loadboard_lane.temperature_control,
                "hazardous_materials": loadboard_lane.hazardous_materials,
                "origin": loadboard_lane.origin_city_province,
                "destination": loadboard_lane.destination_city_province,
                "pickup_number": loadboard_lane.pickup_number,
                "delivery_number": loadboard_lane.delivery_number,
                "pickup_notes": loadboard_lane.pickup_notes,
                "delivery_notes": loadboard_lane.delivery_notes,
                "allow_booking": loadboard_lane.automatically_accept_lower_bid,
                "auction_status": loadboard_lane.status,

                "exchange_information": {
                    "opening_per_shipment_offer": loadboard_lane.per_shipment_offer_rate,
                    "opening_contract_offer": loadboard_lane.contract_offer_rate,
                    "leading_per_shipment_bid": loadboard_lane.leading_per_shipment_offer_bid_amount,
                    "leading_contract_bid": loadboard_lane.leading_contract_offer_bid_amount,
                    "active_bidders": loadboard_lane.number_of_bids_submitted,
                    "auction_end_time": loadboard_lane.exchange_end_time,
                
                "your_bids": [{
                    "bid_id": bid.id,
                    "per_shipment_bid": bid.per_shipment_bid_amount,
                    "total_contract_amount_bid": bid.contract_bid_amount,
                    "bid_status": bid.status,
                    "submitted_at": bid.submitted_at,
                } for bid in bids]
                },

                "contract_details": {
                    "contract_start_date": loadboard_lane.start_date,
                    "contract_end_date": loadboard_lane.end_date,
                    "recurrence_frequency": loadboard_lane.recurrence_frequency,
                    "recurrence_days": loadboard_lane.recurrence_days,
                    "shipments_per_interval": loadboard_lane.shipments_per_interval,
                    "total_shipments": loadboard_lane.total_shipments,
                    "payment_terms": loadboard_lane.payment_terms,
                    "current_contract_price": loadboard_lane.contract_offer_rate,
                    "shipment_schedule": loadboard_lane.shipment_dates,
                    "payment_schedule": loadboard_lane.payment_dates,
                },

                "pickup_facility": {
                    "facility_name": loadboard_lane.pickup_facility_name,
                    "time_window": loadboard_lane.pickup_appointment,
                    "scheduling_type": loadboard_lane.pickup_scheduling_type,
                    "contact_name": f"{loadboard_lane.pickup_first_name} - {loadboard_lane.pickup_last_name}",
                    "email": loadboard_lane.pickup_email,
                    "contact_phone": loadboard_lane.pickup_phone_number,
                    "notes": loadboard_lane.pickup_notes,
                },

                "delivery_facility": {
                    "facility_name": loadboard_lane.delivery_facility_name,
                    "time_window": loadboard_lane.delivery_appointment,
                    "scheduling_type": loadboard_lane.delivery_scheduling_type,
                    "contact_name": f"{loadboard_lane.delivery_first_name} - {loadboard_lane.delivery_last_name}",
                    "email": loadboard_lane.delivery_email,
                    "contact_phone": loadboard_lane.delivery_phone_number,
                    "notes": loadboard_lane.delivery_notes,
                }
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/exchange/ftl-lane-loadboard/bid", status_code=status.HTTP_201_CREATED) #UnTested
def place_ftl_lane_exchange_bid(
    bid_data: Exchange_FTL_Lane_Bid_Create,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        result = place_ftl_lane_bid(
            db,
            bid_data,
            current_user=current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/carrier/exchange-power-loadboard")
def exchange_power_loadboard(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    carrier = db.query(Carrier).filter(Carrier.id == company_id).first()
    if not carrier:
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")

    try:
        loadboard_shipments = (db.query(Exchange_Power_Load_Board).filter(Exchange_Power_Load_Board.status == "Open").all())

        results = []
        for loadboard_shipment in loadboard_shipments:
            trailer = loadboard_shipment.trailer  # thanks to relationship
        return {
            "power_shipments": [{
                "id": loadboard_shipment.exchange_id,
                "rate": loadboard_shipment.offer_rate,
                "trip_type": loadboard_shipment.trip_type,
                "origin": loadboard_shipment.origin_city_province,
                "pickup_date": loadboard_shipment.pickup_date,
                "pickup_window": loadboard_shipment.pickup_appointment,
                "route": loadboard_shipment.route_preview_embed,
                "destination": loadboard_shipment.destination_city_province,
                "eta_date": loadboard_shipment.eta_date,
                "eta_window": loadboard_shipment.eta_window,
                "provider": "SADC FREIGHTLINK",
                "distance": loadboard_shipment.distance,
                "transit_time": loadboard_shipment.estimated_transit_time,
                "truck_type": loadboard_shipment.required_truck_type,
                "axle_configuration": loadboard_shipment.axle_configuration,
                "minimum_weight_bracket": loadboard_shipment.minimum_weight_bracket,
                "equipment_type": trailer.equipment_type,
                "trailer_type": trailer.trailer_type,
                "trailer_length": trailer.trailer_length,
                "shipment_weight": loadboard_shipment.shipment_weight,
                "commodity": loadboard_shipment.commodity,
                "status": loadboard_shipment.status,
                "end_time": loadboard_shipment.exchange_end_time,
                "best bid": loadboard_shipment.leading_bid_amount,
                "allow_carrier_to_book_at_current_or_lower_offer_rate": loadboard_shipment.allow_carrier_to_book_at_current_or_lower_offer_rate,
            } for loadboard_shipment in loadboard_shipments]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/carrier/exchange-power-load/{id}")
def exchange_power_load(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    carrier = db.query(Carrier).filter(Carrier.id == company_id).first()
    if not carrier:
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")

    try:
        loadboard_shipment = db.query(Exchange_Power_Load_Board).filter(Exchange_Power_Load_Board.exchange_id == id).first()
        bids = db.query(Exchange_POWER_Shipment_Bid).filter(Exchange_POWER_Shipment_Bid.exchange_id == loadboard_shipment.exchange_id,
                                                            Exchange_POWER_Shipment_Bid.carrier_id == company_id).all()
        trailer = db.query(ShipperTrailer).filter(ShipperTrailer.id == loadboard_shipment.trailer_id).first()

        return {
            "power_shipment": {
                "id": loadboard_shipment.exchange_id,
                "shipment_type": loadboard_shipment.type,
                "trip_type": loadboard_shipment.trip_type,
                "load_type": loadboard_shipment.load_type,
                "origin": loadboard_shipment.origin_city_province,
                "destination": loadboard_shipment.destination_city_province,
                "distance": loadboard_shipment.distance,
                "estimated_transit_time": loadboard_shipment.estimated_transit_time,
                "route_preview_embed": loadboard_shipment.route_preview_embed,
                "required_truck_type": loadboard_shipment.required_truck_type,
                "axle_configuration": loadboard_shipment.axle_configuration,
                "minimum_weight_bracket": loadboard_shipment.minimum_weight_bracket,
                "minimum_git_cover_amount": loadboard_shipment.minimum_git_cover_amount,
                "minimum_liability_cover_amount": loadboard_shipment.minimum_liability_cover_amount,
                "is_trailer_loaded": loadboard_shipment.is_trailer_loaded,
                "shipment_weight": loadboard_shipment.shipment_weight,
                "commodity": loadboard_shipment.commodity,
                "temperature_control": loadboard_shipment.temperature_control,
                "hazardous_materials": loadboard_shipment.hazardous_materials,
                "packaging_quantity": loadboard_shipment.packaging_quantity,
                "packaging_type": loadboard_shipment.packaging_type,
                "pickup_number": loadboard_shipment.pickup_number,
                "pickup_notes": loadboard_shipment.pickup_notes,
                "delivery_number": loadboard_shipment.delivery_number,
                "delivery_notes": loadboard_shipment.delivery_notes,
                "trailer_return_notes": loadboard_shipment.trailer_return_notes,

                "trailer_information": {
                    "id": trailer.id,
                    "verification_status": trailer.is_verified,
                    "make": trailer.make,
                    "model": trailer.model,
                    "year": trailer.year,
                    "color": trailer.color,
                    "equipment_type": trailer.equipment_type,
                    "trailer_type": trailer.trailer_type,
                    "trailer_length": trailer.trailer_length,
                    "vin": trailer.vin,
                    "license_plate": trailer.license_plate,
                    "tare_weight": trailer.tare_weight,
                    "gvm_weight": trailer.gvm_weight,
                    "payload_capacity": trailer.payload_capacity,
                },

                "exchange_information": {
                    "exchange_offer": loadboard_shipment.offer_rate,
                    "leading_bid": loadboard_shipment.leading_bid_amount,
                    "payment_terms": loadboard_shipment.payment_terms,
                    "rate_per_km": loadboard_shipment.rate_per_km,
                    "rate_per_ton": loadboard_shipment.rate_per_ton,
                
                "your_bids": [{
                    "bid_amount": bid.bid_amount,
                    "bid_status": bid.status,
                    "submitted_at": bid.submitted_at,
                } for bid in bids]
                },

                "pickup_facility": {
                    "facility_name": loadboard_shipment.pickup_facility_name,
                    "pickup_date": loadboard_shipment.pickup_date,
                    "time_window": loadboard_shipment.pickup_appointment,
                    "scheduling_type": loadboard_shipment.pickup_scheduling_type,
                    "contact_name": f"{loadboard_shipment.pickup_first_name} - {loadboard_shipment.pickup_last_name}",
                    "email": loadboard_shipment.pickup_email,
                    "contact_phone": loadboard_shipment.pickup_phone_number,
                    "notes": loadboard_shipment.pickup_notes,
                },

                "delivery_facility": {
                    "facility_name": loadboard_shipment.delivery_facility_name,
                    "eta_date": loadboard_shipment.eta_date,
                    "time_window": loadboard_shipment.delivery_appointment,
                    "eta_window": loadboard_shipment.eta_window,
                    "scheduling_type": loadboard_shipment.delivery_scheduling_type,
                    "contact_name": f"{loadboard_shipment.delivery_first_name} - {loadboard_shipment.delivery_last_name}",
                    "email": loadboard_shipment.delivery_email,
                    "contact_phone": loadboard_shipment.delivery_phone_number,
                    "notes": loadboard_shipment.delivery_notes,
                }
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/carrier/exchange/power-loadboard/id/bid", status_code=status.HTTP_201_CREATED) #UnTested
def place_power_shipment_exchange_bid(
    bid_data: Exchange_POWER_Shipment_Bid_Create,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)):

    try:
        result = place_power_shipment_bid(
            db,
            bid_data,
            current_user=current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.get("/exchange/ftl-loadboard/id/all-bids", response_model=List[Exchange_FTL_Exchange_Loadboard_BidResponse]) #UnTested
def get_all_ftl_load_exchange_bids(
    bid_data: IndividualLoadboardShipmentRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    carrier = db.query(Carrier).filter(
        Carrier.id == company_id).first()
    if not carrier:
        raise ValueError("Carrier Not found")
        
    try:
        # Query all records from the "dedicated_lanes_loadboard" table
        bids = db.query(Exchange_FTL_Shipment_Bid).filter(Exchange_FTL_Shipment_Bid.exchange_id == bid_data.id).all()
        return bids
    except Exception as e:
        return {"error": str(e)}
    

###########################   ONCE-OFF POWER   #############################################
@router.get("/exchange/power-loadboard/id/all-bids", response_model=List[Exchange_Power_Exchange_Loadboard_BidResponse]) #UnTested
def get_all_power_load_exchange_bids(
    bid_data: IndividualLoadboardShipmentRequest,
    db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    carrier = db.query(Carrier).filter(
        Carrier.id == company_id).first()
    if not carrier:
        raise ValueError("Carrier Not found")
        
    try:
        # Query all records from the "dedicated_lanes_loadboard" table
        bids = db.query(Exchange_POWER_Shipment_Bid).filter(Exchange_POWER_Shipment_Bid.exchange_id == bid_data.id).all()
        return bids
    except Exception as e:
        return {"error": str(e)}
    
