from fastapi import APIRouter, Request, HTTPException, status, Response, Depends
from sqlalchemy.orm import Session
from db.database import SessionLocal
from services.brokerage.payment_processor import process_deposit
import xmltodict
import xml.etree.ElementTree as ET
import os
import math
from pydantic import BaseModel
from datetime import date, datetime

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

NEDBANK_SECRET_KEY = os.getenv("NEDBANK_WEBHOOK_KEY")

@router.post("/nedbank/deposit", response_class=Response)
async def nedbank_deposit(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    try:
        root = ET.fromstring(body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid XML")

    ns = {
        "soap": "http://schemas.xmlsoap.org/soap/envelope/",
        "tns": "http://contracts.it.nednet.co.za/services/business-execution/2013-11-01/TIWebDistribution"
    }

    # Extract fields from SOAP body
    body_node = root.find(".//soap:Body", ns)
    rq = body_node.find("tns:DistributeMsgRq", ns)

    transaction_id = rq.findtext("TransactionId")
    unique_key = rq.findtext("UniqueKey")
    amount = float(rq.findtext("Amount"))
    reference = rq.findtext("Reference")
    timestamp = rq.findtext("Timestamp")
    key = rq.findtext("Key")

    # Validate secret key
    if key != NEDBANK_SECRET_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid key")

    result = process_deposit(
        db=db,
        transaction_id=transaction_id,
        unique_transaction_key=unique_key,
        amount=amount,
        reference=reference,
        timestamp=timestamp
    )

    # Build SOAP response
    response_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                   xmlns:tns="http://contracts.it.nednet.co.za/services/business-execution/2013-11-01/TIWebDistribution">
      <soap:Body>
        <tns:DistributeMsgRs>
          <Status>{result['status']}</Status>
          <AccountId>{result.get('account_id', '')}</AccountId>
          <NewCreditBalance>{result.get('new_credit_balance', '')}</NewCreditBalance>
          <NewTotalOutstanding>{result.get('new_total_outstanding', '')}</NewTotalOutstanding>
          <NewTotalPaid>{result.get('new_total_paid', '')}</NewTotalPaid>
          <Message>{result.get('message', '')}</Message>
        </tns:DistributeMsgRs>
      </soap:Body>
    </soap:Envelope>"""

    return Response(content=response_xml, media_type="application/xml")