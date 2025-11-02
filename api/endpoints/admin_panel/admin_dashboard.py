from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from requests import Session
from db.database import SessionLocal
from models.administration import Platform_Super_Admins, Platform_Super_and_Support_Admins_Permissions
from models.shipper import Corporation, Consignor
from models.user import Director, CarrierUser, Driver
from models.carrier import Carrier
from models.vehicle import Vehicle, Trailer, ShipperTrailer
from models.brokerage.finance import FinancialAccounts, CarrierFinancialAccounts, Withdrawal_Request
from models.spot_bookings.dedicated_lane_ftl_shipment import FTL_Lane
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from models.brokerage.loadboards.exchange_loadboards import Exchange_Ftl_Load_Board, Exchange_Ftl_Lane_LoadBoard, Exchange_Power_Load_Board
from models.brokerage.loadboard import Dedicated_lanes_LoadBoard, Ftl_Load_Board, Power_Load_Board
from schemas.brokerage.finance import Individual_Sevice_Invoices_Request
from schemas.vehicle import Individual_Shipper_Trailer_Response, Shipper_Trailers_Summary_Response, ShipperTrailerCreate
from schemas.administration import CreateAdministrationUser, AdminPermissionsSchema
from schemas.auth import LoginRequest, LoginResponse
from services.vehicle_service import create_shipper_trailer
from services.user_service import create_admin_super_user
from utils.auth import get_current_user
from utils.administration_auth import verify_admin_password, get_current_admin
from utils.admin_jwt_handler import create_admin_access_token
router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/admin/admin-user-create", status_code=status.HTTP_201_CREATED)
def create_admin_endpoint(
    user_data: CreateAdministrationUser,
    permissions_data: AdminPermissionsSchema,
    db: Session = Depends(get_db)
):
    try:
        result = create_admin_super_user(db, user_data, permissions_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/admin-sign-in", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    print("Login request received for:", request.email)
    
    # Query super admin table
    admin = db.query(Platform_Super_Admins).filter(
        Platform_Super_Admins.email == request.email
    ).first()

    if admin:
        role = "super"
    else:
        print("User not found in any database.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password
    if not verify_admin_password(request.password, admin.password):
        print("Password verification failed for:", request.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    print(f"User authenticated successfully as {role}: {admin.email}")

    # Create token with role-specific information
    token = create_admin_access_token({
        "id": admin.id,
        "email": admin.email,
        "first_name": admin.first_name,
        "last_name": admin.last_name,
        "role": role
    })
    print("Generated JWT token:", token)

    return {"access_token": token, "token_type": "bearer"}

@router.get("/all-shippers")
def admin_get_all_shipper_companies(
    db: Session = Depends(get_db),
):
    try:
        # Fetch all Enterprise and Standard corporations
        shippers = (
            db.query(Corporation)
            .filter(Corporation.type.in_(["Enterprise", "Standard"]))
            .all()
        )

        # Build response list
        shipper_list = []
        for s in shippers:
            # Fetch all shipments for this shipper
            ftl_shipments = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.shipper_company_id == s.id).count()
            power_shipments = db.query(POWER_SHIPMENT).filter(POWER_SHIPMENT.shipper_company_id == s.id).count()
            total_shipments = ftl_shipments + power_shipments

            shipper_list.append({
                "id": s.id,
                "name": s.legal_business_name,
                "type": s.type,
                "business_registration_number": s.business_registration_number,
                "country_of_incorporation": s.country_of_incorporation,
                "email": s.business_email,
                "verification": s.is_verified,
                "status": s.status,
                "total_shipments": total_shipments,
            })

        return {"shippers": shipper_list}

    except Exception as e:
        return {"error": str(e)}

@router.get("/all-shippers/{status}")
def admin_get_all_shipper_accounts_by_status(
    status: str,
    db: Session = Depends(get_db),
):
    try:
        shippers = (
            db.query(Corporation)
            .filter(
                Corporation.type.in_(["Enterprise", "Standard"]),
                Corporation.status == status
            )
            .all()
        )

        result = []
        for shipper in shippers:
            financial_account = (
                db.query(FinancialAccounts)
                .filter(FinancialAccounts.id == shipper.id)
                .first()
            )

            result.append({
                "name": shipper.legal_business_name,
                "id": shipper.id,
                "type": shipper.type,
                "registration_no": shipper.business_registration_number,
                "country_of_incorporation": shipper.country_of_incorporation,
                "email": shipper.business_email,
                "verification_status": shipper.is_verified,
                "status": shipper.status,
                "total_shipments": financial_account.total_shipments if financial_account else 0
            })

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/all-financial-accounts")
def get_all_shipper_and_broker_financial_account(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        financial_accounts = db.query(FinancialAccounts).all()

        return [{
            "company_name": financial_account.company_name,
            "id": financial_account.id,
            "is_verified": financial_account.is_verified,
            "status": financial_account.status,
            "country_or_incorporation": financial_account.business_country_of_incorporation,
            "payment_terms": financial_account.payment_terms,
            "total_spent": financial_account.total_spent,
            "average_spend": financial_account.average_spend,
            "outstanding": financial_account.total_outstanding,
            "credit_available": financial_account.credit_balance,
            "spending_limit": financial_account.spending_limit,
            "total_paid": financial_account.total_paid
        } for financial_account in financial_accounts]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/all-carriers")
def get_all_carrier_companies(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        carriers = db.query(Carrier).all()

        return {
            "carriers": [{
                "company_name": carrier.legal_business_name,
                "id": carrier.id,
                "type": carrier.type,
                "country_of_incorporation": carrier.country_of_incorporation,
                "email": carrier.business_email,
                "phone_number": carrier.business_phone_number,
                "is_verified": carrier.is_verified,
                "status": carrier.status,
                "shipments_completed": carrier.number_of_completed_shipments,
                "fleet_size": carrier.number_of_vehicles,
            } for carrier in carriers],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/all-financial-accounts/{status}")
def get_all_shipper_and_broker_financial_account_by_status(
    status: str,
    db: Session = Depends(get_db),
):
    try:
        financial_accounts = db.query(FinancialAccounts).filter(FinancialAccounts.status == status).all()

        return [{
            "company_name": financial_account.company_name,
            "id": financial_account.id,
            "is_verified": financial_account.is_verified,
            "status": financial_account.status,
            "country_or_incorporation": financial_account.business_country_of_incorporation,
            "payment_terms": financial_account.payment_terms,
            "total_spent": financial_account.total_spent,
            "average_spend": financial_account.average_spend,
            "outstanding": financial_account.total_outstanding,
            "credit_avaialble": financial_account.credit_balance,
            "spending_limit": financial_account.spending_limit,
            "total_paid": financial_account.total_paid
        } for financial_account in financial_accounts]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

router.get("/all-carrier-accounts")
def get_all_carrier_account(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        carriers = db.query(Carrier).all

        return [{
            "company_name": carrier.legal_business_name,
            "id": carrier.id,
            "type": carrier.type,
            "country_of_incorporation": carrier.country_of_incorporation,
            "email": carrier.business_email,
            "phone_number": carrier.business_phone_number,
            "is_verified": carrier.is_verified,
            "status": carrier.status,
            "shipments_completed": carrier.number_of_completed_shipments,
            "fleet_size": carrier.number_of_vehicles,
        } for carrier in carriers]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/all-carrier-financial-accounts")
def admin_get_all_carrier_financial_accounts(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        financial_accounts = db.query(CarrierFinancialAccounts).all()

        return [{
            "company_name": financial_account.legal_business_name,
            "id": financial_account.id,
            "is_verified": financial_account.is_verified,
            "status": financial_account.status,
            "country_of_incorporation": financial_account.business_country_of_incorporation,
            "business_registration_number": financial_account.business_registration_number,
            "total_earned": financial_account.total_earned,
            "from_contracts": financial_account.earned_from_contracts,
            "holding_balance": financial_account.holding_balance,
            "current_balance": financial_account.current_balance,
            "total_withdrawn": financial_account.total_withdrawn
        } for financial_account in financial_accounts]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/carrier-financial-accounts/{status}")
def admin_get_all_carrier_financial_accounts_by_status(
    status: str,
    db: Session = Depends(get_db)
):
    try:
        financial_accounts = db.query(CarrierFinancialAccounts).filter(CarrierFinancialAccounts.status == status).all()

        return [{
            "id": financial_account.id,
            "verification_status": financial_account.is_verified,
            "status": financial_account.status,
            "company_name": financial_account.legal_business_name,
            "country_of_incorporation": financial_account.business_country_of_incorporation,
            "business_registration_number": financial_account.business_registration_number,
            "total_earned": financial_account.total_earned,
            "from_contracts": financial_account.earned_from_contracts,
            "holding_balance": financial_account.holding_balance,
            "current_balance": financial_account.current_balance,
            "total_withdrawn": financial_account.total_withdrawn
        } for financial_account in financial_accounts]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/all-brokers")
def admin_get_freight_brokers(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        brokers = db.query(Corporation).filter(Corporation.type == "Brokerage Firm").all()

        result = []
        for broker in brokers:
            clients = (
                db.query(Consignor)
                .filter(Consignor.brokerage_firm_id == broker.id)
                .all()
            )

        return [{
            "company_name": broker.legal_business_name,
            "id": broker.id,
            "type": broker.type,
            "registration_number": broker.business_registration_number,
            "country_of_incorporation": broker.country_of_incorporation,
            "email": broker.business_email,
            "is_verified": broker.is_verified,
            "status": broker.status,
            "total_client": len(clients)
        } for broker in brokers]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/all-brokers/{status}")
def admin_get_freight_brokers(
    status: str,
    db: Session = Depends(get_db)
):
    try:
        brokers = db.query(Corporation).filter(Corporation.type == "Brokerage Firm",
                                                Corporation.status == status).all()

        result = []
        for brokerr in brokers:
            financial_account = (
                db.query(FinancialAccounts)
                .filter(FinancialAccounts.id == broker.id)
                .first()
            )

        return [{
            "company_name": broker.legal_business_name,
            "id": broker.id,
            "type": broker.type,
            "registration_number": broker.business_registration_number,
            "country_of_incorporation": broker.country_of_incorporation,
            "email": broker.business_email,
            "verification_status": broker.is_verified,
            "status": broker.status,
            "total_shipments": financial_account.total_shipments if financial_account else 0
        } for broker in brokers]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/all-users")
def admin_get_all_shipper_and_broker_users_by_status(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        users = db.query(Director).all()

        return [{
            "name": f"{user.first_name} - {user.last_name}",
            "id": user.id,
            "is_verified": user.is_verified,
            "status": user.status,
            "id_number": user.id_number,
            "company_id": user.company_id,
            "is_director": user.is_director,
        } for user in users]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/all-user/{status}")
def admin_get_all_shipper_and_broker_users_by_status(
    status: str,
    db: Session = Depends(get_db)
):
    try:
        users = db.query(Director).filter(Director.status == status).all()

        return [{
            "name": f"{user.first_name} - {user.last_name}",
            "id": user.id,
            "id_number": user.id_number,
            "company_id": user.company_id,
            "verification_status": user.is_verified,
            "status": user.status
        } for user in users]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/all-carrier-users")
def admin_get_all_carrier_users(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        carrier_users = db.query(CarrierUser).all()

        return [{
            "name": f"{carrier_user.first_name} - {carrier_user.last_name}",
            "id": carrier_user.id,
            "is_verified": carrier_user.is_verified,
            "status": carrier_user.status,
            "company_id": carrier_user.company_id,
            "role": carrier_user.role,
            "nationality": carrier_user.nationality,
            "id_number": carrier_user.id_number,         
        } for carrier_user in carrier_users]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/all-carrier-user/{status}")
def admin_get_all_carrier_users_by_status(
    status: str = None,
    db: Session = Depends(get_db)
):
    try:
        query = db.query(CarrierUser)
        if status:
            query = query.filter(CarrierUser.status == status)

        carrierusers = query.all()

        return [{
            "name": f"{carrier_user.first_name} - {carrier_user.last_name}",
            "id": carrier_user.id,
            "company_id": carrier_user.company_id,
            "role": carrier_user.role,
            "nationality": carrier_user.nationality,
            "id_number": carrier_user.id_number,
            "verification_status": carrier_user.is_verified,
            "status": carrier_user.status            
        } for carrier_user in carrier_users]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/all-drivers")
def admin_get_all_driver_accounts(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        drivers = db.query(Driver).all()

        return [{
            "name": f"{driver.first_name} - {driver.last_name}",
            "id": driver.id,
            "is_verified": driver.is_verified,
            "status": driver.status,
            "company_id": driver.company_id,
            "nationality": driver.nationality,
            "id_number": driver.id_number,
            "license_number": driver.license_number,
            "current_vehicle_id": driver.current_vehicle_id if driver.current_vehicle_id else "N/A",
        } for driver in drivers]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/all-driver/{status}")
def admin_get_all_driver_accounts_by_status(
    status: str = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        query = db.query(Driver)
        if status:
            query = query.filter(Driver.status == status)

        drivers = query.all()
        return [{
            "name": f"{driver.first_name} - {driver.last_name}",
            "id": driver.id,
            "company_id": driver.company_id,
            "nationality": driver.nationality,
            "id_number": driver.id_number,
            "license_number": driver.license_number,
            "current_vehicle_id": driver.current_vehicle_id if driver.current_vehicle_id else "N/A",
            "verification_status": driver.is_verified,
            "status": driver.status
        } for driver in drivers]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/all-vehicles")
def admin_get_all_platform_vehicles(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        vehicles = db.query(Vehicle).all()

        return [{
            "make_model": f"{vehicle.make} - {vehicle.model}",
            "id": vehicle.id,
            "is_verified": vehicle.is_verified,
            "status": vehicle.status,
            "company": vehicle.owner_id,
            "year": vehicle.year,
            "color": vehicle.color,
            "license_plate": vehicle.license_plate,
            "license_expiry_date": vehicle.license_expiry_date,
            "type": vehicle.type,
            "equipment_type": vehicle.equipment_type,
            "trailer_type": vehicle.trailer_type if vehicle.trailer_type else None,
            "trailer_length": vehicle.trailer_length if vehicle.trailer_length else None,
            "payload_capacity": vehicle.payload_capacity
        } for vehicle in vehicles]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/all-trailers")
def admin_get_all_trailers_by_status(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        trailers = db.query(Trailer).all()
        
        return [{
            "make_and_model": f"{trailer.make} - {trailer.model}",
            "id": trailer.id,
            "is_verified": trailer.is_verified,
            "status": trailer.status,
            "company": trailer.owner_id,
            "year": trailer.year,
            "color": trailer.color,
            "license_plate": trailer.license_plate,
            "payload_capacity": trailer.payload_capacity,
            "current_vehicle": trailer.truck_id if trailer.truck_id else "N/A",
            "equipment_type": trailer.equipment_type,
            "trailer_type": trailer.trailer_type,
            "length": trailer.trailer_length,
        } for trailer in trailers]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/all-shipper-trailers")
def admin_get_all_shipper_trailers_by_status(
    status: str = None,
    db: Session = Depends(get_db)
):
    try:
        trailers = db.query(ShipperTrailer).all()
        
        return [{
            "make_and_model": f"{trailer.make} - {trailer.model}",
            "id": trailer.id,
            "is_verified": trailer.is_verified,
            "status": trailer.status,
            "availability": trailer.availability_status,
            "company": trailer.owner_id,
            "year": trailer.year,
            "color": trailer.color,
            "license_plate": trailer.license_plate,
            "payload_capacity": trailer.payload_capacity,
            "current_vehicle": trailer.truck_id if trailer.truck_id else "N/A",
            "equipment_type": trailer.equipment_type,
            "trailer_type": trailer.trailer_type,
            "length": trailer.trailer_length,
        } for trailer in trailers]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/all-lanes")
def admin_get_all_lanes(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        lanes = db.query(FTL_Lane).all()

        return {
            "lanes": [{
                "id": lane.id,
                "status": lane.status,
                "origin": lane.origin_city_province,
                "distance": lane.distance,
                "destination": lane.destination_city_province,
                "required_truck_type": lane.required_truck_type,
                "equipment_type": lane.equipment_type,
                "trailer_type": lane.trailer_type,
                "trailer_length": lane.trailer_length,
                "weight_bracket": lane.minimum_weight_bracket,
                "contract_period": f"{lane.start_date} to {lane.end_date}",
                "recurrence": lane.recurrence_frequency,
                "days": lane.recurrence_days,
                "shipments_per_interval": lane.shipments_per_interval,
                "per_shipment_rate": lane.qoute_per_shipment,
                "contract_rate": lane.contract_quote,
                "completed_shipments": lane.progress
            } for lane in lanes]
        },
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/all-shipments")
def admin_get_all_shipments(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        # --- Fetch all FTL Shipments ---
        ftl_shipments = db.query(FTL_SHIPMENT).all()

        # --- Fetch all POWER Shipments ---
        power_shipments = db.query(POWER_SHIPMENT).all()

        all_shipments = []

        # --- Add FTL Shipments ---
        for shipment in ftl_shipments:
            all_shipments.append({
                "id": shipment.id,
                "type": "FTL",
                "status": shipment.shipment_status,
                "origin": shipment.origin_city_province,
                "distance": shipment.distance,
                "destination": shipment.destination_city_province,
                "pickup_date": shipment.pickup_date,
                "required_truck_type": shipment.required_truck_type,
                "equipment_type": shipment.equipment_type,
                "trailer_type": shipment.trailer_type,
                "trailer_length": shipment.trailer_length,
                "weight_bracket": shipment.minimum_weight_bracket,
                "shipment_weight": shipment.shipment_weight,
                "hazardous_materials": shipment.hazardous_materials,
                "rate": shipment.quote,
            })

        # --- Add POWER Shipments ---
        for shipment in power_shipments:
            all_shipments.append({
                "id": shipment.id,
                "type": "POWER",
                "status": shipment.shipment_status,
                "origin": shipment.origin_city_province,
                "distance": shipment.distance,
                "destination": shipment.destination_city_province,
                "pickup_date": shipment.pickup_date,
                "required_truck_type": shipment.required_truck_type,
                "axle_configuration": shipment.axle_configuration,
                "weight_bracket": shipment.minimum_weight_bracket,
                "shipment_weight": shipment.shipment_weight,
                "hazardous_materials": shipment.hazardous_materials,
                "rate": shipment.quote,
            })

        return {"shipments": all_shipments}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/exchange-loadboards")
def admin_get_exchange_loadboards(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        ftl_shipment_exchanges = db.query(Exchange_Ftl_Load_Board).filter(Exchange_Ftl_Load_Board.status == "Open").all()
        power_shipment_exchanges = db.query(Exchange_Power_Load_Board).filter(Exchange_Power_Load_Board.status == "Open").all()
        ftl_lane_exchanges = db.query(Exchange_Ftl_Lane_LoadBoard).filter(Exchange_Ftl_Lane_LoadBoard.status == "Open").all()

        return {
            "ftl_exchanges": [{
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
            } for load in ftl_shipment_exchanges],

            "power_exchanges": [{
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
            } for loadboard_shipment in power_shipment_exchanges],

            "ftl_lane_exchanges": [{
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
                "total_slots": loadboard_shipment.shipments_per_interval,
                "available_slots": loadboard_shipment.available_slots,
                "total_shipments_per_slot": loadboard_shipment.each_slot_size,
                "exchange_end_time": loadboard_shipment.exchange_end_time,
                "number_of_bidders": loadboard_shipment.number_of_bids_submitted,
                "per_slot_contract_offer": loadboard_shipment.per_shipment_offer_rate * loadboard_shipment.each_slot_size,
                "per_shipment_offer": loadboard_shipment.per_shipment_offer_rate,
            } for loadboard_shipment in ftl_lane_exchanges]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/spot-loadboards")
def admin_get_loadboards(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        # --- Query all available loads ---
        ftl_shipments_loadboard = db.query(Ftl_Load_Board).filter(Ftl_Load_Board.status == "Available").all()
        power_shipments_loadboard = db.query(Power_Load_Board).filter(Power_Load_Board.status == "Available").all()
        ftl_lanes_loadboard = db.query(Dedicated_lanes_LoadBoard).filter(Dedicated_lanes_LoadBoard.status == "Available").all()

        # --- Return combined JSON ---
        return {
            "ftl_loadboard": [
                {
                    "id": ftl_load.shipment_id,
                    "trip_type": ftl_load.trip_type,
                    "rate": ftl_load.shipment_rate,
                    "distance": ftl_load.distance,
                    "route_preview_embed": ftl_load.route_preview_embed,
                    "rate_per_kilometer": ftl_load.rate_per_km,
                    "origin": ftl_load.origin_city_province,
                    "pickup_date": ftl_load.pickup_date,
                    "pickup_appointment": ftl_load.pickup_appointment,
                    "destination": ftl_load.destination_city_province,
                    "eta_date": ftl_load.eta_date,
                    "eta_window": ftl_load.eta_window,
                    "required_truck_type": ftl_load.required_truck_type,
                    "equipment_type": ftl_load.equipment_type,
                    "trailer_type": ftl_load.trailer_type,
                    "trailer_length": ftl_load.trailer_length,
                    "minimum_weight_bracket": ftl_load.minimum_weight_bracket,
                    "commodity": ftl_load.commodity,
                    "hazardous_materials": ftl_load.hazardous_metarials
                }
                for ftl_load in ftl_shipments_loadboard
            ],

            "power_loadboard": [
                {
                    "id": power_load.shipment_id,
                    "trip_type": power_load.trip_type,
                    "load_type": power_load.load_type,
                    "rate": power_load.shipment_rate,
                    "distance": power_load.distance,
                    "route_preview_embed": power_load.route_preview_embed,
                    "rate_per_kilometer": power_load.rate_per_kilometer,
                    "origin": power_load.origin_city_province,
                    "pickup_date": power_load.pickup_date,
                    "pickup_appointment": power_load.pickup_appointment,
                    "destination": power_load.destination_city_province,
                    "eta_date": power_load.eta_date,
                    "eta_window": power_load.eta_window,
                    "required_truck_type": power_load.required_truck_type,
                    "axle_configuration": power_load.axle_configuration,
                    "minimum_weight_bracket": power_load.minimum_weight_bracket,
                    "commodity": power_load.commodity,
                    "hazardous_materials": power_load.hazardous_materials,
                }
                for power_load in power_shipments_loadboard
            ],

            "ftl_lanes_loadboard": [
                {
                    "id": ftl_lane.shipment_id,
                    "status": ftl_lane.status,
                    "trip_type": ftl_lane.trip_type,
                    "load_type": ftl_lane.load_type,
                    "origin": ftl_lane.origin_city_province,
                    "destination": ftl_lane.destination_city_province,
                    "distance": ftl_lane.distance,
                    "full_route": ftl_lane.route_preview_embed,
                    "truck_type": ftl_lane.required_truck_type,
                    "equipment_type": ftl_lane.equipment_type or "N/A",
                    "trailer_type": ftl_lane.trailer_type or "N/A",
                    "trailer_length": ftl_lane.trailer_length or "N/A",
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
                }
                for ftl_lane in ftl_lanes_loadboard
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/all-withdrawal-requests")
def admin_get_all_withdrawal_requests(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        requests = db.query(WithdrawalRequest).all()

        return {
            "withdrawal_requests": [{
                "id": request.id,
                "status": request.status,
                "request_date_time": request.created_at,
                "carrier_id": request.financial_account_id,
                "carrier_name": request.carrier_company_name,
                "financial_account_id": request.financial_account_id,
                "account_balance": request.financial_account_current_balance,
                "withdrawal_amount": request.to_be_paid_out,

        } for request in requests]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

