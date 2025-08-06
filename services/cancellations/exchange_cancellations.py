from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime
from sqlalchemy.orm import Session
from models.Exchange.ftl_shipment import FTL_SHIPMENT_EXCHANGE
from models.Exchange.power_shipment import POWER_SHIPMENT_EXCHANGE
from models.brokerage.loadboards.exchange_loadboards import Exchange_Ftl_Load_Board, Exchange_Power_Load_Board
from models.brokerage.assigned_shipments import Assigned_Spot_Ftl_Shipments, Assigned_Power_Shipments
from models.brokerage.finance import BrokerageLedger, FinancialAccounts, Shipment_Invoice, Load_Invoice
from utils.auth import get_current_user

############################################FTL Exchange Cancellation###################################
def cancel_exchange_ftl_booking(exchange_id: int, db: Session, current_user: dict):
    user_id = current_user.get("id")
    company_id = current_user.get("company_id")

    # 1. Retrive Exchange
    exchange = db.query(FTL_SHIPMENT_EXCHANGE).filter(FTL_SHIPMENT_EXCHANGE.id == exchange_id).first()
    if not exchange:
        raise HTTPException(status_code=404, detail="Exchange not found")
    if not exchange.shipper_company_id == company_id:
        raise HTTPException(status_code=403, detail="You are not authorized to cancel this exchange")
    if exchange.auction_status == "Cancelled":
        raise HTTPException(status_code=400, detail="Exchange is already cancelled")
    if exchange.auction_status in ["Closed", "Awarded"]:
        raise HTTPException(status_code=400, detail="Exhange booking cannot be cancelled once it's closed or awarded.")

    exchange_loadboard = db.query(Exchange_Ftl_Load_Board).filter(Exchange_Ftl_Load_Board.exchange_id == exchange_id).first()
    if not exchange_loadboard:
        raise HTTPException(status_code=404, detail="Exchange loadboard not found")

    # 3. Update Status
    exchange.auction_status = "Cancelled"
    exchange_loadboard.status = "Cancelled"

    db.add(exchange)
    db.add(exchange_loadboard)
    db.commit()
    return {"message": f"Exchange {exchange.id} cancelled successfully"}

##########################################POWER Exchnage Cancellation####################################
def cancel_exchange_power_booking(exchange_id: int, db: Session, current_user: dict):
    user_id = current_user.get("id")
    company_id = current_user.get("company_id")

    # 1. Retrive Exchange
    exchange = db.query(POWER_SHIPMENT_EXCHANGE).filter(POWER_SHIPMENT_EXCHANGE.id == exchange_id).first()
    if not exchange:
        raise HTTPException(status_code=404, detail="Exchange not found")
    if not exchange.shipper_company_id == company_id:
        raise HTTPException(status_code=403, detail="You are not authorized to cancel this exchange")
    if exchange.auction_status == "Cancelled":
        raise HTTPException(status_code=400, detail="Exchange is already cancelled")
    if exchange.auction_status in ["Closed", "Awarded"]:
        raise HTTPException(status_code=400, detail="Exhange booking cannot be cancelled once it's closed or awarded.")

    exchange_loadboard = db.query(Exchange_Power_Load_Board).filter(Exchange_Power_Load_Board.exchange_id == exchange_id).first()
    if not exchange_loadboard:
        raise HTTPException(status_code=404, detail="Exchange loadboard not found")

    # 3. Update Status
    exchange.auction_status = "Cancelled"
    exchange_loadboard.status = "Cancelled"

    db.add(exchange)
    db.add(exchange_loadboard)
    db.commit()
    return {"message": f"Exchange {exchange.id} cancelled successfully"}