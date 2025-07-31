from fastapi import FastAPI
from datetime import datetime
import pytz

app = FastAPI()

# Define SAST timezone
SAST = pytz.timezone("Africa/Johannesburg")

def get_sast_time():
    """Returns the current time in SAST"""
    return datetime.now(SAST)

@app.get("/time")
async def get_time():
    """Endpoint to return the current time in SAST"""
    return {"current_time": get_sast_time().strftime("%Y-%m-%d %H:%M:%S %Z")}


SAST = pytz.timezone("Africa/Johannesburg")

def format_datetime_sast(dt: datetime) -> str:
    """Convert UTC datetime to SAST and format as 'YYYY, Mon DD, HH:MM'"""
    dt_sast = dt.astimezone(SAST)  # Convert to SAST
    return dt_sast.strftime("%Y, %b %d, %H:%M")