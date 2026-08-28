from datetime import date, datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from models.Exchange.ftl_shipment import FTL_SHIPMENT_EXCHANGE
from models.brokerage.loadboards.exchange_loadboards import Exchange_Ftl_Load_Board
from models.shipper import Corporation
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.brokerage.finance import BrokerageLedger, FinancialAccounts
from models.spot_bookings.shipment_facility import ShipmentFacility, ContactPerson
from schemas.brokerage.loadboard import LoadBoardEntryCreate
from schemas.exchange_bookings.ftl_shipment import Exchange_FTL_Shipment_Booking, Broker_Exchange_FTL_Shipment_Booking
from schemas.spot_bookings.ftl_shipment import FTL_Shipment_Booking
from schemas.shipment_facility import ShipmentFacilityCreate, FacilityContactCreate
from schemas.shipper import ConsignorCreate
from services.brokerage.brokerage_service import calculate_brokerage_details, create_brokerage_ledger_entry
from models.brokerage.loadboard import Ftl_Load_Board
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from services.brokerage.carrier_loadboard_service import calculate_rates, determine_payout_method
from services.finance.finance import handle_30_day_pay, handle_credit_card, handle_instant_eft
from services.shipment_service import calculate_quote_for_shipment
from utils.consignor_service import get_or_create_consignor
from utils.billing import BillingEngine
from utils.google_maps import AddressInput, calculate_distance
