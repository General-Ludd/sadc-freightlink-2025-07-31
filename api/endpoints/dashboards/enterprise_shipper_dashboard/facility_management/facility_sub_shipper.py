from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.brokerage.finance import FinancialAccounts, Shipment_Invoice, Interim_Invoice, Invoices
from models.spot_bookings.shipment_facility import ShipmentFacility
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.spot_bookings.dedicated_lane_ftl_shipment import FTL_Lane
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from models.user import Director
from models.brokerage.finance import FinancialAccounts, Shipment_Invoice, Interim_Invoice, Invoices
from models.shipper import Corporation, Client_Notification
from schemas.brokerage.finance import Shipper_Financial_Account_Create, Client_Financial_Account_Update
from schemas.shipper import CorporationBase, CorporationResponse, CorporationUpdate, FacilityCreation
from schemas.user import DirectorCreate, DirectorResponse, ShipperUserResponse
from utils.auth import get_current_user, verify_password, hash_password

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/enterprise/facility-registration", status_code=status.HTTP_201_CREATED)
def create_facility_shipper_endpoint(
    shipper_data: FacilityCreation,
    manager_data: DirectorCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        result = create_facility_shipper(db, shipper_data, manager_data, current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/enterprise/facility/{id}")
def get_enterprise_facility_id(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        facility = db.query(Corporation).filter(Corporation.id == id).first()
        if not facility:
            raise HTTPException(status_code=404, detail="Facility not found")

        financial_account = (
            db.query(FinancialAccounts)
            .filter(FinancialAccounts.id == facility.id)
            .first()
        )

        shipments = (
            db.query(FTL_SHIPMENT)
            .filter(FTL_SHIPMENT.shipper_company_id == facility.id)
            .all()
        )

        lanes = (
            db.query(FTL_Lane)
            .filter(FTL_Lane.shipper_company_id == facility.id)
            .all()
        )

        users = (
            db.query(Director)
            .filter(Director.company_id == facility.id)
            .all()
        )

        service_invoices = (
            db.query(Shipment_Invoice)
            .filter(Shipment_Invoice.company_id == facility.id)
            .all()
        )

        interim_invoices = (
            db.query(Interim_Invoice)
            .filter(Interim_Invoice.company_id == facility.id)
            .all()
        )

        invoices = (
            db.query(Invoices)
            .filter(Invoices.company_id == facility.id)
            .all()
        )

        # -----------------------------
        # 🔥 1. Average Spend
        # -----------------------------
        all_invoice_amounts = (
            [inv.due_amount for inv in service_invoices] +
            [inv.due_amount for inv in interim_invoices] +
            [inv.due_amount for inv in invoices]
        )

        total_invoice_count = len(all_invoice_amounts)
        total_spend_sum = sum(all_invoice_amounts)

        average_spend = (
            total_spend_sum / total_invoice_count
            if total_invoice_count > 0 else 0
        )

        # -----------------------------
        # 🔥 2. Facility Shipment/Lane Status Metrics
        # -----------------------------
        status_counts = {
            "all_shipments": len(shipments),
            "booked": len([s for s in shipments if s.shipment_status == "Booked"]),
            "in_progress": len([s for s in shipments if s.shipment_status == "In-Progress"]),
            "completed": len([s for s in shipments if s.shipment_status == "Completed"]),
            "cancelled": len([s for s in shipments if s.shipment_status == "Cancelled"]),

            "lanes": len(lanes),
            "in_progress_lanes": len([l for l in lanes if l.status == "In-Progress"]),
            "cancelled_lanes": len([l for l in lanes if l.status == "Cancelled"]),
        }

        # -----------------------------
        # 🔥 3. Bookings by Type
        # -----------------------------
        bookings_by_type_count = {
            "lane_bookings": len([s for s in shipments if s.is_subshipment is True]),
            "shipment_bookings": len([s for s in shipments if s.is_subshipment is False]),
        }

        # -----------------------------
        # 🔥 4. Build API Response
        # -----------------------------
        return {
            "facility": {
                "facility_information": {
                    "id": facility.id,
                    "type": facility.type,
                    "facility_name": facility.legal_business_name,
                    "country": facility.country_of_incorporation,
                    "address": facility.business_address,
                    "email": facility.business_email,
                    "phone_number": facility.business_phone_number,
                },
                "financial_account": {
                    "id": financial_account.id,
                    "payment_terms": financial_account.payment_terms,
                    "years_in_business": financial_account.years_in_business,
                    "nature_of_business": financial_account.nature_of_business,
                    "projected_bookings": financial_account.projected_monthly_bookings,
                    "is_verified": financial_account.is_verified,
                    "status": financial_account.status,
                    "banking_details": {
                        "bank_name": financial_account.bank_name,
                        "branch_code": financial_account.branch_code,
                        "account_number": financial_account.account_number,
                        "account_type": financial_account.account_type,
                    },
                    "financial_metrics": {
                        "total_spent": financial_account.total_spent,
                        "average_spend": average_spend,
                        "total_paid": financial_account.total_paid,
                        "credit_balance": financial_account.credit_balance,
                        "spending_limit": financial_account.spending_limit,
                        "paid_invoices": financial_account.num_paid_invoices,
                        "outstanding_invoices": financial_account.num_outstanding_invoices,
                        "overdue_invoices": financial_account.num_overdue_invoices,
                        "ongoing_interim_invoices": financial_account.ongoing_interim_invoices,
                    },
                },
                "facility_invoices": {
                    "service_invoices": [{
                        "id": inv.id,
                        "status": inv.status,
                        "description": inv.description,
                        "facility": {
                            "name": facility.legal_business_name,
                            "id": facility.id,
                        },
                        "due_amount": inv.due_amount,
                        "billing_date": inv.billing_date,
                        "due_date": inv.due_date,
                        "shipment": {
                            "id": inv.shipment_id,
                            "type": inv.shipment_type,
                        },
                    } for inv in service_invoices],

                    "interim_invoices": [{
                        "id": inv.id,
                        "status": inv.status,
                        "description": inv.description,
                        "facility": {
                            "name": facility.legal_business_name,
                            "id": facility.id,
                        },
                        "due_amount": inv.due_amount,
                        "billing_date": inv.billing_date,
                        "due_date": inv.due_date,
                        "lane": {
                            "id": inv.contract_id,
                            "type": inv.contract_type,
                        },
                    } for inv in interim_invoices],

                    "lane_invoices": [{
                        "id": inv.id,
                        "status": inv.status,
                        "description": inv.description,
                        "facility": {
                            "name": facility.legal_business_name,
                            "id": facility.id,
                        },
                        "due_amount": inv.due_amount,
                        "billing_date": inv.billing_date,
                        "due_date": inv.due_date,
                        "lane": {
                            "id": inv.contract_id,
                            "type": inv.contract_type,
                        },
                        "period": {
                            "start_date": inv.billing_date,
                            "end_date": inv.due_date,
                        }
                    } for inv in invoices],
                }
            },

            # =================================================================== #
            # 🔥 FACILITY ACTIVITY SECTION
            # =================================================================== #
            "facility_activity": {
                "shipments_chart": [{
                    "id": shipment.id,
                    "pickup_date": shipment.pickup_date,
                } for shipment in shipments],

                "booking_by_type": bookings_by_type_count,

                "shipments": [{
                    "type": shipment.type,
                    "id": shipment.id,
                    "status": shipment.shipment_status,
                    "priority_level": shipment.priority_level,
                    "is_subshipment": shipment.is_subshipment,
                    "lane_id": shipment.dedicated_lane_id,
                    "facility": {
                        "name": facility.legal_business_name,
                        "id": facility.id,
                    },
                    "rate": shipment.quote,
                    "origin": {
                        "city": shipment.origin_city_province,
                        "pickup_date": shipment.pickup_date,
                        "pickup_window": shipment.pickup_appointment,
                    },
                    "destination": {
                        "city": shipment.destination_city_province,
                        "eta_date": shipment.eta_date,
                        "eta_window": shipment.eta_window,
                    },
                    "load_details": {
                        "distance": shipment.distance,
                        "weight": shipment.shipment_weight,
                        "commodity": shipment.commodity,
                    },
                    "financials": {
                        "rate_per_km": (shipment.quote / shipment.distance) if shipment.distance else None,
                        "rate_per_ton": (shipment.quote / shipment.shipment_weight),
                    },
                } for shipment in shipments],

                "lanes": [{
                    "id": lane.id,
                    "status": lane.status,
                    "priority_level": lane.priority_level,
                    "type": lane.type,
                    "facility": {
                        "name": facility.legal_business_name,
                        "id": facility.id,
                    },
                    "total_contract_value": lane.contract_quote,
                    "origin": lane.origin_city_province,
                    "destination": lane.destination_city_province,
                    "distance": lane.distance,
                    "contract_and_recurrence": {
                        "start_date": lane.start_date,
                        "end_date": lane.end_date,
                        "frequency": lane.frequency,
                        "recurrence_days": lane.recurrence_days,
                    },
                    "shipment_details": {
                        "shipments_per_interval": lane.shipments_per_interval,
                        "total_shipments": lane.total_shipments,
                        "completed_shipments": lane.completed_shipments,
                    },
                    "financials": {
                        "rate_per_shipment": lane.quote_per_shipment,
                        "payment_terms": lane.payment_terms,
                    },
                } for lane in lanes],

                "users": [{
                    "name": f"{user.first_name} {user.last_name}",
                    "id": user.id,
                    "status": user.status,
                    "role": user.role,
                    "is_verified": user.is_verified,
                    "nationality": user.nationality,
                    "id_number": user.id_number,
                    "address": user.address,
                    "phone": user.phone_number,
                    "email": user.email,
                    # 🔥 NEW FIELDS:
                    "shipments_managed": len([s for s in shipments if s.shipper_user_id == user.id]),
                    "lanes_managed": len([l for l in lanes if l.shipper_user_id == user.id]),
                } for user in users]
            },
        }

    except Exception as e:
        print(str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/enterprise/facility/{facility_id}/spending-limit/{amount}", status_code=status.HTTP_200_OK)
def enterprise_update_facility_spending_limit(
    facility_id: int,
    amount: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    parent_company_id = current_user.get("company_id")

    # --- FIND FACILITY COMPANY ---
    facility_company = db.query(Corporation).filter(
        Corporation.id == facility_id,
        Corporation.parent_company_id == parent_company_id
    ).first()

    if not facility_company:
        raise HTTPException(
            status_code=404,
            detail="Facility not found or does not belong to your enterprise"
        )

    # --- FIND FINANCIAL ACCOUNT ---
    financial_account = db.query(FinancialAccounts).filter(
        FinancialAccounts.id == facility_id
    ).first()

    if not financial_account:
        raise HTTPException(
            status_code=404,
            detail="Financial account for this facility does not exist"
        )

    # --- UPDATE SPENDING LIMIT ---
    financial_account.spending_limit = amount
    db.commit()
    db.refresh(financial_account)

    return {
        "message": "Spending limit updated successfully",
        "facility_id": facility_id,
        "new_spending_limit": amount
    }