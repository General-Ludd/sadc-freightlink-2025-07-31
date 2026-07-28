from fastapi import FastAPI
from fastapi import Request
import logging
import json
import threading
from fastapi.middleware.cors import CORSMiddleware
from api.endpoints.dashboards import tracking
from api.endpoints.dashboards.enterprise_shipper_dashboard import enterprise_dashboard
from api.endpoints.dashboards.enterprise_shipper_dashboard.facility_management import facility_sub_shipper
from api.endpoints.dashboards.enterprise_shipper_dashboard.shipment_management import enterprise_spot_management
from api.endpoints.dashboards.enterprise_shipper_dashboard.shipment_management import enterprise_exchange_management
from api.endpoints.dashboards.standard_shipper_dashboard import standard_facility_dashboard
from api.endpoints.dashboards.standard_shipper_dashboard.finance import general_finance
from api.endpoints.dashboards.standard_shipper_dashboard import user_management
from api.endpoints.dashboards.standard_shipper_dashboard import equipment_management
from api.endpoints.dashboards.standard_shipper_dashboard.shipment_management import spot_shipment_management
from api.endpoints.dashboards.standard_shipper_dashboard.shipment_management import exchange_shipment_management
from api.endpoints.dashboards.standard_shipper_dashboard.bookings import spot_bookings
from api.endpoints.dashboards.standard_shipper_dashboard.bookings import exchange_bookings
from api.endpoints.dashboards.broker_dashboard import brokerage_firm_dashboard
from api.endpoints.dashboards.broker_dashboard import client_management
from api.endpoints.dashboards.broker_dashboard.bookings import brokerage_firm_spot_bookings
from api.endpoints.dashboards.broker_dashboard.bookings import brokerage_firm_exchange_bookings
from api.endpoints.dashboards.broker_dashboard.shipment_management import broker_spot_shipment_management
from api.endpoints.dashboards.broker_dashboard.shipment_management import broker_exchange_shipment_management
from api.endpoints.dashboards.carrier_dashboard import carrier_dashboard
from api.endpoints.dashboards.carrier_dashboard.fleet_management import account_and_user
from api.endpoints.dashboards.carrier_dashboard.fleet_management import vehicle_management
from api.endpoints.dashboards.carrier_dashboard.fleet_management import driver_management
from api.endpoints.dashboards.carrier_dashboard.shipment_management import shipment_management
from api.endpoints.dashboards.carrier_dashboard.shipment_management import dedicated_lanes_management
from api.endpoints.dashboards.carrier_dashboard.finance import financial_account
from api.endpoints.dashboards.carrier_dashboard import spot_loadboards
from api.endpoints.dashboards.carrier_dashboard import exchange_loadboards
from api.endpoints.dashboards.driver_dashboard import driver_dashboard, driver_shipments, driver_trip
from api.endpoints import gcs_upload
from api.endpoints import financial_deposits
from api.endpoints.dashboards import early_access_requests
from api.endpoints.admin_panel.nexus import dashboard
from api.endpoints.admin_panel.nexus import nexus_individual_pages
from api.endpoints.admin_panel.nexus import nexus_admin_func
from api.endpoints.admin_panel import admin_dashboard
from api.endpoints.admin_panel import admin_dashboard_individual_pages
from api.endpoints.admin_panel.admin_dashboard_pages_functions import client_admin_functions
from api.endpoints.admin_panel.admin_dashboard_pages_functions import admin_financial_account, company
from api.endpoints.admin_panel.shipment_management import client_shipment_booking
from services.platform_administration_services.loadboards import admin_exchange_loadboards, admin_spot_loadboards
from api.endpoints.dashboards import contact_us
from services.nexus import border_detection_service
from services.nexus import quote_service
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from triggers.ftl_loadboard_scheduler import start_ftl_loadboard_scheduler

from triggers.scheduler import start_tracking_scheduler

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

# Define which endpoints to log
LOG_ROUTES = [
    "/api/driver/upload-pod",  # add any route paths you want to monitor
]

@app.middleware("http")
async def log_selected_requests(request: Request, call_next):
    # Only log specific routes
    if any(request.url.path.startswith(route) for route in LOG_ROUTES):
        try:
            body_bytes = await request.body()
            body = body_bytes.decode("utf-8")
            try:
                json_body = json.loads(body)
                body_str = json.dumps(json_body, indent=2)
            except json.JSONDecodeError:
                body_str = body

            logging.info(f"""
📦 [REQUEST RECEIVED]
➡️ Path: {request.url.path}
➡️ Method: {request.method}
➡️ Body:
{body_str}
            """)
        except Exception as e:
            logging.error(f"⚠️ Error logging request body for {request.url.path}: {e}")

    response = await call_next(request)
    return response

@app.middleware("http")
async def log_requests(request: Request, call_next):

    print("\n========== REQUEST ==========")

    print("METHOD:", request.method)

    print("URL:", request.url)

    print("\nHEADERS:")
    print(dict(request.headers))

    body = await request.body()

    print("\nBODY:")
    print(body.decode("utf-8"))

    print("=============================\n")

    response = await call_next(request)

    print("STATUS:", response.status_code)

    return response

#################################################Public################################################
app.include_router(contact_us.router, prefix="/api", tags=["Contact Us"])

#################################################Enterprise############################################
app.include_router(enterprise_dashboard.router, prefix="/api", tags=["Enterprise Shipper Dashboard"])
app.include_router(facility_sub_shipper.router, prefix="/api", tags=["Enterprise Facility Management"])
app.include_router(enterprise_spot_management.router, prefix="/api", tags=["Enterprise Spot Shipment Management"])
app.include_router(enterprise_exchange_management.router, prefix="/api", tags=["Enterprise Exchange Shipment Management"])

################################################Shipper Dashboard######################################
app.include_router(gcs_upload.router, prefix="/api", tags=["File Upload"])
app.include_router(standard_facility_dashboard.router, prefix="/api", tags=["Standard Shipper Dashboard"])
app.include_router(general_finance.router, prefix="/api", tags=["Shipper General Finance"])
app.include_router(user_management.router, prefix="/api", tags=["Shipper User Management"])
app.include_router(equipment_management.router, prefix="/api", tags=["Shipper Equipment Management"])
app.include_router(spot_shipment_management.router, prefix="/api", tags=["Spot Shipment Managment"])
app.include_router(exchange_shipment_management.router, prefix="/api", tags=["Exchange Shipment Managment"])
app.include_router(spot_bookings.router, prefix="/api", tags=["Spot Shipment and Lane Bookings"])
app.include_router(exchange_bookings.router, prefix="/api", tags=["Exchange Shipment and Lane Bookings"])

###############################################Broker Dashboard########################################
app.include_router(brokerage_firm_dashboard.router, prefix="/api", tags=["Brokerage Firm Dashboard"])
app.include_router(client_management.router, prefix="/api", tags=["Brokerage Firm Client Management"])
app.include_router(broker_spot_shipment_management.router, prefix="/api", tags=["Brokerage Firm Shipment Management"])
app.include_router(broker_exchange_shipment_management.router, prefix="/api", tags=["Brokerage Firm Exchange Management"])
app.include_router(brokerage_firm_spot_bookings.router, prefix="/api", tags=["Brokerage Firm Spot Bookings"])
app.include_router(brokerage_firm_exchange_bookings.router, prefix="/api", tags=["Brokerage Firm Exchange Bookings"])

################################################Carrier Dashbaoard#####################################
app.include_router(carrier_dashboard.router, prefix="/api", tags=["Carrier_Dashboard"])
app.include_router(account_and_user.router, prefix="/api", tags=["Carrier Dashboard Account and User Management"])
app.include_router(financial_account.router, prefix="/api", tags=["Carrier Dashboard Financial Account Management"])
app.include_router(vehicle_management.router, prefix="/api", tags=["Carrier Dashboard Vehicle Management"])
app.include_router(driver_management.router, prefix="/api", tags=["Carrier Dashboard Driver Management"])
app.include_router(shipment_management.router, prefix="/api", tags=["Carrier Dashboard Shipment Management"])
app.include_router(dedicated_lanes_management.router, prefix="/api", tags=["Carrier Dashboard Dedicated Lanes Management"])
app.include_router(spot_loadboards.router, prefix="/api", tags=["Carrier Dashboard Spot Loadboards"])
app.include_router(exchange_loadboards.router, prefix="/api", tags=["Carrier Dashboard Exchange Loadboards"])

################################################Driver Dashboard#######################################
app.include_router(driver_dashboard.router, prefix="/api", tags=["Driver Dashboard"])
app.include_router(driver_shipments.router, prefix="/api", tags={"Driver Shipments"})
app.include_router(driver_trip.router, prefix="/api", tags={"Driver Trip Functions"})

################################################Tracking###############################################
app.include_router(tracking.router, prefix="/api", tags=["Tracking"])

#########################################Early Access Registration#####################################
app.include_router(early_access_requests.router, prefix="/api", tags=["Early Access Registration"])

################################################Admin Dashboard#######################################
app.include_router(admin_dashboard.router, prefix="/api", tags=["Admin Dashboard"])
app.include_router(admin_dashboard_individual_pages.router, prefix="/api", tags=["Admin Dashboard Pages"])
app.include_router(dashboard.router, prefix="/api", tags=["Admin Nexus"])
app.include_router(nexus_individual_pages.router, prefix="/api", tags=["Admin Nexus individual Pages"])
app.include_router(nexus_admin_func.router, prefix="/api", tags=["Admin Nexus Admin Functions"])
app.include_router(client_admin_functions.router, prefix="/api", tags=["Client Admin Functions"])
app.include_router(admin_financial_account.router, prefix="/api", tags=["Admin Financial Account Management"])
app.include_router(company.router, prefix="/api", tags=["Admin Company Management"])
app.include_router(client_shipment_booking.router, prefix="/api", tags=["Client Shipment Management"])
app.include_router(admin_exchange_loadboards.router, prefix="/api", tags=["Admin Exchange Loadboards"])
app.include_router(admin_spot_loadboards.router, prefix="/api", tags=["Admin Spot Loadboards"])

################################################Border Detection#####################################
app.include_router(border_detection_service.router, prefix="/api", tags=["Border Detection"])
app.include_router(quote_service.router, prefix="/api", tags=["Shipment Quote"])


################################################Deposits###########################################
app.include_router(financial_deposits.router, prefix="/api", tags=["Nedbank Deposits"])

@app.on_event("startup")
def startup_event():
    print("🚀 Starting background services...")

    threading.Thread(target=start_tracking_scheduler, daemon=True).start()

    start_ftl_loadboard_scheduler(interval_minutes=1)

@app.get("/")
def read_root():
    return {"message": "Welcome to SADC FreightLink API"}

@app.exception_handler(RequestValidationError)

async def validation_exception_handler(

    request: Request,

    exc: RequestValidationError

):

    body = await request.body()

    print("\n========== VALIDATION ERROR ==========")

    print("URL:", request.url)

    print("\nBODY:")

    print(body.decode())

    print("\nERRORS:")

    print(exc.errors())

    print("======================================\n")

    return JSONResponse(

        status_code=422,

        content={

            "detail": exc.errors()

        }

    )
