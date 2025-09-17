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

@router.post("/nedbank/deposit")
async def nedbank_deposit(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    xml_str = raw_body.decode("utf-8")

    try:
        # Parse the incoming SOAP XML
        data = xmltodict.parse(xml_str)

        # Navigate SOAP structure (adjust keys based on actual WSDL schema)
        deposit = data["soap:Envelope"]["soap:Body"]["DepositNotification"]

        transaction_id = deposit["TransactionId"]
        unique_transaction_key = deposit["UniqueKey"]
        deposit_amount = float(deposit["Amount"])
        reference = deposit["Reference"]
        timestamp = datetime.fromisoformat(deposit["Timestamp"])
        key = deposit.get("Key")  # optional, depending on WSDL

        # Validate secret key (if provided in payload)
        if key and key != NEDBANK_SECRET_KEY:
            return Response(
                content="""
                <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                  <soap:Body>
                    <soap:Fault>
                      <faultcode>SOAP-ENV:Client</faultcode>
                      <faultstring>Invalid key</faultstring>
                    </soap:Fault>
                  </soap:Body>
                </soap:Envelope>
                """,
                media_type="application/xml",
                status_code=401
            )

        # Process deposit using your existing business logic
        result = process_deposit(
            db=db,
            transaction_id=transaction_id,
            unique_transaction_key=unique_transaction_key,
            amount=deposit_amount,
            reference=reference,
            timestamp=timestamp
        )

        # Build SOAP response
        response_xml = f"""
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <DepositNotificationResponse>
              <Status>{result['status']}</Status>
              <AccountId>{result.get('account_id', '')}</AccountId>
              <NewCreditBalance>{result.get('new_credit_balance', '')}</NewCreditBalance>
              <NewTotalOutstanding>{result.get('new_total_outstanding', '')}</NewTotalOutstanding>
              <NewTotalPaid>{result.get('new_total_paid', '')}</NewTotalPaid>
              <Message>{result.get('message', '')}</Message>
            </DepositNotificationResponse>
          </soap:Body>
        </soap:Envelope>
        """

        return Response(content=response_xml, media_type="application/xml")

    except Exception as e:
        # SOAP Fault on error
        return Response(
            content=f"""
            <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
              <soap:Body>
                <soap:Fault>
                  <faultcode>SOAP-ENV:Server</faultcode>
                  <faultstring>{str(e)}</faultstring>
                </soap:Fault>
              </soap:Body>
            </soap:Envelope>
            """,
            media_type="application/xml",
            status_code=500
        )