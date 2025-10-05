from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from utils.sast_datetime import get_sast_time
from models.communication import Shipper_Support_Ticket, Brokerage_Firm_Support_Ticket, Carrier_Support_Ticket
from modlels.communication import Contact_Us

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/create-shipper-support-ticket", status_code=status.HTTP_201_CREATED)
def create_shipper_support_ticket(ticket_data: Contact_Us, db: Session = Depends(get_db)):
    """
    Create a new Shipper Support Ticket when a shipper submits a support or inquiry form.
    """

    try:
        new_ticket = Shipper_Support_Ticket(
            name=ticket_data.name,
            company_name=ticket_data.company_name,
            phone_number=ticket_data.phone_number,
            email=ticket_data.email,
            subject=ticket_data.subject,
            description=ticket_data.description,
            is_read=False,
            status="Open",
            created_at=get_sast_time(),
            updated_at=get_sast_time(),
        )

        db.add(new_ticket)
        db.commit()
        db.refresh(new_ticket)

        return {
            "message": "Support ticket created successfully, our team will be in touch shortly.",
            "ticket_id": new_ticket.id,
            "status": "open"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create support ticket: {str(e)}"
        )

@router.post("/create-brokerage-firm-support-ticket", status_code=status.HTTP_201_CREATED)
def create_brokerage_firm_support_ticket(ticket_data: Contact_Us, db: Session = Depends(get_db)):
    """
    Create a new Brokerage Firm Support Ticket when a shipper submits a support or inquiry form.
    """

    try:
        new_ticket = Brokerage_Firm_Support_Ticket(
            name=ticket_data.name,
            company_name=ticket_data.company_name,
            phone_number=ticket_data.phone_number,
            email=ticket_data.email,
            subject=ticket_data.subject,
            description=ticket_data.description,
            is_read=False,
            status="Open",
            created_at=get_sast_time(),
            updated_at=get_sast_time(),
        )

        db.add(new_ticket)
        db.commit()
        db.refresh(new_ticket)

        return {
            "message": "Support ticket created successfully, our team will be in touch shortly.",
            "ticket_id": new_ticket.id,
            "status": "open"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create support ticket: {str(e)}"
        )

@router.post("/create-carrier-support-ticket", status_code=status.HTTP_201_CREATED)
def create_carrier_support_ticket(ticket_data: Contact_Us, db: Session = Depends(get_db)):
    """
    Create a new Shipper Support Ticket when a shipper submits a support or inquiry form.
    """

    try:
        new_ticket = Carrier_Support_Ticket(
            name=ticket_data.name,
            company_name=ticket_data.company_name,
            phone_number=ticket_data.phone_number,
            email=ticket_data.email,
            subject=ticket_data.subject,
            description=ticket_data.description,
            is_read=False,
            status="Open",
            created_at=get_sast_time(),
            updated_at=get_sast_time(),
        )

        db.add(new_ticket)
        db.commit()
        db.refresh(new_ticket)

        return {
            "message": "Support ticket created successfully, our team will be in touch shortly.",
            "ticket_id": new_ticket.id,
            "status": "open"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create support ticket: {str(e)}"
        )