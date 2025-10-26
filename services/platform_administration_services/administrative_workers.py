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
from schemas.brokerage.finance import Individual_Sevice_Invoices_Request
from schemas.vehicle import Individual_Shipper_Trailer_Response, Shipper_Trailers_Summary_Response, ShipperTrailerCreate
from services.vehicle_service import create_shipper_trailer
from utils.auth import get_current_user
from utils.administration_auth import get_current_admin

