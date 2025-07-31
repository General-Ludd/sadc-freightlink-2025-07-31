from fastapi import FastAPI
from api.endpoints.dashboards.standard_shipper_dashboard import standard_facility_dashboard
from api.endpoints.dashboards.standard_shipper_dashboard import equipment_management

app = FastAPI()

app.include_router(standard_facility_dashboard.router, prefix="/api", tags=["Standard Shipper Dashboard"])
app.include_router(equipment_management.router, prefix="/api", tags=["Shipper Equipment Management"])

@app.get("/")
def read_root():
    return {"message": "Welcome to SADC FreightLink API"}
