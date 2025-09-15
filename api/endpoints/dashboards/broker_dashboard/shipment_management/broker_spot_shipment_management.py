from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.brokerage.assigned_shipments import Assigned_Spot_Ftl_Shipments
from models.brokerage.finance import BrokerageLedger, CarrierFinancialAccounts, FinancialAccounts, Interim_Invoice, Load_Invoice, Brokers_Brokerage_Transactions
from models.brokerage.loadboard import Ftl_Load_Board
from models.carrier import Carrier
from models.spot_bookings.dedicated_lane_ftl_shipment import FTL_Lane
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from models.Exchange.ftl_shipment import FTL_SHIPMENT_EXCHANGE
from models.Exchange.power_shipment import POWER_SHIPMENT_EXCHANGE
from models.Exchange.dedicated_ftl_lane import FTL_Lane_Exchange
from models.spot_bookings.shipment_facility import ContactPerson, ShipmentFacility
from models.user import Driver
from models.vehicle import ShipperTrailer, Vehicle
from models.shipper import Consignor
from schemas.spot_bookings.dedicated_lanes_ftl_shipment import Ftl_Lanes_Summary_Response, Individual_FTL_Lane_Response, individual_shipment_or_lane_request
from schemas.spot_bookings.ftl_shipment import FTL_Shipment_Response, FTL_Shipments_Summary_Response
from schemas.spot_bookings.power_shipment import POWER_SHIPMENT_RESPONSE, Power_Shipments_Summary_Response
from utils.auth import get_current_user
from services.cancellations.spot_cancellations import cancel_spot_ftl_shipment


router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/broker-access")
def broker_access_get_dashboard_home_data(
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

    # =========================
    # 1. GET SHIPMENTS
    # =========================
    ftl_shipments = db.query(FTL_SHIPMENT).filter(
        FTL_SHIPMENT.shipper_company_id == company_id
    ).all()
    ftl_shipment_ids = [shipment.id for shipment in ftl_shipments]

    power_shipments = db.query(POWER_SHIPMENT).filter(
        POWER_SHIPMENT.shipper_company_id == company_id
    ).all()
    power_shipment_ids = [shipment.id for shipment in power_shipments]

    # Brokerage transactions
    ftl_brokerage_transactions = []
    power_brokerage_transactions = []

    # Brokerage transactions
    if ftl_shipment_ids:
        ftl_brokerage_transactions = db.query(Brokers_Brokerage_Transactions).filter(
            Brokers_Brokerage_Transactions.shipment_id.in_(ftl_shipment_ids),
            Brokers_Brokerage_Transactions.type == "FTL"
        ).all()

    if power_shipment_ids:
        power_brokerage_transactions = db.query(Brokers_Brokerage_Transactions).filter(
            Brokers_Brokerage_Transactions.shipment_id.in_(power_shipment_ids),
            Brokers_Brokerage_Transactions.type == "POWER"
        ).all()

    ftl_brokerage_map = {bt.shipment_id: bt.consignor_billable for bt in ftl_brokerage_transactions}
    power_brokerage_map = {bt.shipment_id: bt.consignor_billable for bt in power_brokerage_transactions}

    loads = ftl_shipments + power_shipments

    def format_load(load):
        brokerage_map = ftl_brokerage_map if load.type == "FTL" else power_brokerage_map
        return {
            "consignor_ref": load.consignor_id,
            "type": load.type,
            "status": {
                "load_status": load.shipment_status,
                "last_updated": load.updated_at,
            },
            "pickup": {
                "origin": load.origin_city_province,
                "appointment": f"{load.pickup_date}-{load.pickup_appointment}"
            },
            "dropoff": {
                "destination": load.destination_city_province,
                "eta_window": f"{load.eta_date}-{load.eta_window}"
            },
            "details": {
                "truck_type": getattr(load, "required_truck_type", None),
                "axle_configuration": getattr(load, "axle_configuration", None),
                "equipment_type": getattr(load, "equipment_type", None),
                "trailer_type": getattr(load, "trailer_type", None),
                "trailer_length": getattr(load, "trailer_length", None),
                "commodity": getattr(load, "commodity", None),
            },
            "distance": {
                "trip_distance": load.distance,
                "transit_time": load.estimated_transit_time,
            },
            "price": {
                "rate": load.quote,
                "consignor_billable": brokerage_map.get(load.id, None),
                "priority_level": load.priority_level
            }
        }

    grouped_loads = {
        "all_loads": [format_load(load) for load in loads],
        "booked": [format_load(load) for load in loads if load.shipment_status == "Booked"],
        "assigned": [format_load(load) for load in loads if load.shipment_status == "Assigned"],
        "in_progress": [format_load(load) for load in loads if load.shipment_status == "In-progress"],
        "completed": [format_load(load) for load in loads if load.shipment_status == "Completed"],
        "cancelled": [format_load(load) for load in loads if load.shipment_status == "Cancelled"],
    }

    # =========================
    # 2. GET LANES
    # =========================
    lanes = db.query(FTL_Lane).filter(FTL_Lane.shipper_company_id == company_id).all()

    def format_lane(lane):
        return {
            "id": lane.id,
            "type": "FTL",
            "status": lane.status,  # e.g., Active
            "per_shipment_rate": lane.qoute_per_shipment,
            "origin": lane.origin_city_province,
            "destination": lane.destination_city_province,
            "distance": lane.distance,
            "frequency": lane.recurrence_frequency,  # e.g., "3 times weekly"
            "completed_shipments": lane.progress,
            "total_shipments": lane.total_shipments,
        }

    formatted_lanes = [format_lane(lane) for lane in lanes]

    # =========================
    # 3. GET EXCHANGES
    # =========================
    ftl_exchanges = db.query(FTL_SHIPMENT_EXCHANGE).filter(
        FTL_SHIPMENT_EXCHANGE.shipper_company_id == company_id
    ).all()

    power_exchanges = db.query(POWER_SHIPMENT_EXCHANGE).filter(
        POWER_SHIPMENT_EXCHANGE.shipper_company_id == company_id
    ).all()

    shipment_exchanges = ftl_exchanges + power_exchanges

    lane_exchanges = db.query(FTL_Lane_Exchange).filter(
        FTL_Lane_Exchange.shipper_company_id == company_id
    ).all()

    def format_shipment_exchange(exchange):
        return {
            "id": exchange.id,
            "type": exchange.type,
            "status": exchange.auction_status,  # e.g., Open
            "origin": exchange.origin_city_province,
            "pickup_date": exchange.pickup_date,
            "destination": exchange.destination_city_province,
            "your_offer_rate": exchange.offer_price,
            "leading_bid": exchange.leading_bid_amount if exchange.leading_bid_amount else None,
            "bids_submitted": exchange.number_of_bids_submitted,
        }

    def format_lane_exchange(exchange):
        return {
            "id": exchange.id,
            "type": "FTL Lane",
            "status": exchange.auction_status,  # e.g., Open
            "bids": exchange.number_of_bids_submitted,
            "origin": exchange.origin_city_province,
            "destination": exchange.destination_city_province,
            "per_shipment_offer": exchange.per_shipment_offer_rate,
            "contract_offer": exchange.contract_offer_rate,
            "leading_bid_per_shipment": exchange.leading_per_shipment_bid_amount,
            "leading_bid_contract_total": exchange.leading_contract_bid_amount,
            "end_time": exchange.exchange_end_time
        }

    formatted_shipment_exchanges = [format_shipment_exchange(ex) for ex in shipment_exchanges]
    formatted_lane_exchanges = [format_lane_exchange(ex) for ex in lane_exchanges]

    # =========================
    # FINAL RESPONSE
    # =========================
    return {
        "shipments": grouped_loads,
        "lanes": formatted_lanes,
        "exchanges": {
            "shipment_exchanges": formatted_shipment_exchanges,
            "lane_exchanges": formatted_lane_exchanges
        }
    }
