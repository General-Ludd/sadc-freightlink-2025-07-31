from fastapi import FastAPI
from api.endpoints.dashboards.standard_shipper_dashboard import standard_facility_dashboard
from api.endpoints.dashboards.standard_shipper_dashboard import equipment_management
from api.endpoints.dashboards.standard_shipper_dashboard.shipment_management import spot_shipment_management
from api.endpoints.dashboards.standard_shipper_dashboard.shipment_management import exchange_shipment_management
from api.endpoints.dashboards.standard_shipper_dashboard.bookings import spot_bookings
from api.endpoints.dashboards.standard_shipper_dashboard.bookings import exchange_bookings

app = FastAPI()

app.include_router(standard_facility_dashboard.router, prefix="/api", tags=["Standard Shipper Dashboard"])
app.include_router(equipment_management.router, prefix="/api", tags=["Shipper Equipment Management"])
app.include_router(spot_shipment_management.router, prefix="/api", tags=["Spot Shipment Managment"])
app.include_router(exchange_shipment_management.router, prefix="/api", tags=["Exchange Shipment Managment"])
app.include_router(spot_bookings.router, prefix="/api", tags=["Spot Shipment and Lane Bookings"])
app.include_router(exchange_bookings.router, prefix="/api", tags=["Exchange Shipment and Lane Bookings"])

@app.get("/")
def read_root():
    return {"message": "Welcome to SADC FreightLink API"}
