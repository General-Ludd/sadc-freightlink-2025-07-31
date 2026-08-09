from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.Exchange.auction import Exchange_FTL_Lane_Bid, Exchange_FTL_Shipment_Bid, Exchange_POWER_Shipment_Bid
from models.brokerage.loadboard import Dedicated_lanes_LoadBoard, Ftl_Load_Board, Power_Load_Board
from models.brokerage.loadboards.exchange_loadboards import Exchange_Ftl_Lane_LoadBoard, Exchange_Ftl_Load_Board, Exchange_Power_Load_Board
from models.carrier import Carrier
from models.spot_bookings.shipment_facility import ContactPerson, ShipmentFacility
from schemas.brokerage.loadboard import AssignShipmentRequest, FTL_Lane_LoadBoard_Summary_Response, FTL_Lane_Loadboard_Individual_Shipment_Response, Individual_lane_id, AssignLaneSlotRequest, IndividualLoadboardShipmentRequest, IndividualSpotPowerLoadboardShipmentResponse, SpotFTLLoadBoardSummaryResponse, SpotPowerLoadBoardSummaryResponse
from schemas.shipment_facility import FacilityContactPersonResponse
from schemas.user import DriverCreate, DriverResponse
from schemas.vehicle import TrailerCreate, TrailerResponse, VehicleCreate, VehicleResponse, VehicleUpdate
from services.brokerage.carrier_loadboard_service import assign_spot_ftl_lane_to_carrier, assign_spot_ftl_shipment_to_carrier, assign_spot_power_shipment_to_carrier
from services.carrier_service import fleet_create_driver
from services.carrier_dashboards import assign_trailer_to_vehicle
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

@router.get("/spot/ftl-loadboard") #UnTested
def get_all_spot_ftl_loadboard_loads(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
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

        return {
            "shipments": [{
                "id": shipment.shipment_id,
                "trip_type": shipment.trip_type,
                "rate": shipment.shipment_rate,
                "distance": shipment.distance,
                "route_preview_embed": shipment.route_preview_embed,
                "rate_per_kilometer": shipment.rate_per_km,
                "origin": shipment.origin_city_province,
                "pickup_date": shipment.pickup_date,
                "pickup_appointment": shipment.pickup_appointment,
                "destination": shipment.destination_city_province,
                "eta_date": shipment.eta_date,
                "eta_window": shipment.eta_window,
                "required_truck_type": shipment.required_truck_type,
                "equipment_type": shipment.equipment_type,
                "trailer_type": shipment.trailer_type,
                "trailer_length": shipment.trailer_length,
                "minimum_weight_bracket": shipment.minimum_weight_bracket,
                "commodity": shipment.commodity,
                "hazardous_materials": shipment.hazardous_metarials
            } for shipment in shipments]
        }
    except Exception as e:
        return {"error": str(e)}
    
@router.get("/spot/ftl-loadboard/{id}")
def get_individual_spot_ftl_loadboard_shipment(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:

        # ============================================================
        # 1. GET LOADBOARD SHIPMENT
        # ============================================================

        shipment = (
            db.query(Ftl_Load_Board)
            .filter(Ftl_Load_Board.shipment_id == id)
            .first()
        )

        if not shipment:
            raise HTTPException(
                status_code=404,
                detail=f"Loadboard shipment {id} not found"
            )

        # ============================================================
        # 2. BUILD DYNAMIC STOP ADDRESSES
        # ============================================================
        #
        # Only addresses that actually exist are returned.
        #
        # Example:
        #
        # Origin
        # Stop 1
        # Stop 2
        # Destination
        #
        # If there are no stops:
        #
        # Origin
        # Destination
        #
        # ============================================================

        stop_addresses = []

        for stop_number in range(1, 6):

            stop_address = getattr(
                shipment,
                f"stop_{stop_number}_address",
                None
            )

            if stop_address:
                stop_addresses.append({
                    "stop_number": stop_number,
                    "address": stop_address
                })

        # ============================================================
        # 3. BUILD DYNAMIC STOP FACILITIES + CONTACTS
        # ============================================================
        #
        # The loadboard stores only the facility ID:
        #
        # stop_1_facility_id
        # stop_2_facility_id
        # stop_3_facility_id
        # stop_4_facility_id
        # stop_5_facility_id
        #
        # We use that ID to:
        #
        # 1. Find ShipmentFacility
        # 2. Get its contact_person ID
        # 3. Find ContactPerson
        #
        # ============================================================

        stop_facilities = []

        for stop_number in range(1, 6):

            # --------------------------------------------------------
            # Get stop address
            # --------------------------------------------------------

            stop_address = getattr(
                shipment,
                f"stop_{stop_number}_address",
                None
            )

            # --------------------------------------------------------
            # Get stop facility ID
            # --------------------------------------------------------

            stop_facility_id = getattr(
                shipment,
                f"stop_{stop_number}_facility_id",
                None
            )

            # If neither the address nor facility exists,
            # this stop does not exist.
            if not stop_address and not stop_facility_id:
                continue

            facility = None
            contact = None

            # ========================================================
            # QUERY STOP FACILITY
            # ========================================================

            if stop_facility_id:

                facility = (
                    db.query(ShipmentFacility)
                    .filter(
                        ShipmentFacility.id == stop_facility_id
                    )
                    .first()
                )

                # ====================================================
                # QUERY CONTACT PERSON
                # ====================================================
                #
                # ShipmentFacility stores the ContactPerson ID.
                #
                # ====================================================

                if facility and facility.contact_person:

                    contact = (
                        db.query(ContactPerson)
                        .filter(
                            ContactPerson.id == facility.contact_person
                        )
                        .first()
                    )

            # ========================================================
            # BUILD STOP FACILITY RESPONSE
            # ========================================================

            stop_facilities.append({

                "stop_number": stop_number,

                "address": stop_address,

                "facility": {

                    "id": (
                        facility.id
                        if facility
                        else stop_facility_id
                    ),

                    "name": (
                        facility.name
                        if facility
                        else None
                    ),

                    "scheduling_type": (
                        facility.scheduling_type
                        if facility
                        else None
                    ),

                    "start_time": (
                        str(facility.start_time)
                        if facility and facility.start_time
                        else None
                    ),

                    "end_time": (
                        str(facility.end_time)
                        if facility and facility.end_time
                        else None
                    ),

                    "facility_notes": (
                        facility.facility_notes
                        if facility
                        else None
                    ),
                },

                "contact": {

                    "first_name": (
                        contact.first_name
                        if contact
                        else None
                    ),

                    "last_name": (
                        contact.last_name
                        if contact
                        else None
                    ),

                    "phone_number": (
                        contact.phone_number
                        if contact
                        else None
                    ),

                    "email": (
                        contact.email
                        if contact
                        else None
                    ),
                }
            })

        # ============================================================
        # 4. RETURN RESPONSE
        # ============================================================

        return {

            # ========================================================
            # SHIPMENT DETAILS
            # ========================================================

            "shipment_details": {

                "id": shipment.shipment_id,

                "type": shipment.type,

                "load_type": shipment.load_type,

                "trip_type": shipment.trip_type,

                "status": shipment.status,

                "required_truck_type": shipment.required_truck_type,

                "equipment_type": shipment.equipment_type,

                "trailer_type": (
                    shipment.trailer_type
                    if shipment.trailer_type
                    else "N/A"
                ),

                "trailer_length": (
                    shipment.trailer_length
                    if shipment.trailer_length
                    else "N/A"
                ),

                "minimum_weight_bracket": (
                    shipment.minimum_weight_bracket
                ),

                "minimum_git_cover_amount": (
                    shipment.minimum_git_cover_amount
                ),

                "minimum_liability_cover_amount": (
                    shipment.minimum_liability_cover_amount
                ),

                # ====================================================
                # ORIGIN
                # ====================================================

                "origin": shipment.origin_address,

                # ====================================================
                # DYNAMIC STOP ADDRESSES
                #
                # These are ONLY the addresses.
                #
                # ====================================================

                "stops": stop_addresses,

                # ====================================================
                # DESTINATION
                # ====================================================

                "destination": shipment.destination_address,

                "distance": shipment.distance,

                "rate": shipment.shipment_rate,

                "rate_per_km": shipment.rate_per_km,

                "rate_per_ton": shipment.rate_per_ton,

                "pickup_date": shipment.pickup_date,

                "eta_data": shipment.eta_date,

                "payment_terms": shipment.payment_terms,

                "payment_date": shipment.payment_date,

                "minimum_transit_time": (
                    shipment.estimated_transit_time
                ),

                "route_preview": shipment.route_preview_embed,

                "commodity": shipment.commodity,

                "temperature_control": shipment.temperature_control,

                "hazardous_materails": (
                    shipment.hazardous_metarials
                ),

                "packaging_quantity": (
                    shipment.packaging_quantity
                ),

                "packaging_type": shipment.packaging_type,

                "pickup_number": shipment.pickup_number,

                "pickup_notes": shipment.pickup_notes,

                "delivery_number": shipment.delivery_number,

                "delivery_notes": shipment.delivery_notes,
            },

            # ========================================================
            # PICKUP FACILITY + CONTACT
            # ========================================================

            "pickup_facility": {

                "name": shipment.pickup_facility_name,

                "address": shipment.origin_address,

                "scheduling_type": (
                    shipment.pickup_scheduling_type
                ),

                "operating_hours": (
                    f"{shipment.pickup_start_time} - "
                    f"{shipment.pickup_end_time}"
                ),

                "facility_notes": (
                    shipment.pickup_facility_notes
                ),

                "contact_person": (
                    f"{shipment.pickup_first_name} "
                    f"{shipment.pickup_last_name}"
                ),

                "phone_number": (
                    shipment.pickup_phone_number
                ),

                "email": shipment.pickup_email,
            },

            # ========================================================
            # DYNAMIC STOP FACILITIES + CONTACTS
            #
            # These sit logically BETWEEN pickup and delivery.
            #
            # ========================================================

            "stop_facilities": stop_facilities,

            # ========================================================
            # DELIVERY FACILITY + CONTACT
            # ========================================================

            "delivery_facility": {

                "name": shipment.delivery_facility_name,

                "address": shipment.destination_address,

                "scheduling_type": (
                    shipment.delivery_scheduling_type
                ),

                "operating_hours": (
                    f"{shipment.delivery_start_time} - "
                    f"{shipment.delivery_end_time}"
                ),

                "facility_notes": (
                    shipment.delivery_facility_notes
                ),

                "contact_person": (
                    f"{shipment.delivery_first_name} "
                    f"{shipment.delivery_last_name}"
                ),

                "phone_number": (
                    shipment.delivery_phone_number
                ),

                "email": shipment.delivery_email,
            },
        }

    except HTTPException:
        raise

    except Exception as e:

        print("============================================================")
        print("ERROR IN get_individual_spot_ftl_loadboard_shipment")
        print("============================================================")
        print(f"Shipment ID: {id}")
        print(f"Error: {str(e)}")
        print("============================================================")

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.get("/public-spot/ftl-loadboard")  # UnTested
def get_public_spot_ftl_loadboard_loads(
    db: Session = Depends(get_db)
):
    try:

        # ============================================================
        # GET ALL AVAILABLE LOADS
        # ============================================================

        shipments = (
            db.query(Ftl_Load_Board)
            .filter(Ftl_Load_Board.status == "Available")
            .all()
        )

        # ============================================================
        # BUILD LOADBOARD RESPONSE
        # ============================================================

        loadboard_shipments = []

        for shipment in shipments:

            # --------------------------------------------------------
            # BUILD DYNAMIC STOP ADDRESSES
            # --------------------------------------------------------
            #
            # Only addresses that actually exist will be returned.
            #
            # Example:
            #
            # origin
            # stops:
            #   Stop 1
            #   Stop 2
            # destination
            #
            # If there are no stops:
            #
            # origin
            # stops: []
            # destination
            #
            # --------------------------------------------------------

            stop_addresses = []

            for stop_number in range(1, 6):

                stop_address = getattr(
                    shipment,
                    f"stop_{stop_number}_address",
                    None
                )

                if stop_address:
                    stop_addresses.append({
                        "stop_number": stop_number,
                        "address": stop_address
                    })

            # --------------------------------------------------------
            # BUILD SHIPMENT
            # --------------------------------------------------------

            loadboard_shipments.append({

                "id": shipment.shipment_id,

                "trip_type": shipment.trip_type,

                "rate": shipment.shipment_rate,

                "distance": shipment.distance,

                "route_preview_embed": shipment.route_preview_embed,

                "rate_per_kilometer": shipment.rate_per_km,

                "origin": shipment.origin_city_province,

                # ====================================================
                # DYNAMIC STOPS
                # ====================================================
                "stops": stop_addresses,

                "pickup_date": shipment.pickup_date,

                "pickup_appointment": shipment.pickup_appointment,

                "destination": shipment.destination_city_province,

                "eta_date": shipment.eta_date,

                "eta_window": shipment.eta_window,

                "required_truck_type": shipment.required_truck_type,

                "equipment_type": shipment.equipment_type,

                "trailer_type": shipment.trailer_type,

                "trailer_length": shipment.trailer_length,

                "minimum_weight_bracket": shipment.minimum_weight_bracket,

                "commodity": shipment.commodity,

                "hazardous_materials": shipment.hazardous_metarials
            })

        # ============================================================
        # RETURN RESPONSE
        # ============================================================

        return {
            "shipments": loadboard_shipments
        }

    except Exception as e:

        print("============================================================")
        print("ERROR IN get_public_spot_ftl_loadboard_loads")
        print("============================================================")
        print(f"Error: {str(e)}")
        print("============================================================")

        return {
            "error": str(e)
        }


@router.get("/public-spot/ftl-loadboard/{id}")
def get_public_individual_spot_ftl_loadboard_shipment(
    id: int,
    db: Session = Depends(get_db),
):
    try:

        # ============================================================
        # 1. GET LOADBOARD SHIPMENT
        # ============================================================

        shipment = (
            db.query(Ftl_Load_Board)
            .filter(Ftl_Load_Board.shipment_id == id)
            .first()
        )

        if not shipment:
            raise HTTPException(
                status_code=404,
                detail="Shipment not found"
            )

        # ============================================================
        # 2. BUILD DYNAMIC STOP ADDRESSES
        # ============================================================
        #
        # The loadboard contains:
        #
        # stop_1_address
        # stop_2_address
        # stop_3_address
        # stop_4_address
        # stop_5_address
        #
        # Only stops that actually contain an address are returned.
        #
        # Example:
        #
        # Origin
        # Stop 1
        # Stop 2
        # Destination
        #
        # If there are no stops:
        #
        # Origin
        # Destination
        #
        # ============================================================

        stop_addresses = []

        for stop_number in range(1, 6):

            stop_address = getattr(
                shipment,
                f"stop_{stop_number}_address",
                None
            )

            if stop_address:
                stop_addresses.append({
                    "stop_number": stop_number,
                    "address": stop_address
                })

        # ============================================================
        # 3. BUILD DYNAMIC STOP FACILITIES + CONTACTS
        # ============================================================
        #
        # The loadboard stores ONLY the facility ID for stops.
        #
        # stop_1_facility_id
        # stop_2_facility_id
        # ...
        #
        # We use the facility ID to:
        #
        # 1. Query ShipmentFacility
        # 2. Get the facility's contact_person ID
        # 3. Query ContactPerson using that ID
        #
        # ============================================================

        stop_facilities = []

        for stop_number in range(1, 6):

            # --------------------------------------------------------
            # Get stop address
            # --------------------------------------------------------

            stop_address = getattr(
                shipment,
                f"stop_{stop_number}_address",
                None
            )

            # --------------------------------------------------------
            # Get corresponding facility ID
            # --------------------------------------------------------

            stop_facility_id = getattr(
                shipment,
                f"stop_{stop_number}_facility_id",
                None
            )

            # If there is no stop address AND no facility ID,
            # there is no stop to return.
            if not stop_address and not stop_facility_id:
                continue

            facility = None
            contact = None

            # --------------------------------------------------------
            # Query stop facility
            # --------------------------------------------------------

            if stop_facility_id:

                facility = (
                    db.query(ShipmentFacility)
                    .filter(
                        ShipmentFacility.id == stop_facility_id
                    )
                    .first()
                )

                # ----------------------------------------------------
                # Query contact person associated with facility
                # ----------------------------------------------------

                if facility and facility.contact_person:

                    contact = (
                        db.query(ContactPerson)
                        .filter(
                            ContactPerson.id == facility.contact_person
                        )
                        .first()
                    )

            # --------------------------------------------------------
            # Build stop facility response
            # --------------------------------------------------------

            stop_facilities.append({

                "stop_number": stop_number,

                "address": stop_address,

                "facility": {

                    "id": (
                        facility.id
                        if facility
                        else stop_facility_id
                    ),

                    "name": (
                        facility.name
                        if facility
                        else None
                    ),

                    "scheduling_type": (
                        facility.scheduling_type
                        if facility
                        else None
                    ),

                    "start_time": (
                        str(facility.start_time)
                        if facility and facility.start_time
                        else None
                    ),

                    "end_time": (
                        str(facility.end_time)
                        if facility and facility.end_time
                        else None
                    ),

                    "facility_notes": (
                        facility.facility_notes
                        if facility
                        else None
                    ),
                },

                "contact": {

                    "first_name": (
                        contact.first_name
                        if contact
                        else None
                    ),

                    "last_name": (
                        contact.last_name
                        if contact
                        else None
                    ),

                    "phone_number": (
                        contact.phone_number
                        if contact
                        else None
                    ),

                    "email": (
                        contact.email
                        if contact
                        else None
                    ),
                }
            })

        # ============================================================
        # 4. RETURN RESPONSE
        # ============================================================

        return {

            # ========================================================
            # SHIPMENT DETAILS
            # ========================================================

            "shipment_details": {

                "id": shipment.shipment_id,

                "type": shipment.type,

                "load_type": shipment.load_type,

                "trip_type": shipment.trip_type,

                "status": shipment.status,

                "required_truck_type": shipment.required_truck_type,

                "equipment_type": shipment.equipment_type,

                "trailer_type": (
                    shipment.trailer_type
                    if shipment.trailer_type
                    else "N/A"
                ),

                "trailer_length": (
                    shipment.trailer_length
                    if shipment.trailer_length
                    else "N/A"
                ),

                "minimum_weight_bracket": (
                    shipment.minimum_weight_bracket
                ),

                "minimum_git_cover_amount": (
                    shipment.minimum_git_cover_amount
                ),

                "minimum_liability_cover_amount": (
                    shipment.minimum_liability_cover_amount
                ),

                # ----------------------------------------------------
                # ORIGIN
                # ----------------------------------------------------

                "origin": shipment.origin_address,

                # ----------------------------------------------------
                # DYNAMIC STOPS
                #
                # Only stop addresses are returned here.
                # ----------------------------------------------------

                "stops": stop_addresses,

                # ----------------------------------------------------
                # DESTINATION
                # ----------------------------------------------------

                "destination": shipment.destination_address,

                "distance": shipment.distance,

                "rate": shipment.shipment_rate,

                "rate_per_km": shipment.rate_per_km,

                "rate_per_ton": shipment.rate_per_ton,

                "pickup_date": shipment.pickup_date,

                "eta_data": shipment.eta_date,

                "payment_terms": shipment.payment_terms,

                "payment_date": shipment.payment_date,

                "minimum_transit_time": (
                    shipment.estimated_transit_time
                ),

                "route_preview": shipment.route_preview_embed,

                "commodity": shipment.commodity,

                "temperature_control": (
                    shipment.temperature_control
                ),

                "hazardous_materails": (
                    shipment.hazardous_metarials
                ),

                "packaging_quantity": (
                    shipment.packaging_quantity
                ),

                "packaging_type": (
                    shipment.packaging_type
                ),

                "pickup_number": shipment.pickup_number,

                "pickup_notes": shipment.pickup_notes,

                "delivery_number": shipment.delivery_number,

                "delivery_notes": shipment.delivery_notes,
            },

            # ========================================================
            # PICKUP FACILITY + CONTACT
            # ========================================================

            "pickup_facility": {

                "name": shipment.pickup_facility_name,

                "address": shipment.origin_address,

                "scheduling_type": (
                    shipment.pickup_scheduling_type
                ),

                "operating_hours": (
                    f"{shipment.pickup_start_time} - "
                    f"{shipment.pickup_end_time}"
                ),

                "facility_notes": (
                    shipment.pickup_facility_notes
                ),

                "contact_person": (
                    f"{shipment.pickup_first_name} "
                    f"{shipment.pickup_last_name}"
                ),

                "phone_number": (
                    shipment.pickup_phone_number
                ),

                "email": shipment.pickup_email,
            },

            # ========================================================
            # DYNAMIC STOP FACILITIES + CONTACTS
            #
            # These are returned BETWEEN pickup and delivery.
            # ========================================================

            "stop_facilities": stop_facilities,

            # ========================================================
            # DELIVERY FACILITY + CONTACT
            # ========================================================

            "delivery_facility": {

                "name": shipment.delivery_facility_name,

                "address": shipment.destination_address,

                "scheduling_type": (
                    shipment.delivery_scheduling_type
                ),

                "operating_hours": (
                    f"{shipment.delivery_start_time} - "
                    f"{shipment.delivery_end_time}"
                ),

                "facility_notes": (
                    shipment.delivery_facility_notes
                ),

                "contact_person": (
                    f"{shipment.delivery_first_name} "
                    f"{shipment.delivery_last_name}"
                ),

                "phone_number": (
                    shipment.delivery_phone_number
                ),

                "email": shipment.delivery_email,
            },
        }

    except HTTPException:
        raise

    except Exception as e:

        print("============================================================")
        print("ERROR IN get_public_individual_spot_ftl_loadboard_shipment")
        print("============================================================")
        print(f"Shipment ID: {id}")
        print(f"Error: {str(e)}")
        print("============================================================")

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

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
    
@router.get("/dedicated-ftl-lane-loadboard") #UnTested
def get_all_spot_ftl_lanes_loads(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
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
        return {
            "lanes": [{
                "id": ftl_lane.shipment_id,
                "status": ftl_lane.status,
                "trip_type": ftl_lane.trip_type,
                "load_type": ftl_lane.load_type,
                "origin": ftl_lane.origin_city_province,
                "destination": ftl_lane.destination_city_province,
                "distance": ftl_lane.distance,
                "full_route": ftl_lane.route_preview_embed,
                "truck_type": ftl_lane.required_truck_type,
                "equipment_type": ftl_lane.equipment_type if ftl_lane.equipment_type else "N/A",
                "trailer_type": ftl_lane.trailer_type if ftl_lane.trailer_type else "N/A",
                "trailer_length": ftl_lane.trailer_length if ftl_lane.trailer_length else "N/A",
                "minimum_weight_bracket": ftl_lane.minimum_weight_bracket,
                "commodity": ftl_lane.commodity,
                "packaging_type": ftl_lane.packaging_type,
                "average_shipment_weight": ftl_lane.average_shipment_weight,
                "start_date": ftl_lane.start_date,
                "end_date": ftl_lane.end_date,
                "frequency": ftl_lane.recurrence_frequency,
                "recurrence_days": ftl_lane.recurrence_days,
                "total_slots": ftl_lane.shipments_per_interval,
                "available_slots": ftl_lane.available_slots,
                "total_shipments_per_slot": ftl_lane.per_slot_size,
                "per_shipment_rate": ftl_lane.rate_per_shipment,
                "per_slot_contract_rate": int(ftl_lane.rate_per_shipment * ftl_lane.per_slot_size),
            } for ftl_lane in ftl_lanes]
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/spot/ftl-lane-loadboard/{id}")
def get_individual_loadboard_ftl_lane(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        # Query all records from the "dedicated_lanes_loadboard" table
        lane = db.query(Dedicated_lanes_LoadBoard).filter(Dedicated_lanes_LoadBoard.shipment_id == id).first()
        if not lane:
            raise HTTPException(status_code=404, detail="Lane not found")
            
        return {
            "lane_information": {
                "id": lane.shipment_id,
                "status": lane.status,
                "type": lane.type,
                "load_type": lane.load_type,
                "trip_type": lane.trip_type,
                "origin": lane.origin_city_province,
                "destination": lane.destination_city_province,
                "distance": lane.distance,
                "minimum_transit_time": lane.estimated_transit_time,
                "route_preview": lane.route_preview_embed,
                "required_truck_type": lane.required_truck_type,
                "equipment_type": lane.equipment_type,
                "trailer_type": lane.trailer_type if lane.trailer_type else "N/A",
                "trailer_length": lane.trailer_length if lane.trailer_length else "N/A",
                "minimum_weight_bracket": lane.minimum_weight_bracket,
                "average_shipment_weight": lane.average_shipment_weight,
                "minimum_git_cover_amount": lane.minimum_git_cover_amount,
                "minimum_liability_cover_amount": lane.minimum_liability_cover_amount,
                "commodity": lane.commodity,
                "temperature_control": lane.temperature_control,
                "hazardous_materials": lane.hazardous_materials,
                "packaging_quantity": lane.packaging_quantity,
                "packaging_type": lane.packaging_type,
                "pickup_number": lane.pickup_number,
                "pickup_notes": lane.pickup_notes,
                "delivery_number": lane.delivery_number,
                "delivery_notes": lane.delivery_notes,
            },
            "contract_information": {
                "start_date": lane.start_date,
                "end_date": lane.end_date,
                "recurrence_frequency": lane.recurrence_frequency,
                "recurrence_days": lane.recurrence_days,
                "slots_per_interval": lane.shipments_per_interval,
                "total_shipments": lane.total_shipments,
                "per_shipment_rate": lane.rate_per_shipment,
                "per_slot_contract_rate": (lane.rate_per_shipment * lane.per_slot_size),
                "distance_per_shipment": lane.distance,
                "rate_per_km": lane.rate_per_km,
                "rate_per_ton": lane.rate_per_ton,
                "payment_terms": lane.payment_terms,
                "shipment_dates": lane.shipment_dates,
                "payment_dates": lane.payment_dates,
                "total_slots": lane.total_slots,
                "available_slots": lane.available_slots,
                "total_shipments_per_slot": lane.per_slot_size,
            },
            "pickup_facility": {
                "name": lane.pickup_facility_name,
                "address": lane.origin_address,
                "scheduling_type": lane.pickup_scheduling_type,
                "operating_hours": f"{lane.pickup_start_time} - {lane.pickup_end_time}",
                "contact_person": f"{lane.pickup_first_name} {lane.pickup_last_name}",
                "phone_number": lane.pickup_phone_number,
                "email": lane.pickup_email,
            },
            "delivery_facility": {
                "name": lane.delivery_facility_name,
                "address": lane.destination_address,
                "scheduling_type": lane.delivery_scheduling_type,
                "operating_hours": f"{lane.delivery_start_time} - {lane.delivery_end_time}",
                "contact_person": f"{lane.delivery_first_name} {lane.delivery_last_name}",
                "phone_number": lane.delivery_phone_number,
                "email": lane.delivery_email,
            },
        }
    except Exception as e:
        return {"error": str(e)}


@router.post("/spot/loadboard/accept-ftl-lane", status_code=status.HTTP_202_ACCEPTED) #UnTested
def accept_spot_ftl_lane_from_loadboard(
    lane_data: AssignLaneSlotRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        result = assign_spot_ftl_lane_to_carrier(db, lane_data, current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.get("/spot/power-loadboard") #UnTested
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
        return {
            "shipments": [{
                "id": shipment.id,
                "rate": shipment.shipment_rate,
                "load_type": shipment.load_type,
                "origin": shipment.origin_city_province,
                "pickup_date": shipment.pickup_date,
                "pickup_appointment": shipment.pickup_appointment,
                "destination": shipment.destination_city_province,
                "eta_date": shipment.eta_date,
                "eta_window": shipment.eta_window,
                "route_preview_embed": shipment.route_preview_embed,
                "distance": shipment.distance,
                "rate_per_kilometer": shipment.rate_per_kilometer,
                "truck_type": shipment.required_truck_type,
                "axle_configuration": shipment.axle_configuration,
                "minimum_weight_bracket": shipment.minimum_weight_bracket,
                "commodity": shipment.commodity,
                "hazardous_materials": shipment.hazardous_materials,
            } for shipment in shipments]
        }
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


@router.get("/carrier/ftl-loadboard")
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
    
@router.get("/carrier/ftl-lane-loadboard")
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

@router.get("/carrier/power-loadboard")
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

        return {
            "shipments": [{
                "id": loadboard_shipment.exchange_id,
                "offer_rate": loadboard_shipment.shipment_rate,
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
                "hazardous_materials": loadboard_shipment.hazardous_materials,
                "status": loadboard_shipment.status,
                "end_time": loadboard_shipment.exchange_end_time,
                "best_bid": loadboard_shipment.leading_bid_amount,
                "allow_carrier_to_book_at_current_or_lower_offer_rate":
                    loadboard_shipment.allow_carrier_to_book_at_current_or_lower_offer_rate,
            } for loadboard_shipment in loadboard_shipments]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))