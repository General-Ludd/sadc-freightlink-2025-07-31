from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from models.brokerage.finance import FinancialAccounts
from models.user import User, Director
from models.administration import Platform_Super_Admins, Platform_Super_and_Support_Admins_Permissions
from schemas.user import DirectorCreate, DirectorUpdate
from schemas.administration import CreateAdministrationUser, AdminPermissionsSchema
from utils.auth import hash_password

def create_shipper_sub_user(db: Session, user_data: DirectorCreate, current_user=dict):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")

    user = Director(
        company_id=company_id,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        id_number=user_data.id_number,
        nationality=user_data.nationality,
        home_address=user_data.home_address,
        phone_number=user_data.phone_number,
        email=user_data.email,
        password_hash=hash_password(user_data.password_hash),
        is_director=False,
        id_document=user_data.id_document,
        proof_of_address=user_data.proof_of_address,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {f"sub-user-{user.id} ({user.first_name}-{user.last_name}) successfully created, currently awaiting verification"}


def create_admin_super_user(db: Session, user_data: CreateAdministrationUser, permissions_data: AdminPermissionsSchema):
    # Create the user
    user = Platform_Super_Admins(
        type="Admin",
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        id_number=user_data.id_number,
        nationality=user_data.nationality,
        home_address=user_data.home_address,
        phone_number=user_data.phone_number,
        email=user_data.email,
        password=hash_password(user_data.password),
        is_verified=False,
        id_document=user_data.id_document,
        proof_of_address=user_data.proof_of_address,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create permissions tied to the same ID as the user
    permissions = Platform_Super_and_Support_Admins_Permissions(
        id=user.id,  # tie to user
        cancel_shipments=permissions_data.cancel_shipments,
        create_shipments=permissions_data.create_shipments,
        update_shipments=permissions_data.update_shipments,
        delete_shipments=permissions_data.delete_shipments,
        cancel_lanes=permissions_data.cancel_lanes,
        create_lanes=permissions_data.create_lanes,
        update_lanes=permissions_data.update_lanes,
        delete_lanes=permissions_data.delete_lanes,
        cancel_shipment_exchanges=permissions_data.cancel_shipment_exchanges,
        create_shipment_exchanges=permissions_data.create_shipment_exchanges,
        update_shipment_exchanges=permissions_data.update_shipment_exchanges,
        delete_shipment_exchanges=permissions_data.delete_shipment_exchanges,
        cancel_lane_exchanges=permissions_data.cancel_lane_exchanges,
        create_lane_exchanges=permissions_data.create_lane_exchanges,
        update_lane_exchanges=permissions_data.update_lane_exchanges,
        delete_lane_exchanges=permissions_data.delete_lane_exchanges,
        verify_shipper_companies=permissions_data.verify_shipper_companies,
        verify_shipper_financial_accounts=permissions_data.verify_shipper_financial_accounts,
        verify_shipper_users=permissions_data.verify_shipper_users,
        activate_shipper_companies=permissions_data.activate_shipper_companies,
        activate_shipper_financial_accounts=permissions_data.activate_shipper_financial_accounts,
        activate_shipper_users=permissions_data.activate_shipper_users,
        suspend_shipper_companies=permissions_data.suspend_shipper_companies,
        suspend_shipper_financial_accounts=permissions_data.suspend_shipper_financial_accounts,
        suspend_shipper_users=permissions_data.suspend_shipper_users,
        verify_carrier_companies=permissions_data.verify_carrier_companies,
        verify_carrier_financial_accounts=permissions_data.verify_carrier_financial_accounts,
        verify_carrier_users=permissions_data.verify_carrier_users,
        activate_carrier_companies=permissions_data.activate_carrier_companies,
        activate_carrier_financial_accounts=permissions_data.activate_carrier_financial_accounts,
        activate_carrier_users=permissions_data.activate_carrier_users,
        suspend_carrier_companies=permissions_data.suspend_carrier_companies,
        suspend_carrier_financial_accounts=permissions_data.suspend_carrier_financial_accounts,
        suspend_carrier_users=permissions_data.suspend_carrier_users,
        process_carrier_withdrawal_requests=permissions_data.process_carrier_withdrawal_requests,
        process_shipper_withdrawal_requests=permissions_data.process_shipper_withdrawal_requests,
        close_shipment_disputes=permissions_data.close_shipment_disputes,
        close_lane_disputes=permissions_data.close_lane_disputes,
        close_invoice_disputes=permissions_data.close_invoice_disputes,
        credit_shipper_financial_accounts=permissions_data.credit_shipper_financial_accounts,
        debit_shipper_financial_accounts=permissions_data.debit_shipper_financial_accounts,
        manage_shipper_spending_credit_limit=permissions_data.manage_shipper_spending_credit_limit,
        change_financial_account_payment_terms=permissions_data.change_financial_account_payment_terms,
        debit_carrier_financial_account=permissions_data.debit_carrier_financial_account,
        credit_carrier_financial_account=permissions_data.credit_carrier_financial_account,
        create_administrator=permissions_data.create_administrator,
        create_support_administrator=permissions_data.create_support_administrator,
        modify_administrator_permissions=permissions_data.modify_administrator_permissions,
        update_administrator=permissions_data.update_administrator,
        delete_administrator=permissions_data.delete_administrator,
        suspend_administrator=permissions_data.suspend_administrator,
        activate_administrator=permissions_data.activate_administrator,
    )
    db.add(permissions)
    db.commit()
    db.refresh(permissions)

    return {
        "message": f"Admin user {user.first_name} {user.last_name} created successfully.",
        "user_id": user.id,
        "permissions_id": permissions.id
    }

