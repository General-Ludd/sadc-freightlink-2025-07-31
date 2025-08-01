from datetime import datetime
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.vehicle import Vehicle
from trackers.tracker_selector import get_vehicle_location

def update_all_vehicle_locations():
    db: Session = SessionLocal()

    try:
        vehicles = db.query(Vehicle).all()  # Fetch all vehicles

        for vehicle in vehicles:
            # Get location data (this could be your API call or another method)
            tracking_data = get_vehicle_location(vehicle)

            if tracking_data:
                # Ensure that latitude, longitude, and speed are correctly handled if None
                latitude = tracking_data.get('latitude')
                longitude = tracking_data.get('longitude')
                speed = tracking_data.get('speed')
                heading = tracking_data.get('bearing')
                location_description = tracking_data.get("position_description")
                time_stamp = tracking_data.get('time_stamp')

                # If any of the values are None, set them to default (NULL or 0)
                if latitude is None:
                    latitude = 0.0  # Or 0 if that's your preference
                if longitude is None:
                    longitude = 0.0  # Or 0 if that's your preference
                if speed is None:
                    speed = 0  # Or 0 if that's your preference
                if heading is None:
                    heading = 0

                # Update the vehicle with the new location data
                vehicle.latitude = latitude
                vehicle.longitude = longitude
                vehicle.speed = speed
                vehicle.heading = heading  # Assuming it's available
                vehicle.location_description = location_description
                vehicle.time_stamp = time_stamp

        # Commit all updates to the database
        db.commit()

    except Exception as e:
        # Handle any errors that occur during the update process
        print(f"❌ Error updating vehicles: {e}")
        db.rollback()  # Rollback any changes if there was an error

    finally:
        # Ensure the database session is closed
        db.close()

def update_all_vehicle_locations():
    db: Session = SessionLocal()

    try:
        vehicles = db.query(Vehicle).all()

        for vehicle in vehicles:
            tracking_data = get_vehicle_location(vehicle)

            if tracking_data:
                vehicle.latitude = float(tracking_data["latitude"])
                vehicle.longitude = float(tracking_data["longitude"])
                vehicle.speed = int(tracking_data["speed"])
                vehicle.heading = int(tracking_data["heading"])
                vehicle.location_description = tracking_data["location_description"]
                vehicle.time_stamp = tracking_data.get("time_stamp")

        db.commit()

    except Exception as e:
        print(f"❌ Error updating vehicles: {e}")

    finally:
        db.close()