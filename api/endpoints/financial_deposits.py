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
        "ent": "http://contracts.it.nednet.co.za/Infrastructure/2008/09/EnterpriseContext",
    }

    # Find SOAP body and DistributeMsgRq
    body_node = root.find(".//soapenv:Body", ns)
    if body_node is None:
        raise HTTPException(status_code=400, detail="Missing SOAP Body")

    rq = body_node.find("ns2:DistributeMsgRq", ns)
    if rq is None:
        raise HTTPException(status_code=400, detail="Missing DistributeMsgRq")

    # Extract TransformedData
    transformed_data_node = rq.find(".//ns2:TransformedData", ns)
    if transformed_data_node is None or not transformed_data_node.text:
        raise HTTPException(status_code=400, detail="Missing TransformedData")

    # Clean + decode TransformedData
    clean_data = "".join(transformed_data_node.text.split())
    try:
        decoded_xml = base64.b64decode(clean_data).decode("utf-8")
        inner_root = ET.fromstring(decoded_xml)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid TransformedData")

    # Extract fields from decoded XML
    transaction_id = inner_root.findtext(".//TransactionKey")
    unique_key = inner_root.findtext(".//ProcessKey")
    reference = inner_root.findtext(".//UserRef")
    amount = inner_root.findtext(".//Amount")

    # Call business logic (safe defaults if None)
    result = process_deposit(
        db=db,
        transaction_id=transaction_id or "",
        unique_transaction_key=unique_key or "",
        amount=float(amount) if amount else 0.0,
        reference=reference or "",
        timestamp=None
    )

    # Build SOAP response (as per Nedbank contract)
    response_xml = """<?xml version="1.0" encoding="UTF-8"?>
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