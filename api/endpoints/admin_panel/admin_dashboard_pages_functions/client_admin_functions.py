from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from requests import Session
from db.database import SessionLocal
from models.shipper import Corporation
from models.user import Director, CarrierUser, Driver
from models.carrier import Carrier
from models.vehicle import Vehicle, Vehicle_Schedule, Trailer, ShipperTrailer
from models.brokerage.finance import FinancialAccounts, CarrierFinancialAccounts, Withdrawal_Request, Shipment_Invoice, Interim_Invoice, Invoices
from models.spot_bookings.dedicated_lane_ftl_shipment import FTL_Lane
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from models.brokerage.loadboard import Ftl_Load_Board, Power_Load_Board, Dedicated_lanes_LoadBoard
from models.Exchange.auction import Exchange_FTL_Shipment_Bid, Exchange_FTL_Lane_Bid, Exchange_POWER_Shipment_Bid
from models.brokerage.loadboards.exchange_loadboards import Exchange_Ftl_Load_Board, Exchange_Ftl_Lane_LoadBoard
from models.brokerage.assigned_lanes import Assigned_Ftl_Lanes
from models.brokerage.assigned_shipments import Assigned_Spot_Ftl_Shipments, Assigned_Power_Shipments
from models.administration import Platform_Super_Admins, Platform_Super_and_Support_Admins_Permissions
from schemas.brokerage.finance import Individual_Sevice_Invoices_Request
from schemas.vehicle import Individual_Shipper_Trailer_Response, Shipper_Trailers_Summary_Response, ShipperTrailerCreate
from services.vehicle_service import create_shipper_trailer
from utils.auth import get_current_user
from utils.administration_auth import get_current_admin
from enums  import Account_Status

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.put("/admin/update-shipper-company-{id}/{status}")
def admin_update_shipper_company_status(
    id: int,
    status: Account_Status,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        # 1️⃣ Verify admin
        admin = (
            db.query(Platform_Super_Admins)
            .filter(Platform_Super_Admins.id == current_user.get("admin_id"))
            .first()
        )
        if not admin:
            raise HTTPException(status_code=401, detail="Unauthorized administrator account")
        if not admin.is_verified:
            raise HTTPException(status_code=403, detail="Administrator account not verified")

        # 2️⃣ Fetch permissions
        permissions = (
            db.query(Platform_Super_and_Support_Admins_Permissions)
            .filter(Platform_Super_and_Support_Admins_Permissions.id == admin.id)
            .first()
        )
        if not permissions:
            raise HTTPException(status_code=403, detail="Administrator permissions not found")

        # 3️⃣ Determine required permission based on status
        required_permission = None
        if status == Account_Status.ACTIVE:
            required_permission = "activate_shipper_companies"
        elif status == Account_Status.SUSPENDED:
            required_permission = "suspend_shipper_companies"
        elif status == Account_Status.UNVERIFIED:
            required_permission = "verify_shipper_companies"
        elif status == Account_Status.UNDER_INVESTIGATION:
            required_permission = "suspend_shipper_companies"

        if required_permission and not getattr(permissions, required_permission, False):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions to set company status to '{status.value}'"
            )

        # 4️⃣ Retrieve the company
        shipper = db.query(Corporation).filter(Corporation.id == id).first()
        if not shipper:
            raise HTTPException(status_code=404, detail=f"Shipper company with ID {id} not found")

        # 5️⃣ Update status
        old_status = shipper.status
        shipper.status = status
        shipper.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(shipper)

        # 6️⃣ Return response
        return {
            "status": "success",
            "message": f"Shipper company status changed from '{old_status}' to '{shipper.status}'."
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/admin/verify-shipper-company/{id}")
def verify_shipper_company(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        # 1️⃣ Verify admin
        admin = (
            db.query(Platform_Super_Admins)
            .filter(Platform_Super_Admins.id == current_user.get("admin_id"))
            .first()
        )
        if not admin:
            raise HTTPException(status_code=401, detail="Unauthorized administrator")
        if not admin.is_verified:
            raise HTTPException(status_code=403, detail="Administrator account not verified")

        # 2️⃣ Check permissions
        permissions = (
            db.query(Platform_Super_and_Support_Admins_Permissions)
            .filter(Platform_Super_and_Support_Admins_Permissions.id == admin.id)
            .first()
        )
        if not permissions or not permissions.verify_shipper_companies:
            raise HTTPException(status_code=403, detail="Permission denied to verify shipper companies")

        # 3️⃣ Find company
        shipper = db.query(Corporation).filter(Corporation.id == id).first()
        if not shipper:
            raise HTTPException(status_code=404, detail=f"Shipper company with ID {id} not found")

        # 4️⃣ Update verification status
        old_status = shipper.is_verified
        shipper.is_verified = True
        shipper.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(shipper)

        # 5️⃣ Return JSON
        return {
            "status": "success",
            "message": f"Shipper company '{shipper.legal_business_name}' verified successfully.",
            "previous_verification_status": old_status
            }

    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/admin/unverify-shipper-company/{id}")
def unverify_shipper_company(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        # 1️⃣ Verify admin
        admin = (
            db.query(Platform_Super_Admins)
            .filter(Platform_Super_Admins.id == current_user.get("admin_id"))
            .first()
        )
        if not admin:
            raise HTTPException(status_code=401, detail="Unauthorized administrator")
        if not admin.is_verified:
            raise HTTPException(status_code=403, detail="Administrator account not verified")

        # 2️⃣ Check permissions
        permissions = (
            db.query(Platform_Super_and_Support_Admins_Permissions)
            .filter(Platform_Super_and_Support_Admins_Permissions.id == admin.id)
            .first()
        )
        if not permissions or not permissions.verify_shipper_companies:
            raise HTTPException(status_code=403, detail="Permission denied to modify verification status")

        # 3️⃣ Find company
        shipper = db.query(Corporation).filter(Corporation.id == id).first()
        if not shipper:
            raise HTTPException(status_code=404, detail=f"Shipper company with ID {id} not found")

        # 4️⃣ Update verification status
        old_status = shipper.status
        shipper.status = "Un-verified"
        shipper.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(shipper)

        # 5️⃣ Return JSON
        return {
            "status": "success",
            "message": f"Shipper company '{shipper.legal_business_name}' status unverified successfully.",
            "previous_verification_status": old_status,
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/admin/update-shipper-financial-account-{id}/{status}")
def admin_update_shipper_financial_account_status(
    id: int,
    status: Account_Status,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        # 1️⃣ Verify admin
        admin = (
            db.query(Platform_Super_Admins)
            .filter(Platform_Super_Admins.id == current_user.get("admin_id"))
            .first()
        )
        if not admin:
            raise HTTPException(status_code=401, detail="Unauthorized administrator account")
        if not admin.is_verified:
            raise HTTPException(status_code=403, detail="Administrator account not verified")

        # 2️⃣ Fetch permissions
        permissions = (
            db.query(Platform_Super_and_Support_Admins_Permissions)
            .filter(Platform_Super_and_Support_Admins_Permissions.id == admin.id)
            .first()
        )
        if not permissions:
            raise HTTPException(status_code=403, detail="Administrator permissions not found")

        # 3️⃣ Determine required permission based on status
        required_permission = None
        if status == Account_Status.ACTIVE:
            required_permission = "activate_shipper_financial_accounts"
        elif status == Account_Status.SUSPENDED:
            required_permission = "suspend_shipper_financial_accounts"
        elif status == Account_Status.UNVERIFIED:
            required_permission = "verify_shipper_financial_accounts"
        elif status == Account_Status.UNDER_INVESTIGATION:
            required_permission = "suspend_shipper_financial_accounts"

        if required_permission and not getattr(permissions, required_permission, False):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions to set company status to '{status.value}'"
            )

        # 4️⃣ Retrieve the company financial account
        financial_account = db.query(FinancialAccounts).filter(FinancialAccounts.id == id).first()
        if not financial_account:
            raise HTTPException(status_code=404, detail=f"Financial Account with ID {id} not found")

        # 5️⃣ Update status
        old_status = financial_account.status
        financial_account.status = status
        financial_account.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(financial_account)

        # 6️⃣ Return response
        return {
            "status": "success",
            "message": f"Financial account status changed from '{old_status}' to '{financial_account.status}'."
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/admin/verify-shipper-financial-account/{id}")
def verify_shipper_financial_account(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        # 1️⃣ Verify admin
        admin = (
            db.query(Platform_Super_Admins)
            .filter(Platform_Super_Admins.id == current_user.get("admin_id"))
            .first()
        )
        if not admin:
            raise HTTPException(status_code=401, detail="Unauthorized administrator")
        if not admin.is_verified:
            raise HTTPException(status_code=403, detail="Administrator account not verified")

        # 2️⃣ Check permissions
        permissions = (
            db.query(Platform_Super_and_Support_Admins_Permissions)
            .filter(Platform_Super_and_Support_Admins_Permissions.id == admin.id)
            .first()
        )
        if not permissions or not permissions.verify_shipper_financial_accounts:
            raise HTTPException(status_code=403, detail="Permission denied to verify shipper companies")

        # 4️⃣ Retrieve the company financial account
        financial_account = db.query(FinancialAccounts).filter(FinancialAccounts.id == id).first()
        if not financial_account:
            raise HTTPException(status_code=404, detail=f"Financial Account with ID {id} not found")

        # 4️⃣ Update verification status
        old_status = financial_account.is_verified
        financial_account.is_verified = True
        financial_account.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(financial_account)

        # 5️⃣ Return JSON
        return {
            "status": "success",
            "message": f"Shipper financial account '{financial_account.id}' verified successfully.",
            "previous_verification_status": old_status
            }

    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/admin/unverify-shipper-financial-account/{id}")
def unverify_shipper_financial_account(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        # 1️⃣ Verify admin
        admin = (
            db.query(Platform_Super_Admins)
            .filter(Platform_Super_Admins.id == current_user.get("admin_id"))
            .first()
        )
        if not admin:
            raise HTTPException(status_code=401, detail="Unauthorized administrator")
        if not admin.is_verified:
            raise HTTPException(status_code=403, detail="Administrator account not verified")

        # 2️⃣ Check permissions
        permissions = (
            db.query(Platform_Super_and_Support_Admins_Permissions)
            .filter(Platform_Super_and_Support_Admins_Permissions.id == admin.id)
            .first()
        )
        if not permissions or not permissions.verify_shipper_financial_accounts:
            raise HTTPException(status_code=403, detail="Permission denied to modify verification status")

        # 4️⃣ Retrieve the company financial account
        financial_account = db.query(FinancialAccounts).filter(FinancialAccounts.id == id).first()
        if not financial_account:
            raise HTTPException(status_code=404, detail=f"Financial Account with ID {id} not found")

        # 4️⃣ Update verification status
        old_status = shipper.status
        financial_account.status = "Un-verified"
        financial_account.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(financial_account)

        # 5️⃣ Return JSON
        return {
            "status": "success",
            "message": f"Shipper company '{financial_account.id}' status unverified successfully.",
            "previous_verification_status": old_status,
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/admin/financial-account-outstanding/{account_id}/{action}")
def admin_update_financial_account_outstanding_balance(
    account_id: int,
    action: str,  # "credit" or "debit"
    amount: float = Body(..., embed=True, gt=0.0),
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    try:
        # 1️⃣ Verify Admin Identity
        admin = db.query(Platform_Super_Admins).filter(
            Platform_Super_Admins.email == current_admin.get("admin_id")
        ).first()

        if not admin:
            raise HTTPException(status_code=401, detail="Unauthorized")

        if not admin.is_verified:
            raise HTTPException(status_code=403, detail="Administrator account not verified")

        # 2️⃣ Check Permissions
        permissions = db.query(Platform_Super_and_Support_Admins_Permissions).filter(
            Platform_Super_and_Support_Admins_Permissions.id == admin.id
        ).first()

        if not permissions:
            raise HTTPException(status_code=403, detail="No permissions record found")

        # 4️⃣ Retrieve the company financial account
        account = db.query(FinancialAccounts).filter(FinancialAccounts.id == id).first()
        if not account:
            raise HTTPException(status_code=404, detail=f"Financial Account with ID {id} not found")


        # 4️⃣ Perform Credit or Debit
        if action.lower() == "credit":
            if not permissions.manage_shipper_spending_credit_limit:
                raise HTTPException(status_code=403, detail="No permission to credit financial accounts")

            account.outstanding_balance += amount
            operation_type = "credited"

        elif action.lower() == "debit":
            if not permissions.manage_shipper_spending_credit_limit:
                raise HTTPException(status_code=403, detail="No permission to debit financial accounts")

            if amount > account.outstanding_balance:
                raise HTTPException(status_code=400, detail="Insufficient outstanding balance")

            account.outstanding_balance -= amount
            operation_type = "debited"

        else:
            raise HTTPException(status_code=400, detail="Invalid action. Use 'credit' or 'debit'.")

        db.commit()
        db.refresh(account)

        # 5️⃣ Return Response
        return {
            "message": f"Account successfully {operation_type}.",
            "account_id": account.id,
            "updated_outstanding_balance": account.outstanding_balance,
            "timestamp": account.updated_at
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/admin/financial-account-credit-balance/{account_id}/{action}")
def admin_update_financial_account_credit_balance(
    account_id: int,
    action: str,  # "credit" or "debit"
    amount: float = Body(..., embed=True, gt=0.0),
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    try:
        # 1️⃣ Verify Admin Identity
        admin = db.query(Platform_Super_Admins).filter(
            Platform_Super_Admins.id == current_admin.get("admin_id")
        ).first()

        if not admin:
            raise HTTPException(status_code=401, detail="Unauthorized")

        if not admin.is_verified:
            raise HTTPException(status_code=403, detail="Administrator account not verified")

        # 2️⃣ Check Permissions
        permissions = db.query(Platform_Super_and_Support_Admins_Permissions).filter(
            Platform_Super_and_Support_Admins_Permissions.id == admin.id
        ).first()

        if not permissions:
            raise HTTPException(status_code=403, detail="No permissions record found")

        # 4️⃣ Retrieve the company financial account
        account = db.query(FinancialAccounts).filter(FinancialAccounts.id == id).first()
        if not account:
            raise HTTPException(status_code=404, detail=f"Financial Account with ID {id} not found")


        # 4️⃣ Perform Credit or Debit
        if action.lower() == "credit":
            if not permissions.credit_shipper_spending_credit_limit:
                raise HTTPException(status_code=403, detail="No permission to credit financial accounts")

            account.credit_balance += amount
            operation_type = "credited"

        elif action.lower() == "debit":
            if not permissions.debit_shipper_financial_accounts:
                raise HTTPException(status_code=403, detail="No permission to debit financial accounts")

            if amount > account.credit_balance:
                raise HTTPException(status_code=400, detail="Insufficient outstanding balance")

            account.credit_balance -= amount
            operation_type = "debited"

        else:
            raise HTTPException(status_code=400, detail="Invalid action. Use 'credit' or 'debit'.")

        db.commit()
        db.refresh(account)

        # 5️⃣ Return Response
        return {
            "message": f"Account successfully {operation_type}.",
            "account_id": account.id,
            "updated_outstanding_balance": account.outstanding_balance,
            "timestamp": account.updated_at
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/admin/update-shipper-user-{id}/{status}")
def admin_update_shipper_user_status(
    id: int,
    status: Account_Status,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        # 1️⃣ Verify admin
        admin = (
            db.query(Platform_Super_Admins)
            .filter(Platform_Super_Admins.id == current_user.get("admin_id"))
            .first()
        )
        if not admin:
            raise HTTPException(status_code=401, detail="Unauthorized administrator account")
        if not admin.is_verified:
            raise HTTPException(status_code=403, detail="Administrator account not verified")

        # 2️⃣ Fetch permissions
        permissions = (
            db.query(Platform_Super_and_Support_Admins_Permissions)
            .filter(Platform_Super_and_Support_Admins_Permissions.id == admin.id)
            .first()
        )
        if not permissions:
            raise HTTPException(status_code=403, detail="Administrator permissions not found")

        # 3️⃣ Determine required permission based on status
        required_permission = None
        if status == Account_Status.ACTIVE:
            required_permission = "activate_shipper_users"
        elif status == Account_Status.SUSPENDED:
            required_permission = "suspend_shipper_users"
        elif status == Account_Status.UNVERIFIED:
            required_permission = "verify_carrier_users"
        elif status == Account_Status.UNDER_INVESTIGATION:
            required_permission = "suspend_shipper_users"

        if required_permission and not getattr(permissions, required_permission, False):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions to set company status to '{status.value}'"
            )

        # 4️⃣ Retrieve the company
        shipper_user = db.query(Director).filter(Director.id == id).first()
        if not shipper_user:
            raise HTTPException(status_code=404, detail=f"Shipper user with ID {id} not found")

        # 5️⃣ Update status
        old_status = shipper_user.status
        shipper_user.status = status
        shipper_user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(shipper_user)

        # 6️⃣ Return response
        return {
            "status": "success",
            "message": f"Shipper user status changed from '{old_status}' to '{shipper_user.status}'."
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")