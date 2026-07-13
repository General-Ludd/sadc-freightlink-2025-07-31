from datetime import date, datetime
from pydantic import BaseModel, EmailStr
from typing import Optional

class CreateAdministrationUser(BaseModel):
    first_name: str
    last_name: str
    id_number: str
    nationality: str
    home_address: str
    email: EmailStr
    phone_number: str
    proof_of_address: str
    id_document: str
    password: str

class AdminPermissionsSchema(BaseModel):
    cancel_shipments: Optional[bool] = False
    create_shipments: Optional[bool] = False
    update_shipments: Optional[bool] = False
    delete_shipments: Optional[bool] = False
    cancel_lanes: Optional[bool] = False
    create_lanes: Optional[bool] = False
    update_lanes: Optional[bool] = False
    delete_lanes: Optional[bool] = False
    cancel_shipment_exchanges: Optional[bool] = False
    create_shipment_exchanges: Optional[bool] = False
    update_shipment_exchanges: Optional[bool] = False
    delete_shipment_exchanges: Optional[bool] = False
    cancel_lane_exchanges: Optional[bool] = False
    create_lane_exchanges: Optional[bool] = False
    update_lane_exchanges: Optional[bool] = False
    delete_lane_exchanges: Optional[bool] = False
    verify_shipper_companies: Optional[bool] = False
    verify_shipper_financial_accounts: Optional[bool] = False
    verify_shipper_users: Optional[bool] = False
    activate_shipper_companies: Optional[bool] = False
    activate_shipper_financial_accounts: Optional[bool] = False
    activate_shipper_users: Optional[bool] = False
    suspend_shipper_companies: Optional[bool] = False
    suspend_shipper_financial_accounts: Optional[bool] = False
    suspend_shipper_users: Optional[bool] = False
    verify_carrier_companies: Optional[bool] = False
    verify_carrier_financial_accounts: Optional[bool] = False
    verify_carrier_users: Optional[bool] = False
    activate_carrier_companies: Optional[bool] = False
    activate_carrier_financial_accounts: Optional[bool] = False
    activate_carrier_users: Optional[bool] = False
    suspend_carrier_companies: Optional[bool] = False
    suspend_carrier_financial_accounts: Optional[bool] = False
    suspend_carrier_users: Optional[bool] = False
    process_carrier_withdrawal_requests: Optional[bool] = False
    process_shipper_withdrawal_requests: Optional[bool] = False
    close_shipment_disputes: Optional[bool] = False
    close_lane_disputes: Optional[bool] = False
    close_invoice_disputes: Optional[bool] = False
    credit_shipper_financial_accounts: Optional[bool] = False
    debit_shipper_financial_accounts: Optional[bool] = False
    manage_shipper_spending_credit_limit: Optional[bool] = False
    change_financial_account_payment_terms: Optional[bool] = False
    debit_carrier_financial_account: Optional[bool] = False
    credit_carrier_financial_account: Optional[bool] = False
    create_administrator: Optional[bool] = False
    create_support_administrator: Optional[bool] = False
    modify_administrator_permissions: Optional[bool] = False
    update_administrator: Optional[bool] = False
    delete_administrator: Optional[bool] = False
    suspend_administrator: Optional[bool] = False
    activate_administrator: Optional[bool] = False
####################################################
    view_platform_revenue: Optional[bool] = False
    update_vehicle_rates: Optional[bool] = False
    update_platform_commission_rates: Optional[bool] = False