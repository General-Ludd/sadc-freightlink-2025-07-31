from fastapi import APIRouter, Request, HTTPException, status, Response, Depends
from sqlalchemy.orm import Session
from db.database import SessionLocal
from services.brokerage.payment_processor import process_deposit
import xmltodict
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
    """
    SOAP endpoint for Nedbank DistributeMsg operation.
    Accepts XML and returns SOAP-compliant XML.
    """
    body = await request.body()
    try:
        parsed = xmltodict.parse(body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid XML: {str(e)}")

    # Navigate SOAP Envelope
    envelope = parsed.get("soap:Envelope") or parsed.get("Envelope")
    if not envelope:
        raise HTTPException(status_code=400, detail="Missing SOAP Envelope")

    # Extract Header (EnterpriseContext)
    header = envelope.get("soap:Header", {}).get("ent2:EnterpriseContext")
    # You may want to validate fields from EnterpriseContext later

    # Extract Body (DistributeMsgRq)
    body_content = envelope.get("soap:Body")
    if not body_content or "tns:DistributeMsgRq" not in body_content:
        raise HTTPException(status_code=400, detail="Missing DistributeMsgRq")

    rq = body_content["tns:DistributeMsgRq"]

    # Map XML fields to Python variables
    transaction_id = rq.get("TransactionId")
    unique_key = rq.get("UniqueKey")
    amount = float(rq.get("Amount", 0))
    reference = rq.get("Reference")
    timestamp = rq.get("Timestamp")
    key = rq.get("Key")

    # Security check
    if key != NEDBANK_SECRET_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid key")

    # Process deposit
    result = process_deposit(
        db=db,
        transaction_id=transaction_id,
        unique_transaction_key=unique_key,
        amount=amount,
        reference=reference,
        timestamp=timestamp
    )

    # Build SOAP Response
    response_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                   xmlns:tns="http://contracts.it.nednet.co.za/services/business-execution/2013-11-01/TIWebDistribution">
      <soap:Header>
        <!-- Echo EnterpriseContext if needed -->
      </soap:Header>
      <soap:Body>
        <tns:DistributeMsgRs>
          <Status>{result.get("status")}</Status>
          <AccountId>{result.get("account_id") or ""}</AccountId>
          <NewCreditBalance>{result.get("new_credit_balance") or ""}</NewCreditBalance>
          <NewTotalOutstanding>{result.get("new_total_outstanding") or ""}</NewTotalOutstanding>
          <NewTotalPaid>{result.get("new_total_paid") or ""}</NewTotalPaid>
          <Message>{result.get("message") or ""}</Message>
        </tns:DistributeMsgRs>
      </soap:Body>
    </soap:Envelope>
    """

    return Response(content=response_xml, media_type="application/xml")