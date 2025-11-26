from fastapi import APIRouter, Depends, HTTPException, status
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.brokerage.finance import FinancialAccounts, Shipment_Invoice, Interim_Invoice, Invoices
from models.spot_bookings.shipment_facility import ShipmentFacility
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.spot_bookings.dedicated_lane_ftl_shipment import FTL_Lane
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from models.Exchange.ftl_shipment import FTL_SHIPMENT_EXCHANGE
from models.Exchange.dedicated_ftl_lane import FTL_Lane_Exchange
from models.shipper import Corporation, Client_Notification
from schemas.brokerage.finance import Shipper_Financial_Account_Create, Enterprise_Financial_Account_Create, Client_Financial_Account_Update
from schemas.shipper import CorporationBase, CorporationResponse, CorporationUpdate
from schemas.user import DirectorCreate, DirectorResponse, ShipperUserResponse
from services.shipper_service import create_enterprise_shipper
from utils.auth import get_current_user, verify_password, hash_password
from utils.jwt_handler import create_access_token
from utils.mailgun_handler import send_email
from utils.sast_datetime import get_sast_time
from pytz import timezone, UTC
from models.user import Director, User, Driver, CarrierDirector, PasswordResetCode
from models.vehicle import Vehicle
from schemas.auth import LoginRequest, LoginResponse

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def make_aware(dt):
    """
    Safely handles:
    - None
    - date
    - naive datetime
    - timezone-aware datetime
    """

    if dt is None:
        return None

    sast = ZoneInfo("Africa/Johannesburg")

    # Case 1: date-only → convert to datetime at midnight SAST
    if isinstance(dt, datetime) is False:
        # dt is a datetime.date
        return datetime(dt.year, dt.month, dt.day, tzinfo=sast)

    # Case 2: already timezone-aware
    if dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None:
        return dt

    # Case 3: naive datetime → make SAST aware
    return dt.replace(tzinfo=sast)

@router.get("/enterprise-shipper/company-name")
def get_enterprise_shipper_company_name(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        shipper = db.query(Corporation).filter(Corporation.id == current_user.get("company_id")).first()
        return shipper.legal_business_name
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/enterprise-shipper/current-user-name")
def get_current_enterprise_user_name(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        user = db.query(Director).filter(Director.id == current_user.get("id")).first()
        return user.first_name
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/shippers/enterprise-registration", status_code=status.HTTP_201_CREATED)
def create_enterprise_shipper_endpoint(
    shipper_data: CorporationBase,
    director_data: DirectorCreate,
    financial_data: Enterprise_Financial_Account_Create,
    db: Session = Depends(get_db)
):
    try:
        result = create_enterprise_shipper(db, shipper_data, director_data, financial_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/enterprise-shipper-sign-in", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    print("Login request received for:", request.email)
    
    # Check the `Carrier Director` table
    user = db.query(Director).filter(Director.email == request.email).first()
    if user:
        role = "director"
    else:
        print("User not found in any database.")
        raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password
    if not verify_password(request.password, user.password_hash):
        print("Password verification failed for:", request.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    print(f"User authenticated successfully as {role}: {user.email}")

    # Create token with role-specific information
    token = create_access_token({"id": user.id, "email": user.email, "first_name": user.first_name, "last_name": user.last_name, "company_id": user.company_id})
    print("Generated JWT token:", token)

    return {"access_token": token, "token_type": "bearer"}

@router.get("/enterprise-dashboard")
def get_enterprise_shipper_dashboard(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        # 1. Get all facilities under this user's company
        facilities = (
            db.query(Corporation)
            .filter(Corporation.parent_company_id == current_user.get("company_id"))
            .all()
        )

        # 2. Extract facility IDs
        facility_ids = [f.id for f in facilities]

        # 3. Include parent company + all its facilities
        company_scope_ids = [current_user.get("company_id")] + facility_ids

        # 4. Query all shipments belonging to this company or its facilities
        shipments = (
            db.query(FTL_SHIPMENT)
            .filter(FTL_SHIPMENT.shipper_company_id.in_(company_scope_ids))
            .all()
        )

        # 4b. Cancelled shipments
        cancelled_shipments = (
            db.query(FTL_SHIPMENT)
            .filter(
                FTL_SHIPMENT.shipper_company_id.in_(company_scope_ids),
                FTL_SHIPMENT.shipment_status == "Cancelled"
            )
            .count()
        )

        # 4c. All pickup dates for operations_growth
        operations_growth = [
            s.pickup_date for s in shipments if s.pickup_date is not None
        ]

        # 5. Query all lanes for this company or its facilities
        lanes = (
            db.query(FTL_Lane)
            .filter(FTL_Lane.shipper_company_id.in_(company_scope_ids))
            .all()
        )

        # 5b. Active lanes ("Booked" or "In-Progress")
        active_lanes = (
            db.query(FTL_Lane)
            .filter(
                FTL_Lane.shipper_company_id.in_(company_scope_ids),
                FTL_Lane.status.in_(["Booked", "In-Progress"])
            )
            .count()
        )

        # 6. Active users in all companies & facilities
        users = (
            db.query(Director)
            .filter(Director.company_id.in_(company_scope_ids))
            .all()
        )

        # 7. Lanes ranked by total shipments
        # Build mapping: lane_id -> count of shipments
        lane_counts = {}
        for shipment in shipments:
            if shipment.dedicated_lane_id:
                lane_counts[shipment.dedicated_lane_id] = lane_counts.get(shipment.dedicated_lane_id, 0) + 1

        # Build list with Origin, Destination, Total Shipments
        lanes_by_volume = []
        for lane in lanes:
            total_shipments = lane_counts.get(lane.id, 0)
            lanes_by_volume.append({
                "origin": lane.origin_city_province,
                "destination": lane.destination_city_province,
                "total_shipments": total_shipments
            })

        # Sort from highest to lowest
        lanes_by_volume.sort(key=lambda x: x["total_shipments"], reverse=True)

        return {
            "total_shipments": len(shipments),
            "cancellations": cancelled_shipments,
            "active_lanes": active_lanes,
            "total_facilities": len(facilities),
            "active_users": len(users),
            "operations_growth": operations_growth,
            "leading_lanes": lanes_by_volume
        }

    except Exception as e:
        print(str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/enterprise-facilities")
def get_enterprise_facilities(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # 1. Fetch all subsidiary facilities
    facilities = (
        db.query(Corporation)
        .filter(Corporation.parent_company_id == current_user.get("company_id"))
        .all()
    )

    # 2. Build summary counts
    status_counts = {
        "active": len([f for f in facilities if f.status == "Active"]),
        "unverified": len([f for f in facilities if f.status == "Un-verified"]),
        "under-investigation": len([f for f in facilities if f.status == "Under-Investigation"]),
        "suspended": len([f for f in facilities if f.status == "Suspended"]),
    }

    facility_list = []

    # 3. Build facility list with director, financial account, cancellations
    for facility in facilities:

        # Fetch manager/director
        manager = (
            db.query(Director)
            .filter(Director.company_id == facility.id)
            .first()
        )

        # active users
        users = (
            db.query(Director)
            .filter(
                Director.company_id == facility.id,
                Director.status == "Active"
            )
            .all()
        )

        # all shipments for this facility
        shipments = (
            db.query(FTL_SHIPMENT)
            .filter(FTL_SHIPMENT.shipper_company_id == facility.id)
            .all()
        )

        # cancelled shipments
        cancelled_shipments = (
            db.query(FTL_SHIPMENT)
            .filter(
                FTL_SHIPMENT.shipper_company_id == facility.id,
                FTL_SHIPMENT.shipment_status == "Cancelled"
            )
            .count()
        )

        # all lanes for this facility
        lanes = (
            db.query(FTL_Lane)
            .filter(FTL_Lane.shipper_company_id == facility.id)
            .all()
        )

        # cancelled lanes
        cancelled_lanes = (
            db.query(FTL_Lane)
            .filter(
                FTL_Lane.shipper_company_id == facility.id,
                FTL_Lane.status == "Cancelled"
            )
            .count()
        )

        # Financial account
        financial_account = (
            db.query(FinancialAccounts)
            .filter(FinancialAccounts.company_id == facility.id)
            .first()
        )

        facility_list.append({
            "id": facility.id,
            "name": facility.legal_business_name,
            "status": facility.status,
            "is_verified": facility.is_verified,
            "manager": f"{manager.first_name} {manager.last_name}" if manager else None,
            "address": facility.business_address,

            "active_users": len(users),

            "total_shipments": len(shipments),
            "cancelled_shipments": cancelled_shipments,

            "total_lanes": len(lanes),
            "cancelled_lanes": cancelled_lanes,

            "total_spent": financial_account.total_spent if financial_account else 0,
            "outstanding": financial_account.total_outstanding if financial_account else 0,
        })

    return {
        "summary": status_counts,
        "facilities": facility_list
    }

@router.get("/enterprise-shipments")
def get_enterprise_shipper_shipments(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        # 1. Facilities under parent company
        facilities = (
            db.query(Corporation)
            .filter(Corporation.parent_company_id == current_user.get("company_id"))
            .all()
        )

        # 2. Facility IDs
        facility_ids = [f.id for f in facilities]

        # 3. Scope includes parent + all facilities
        company_scope_ids = [current_user.get("company_id")] + facility_ids

        # 4. Shipments in scope
        shipments = (
            db.query(FTL_SHIPMENT)
            .filter(FTL_SHIPMENT.shipper_company_id.in_(company_scope_ids))
            .all()
        )

        # 5. Status counts
        status_counts = {
            "total_shipments": len(shipments),
            "in_progress": len([s for s in shipments if s.shipment_status == "In-Progress"]),
            "completed": len([s for s in shipments if s.shipment_status == "Completed"]),
            "cancelled": len([s for s in shipments if s.shipment_status == "Cancelled"]),
            "sub_shipments": len([s for s in shipments if s.is_subshipment]),
        }

        shipment_list = []

        for shipment in shipments:
            facility = (
                db.query(Corporation)
                .filter(Corporation.id == shipment.shipper_company_id)
                .first()
            )

            # safe division
            rate_per_km = shipment.quote / shipment.distance if shipment.distance else None
            rate_per_ton = shipment.quote / shipment.shipment_weight if shipment.shipment_weight else None

            shipment_list.append({
                "type": shipment.type,
                "id": shipment.id,
                "status": shipment.shipment_status,
                "priority_level": shipment.priority_level,
                "is_subshipment": shipment.is_subshipment,
                "lane_id": shipment.dedicated_lane_id if shipment.dedicated_lane_id else None,

                "facility": {
                    "name": facility.legal_business_name if facility else None,
                    "id": facility.id if facility else None,
                },

                "rate": shipment.quote,
                "origin": shipment.origin_city_province,
                "pickup_date": shipment.pickup_date,
                "pickup_appointment": shipment.pickup_appointment,

                "destination": shipment.destination_city_province,
                "eta_date": shipment.eta_date,
                "eta_window": shipment.eta_window,

                "distance": shipment.distance,
                "shipment_weight": shipment.shipment_weight,
                "commodity": shipment.commodity,

                "rate_per_km": rate_per_km,
                "rate_per_ton": rate_per_ton,
            })

        return {
            "summary": status_counts,
            "shipments": shipment_list
        }

    except Exception as e:
        print(str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/enterprise-exchange-shipments")
def get_enterprise_shipper_shipment_exchanges(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        # 1. Facilities under parent company
        facilities = (
            db.query(Corporation)
            .filter(Corporation.parent_company_id == current_user.get("company_id"))
            .all()
        )

        # 2. Facility IDs
        facility_ids = [f.id for f in facilities]

        # 3. Scope includes parent + all facilities
        company_scope_ids = [current_user.get("company_id")] + facility_ids

        # 4. Fetch all shipments for the scope
        shipment_exchanges = (
            db.query(FTL_SHIPMENT_EXCHANGE)
            .filter(FTL_SHIPMENT_EXCHANGE.shipper_company_id.in_(company_scope_ids))
            .all()
        )

        # 5. Current SAST time
        now = get_sast_time()
        two_hours_from_now = now + timedelta(hours=2)

        # 6. Status counts (timezone-safe)
        status_counts = {
            "total_exchanges": len(shipment_exchanges),
            "open": len([
                s for s in shipment_exchanges
                if s.auction_status == "Open"
            ]),
            "closing_soon": len([
                s for s in shipment_exchanges
                if s.auction_status == "Open"
                and make_aware(s.end_time) is not None
                and now <= make_aware(s.end_time) <= two_hours_from_now
            ]),
            "closed": len([
                s for s in shipment_exchanges
                if s.auction_status == "Closed"
            ]),
        }

        exchanges_list = []

        for shipment in shipment_exchanges:

            # ===========================
            #  TIMEZONE FIXES FOR FIELDS
            # ===========================
            end_time = make_aware(shipment.end_time)
            pickup_date = make_aware(shipment.pickup_date)

            facility = (
                db.query(Corporation)
                .filter(Corporation.id == shipment.shipper_company_id)
                .first()
            )

            pickup_facility = (
                db.query(ShipmentFacility)
                .filter(ShipmentFacility.id == shipment.pickup_facility_id)
                .first()
            )

            # Convert pickup_facility.end_time if needed
            pickup_window_time = make_aware(pickup_facility.end_time) if pickup_facility and pickup_facility.end_time else None

            # ===========================
            #  TRIP ETA + POLYLINES
            # ===========================
            try:
                trip_data = get_eta_and_polyline(RouteETAInput(
                    origin_address=shipment.origin_address,
                    destination_address=shipment.destination_address,
                    start_date=pickup_date,
                    start_time=pickup_window_time,
                ))

                eta_date = trip_data["eta_date"]
                eta_window = trip_data["eta_window"]

            except HTTPException as e:
                raise HTTPException(status_code=500, detail=f"Trip info calculation failed: {e.detail}")

            exchanges_list.append({
                "id": shipment.id,
                "status": shipment.auction_status,
                "type": shipment.type,
                "facility": {
                    "name": facility.legal_business_name,
                    "id": facility.id,
                },
                "end_time": end_time.isoformat() if end_time else None,
                "origin": {
                    "origin_city_province": shipment.origin_city_province,
                    "pickup_date": pickup_date.isoformat() if pickup_date else None,
                    "pickup_window": shipment.pickup_appointment,
                },
                "destination": {
                    "destination_city_province": shipment.destination_city_province,
                    "eta_date": eta_date,
                    "eta_window": eta_window,
                },
                "load_details": {
                    "distance": shipment.distance,
                    "weight": shipment.shipment_weight,
                    "commodity": shipment.commodity,
                },
                "financials": {
                    "offer": shipment.offer_price,
                    "leading_bid": shipment.leading_bid_amount,
                },
            })

        return {
            "summary": status_counts,
            "exchanges": exchanges_list
        }

    except Exception as e:
        print("Error:", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")
    
@router.get("/enterprise-lanes")
def get_enterprise_shipper_lanes(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        # 1. Facilities under parent company
        facilities = (
            db.query(Corporation)
            .filter(Corporation.parent_company_id == current_user.get("company_id"))
            .all()
        )

        # 2. Facility IDs
        facility_ids = [f.id for f in facilities]

        # 3. Scope includes parent + all facilities
        company_scope_ids = [current_user.get("company_id")] + facility_ids

        # 4. Fetch all lanes
        lanes = (
            db.query(FTL_Lane)
            .filter(FTL_Lane.shipper_company_id.in_(company_scope_ids))
            .all()
        )

        # 5. Status counts
        status_counts = {
            "total_lanes": len(lanes),
            "in_progress": len([l for l in lanes if l.status == "In-Progress"]),
            "completed": len([l for l in lanes if l.status == "Completed"]),
            "cancelled": len([l for l in lanes if l.status == "Cancelled"]),
            "disputed": len([l for l in lanes if l.status.lower() == "Disputed"]),
        }

        lane_list = []

        for lane in lanes:
            facility = (
                db.query(Corporation)
                .filter(Corporation.id == lane.shipper_company_id)
                .first()
            )

            lane_list.append({
                "id": lane.id,
                "status": lane.status,
                "priority_level": lane.priority_level,
                "type": lane.type,
                "facility": {
                    "name": facility.legal_business_name if facility else None,
                    "id": facility.id if facility else None,
                },
                "total_contract_value": lane.contract_quote,
                "origin": lane.origin_city_province,
                "destination": lane.destination_city_province,
                "distance": lane.distance,
                "contract_start_date": lane.start_date,
                "contract_end_date": lane.end_date,
                "frequency": lane.recurrence_frequency,
                "recurrence_days": lane.recurrence_days,
                "shipments_per_interval": lane.shipments_per_interval,
                "total_shipments": lane.total_shipments,
                "completed_shipments": lane.progress if lane.progress else 0,
                "rate_per_shipment": lane.qoute_per_shipment,
                "payment_terms": lane.payment_terms,
            })

        return {
            "summary": status_counts,
            "lanes": lane_list
        }

    except Exception as e:
        print("Error:", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

def make_aware(dt):
    """
    Safely handles:
    - None
    - date
    - naive datetime
    - timezone-aware datetime
    """

    if dt is None:
        return None

    sast = ZoneInfo("Africa/Johannesburg")

    # Case 1: date-only → convert to datetime at midnight SAST
    if isinstance(dt, datetime) is False:
        # dt is a datetime.date
        return datetime(dt.year, dt.month, dt.day, tzinfo=sast)

    # Case 2: already timezone-aware
    if dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None:
        return dt

    # Case 3: naive datetime → make SAST aware
    return dt.replace(tzinfo=sast)

@router.get("/enterprise-exchange-lanes")
def get_enteprise_shipper_exchange_lanes(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        # 1. Facilities under parent company
        facilities = (
            db.query(Corporation)
            .filter(Corporation.parent_company_id == current_user.get("company_id"))
            .all()
        )

        # 2. Facility IDs
        facility_ids = [f.id for f in facilities]

        # 3. Scope includes parent + all facilities
        company_scope_ids = [current_user.get("company_id")] + facility_ids

        # 4. Fetch all lanes
        lane_exchanges = (
            db.query(FTL_Lane_Exchange)
            .filter(FTL_Lane_Exchange.shipper_company_id.in_(company_scope_ids))
            .all()
        )

        # Current SAST time
        now = get_sast_time()
        two_hours_from_now = now + timedelta(hours=2)

        # 5. Status counts with safe timezone-aware handling
        status_counts = {
            "total_exchanges": len(lane_exchanges),
            "open": len([
                l for l in lane_exchanges
                if l.auction_status == "Open"
            ]),
            "closing_soon": len([
                l for l in lane_exchanges
                if l.auction_status == "Open"
                and make_aware(l.exchange_end_time) is not None
                and now <= make_aware(l.exchange_end_time) <= two_hours_from_now
            ]),
            "closed": len([l for l in lane_exchanges if l.auction_status == "Closed"]),
        }

        lane_list = []

        for lane in lane_exchanges:

            # Make DB times timezone-aware
            start_date = make_aware(lane.start_date)
            end_date = make_aware(lane.end_date)
            exchange_end_time = make_aware(lane.exchange_end_time)

            facility = (
                db.query(Corporation)
                .filter(Corporation.id == lane.shipper_company_id)
                .first()
            )

            lane_list.append({
                "id": lane.id,
                "status": lane.auction_status,
                "facility": {
                    "name": facility.legal_business_name,
                    "id": facility.id,
                },
                "exchange_end_time": exchange_end_time.isoformat() if exchange_end_time else None,
                "origin": lane.origin_city_province,
                "destination": lane.destination_city_province,
                "distance": lane.distance,
                "average_weight": lane.average_shipment_weight,
                "commodity": lane.commodity,
                "contract_details": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                    "frequency": lane.recurrence_frequency,
                    "recurrence_days": lane.recurrence_days,
                },
                "shipment_details": {
                    "shipments_per_interval": lane.shipments_per_interval,
                    "total_shipments": lane.total_shipments,
                    "payment_terms": lane.payment_terms,
                },
                "bidding_details": {
                    "bids_submitted": lane.number_of_bids_submitted,
                    "offer": {
                        "per_shipment": lane.per_shipment_offer_rate,
                        "contract_total": lane.contract_offer_rate,
                    },
                    "leading_bid": {
                        "per_shipment": lane.leading_per_shipment_bid_amount,
                        "contract_total": lane.leading_contract_bid_amount,
                    }
                },
            })

        return {
            "summary": status_counts,
            "lanes": lane_list
        }

    except Exception as e:
        print("Error:", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

