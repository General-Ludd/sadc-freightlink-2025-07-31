from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from requests import Session
from db.database import SessionLocal
from models.shipper import Consignor
from schemas.shipper import ConsignorCreate
from services.shipper_service import create_brokerage_firm_consignor_client
from utils.auth import get_current_user


router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/broker-access/create-client")
def create_new_brokerage_firm_client(
    consignor_data: ConsignorCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        result = create_brokerage_firm_consignor_client(consignor_data, db, current_user=current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/broker-access/all-clients")
def get_all_brokerage_firm_clients(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    try:
        clients = db.query(Consignor).filter(
            Consignor.brokerage_firm_id == company_id,
        ).all()

        # Group by priority levels
        high_priority = []
        medium_priority = []
        low_priority = []

        for client in clients:
            client_data = {
                "company_name": client.company_name,
                "id": client.id,
                "status": client.status,
                "priority_level": client.priority_level,
                "phone_number": client.phone_number,
                "email": client.email,
                "client_type": client.client_type,
                "business_sector": client.business_sector,
                "shipments": client.shipments,
                "contracts": client.contract_lanes,
                "revenue_generated": client.revenue_generated,
                "profit_generated": client.profit_generated
            }

            if client.priority_level == "High":
                high_priority.append(client_data)
            elif client.priority_level == "Medium":
                medium_priority.append(client_data)
            elif client.priority_level == "Low":
                low_priority.append(client_data)

        return {
            "high_priority_clients": high_priority,
            "medium_priority_clients": medium_priority,
            "low_priority_clients": low_priority
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

from sqlalchemy import desc

@router.get("/broker-access/{client_id}")
def get_brokerage_firm_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    try:
        client = db.query(Consignor).filter(
            Consignor.id == client_id,
            Consignor.brokerage_firm_id == company_id
        ).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Fetch shipments ordered by newest first
        ftl_shipments = db.query(FTL_SHIPMENT).filter(
            FTL_SHIPMENT.consignor_id == client.id
        ).order_by(desc(FTL_SHIPMENT.pickup_date)).all()

        power_shipments = db.query(POWER_SHIPMENT).filter(
            POWER_SHIPMENT.consignor_id == client.id
        ).order_by(desc(POWER_SHIPMENT.pickup_date)).all()

        shipments = ftl_shipments + power_shipments
        cancelled_loads = sum(1 for s in shipments if s.shipment_status == "Cancelled")

        # Fetch all transactions for this client
        transactions = db.query(Brokers_Brokerage_Transactions).filter(
            Brokers_Brokerage_Transactions.consignor_id == client.id
        ).order_by(desc(Brokers_Brokerage_Transactions.created_at)).all()

        # Build lookups for transactions
        shipment_tx_map = {f"{t.type}-{t.shipment_id}": t for t in transactions if t.shipment_id}
        lane_tx_map = {t.lane_id: t for t in transactions if t.lane_id}

        # Fetch lanes ordered by newest first
        lanes = db.query(FTL_Lane).filter(
            FTL_Lane.consignor_id == client.id
        ).order_by(desc(FTL_Lane.start_date)).all()

        cancelled_lanes = sum(1 for l in lanes if l.status == "Cancelled")

        # Shipments + invoices
        shipment_list = []
        invoice_list = []
        for shipment in shipments:
            invoices = db.query(Shipment_Invoice).filter(
                Shipment_Invoice.shipment_id == shipment.id,
                Shipment_Invoice.shipment_type == shipment.type,
                Shipment_Invoice.is_applied == True
            ).order_by(desc(Shipment_Invoice.billing_date)).all()
            invoice_list.extend(invoices)

            key = f"{shipment.type}-{shipment.id}"
            tx = shipment_tx_map.get(key)
            shipment_list.append({
                "id": shipment.id,
                "type": shipment.type,
                "status": shipment.shipment_status,
                "origin": shipment.origin_city_province,
                "destination": shipment.destination_city_province,
                "distance": shipment.distance,
                "pickup_date": shipment.pickup_date,
                "rate": shipment.quote,
                "consignor_billable": tx.per_shipment_consignor_billable if tx else 0,
                "profit": tx.per_shipment_profit if tx else 0
            })

        # Lanes response
        lane_list = []
        for lane in lanes:
            tx = lane_tx_map.get(lane.id)
            lane_list.append({
                "id": lane.id,
                "type": lane.type,
                "status": lane.status,
                "start_date": lane.start_date,
                "end_date": lane.end_date,
                "origin": lane.origin_city_province,
                "destination": lane.destination_city_province,
                "total_shipments": lane.total_shipments,
                "completed_shipments": lane.progress,
                "total_contract_rate": lane.contract_quote,
                "carrier_rates": {
                    "per_shipment": lane.qoute_per_shipment,  # ✅ fixed typo
                    "contract_total": lane.contract_quote
                },
                "client_billable": {
                    "per_shipment": tx.per_shipment_consignor_billable if tx else 0,
                    "contract_total": tx.contract_consignor_billable if tx else 0,
                },
                "profit_summary": {
                    "per_shipment": tx.per_shipment_profit if tx else 0,
                    "contract_total": tx.contract_profit if tx else 0
                }
            })

        return {
            "client": {
                "company_name": client.company_name,
                "id": client.id,
                "status": client.status,
                "priority_level": client.priority_level,
                "client_type": client.client_type,
                "business_sector": client.business_sector,
                "company_website": client.company_website,
                "address": client.business_address,
                "contact_person_name": client.contact_person_name,
                "position": client.position,
                "phone_number": client.phone_number,
                "email": client.email,
                "preferred_contact_method": client.preferred_contact_method,
                "client_notes": client.client_notes,
            },
            "activity_overview": {
                "shipments": [{"pickup_date": s.pickup_date} for s in shipments],
                "revenue": [{"date": inv.billing_date, "amount": inv.due_amount} for inv in invoice_list],
            },
            "financial_summary": {
                "total_loads": len(shipments),
                "cancelled_loads": cancelled_loads,
                "total_contract_lanes": len(lanes),
                "cancelled_contract_lanes": cancelled_lanes,
                "total_revenue_generated": client.revenue_generated,
                "total_profit_generated": client.profit_generated
            },
            "shipments": shipment_list,
            "contract_lanes": lane_list
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
