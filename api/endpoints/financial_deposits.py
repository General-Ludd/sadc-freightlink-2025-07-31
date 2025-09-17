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
    decoded = body.decode("utf-8", errors="replace")

    try:
        root = ET.fromstring(decoded)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid XML: {str(e)}")

    ns = {
        "soapenv": "http://schemas.xmlsoap.org/soap/envelope/",
        "ns2": "http://contracts.it.nednet.co.za/services/business-execution/2013-11-01/TIWebDistribution",
        "ent": "http://contracts.it.nednet.co.za/Infrastructure/2008/09/EnterpriseContext"
    }

    # Extract fields from SOAP body
    body_node = root.find(".//soapenv:Body", ns)
    if body_node is None:
        raise HTTPException(status_code=400, detail="SOAP Body not found")

    rq = body_node.find("ns2:DistributeMsgRq", ns)
    if rq is None:
        raise HTTPException(status_code=400, detail="DistributeMsgRq element not found")

    transaction_id = rq.findtext("TransactionId")
    unique_key = rq.findtext("UniqueKey")
    amount = float(rq.findtext("Amount"))
    reference = rq.findtext("Reference")
    timestamp = rq.findtext("Timestamp")
    key = rq.findtext("Key")

    # Validate secret key
    if key != NEDBANK_SECRET_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid key")

    # Process the deposit
    process_deposit(
        db=db,
        transaction_id=transaction_id,
        unique_transaction_key=unique_key,
        amount=amount,
        reference=reference,
        timestamp=timestamp
    )

    # Respond **only** with ResultCode R00 (success)
    response_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:ns2="http://contracts.it.nednet.co.za/services/business-execution/2013-11-01/TIWebDistribution"
                  xmlns="http://contracts.it.nednet.co.za/Infrastructure/2008/09/EnterpriseContext">
  <soapenv:Body>
    <ns2:DistributeMsgRs>
      <ns2:ResultCode>R00</ns2:ResultCode>
    </ns2:DistributeMsgRs>
  </soapenv:Body>
</soapenv:Envelope>"""

    return Response(content=response_xml, media_type="application/xml")