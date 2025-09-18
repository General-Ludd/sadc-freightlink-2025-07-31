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

def strip_ns(tag: str) -> str:
    """Remove XML namespace from tag name."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag

@router.post("/nedbank/deposit", response_class=Response)
async def nedbank_deposit(request: Request, db: Session = Depends(get_db)):
    result_code = "R00"  # Always return R00
    try:
        body = await request.body()
        root = ET.fromstring(body.decode("utf-8"))

        # Extract SOAP Body → DistributeMsgRq
        body_node = root.find(".//{http://schemas.xmlsoap.org/soap/envelope/}Body")
        rq = None
        for child in body_node:
            if strip_ns(child.tag) == "DistributeMsgRq":
                rq = child
                break
        if rq is None:
            raise ValueError("DistributeMsgRq not found")

        # Find TransformedData node
        transformed_data_node = None
        for elem in rq.iter():
            if strip_ns(elem.tag) == "TransformedData":
                transformed_data_node = elem
                break
        if transformed_data_node is None or not transformed_data_node.text:
            raise ValueError("TransformedData missing")

        # Decode Base64 safely
        clean_data = "".join(transformed_data_node.text.split())
        decoded_xml = base64.b64decode(clean_data, validate=False).decode("utf-8")

        # Parse inner XML and remove namespaces
        inner_root = ET.fromstring(decoded_xml)
        inner_data = {strip_ns(child.tag): child.text for child in inner_root.iter()}

        # Map to deposit function
        transaction_id = inner_data.get("TransactionKey", "")
        unique_key = inner_data.get("ProcessKey", "")
        reference = inner_data.get("UserRef", "")
        amount = float(inner_data.get("Amount", 0))
        timestamp = inner_data.get("Time", "")

        # Call deposit function
        deposit_result = process_deposit(
            db=db,
            transaction_id=transaction_id,
            unique_transaction_key=unique_key,
            amount=amount,
            reference=reference,
            timestamp=timestamp
        )
        print("Deposit result:", deposit_result)

    except Exception as e:
        # Log errors but always return R00
        print("Error processing Nedbank deposit:", str(e))

    # Build SOAP response
    response_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:ns2="http://contracts.it.nednet.co.za/services/business-execution/2013-11-01/TIWebDistribution"
                  xmlns="http://contracts.it.nednet.co.za/Infrastructure/2008/09/EnterpriseContext">
  <soapenv:Body>
    <ns2:DistributeMsgRs>
      <ns2:ResultCode>{result_code}</ns2:ResultCode>
    </ns2:DistributeMsgRs>
  </soapenv:Body>
</soapenv:Envelope>"""
    return Response(content=response_xml, media_type="application/xml")