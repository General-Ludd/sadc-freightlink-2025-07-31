from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.Exchange.auction import Exchange_FTL_Lane_Bid, Exchange_FTL_Shipment_Bid, Exchange_POWER_Shipment_Bid
from models.Exchange.dedicated_ftl_lane import FTL_Lane_Exchange
from models.Exchange.ftl_shipment import FTL_SHIPMENT_EXCHANGE
from models.Exchange.power_shipment import POWER_SHIPMENT_EXCHANGE
from models.brokerage.loadboards.exchange_loadboards import Exchange_Ftl_Load_Board, Exchange_Power_Load_Board
from models.spot_bookings.shipment_facility import ContactPerson, ShipmentFacility
from models.vehicle import ShipperTrailer
from schemas.exchange_bookings.auction import Accept_Bid, Exchange_FTL_Lane_ShipperSide_BidResponse, Exchange_Id, FTL_Exchange_ShipperSide_BidResponse, POWER_Exchange_ShipperSide_BidResponse
from schemas.exchange_bookings.dedicated_ftl_lane import Exchange_Ftl_Lane_Response, Exchange_Ftl_Lane_Summary_Response
from schemas.exchange_bookings.ftl_shipment import Exchange_FTL_Shipment_Response, Exchange_Ftl_Shipments_Summary_Response
from schemas.exchange_bookings.power_shipment import Exchange_Power_Shipments_Summary_Response, exchange_power_shipment_response
from services.exchange.auction import accept_a_ftl_lane_exchange_bid, accept_ftl_shipment_exchange_bid, accept_power_shipment_exchange_bid
from utils.auth import get_current_user

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

##############################################FTL EXCHANGE##################################################
@router.get("/shipper/all-exchanges")
def get_all_shipper_exchanges(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    try:
        ftl_exchanges = db.query(FTL_SHIPMENT_EXCHANGE).filter(FTL_SHIPMENT_EXCHANGE.shipper_company_id == company_id).all()
        power_exchanges = db.query(POWER_SHIPMENT_EXCHANGE).filter(POWER_SHIPMENT_EXCHANGE.shipper_company_id == company_id).all()
        ftl_lane_exchanges = db.query(FTL_Lane_Exchange).filter(FTL_Lane_Exchange.shipper_company_id == company_id).all()

        return {
            "ftl_exchanges": [{
                "id": ftl_exchange.id,
                "type": ftl_exchange.type,
                "status": ftl_exchange.auction_status,
                "origin": ftl_exchange.origin_city_province,
                "destination": ftl_exchange.destination_city_province,
                "pickup_date": ftl_exchange.pickup_date,
                #############ADD Payment Terms##########
                "number_of_bids_submitted": ftl_exchange.number_of_bids_submitted,
                "offer_rate": ftl_exchange.offer_price,
                "leading_bid": ftl_exchange.leading_bid_amount,
            } for ftl_exchange in ftl_exchanges],

            "power_exchanges": [{
                "id": power_exchange.id,
                "type": power_exchange.type,
                "status": power_exchange.auction_status,
                "origin": power_exchange.origin_city_province,
                "destination": power_exchange.destination_city_province,
                "pickup_date": power_exchange.pickup_date,
                #############ADD Payment Terms##########
                "number_of_bids_submitted": power_exchange.number_of_bids_submitted,
                "offer_rate": power_exchange.offer_rate,
                "leading_bid": power_exchange.leading_bid_amount,
            } for power_exchange in power_exchanges],

            "ftl_lane_exchanges": [{
                "id": ftl_lane_exchange.id,
                "type": ftl_lane_exchange.type,
                "status": ftl_lane_exchange.auction_status,
                "origin": ftl_lane_exchange.origin_city_province,
                "destination": ftl_lane_exchange.destination_city_province,
                "contract_period": f"{ftl_lane_exchange.start_date} - {ftl_lane_exchange.end_date}",
                "recurrence_frequency": ftl_lane_exchange.recurrence_frequency,
                "shipments_per_interval": ftl_lane_exchange.shipments_per_interval,
                "total_shipments": ftl_lane_exchange.total_shipments,
                "payment_terms": ftl_lane_exchange.payment_terms,
                "per_shipment_offer": ftl_lane_exchange.per_shipment_offer_rate,
                "contract_offer": ftl_lane_exchange.contract_offer_rate,
                "number_of_bids_submitted": ftl_lane_exchange.number_of_bids_submitted,
                "leading_per_shipment_bid": ftl_lane_exchange.leading_per_shipment_bid_amount,
                "leading_contract_bid": ftl_lane_exchange.leading_contract_bid_amount
            } for ftl_lane_exchange in ftl_lane_exchanges]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("shipper/ftl-exchange/id")
def get_single_ftl_exchange_details(
    shipment_data: Exchange_Id,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    try:
        exchange = db.query(FTL_SHIPMENT_EXCHANGE).filter(FTL_SHIPMENT_EXCHANGE.id == shipment_data.id,
                                                          FTL_SHIPMENT_EXCHANGE.shipper_company_id == company_id).first()
        
        pickup_facility = db.query(ShipmentFacility).filter_by(id=exchange.pickup_facility_id).first()
        delivery_facility = db.query(ShipmentFacility).filter_by(id=exchange.delivery_facility_id).first()

        pickup_contact = db.query(ContactPerson).filter_by(id=pickup_facility.contact_person).first() if pickup_facility else None
        delivery_contact = db.query(ContactPerson).filter_by(id=delivery_facility.contact_person).first() if delivery_facility else None
        
        bids = db.query(Exchange_FTL_Shipment_Bid).filter(Exchange_FTL_Shipment_Bid.exchange_id == exchange.id).all()

        return {
            "id": exchange.id,
            "exchange_status": exchange.auction_status,
            "type": exchange.type,
            "trip_type": exchange.trip_type,
            "load_type": exchange.load_type,
            "booked_by": exchange.shipper_user_id,
            "required_truck_type": exchange.required_truck_type,
            "equipment_type": exchange.equipment_type,
            "trailer_type": exchange.trailer_type,
            "trailer_length": exchange.trailer_length,
            "minimum_weight_bracket": exchange.minimum_weight_bracket,
            "minimum_git_cover": exchange.minimum_git_cover_amount,
            "minimum_liability_cover": exchange.minimum_liability_cover_amount,
            "origin_address": exchange.complete_origin_address,
            "destination_address": exchange.complete_destination_address,
            "pickup_date": exchange.pickup_date,
            "priority_level": exchange.priority_level,
            "customer_reference": exchange.customer_reference_number,
            "shipment_weight": exchange.shipment_weight,
            "commodity": exchange.commodity,
            "temperature_control": exchange.temperature_control,
            "hazardous_materials": exchange.hazardous_materials,
            "packaging_quantity": exchange.packaging_quantity,
            "packaging_type": exchange.packaging_type,
            "pickup_number": exchange.pickup_number,
            "delivery_number": exchange.delivery_number,
            "pickup_notes": exchange.pickup_notes,
            "delivery_notes": exchange.delivery_notes,
            "distance": exchange.distance,
            "estimated_transit_time": exchange.estimated_transit_time,
            "offer_rate": exchange.offer_price,
            "suggested_rate": exchange.suggested_price,
            "winning_bid_amount": exchange.winning_bid_price,
            "trip_savings": exchange.trip_savings,
            "exchange_saving": exchange.exchange_savings,
            "route_preview_embed": exchange.route_preview_embed,
            "created_at": exchange.created_at,

            "exchange_finance": {
                "offer_rate": exchange.offer_price,
                "suggested_rate": exchange.suggested_price,
                "best_offer_rate": exchange.leading_bid_amount,
                "payment_terms": exchange.payment_terms,
                "bids": [{
                    "id": bid.id,
                    "status": bid.status,
                    "carrier": bid.carrier_id,
                    "amount": bid.baked_bid_amount,
                    "submitted_at": bid.submitted_at,
                } for bid in bids],

            "pickup_facility": {
                "facility_name": pickup_facility.name if pickup_facility else None,
                "address": pickup_facility.address if pickup_facility else None,
                "time_window": f"{pickup_facility.start_time} - {pickup_facility.end_time}",
                "contact_name": f"{pickup_contact.first_name} - {pickup_contact.last_name}" if pickup_contact else None,
                "email": pickup_contact.email if pickup_contact else None,
                "contact_phone": pickup_contact.phone_number if pickup_contact else None,
                "notes": pickup_facility.facility_notes if pickup_facility else None,
            } if pickup_facility else None,

            "delivery_facility": {
                "facility_name": delivery_facility.name if pickup_facility else None,
                "address": delivery_facility.address if delivery_facility else None,
                "time_window": f"{delivery_facility.start_time} - {delivery_facility.end_time}",
                "contact_name": f"{delivery_contact.first_name} - {delivery_contact.last_name}" if pickup_contact else None,
                "email": delivery_contact.email if pickup_contact else None,
                "contact_phone": delivery_contact.phone_number if delivery_contact else None,
                "notes": delivery_facility.facility_notes if delivery_facility else None,
            } if delivery_facility else None,

            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("shipper/power-exchange/id")
def get_single_power_exchange_details(
    shipment_data: Exchange_Id,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    try:
        exchange = db.query(POWER_SHIPMENT_EXCHANGE).filter(POWER_SHIPMENT_EXCHANGE.id == shipment_data.id,
                                                          POWER_SHIPMENT_EXCHANGE.shipper_company_id == company_id).first()
        
        trailer = db.query(ShipperTrailer).filter(ShipperTrailer.id == exchange.trailer_id).first()
        
        pickup_facility = db.query(ShipmentFacility).filter_by(id=exchange.pickup_facility_id).first()
        delivery_facility = db.query(ShipmentFacility).filter_by(id=exchange.delivery_facility_id).first()

        pickup_contact = db.query(ContactPerson).filter_by(id=pickup_facility.contact_person).first() if pickup_facility else None
        delivery_contact = db.query(ContactPerson).filter_by(id=delivery_facility.contact_person).first() if delivery_facility else None
        
        bids = db.query(Exchange_FTL_Shipment_Bid).filter(Exchange_FTL_Shipment_Bid.exchange_id == exchange.id).all()

        return {
            "id": exchange.id,
            "exchange_status": exchange.auction_status,
            "type": exchange.type,
            "trip_type": exchange.trip_type,
            "load_type": exchange.load_type,
            "booked_by": exchange.shipper_user_id,
            "required_truck_type": exchange.required_truck_type,
            "axle_configuration": exchange.axle_configuration,
            "trailer_id": exchange.trailer_id,
            "minimum_weight_bracket": exchange.minimum_weight_bracket,
            "minimum_git_cover": exchange.minimum_git_cover_amount,
            "minimum_liability_cover": exchange.minimum_liability_cover_amount,
            "origin_address": exchange.complete_origin_address,
            "destination_address": exchange.complete_destination_address,
            "trailer_return_instructions": exchange.trailer_return_instructions,
            "pickup_date": exchange.pickup_date,
            "priority_level": exchange.priority_level,
            "customer_reference": exchange.customer_reference_number,
            "shipment_weight": exchange.shipment_weight,
            "commodity": exchange.commodity,
            "temperature_control": exchange.temperature_control,
            "hazardous_materials": exchange.hazardous_materials,
            "packaging_quantity": exchange.packaging_quantity,
            "packaging_type": exchange.packaging_type,
            "pickup_number": exchange.pickup_number,
            "delivery_number": exchange.delivery_number,
            "pickup_notes": exchange.pickup_notes,
            "delivery_notes": exchange.delivery_notes,
            "distance": exchange.distance,
            "estimated_transit_time": exchange.estimated_transit_time,
            "offer_rate": exchange.offer_rate,
            "suggested_rate": exchange.suggested_rate,
            "winning_bid_amount": exchange.winning_bid_price,
            "trip_savings": exchange.trip_savings,
            "exchange_saving": exchange.exchange_savings,
            "route_preview_embed": exchange.route_preview_embed,
            "created_at": exchange.created_at,

            "trailer_information": {
                "id": trailer.id,
                "make": trailer.make,
                "model": trailer.model,
                "year": trailer.year,
                "color": trailer.color,
                "license_plate": trailer.license_plate,
                "vin": trailer.vin,
                "tare_weight": trailer.tare_weight,
                "gvm_weight": trailer.gvm_weight,
                "trailer_equipment_type": trailer.equipment_type,
                "trailer_type": trailer.trailer_type,
                "trailer_length": trailer.trailer_length,
            },

            "exchange_finance": {
                "offer_rate": exchange.offer_rate,
                "suggested_rate": exchange.suggested_rate,
                "best_offer_rate": exchange.leading_bid_amount,
                "payment_terms": exchange.payment_terms,
                "bids": [{
                    "id": bid.id,
                    "status": bid.status,
                    "carrier": bid.carrier_id,
                    "amount": bid.baked_bid_amount,
                    "submitted_at": bid.submitted_at,
                } for bid in bids],

            "pickup_facility": {
                "facility_name": pickup_facility.name if pickup_facility else None,
                "address": pickup_facility.address if pickup_facility else None,
                "time_window": f"{pickup_facility.start_time} - {pickup_facility.end_time}",
                "contact_name": f"{pickup_contact.first_name} - {pickup_contact.last_name}" if pickup_contact else None,
                "email": pickup_contact.email if pickup_contact else None,
                "contact_phone": pickup_contact.phone_number if pickup_contact else None,
                "notes": pickup_facility.facility_notes if pickup_facility else None,
            } if pickup_facility else None,

            "delivery_facility": {
                "facility_name": delivery_facility.name if delivery_facility else None,
                "address": delivery_facility.address if delivery_facility else None,
                "time_window": f"{delivery_facility.start_time} - {delivery_facility.end_time}",
                "contact_name": f"{delivery_contact.first_name} - {delivery_contact.last_name}" if pickup_contact else None,
                "email": delivery_contact.email if pickup_contact else None,
                "contact_phone": delivery_contact.phone_number if delivery_contact else None,
                "notes": delivery_facility.facility_notes if delivery_facility else None,
            } if delivery_facility else None,

            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shipper/ftl-lane-exchange/id")
def shipper_single_ftl_lane_exchange_detials(
    shipment_data: Exchange_Id,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    try:
        exchange = db.query(FTL_Lane_Exchange).filter(FTL_Lane_Exchange.id == shipment_data.id,
                                                          FTL_Lane_Exchange.shipper_company_id == company_id).first()

        bids = db.query(Exchange_FTL_Lane_Bid).filter(Exchange_FTL_Lane_Bid.exchange_id == exchange.id,
                                                      Exchange_FTL_Lane_Bid.type == exchange.type).all()

        pickup_facility = db.query(ShipmentFacility).filter_by(id=exchange.pickup_facility_id).first()
        delivery_facility = db.query(ShipmentFacility).filter_by(id=exchange.delivery_facility_id).first()

        pickup_contact = db.query(ContactPerson).filter_by(id=pickup_facility.contact_person).first() if pickup_facility else None
        delivery_contact = db.query(ContactPerson).filter_by(id=delivery_facility.contact_person).first() if delivery_facility else None

        return {
                "exchange_lane_details": {
                    "id": exchange.id,
                    "type": exchange.type,
                    "trip_type": exchange.trip_type,
                    "load_type": exchange.load_type,
                    "required_truck_type": exchange.required_truck_type,
                    "equipment_type": exchange.equipment_type,
                    "trailer_type": exchange.trailer_type,
                    "trailer_length": exchange.trailer_length,
                    "minimum_weight_bracket": exchange.minimum_weight_bracket,
                    "priority_level": exchange.priority_level,
                    "average_shipment_weight": exchange.average_shipment_weight,
                    "commodity": exchange.commodity,
                    "temperature_control": exchange.temperature_control,
                    "hazardous_materials": exchange.hazardous_materials,
                    "minimum_git_cover": exchange.minimum_git_cover_amount,
                    "minimum_liability_cover": exchange.minimum_liability_cover_amount,
                    "customer_reference": exchange.customer_reference_number,
                    "packaging_type": exchange.packaging_type,
                    "packaging_quantity": exchange.packaging_quantity,
                    "pickup_number": exchange.pickup_number,
                    "delivery_number": exchange.delivery_number,
                    "distance": exchange.distance,
                    "estimated_transit_time": exchange.estimated_transit_time,
                    "origin_address": exchange.origin_address,
                    "destination_address": exchange.destination_address,
                    "pickup_notes": exchange.pickup_notes,
                    "delivery_notes": exchange.delivery_notes,
                    "start_date": exchange.start_date,
                    "end_date": exchange.end_date,
                    "created": exchange.created_at,

                    "financial_information": {
                        "suggested_per_shipment_rate": exchange.suggested_per_shipment_rate,
                        "suggested_contract_rate": exchange.suggested_contract_rate,
                        "per_shipment_offer_rate": exchange.per_shipment_offer_rate,
                        "contract_offer_rate": exchange.contract_offer_rate,
                        "per_shipment_savings": (exchange.suggested_per_shipment_rate - exchange.per_shipment_offer_rate),
                        "contract_savings": (exchange.suggested_contract_rate - exchange.contract_offer_rate),
                        "trip_savings": (exchange.per_shipment_offer_rate - exchange.leading_per_shipment_bid_amount),
                        "exchange_savings": (exchange.contract_offer_rate - exchange.leading_contract_bid_amount)
                    },

                    "exchange_finance": {
                        "suggested_per_shipment_rate": exchange.suggested_per_shipment_rate,
                        "suggested_contract_rate": exchange.suggested_contract_rate,
                        "per_shipment_offer_rate": exchange.per_shipment_offer_rate,
                        "contract_offer_rate": exchange.contract_offer_rate,
                        "leading_per_shipment_bid": exchange.leading_per_shipment_bid_amount,
                        "leading_contract_bid": exchange.leading_contract_bid_amount,
                        "number_of_bids": exchange.number_of_bids_submitted,
                        "payment_terms": exchange.payment_terms,

                        "bid": [{
                            "id": bid.id,
                            "status": bid.status,
                            "carrier_id": bid.carrier_id,
                            "carrier_name": f"SADC FREIGHTLINK Carrier-{bid.carrier_id}",
                            "per_shipment_rate": bid.baked_per_shipment_bid_amount,
                            "contract_rate": bid.baked_contract_bid_amount,
                            "submitted_at": bid.submitted_at,
                        } for bid in bids]
                    },
                    
                    "lane_contract_details": {
                        "recurrence_frequency": exchange.recurrence_frequency,
                        "recurrence_days": exchange.recurrence_days,
                        "shipments_per_interval": exchange.shipments_per_interval,
                        "total_shipments": exchange.total_shipments,
                        "per_shipment_offer_rate": exchange.per_shipment_offer_rate,
                        "contract_offer_rate": exchange.contract_offer_rate,
                        "payment_terms": exchange.payment_terms,
                    },

            "pickup_facility": {
                "facility_name": pickup_facility.name if pickup_facility else None,
                "address": pickup_facility.address if pickup_facility else None,
                "time_window": f"{pickup_facility.start_time} - {pickup_facility.end_time}",
                "scheduling_type": pickup_facility.scheduling_type,
                "contact_name": f"{pickup_contact.first_name} - {pickup_contact.last_name}" if pickup_contact else None,
                "email": pickup_contact.email if pickup_contact else None,
                "contact_phone": pickup_contact.phone_number if pickup_contact else None,
                "notes": pickup_facility.facility_notes if pickup_facility else None,
            } if pickup_facility else None,

            "delivery_facility": {
                "facility_name": delivery_facility.address.name if delivery_facility else None,
                "address": delivery_facility.address if delivery_facility else None,
                "time_window": f"{delivery_facility.start_time} - {delivery_facility.end_time}",
                "scheduling_type": delivery_facility.scheduling_type,
                "contact_name": f"{delivery_contact.first_name} - {delivery_contact.last_name}" if pickup_contact else None,
                "email": delivery_contact.email if pickup_contact else None,
                "contact_phone": delivery_contact.phone_number if delivery_contact else None,
                "notes": delivery_facility.facility_notes if delivery_facility else None,
            } if delivery_facility else None,

                }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/shipper/ftl/all-exchanges", response_model=List[Exchange_Ftl_Shipments_Summary_Response]) #UnTested
def get_all_shipper_ftl_exchanges(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        exchanges = db.query(FTL_SHIPMENT_EXCHANGE).filter(
            FTL_SHIPMENT_EXCHANGE.shipper_company_id == company_id
        ).all()

        if not exchanges:
            raise HTTPException(
                status_code=404,
                detail=f"Shipments linked to carrier ID {id} not found or not authorized"
            )
        
        return exchanges

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/exchange/ftl-exchange/id", response_model=Exchange_FTL_Shipment_Response) #UnTested
def shipper_get_individual_ftl_exchange(
    bid_data: Exchange_Id,
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
        
    try:
        # Query all records from the "dedicated_lanes_loadboard" table
        exchange = db.query(FTL_SHIPMENT_EXCHANGE).filter(FTL_SHIPMENT_EXCHANGE.id == bid_data.id).all()
        return exchange
    except Exception as e:
        return {"error": str(e)}

@router.get("/exchange/ftl-exchange-id/all-bids", response_model=List[FTL_Exchange_ShipperSide_BidResponse]) #UnTested
def shipper_get_all_ftl_exchange_bids(
    bid_data: Exchange_Id,
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
        
    try:
        # Query all records from the "dedicated_lanes_loadboard" table
        bids = db.query(Exchange_FTL_Shipment_Bid).filter(Exchange_FTL_Shipment_Bid.exchange_id == bid_data.id).all()
        return bids
    except Exception as e:
        return {"error": str(e)}
    
@router.post("/exchange/ftl-exchange-id/accept-bid-id", status_code=status.HTTP_201_CREATED) #UnTested
def accept_ftl_exchange_bid(
    bid_data: Accept_Bid,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        result = accept_ftl_shipment_exchange_bid(
            db,
            bid_data,
            current_user=current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
##############################################POWER EXCHANGE################################################

@router.get("/shipper/power/all-exchanges", response_model=List[Exchange_Power_Shipments_Summary_Response]) #UnTested
def get_all_shipper_power_exchanges(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        exchanges = db.query(POWER_SHIPMENT_EXCHANGE).filter(
            POWER_SHIPMENT_EXCHANGE.shipper_company_id == company_id
        ).all()

        if not exchanges:
            raise HTTPException(
                status_code=404,
                detail=f"Shipments linked to carrier ID {id} not found or not authorized"
            )
        
        return exchanges

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/exchange/power-exchange/id", response_model=exchange_power_shipment_response) #UnTested
def shipper_get_individual_power_exchange(
    bid_data: Exchange_Id,
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
        
    try:
        # Query all records from the "dedicated_lanes_loadboard" table
        exchange = db.query(POWER_SHIPMENT_EXCHANGE).filter(POWER_SHIPMENT_EXCHANGE.id == bid_data.id).all()
        return exchange
    except Exception as e:
        return {"error": str(e)}

@router.get("/exchange/power-exchange-id/all-bids", response_model=List[POWER_Exchange_ShipperSide_BidResponse]) #UnTested
def shipper_get_all_power_exchange_bids(
    bid_data: Exchange_Id,
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
        
    try:
        # Query all records from the "dedicated_lanes_loadboard" table
        bids = db.query(Exchange_POWER_Shipment_Bid).filter(Exchange_POWER_Shipment_Bid.exchange_id == bid_data.id).all()
        return bids
    except Exception as e:
        return {"error": str(e)}
    
@router.post("/exchange/power-exchange-id/accept-bid-id", status_code=status.HTTP_201_CREATED) #UnTested
def accept_power_exchange_bid(
    bid_data: Accept_Bid,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        result = accept_power_shipment_exchange_bid(
            db,
            bid_data,
            current_user=current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

####################################################FTL LANE EXCHANGES MANAGEMENTS###########################
@router.get("/exchange/ftl-lane/all-exchanges", response_model=List[Exchange_Ftl_Lane_Summary_Response]) #UnTested
def get_all_shipper_ftl_lane_exchanges(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        exchanges = db.query(FTL_Lane_Exchange).filter(
            FTL_Lane_Exchange.shipper_company_id == company_id
        ).all()

        if not exchanges:
            raise HTTPException(
                status_code=404,
                detail=f"Shipments linked to carrier ID {id} not found or not authorized"
            )
        return exchanges

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/exchange/ftl-lane/id", response_model=Exchange_Ftl_Lane_Response) #UnTested
def shipper_get_individual_ftl_lane_exchange(
    bid_data: Exchange_Id,
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
        
    try:
        # Query all records from the "dedicated_lanes_loadboard" table
        exchange = db.query(FTL_Lane_Exchange).filter(FTL_Lane_Exchange.id == bid_data.id).all()
        return exchange
    except Exception as e:
        return {"error": str(e)}

@router.get("/exchange/ftl-lane-id/all-bids", response_model=List[Exchange_FTL_Lane_ShipperSide_BidResponse]) #UnTested
def shipper_get_all_ftl_lane_exchange_bids(
    bid_data: Exchange_Id,
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
        
    try:
        # Query all records from the "dedicated_lanes_loadboard" table
        bids = db.query(Exchange_FTL_Lane_Bid).filter(Exchange_FTL_Lane_Bid.exchange_id == bid_data.id).all()
        return bids
    except Exception as e:
        return {"error": str(e)}

@router.post("/exchange/ftl-lane-exchange-id/accept-bid-id", status_code=status.HTTP_201_CREATED) #UnTested
def accept_ftl_lane_exchange_bid(
    bid_data: Accept_Bid,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        result = accept_a_ftl_lane_exchange_bid(
            db,
            bid_data,
            current_user=current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.post("/exchange/ftl/id/cancel")
def cancel_ftl_shipment_exchange(
    exchange_data: Exchange_Id,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    assert "company_id" in current_user, "Missing company_id in current_user"

    # Step 1: Load Shipment Exchange
    shipment = db.query(FTL_SHIPMENT_EXCHANGE).filter(FTL_SHIPMENT_EXCHANGE.id == exchange_data.id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment exchange not found.")

    # Step 2: Check if exchange is open
    if shipment.auction_status != "Open":
        raise HTTPException(status_code=403, detail="Cannot cancel a closed exchange. Please contact support.")

    # Step 3: Update Loadboard Entry Status
    loadboard_entry = db.query(Exchange_Ftl_Load_Board).filter(
        Exchange_Ftl_Load_Board.exchange_id == shipment.id
    ).first()
    if loadboard_entry:
        loadboard_entry.status = "Cancelled"
        db.add(loadboard_entry)
        db.commit()

    return {"message": f"FTL Shipment Exchange ID {exchange_data.id} has been cancelled successfully."}
    
@router.post("/exchange/power/cancel/id")
def cancel_ftl_shipment_exchange(
    exchange_data: Exchange_Id,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    assert "company_id" in current_user, "Missing company_id in current_user"

    # Step 1: Load Shipment Exchange
    shipment = db.query(POWER_SHIPMENT_EXCHANGE).filter(POWER_SHIPMENT_EXCHANGE.id == exchange_data.id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment exchange not found.")

    # Step 2: Check if exchange is open
    if shipment.auction_status != "Open":
        raise HTTPException(status_code=403, detail="Cannot cancel a closed exchange. Please contact support.")

    # Step 3: Update Loadboard Entry Status
    loadboard_entry = db.query(Exchange_Power_Load_Board).filter(
        Exchange_Power_Load_Board.exchange_id == shipment.id
    ).first()
    if loadboard_entry:
        loadboard_entry.status = "Cancelled"
        db.add(loadboard_entry)
        db.commit()

    return {"message": f"FTL Shipment Exchange ID {exchange_data.id} has been cancelled successfully."}