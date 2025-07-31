from fastapi import FastAPI
from api.endpoints.dashboards.standard_shipper_dashboard import standard_facility_dashboard

app = FastAPI()

app.include_router(standard_facility_dashboard.router, prefix="/api", tags=["Standard Shipper Dashboard"])

@app.get("/")
def read_root():
    return {"message": "Welcome to SADC FreightLink API"}
