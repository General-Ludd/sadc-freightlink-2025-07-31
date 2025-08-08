from fastapi import FastAPI
import threading
from api.endpoints.dashboards.standard_shipper_dashboard import standard_facility_dashboard
from api.endpoints.dashboards.standard_shipper_dashboard import equipment_management
from api.endpoints.dashboards.standard_shipper_dashboard.shipment_management import spot_shipment_management
from api.endpoints.dashboards.standard_shipper_dashboard.shipment_management import exchange_shipment_management
from api.endpoints.dashboards.standard_shipper_dashboard.bookings import spot_bookings
from api.endpoints.dashboards.standard_shipper_dashboard.bookings import exchange_bookings
from api.endpoints.dashboards.broker_dashboard import brokerage_firm_dashboard
from api.endpoints.dashboards.broker_dashboard import client_management
from api.endpoints.dashboards.broker_dashboard.bookings import brokerage_firm_spot_bookings
from api.endpoints.dashboards.carrier_dashboard import carrier_dashboard
from api.endpoints.dashboards.carrier_dashboard.fleet_management import account_and_user
from api.endpoints.dashboards.carrier_dashboard.fleet_management import vehicle_management
from api.endpoints.dashboards.carrier_dashboard.fleet_management import driver_management
from api.endpoints.dashboards.carrier_dashboard.shipment_management import shipment_management
from api.endpoints.dashboards.carrier_dashboard.shipment_management import dedicated_lanes_management
from api.endpoints.dashboards.carrier_dashboard.finance import financial_account
from api.endpoints.dashboards.carrier_dashboard import spot_loadboards
from api.endpoints.dashboards.carrier_dashboard import exchange_loadboards

from triggers.scheduler import start_tracking_scheduler

app = FastAPI()

################################################Shipper Dashboard######################################
app.include_router(standard_facility_dashboard.router, prefix="/api", tags=["Standard Shipper Dashboard"])
app.include_router(equipment_management.router, prefix="/api", tags=["Shipper Equipment Management"])
app.include_router(spot_shipment_management.router, prefix="/api", tags=["Spot Shipment Managment"])
app.include_router(exchange_shipment_management.router, prefix="/api", tags=["Exchange Shipment Managment"])
app.include_router(spot_bookings.router, prefix="/api", tags=["Spot Shipment and Lane Bookings"])
app.include_router(exchange_bookings.router, prefix="/api", tags=["Exchange Shipment and Lane Bookings"])

###############################################Broker Dashboard########################################
app.include_router(brokerage_firm_dashboard.router, prefix="/api", tags=["Brokerage Firm Dashboard"])
app.include_router(client_management.router, prefix="/api", tags=["Brokerage Firm Client Management"])
app.include_router(brokerage_firm_spot_bookings.router, prefix="/api", tags=["Brokerage Firm Spot Bookings"])

################################################Carrier Dashbaoard#####################################
app.include_router(carrier_dashboard.router, prefix="/api", tags=["Carrier_Dashboard"])
app.include_router(account_and_user.router, prefix="/api", tags=["Carrier Dashboard Account and User Management"])
app.include_router(financial_account.router, prefix="/api", tags=["Carrier Dashboard Financial Account Management"])
app.include_router(vehicle_management.router, prefix="/api", tags=["Carrier Dashboard Vehicle Management"])
app.include_router(driver_management.router, prefix="/api", tags=["Carrier Dashboard Driver Management"])
app.include_router(shipment_management.router, prefix="/api", tags=["Carrier Dashboard Shipment Management"])
app.include_router(dedicated_lanes_management.router, prefix="/api", tags=["Carrier Dashboard Dedicated Lanes Management"])
app.include_router(spot_loadboards.router, prefix="/api", tags=["Carrier Dashboard Exchange Loadboards"])
app.include_router(exchange_loadboards.router, prefix="/api", tags=["Carrier Dashboard Exchange Loadboards"])

@app.on_event("startup")
def startup_event():
    print("🚀 Starting background vehicle tracking...")
    threading.Thread(target=start_tracking_scheduler, daemon=True).start()

@app.get("/")
def read_root():
    return {"message": "Welcome to SADC FreightLink API"}
