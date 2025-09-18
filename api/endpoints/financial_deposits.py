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
        "soapenv": "http://schemas.xmlsoap.org/soap/envelope/",
        "ns2": "http://contracts.it.nednet.co.za/services/business-execution/2013-11-01/TIWebDistribution",
        "ec": "http://contracts.it.nednet.co.za/Infrastructure/2008/09/EnterpriseContext"
    }

    # Find DistributeMsgRq
    body_node = root.find(".//soapenv:Body", ns)
    rq = body_node.find("ns2:DistributeMsgRq", ns)

    if rq is None:
        raise HTTPException(status_code=400, detail="Missing DistributeMsgRq")

    # Extract TransformedData (base64 encoded XML)
    transformed_data_node = rq.find(".//ns2:TransformedData", ns)
    if transformed_data_node is None or not transformed_data_node.text:
        raise HTTPException(status_code=400, detail="Missing TransformedData")

    try:
        inner_xml = base64.b64decode(transformed_data_node.text).decode("utf-8")
        inner_root = ET.fromstring(inner_xml)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid TransformedData")

    # Extract fields from inner XML
    record = inner_root.find(".//TIRealtimeRecord")
    if record is None:
        raise HTTPException(status_code=400, detail="Invalid TIRealtimeRecord")

    transaction_id = record.findtext("TransactionKey")
    unique_key = record.findtext("ProcessKey")
    amount = float(record.findtext("Amount"))
    reference = record.findtext("UserRef")
    date = record.findtext("Date")
    time = record.findtext("Time")
    timestamp = f"{date}T{time}" if date and time else None

    # Call your deposit processor
    result = process_deposit(
        db=db,
        transaction_id=transaction_id,
        unique_transaction_key=unique_key,
        amount=amount,
        reference=reference,
        timestamp=timestamp
    )

    # Build SOAP response in Nedbank's required format
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