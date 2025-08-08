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
        result = create_brokerage_firm_consignor_client(db, consignor_data, current_user=current_user)
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
        clients = db.query(Consignor).filter(Consignor.brokerage_firm_id == company_id).all()

        return {
            "clients": [{
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
            } for client in clients]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/broker-access/all-clients/{status}")
def get_all_brokerage_firm_clients_by_status(
    status: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    try:
        clients = db.query(Consignor).filter(Consignor.brokerage_firm_id == company_id,
                                            Consignor.status == status).all()

        return {
            "clients": [{
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
            } for client in clients]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/broker-access/{client_id}")
def get_brokerage_firm_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    try:
        client = db.query(Consignor).filter(Consignor.id == client_id,
                                            Consignor.brokerage_firm_id == company_id).first()

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
                "position": position,
                "phone_number": client.phone_number,
                "email": client.email,
                "preferred_contact_method": client.preferred_contact_method,
                "client_notes": client.client_notes,
                "shipments": client.shipments,
                "contracts": client.contract_lanes,
                "revenue_generated": client.revenue_generated,
                "profit_generated": client.profit_generated
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))