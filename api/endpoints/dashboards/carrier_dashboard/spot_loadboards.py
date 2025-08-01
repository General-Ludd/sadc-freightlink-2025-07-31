from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.Exchange.auction import Exchange_FTL_Lane_Bid, Exchange_FTL_Shipment_Bid, Exchange_POWER_Shipment_Bid
from models.brokerage.loadboard import Dedicated_lanes_LoadBoard, Ftl_Load_Board, Power_Load_Board
from models.brokerage.loadboards.exchange_loadboards import Exchange_Ftl_Lane_LoadBoard, Exchange_Ftl_Load_Board, Exchange_Power_Load_Board
from models.carrier import Carrier
from models.spot_bookings.shipment_facility import ContactPerson, ShipmentFacility
from schemas.brokerage.loadboard import AssignShipmentRequest, FTL_Lane_LoadBoard_Summary_Response, FTL_Lane_Loadboard_Individual_Shipment_Response, Individual_lane_id, IndividualLoadboardShipmentRequest, IndividualSpotPowerLoadboardShipmentResponse, SpotFTLLoadBoardSummaryResponse, SpotPowerLoadBoardSummaryResponse
from schemas.shipment_facility import FacilityContactPersonResponse
from schemas.user import DriverCreate, DriverResponse
from schemas.vehicle import TrailerCreate, TrailerResponse, VehicleCreate, VehicleResponse, VehicleUpdate
from services.brokerage.carrier_loadboard_service import assign_spot_ftl_lane_to_carrier, assign_spot_ftl_shipment_to_carrier, assign_spot_power_shipment_to_carrier
from services.carrier_service import fleet_create_driver
from services.carrier_dashboards import assign_primary_driver, assign_trailer_to_vehicle
from services.vehicle_service import create_trailer, create_vehicle
from utils.auth import get_current_user, verify_password
from utils.jwt_handler import create_access_token
from models.user import CarrierUser, Driver
from models.vehicle import ShipperTrailer, Trailer, Vehicle
from schemas.auth import LoginRequest, LoginResponse

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/spot/ftl-loadboard", response_model=List[SpotFTLLoadBoardSummaryResponse]) #UnTested
def get_all_spot_ftl_loads(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
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
    if not carrier or not carrier.is_verified or carrier.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")
        
    try:
        # Query all records from the "dedicated_lanes_loadboard" table
        shipments = db.query(Ftl_Load_Board).filter(Ftl_Load_Board.status == "Available").all()
        return shipments
    except Exception as e:
        return {"error": str(e)}
    
@router.post("/spot/loadboard/accept-ftl-shipment", status_code=status.HTTP_202_ACCEPTED) #UnTested
def accept_spot_ftl_shipment_from_loadboard(
    shipment_data: AssignShipmentRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        result = assign_spot_ftl_shipment_to_carrier(db, shipment_data, current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.get("/dedicated-ftl-lane-loadboard", response_model=List[FTL_Lane_LoadBoard_Summary_Response]) #UnTested
def get_all_spot_ftl_loads(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
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
    if not carrier or not carrier.is_verified or carrier.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")
        
    try:
        # Query all records from the "dedicated_lanes_loadboard" table
        ftl_lanes = db.query(Dedicated_lanes_LoadBoard).filter(Dedicated_lanes_LoadBoard.status == "Available").all()
        return ftl_lanes
    except Exception as e:
        return {"error": str(e)}

@router.get("/spot/ftl-lane-loadboard/id", response_model=FTL_Lane_Loadboard_Individual_Shipment_Response) #UnTested
def loadboard_get_individual_ftl_lane(
    loadboard_data: IndividualLoadboardShipmentRequest,
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
    carrier = db.query(Carrier).filter(Carrier.id == company_id).first()
    if not carrier or not carrier.is_verified or carrier.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")
        
    try:
        # Query all records from the "dedicated_lanes_loadboard" table
        lane = db.query(Dedicated_lanes_LoadBoard).filter(Dedicated_lanes_LoadBoard.shipment_id == loadboard_data.id).first()
        return lane
    except Exception as e:
        return {"error": str(e)}

@router.post("/spot/loadboard/accept-ftl-lane", status_code=status.HTTP_202_ACCEPTED) #UnTested
def accept_spot_ftl_lane_from_loadboard(
    shipment_data: Individual_lane_id,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        result = assign_spot_ftl_lane_to_carrier(db, shipment_data, current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    

@router.get("/shipment/facility-contact-person/{id}", response_model=FacilityContactPersonResponse) #UnTested
def get__shipment_facility_contact_person(
    id: int,
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
        facility_contact_person = db.query(ContactPerson).filter(
            ContactPerson.id == id
        ).first()

        if not facility_contact_person:
            raise HTTPException(
                status_code=404,
                detail=f"User with ID {id} not found or not authorized"
            )

        return facility_contact_person

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/spot/power-loadboard", response_model=List[SpotPowerLoadBoardSummaryResponse]) #UnTested
def get_all_spot_power_loads(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
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
    if not carrier or not carrier.is_verified or carrier.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")
        
    try:
        # Query all records from the "dedicated_lanes_loadboard" table
        shipments = db.query(Power_Load_Board).filter(Power_Load_Board.status == "Available").all()
        return shipments
    except Exception as e:
        return {"error": str(e)}
    

@router.get("/spot/power-loadboard/id", response_model=IndividualSpotPowerLoadboardShipmentResponse) #UnTested
def loadboard_get_individual_spot_power_load(
    loadboard_data: IndividualLoadboardShipmentRequest,
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
    carrier = db.query(Carrier).filter(Carrier.id == company_id).first()
    if not carrier or not carrier.is_verified or carrier.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")
        
    try:
        # Query all records from the "dedicated_lanes_loadboard" table
        shipment = db.query(Power_Load_Board).filter(Power_Load_Board.shipment_id == loadboard_data.id).first()
        return shipment
    except Exception as e:
        return {"error": str(e)}
    
@router.post("/spot/loadboard/accept-power-shipment", status_code=status.HTTP_202_ACCEPTED) #Tested
def accept_spot_power_shipment_from_loadboard(
    shipment_data: AssignShipmentRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        result = assign_spot_power_shipment_to_carrier(db, shipment_data, current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/carrier/ftl-loadboard")
def spot_ftl_loadboard(
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
    if not carrier or not carrier.is_verified or carrier.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")

    try:
        loadboard_shipments = db.query(Ftl_Load_Board).filter(Ftl_Load_Board.status == "Available").all()

        return [{
            "id": loadboard_shipment.shipment_id,
            "rate": loadboard_shipment.shipment_rate,
            "trip_type": loadboard_shipment.trip_type,
            "origin": loadboard_shipment.origin_city_province,
            "pickup_date": loadboard_shipment.pickup_date,
            "pickup_window": loadboard_shipment.pickup_appointment,
            "route": loadboard_shipment.route_preview_embed,
            "destination": loadboard_shipment.destination_city_province,
            "eta_date": loadboard_shipment.eta_date,
            "eta_window": loadboard_shipment.eta_window,
            "distance": loadboard_shipment.distance,
            "rate_per_km": loadboard_shipment.rate_per_km,
            "truck_type": loadboard_shipment.required_truck_type,
            "equipment_type": loadboard_shipment.equipment_type,
            "trailer_type": loadboard_shipment.trailer_type,
            "trailer_length": loadboard_shipment.trailer_length,
            "min_weight_bracket": loadboard_shipment.minimum_weight_bracket,
            "commodity": loadboard_shipment.commodity,
        } for loadboard_shipment in loadboard_shipments]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/carrier/ftl-lane-loadboard")
def spot_ftl_lane_loadboard(
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
    if not carrier or not carrier.is_verified or carrier.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")

    try:
        loadboard_lanes = db.query(Dedicated_lanes_LoadBoard).filter(Dedicated_lanes_LoadBoard.status == "Available").all()

        return [{
            "id": loadboard_lane.shipment_id,
            "status": loadboard_lane.status,
            "lane_trip_type": loadboard_lane.trip_type,
            "lane_load_type": loadboard_lane.load_type,
            "origin": loadboard_lane.origin_city_province,
            "destination": loadboard_lane.destination_city_province,
            "distance": loadboard_lane.distance,
            "truck_type": loadboard_lane.required_truck_type,
            "equipment_type": loadboard_lane.equipment_type,
            "trailer": loadboard_lane.trailer_type,
            "length": loadboard_lane.trailer_length,
            "min_weight_bracket": loadboard_lane.minimum_weight_bracket,
            "commodity": loadboard_lane.commodity,
            "packaging_type": loadboard_lane.packaging_type,
            "shipment_weight": loadboard_lane.average_shipment_weight,
            "start_date": loadboard_lane.start_date,
            "end_date": loadboard_lane.end_date,
            "frequency": loadboard_lane.recurrence_frequency,
            "shipments_per_interval": loadboard_lane.shipments_per_interval,
            "total_shipments": loadboard_lane.total_shipments,
            "per_shipment_rate": loadboard_lane.rate_per_shipment,
            "contract_rate": loadboard_lane.contract_rate
        } for loadboard_lane in loadboard_lanes]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/carrier/power-loadboard")
def spot_power_loadboard(
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
    if not carrier or not carrier.is_verified or carrier.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")

    try:
        loadboard_shipments = db.query(Power_Load_Board).filter(Power_Load_Board.status == "Available").all()

        return [{
            "id": loadboard_shipment.shipment_id,
            "rate": loadboard_shipment.shipment_rate,
            "load_type": loadboard_shipment.load_type,
            "origin": loadboard_shipment.origin_city_province,
            "pickup_date": loadboard_shipment.pickup_date,
            "pickup_window": loadboard_shipment.pickup_appointment,
            "route": loadboard_shipment.route_preview_embed,
            "destination": loadboard_shipment.destination_city_province,
            "eta_date": loadboard_shipment.eta_date,
            "eta_window": loadboard_shipment.eta_window,
            "distance": loadboard_shipment.distance,
            "rate_per_km": loadboard_shipment.rate_per_km,
            "truck_type": loadboard_shipment.required_truck_type,
            "axle_configuration": loadboard_shipment.axle_configuration,
            "equipment": loadboard_shipment.trailer_equipment_type,
            "trailer_type": loadboard_shipment.trailer_type,
            "min_weight_bracket": loadboard_shipment.minimum_weight_bracket,
        } for loadboard_shipment in loadboard_shipments]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

##########################################Exchange Loadboards##############################################
@router.post("/carrier/exchange-ftl-loadboard")
def exchange_ftl_loadboard(
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
    if not carrier or not carrier.is_verified or carrier.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")

    try:
        loadboard_shipments = db.query(Exchange_Ftl_Load_Board).filter(Exchange_Ftl_Load_Board.status == "Open").all()

        return [{
            "id": loadboard_shipment.exchange_id,
            "rate": loadboard_shipment.shipment_rate,
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
            "equipment_type": loadboard_shipment.equipment_type,
            "trailer_type": loadboard_shipment.trailer_type,
            "trailer_length": loadboard_shipment.trailer_length,
            "weight": loadboard_shipment.shipment_weight,
            "commodity": loadboard_shipment.commodity,
            "status": loadboard_shipment.status,
            "best bid": loadboard_shipment.leading_bid_amount,
            "accept_lower_bids": loadboard_shipment.automatically_accept_lower_bid,
        } for loadboard_shipment in loadboard_shipments]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/carrier/exchange-ftl-load/id")
def exchange_ftl_load(
    loadboard_data: IndividualLoadboardShipmentRequest,
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
    if not carrier or not carrier.is_verified or carrier.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")

    try:
        loadboard_shipment = db.query(Exchange_Ftl_Load_Board).filter(Exchange_Ftl_Load_Board.exchange_id == loadboard_data.id).first()
        bids = db.query(Exchange_FTL_Shipment_Bid).filter(Exchange_FTL_Shipment_Bid.carrier_id == company_id).all()

        return {
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
            "end_time": loadboard_shipment.end_time,

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

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/carrier/exchange-ftl-lane-loadboard")
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
    if not carrier or not carrier.is_verified or carrier.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")

    try:
        loadboard_shipments = db.query(Exchange_Ftl_Lane_LoadBoard).filter(Exchange_Ftl_Lane_LoadBoard.status == "Open").all()

        return [{
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
            "exchange_end_time": loadboard_shipment.end_time,
            "number_of_bidders": loadboard_shipment.number_of_bids_submitted,
            "opening_contract_offer": loadboard_shipment.contract_offer_rate,
            "opening_per_shipment_offer": loadboard_shipment.per_shipment_offer_rate,
        } for loadboard_shipment in loadboard_shipments]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/carrier/exchange-ftl-lane/id")
def exchange_ftl_lane(
    loadboard_data: IndividualLoadboardShipmentRequest,
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
    if not carrier or not carrier.is_verified or carrier.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")

    try:
        loadboard_lane = db.query(Exchange_Ftl_Lane_LoadBoard).filter(Exchange_Ftl_Lane_LoadBoard.exchange_id == loadboard_data.id).first()
        bids = db.query(Exchange_FTL_Lane_Bid).filter(Exchange_FTL_Lane_Bid.carrier_id == company_id).all()

        return {
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
            "end_time": loadboard_lane.end_time,

            "exchange_information": {
                "opening_per_shipment_offer": loadboard_lane.per_shipment_offer_rate,
                "opening_contract_offer": loadboard_lane.contract_offer_rate,
                "leading_per_shipment_bid": loadboard_lane.leading_per_shipment_offer_bid_amount,
                "leading_contract_bid": loadboard_lane.leading_contract_offer_bid_amount,
                "active_bidders": loadboard_lane.number_of_bids_submitted,
                "auction_end_time": loadboard_lane.end_time,
            
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

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/carrier/exchange-power-loadboard")
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
    if not carrier or not carrier.is_verified or carrier.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")

    try:
        loadboard_shipments = db.query(Exchange_Power_Load_Board).filter(Exchange_Power_Load_Board.status == "Open").all()

        return [{
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
            "weight": loadboard_shipment.shipment_weight,
            "commodity": loadboard_shipment.commodity,
            "status": loadboard_shipment.status,
            "best bid": loadboard_shipment.leading_bid_amount,
            "accept_lower_bids": loadboard_shipment.automatically_accept_lower_bid,
        } for loadboard_shipment in loadboard_shipments]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/carrier/exchange-power-load/id")
def exchange_power_load(
        loadboard_data: IndividualLoadboardShipmentRequest,
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
    if not carrier or not carrier.is_verified or carrier.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")

    try:
        loadboard_shipment = db.query(Exchange_Power_Load_Board).filter(Exchange_Power_Load_Board.exchange_id == loadboard_data.id).first()
        bids = db.query(Exchange_POWER_Shipment_Bid).filter(Exchange_POWER_Shipment_Bid.carrier_id == company_id).all()
        trailer = db.query(ShipperTrailer).filter(ShipperTrailer.id == loadboard_shipment.trailer_id).first()

        return {
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

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))