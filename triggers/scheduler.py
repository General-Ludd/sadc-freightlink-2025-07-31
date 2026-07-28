from apscheduler.schedulers.background import BackgroundScheduler
from services.tracking_updater import update_all_vehicle_locations
import time

scheduler = None

def start_tracking_scheduler():
    # Initialize the background scheduler
    scheduler = BackgroundScheduler()

    # Schedule the tracking function to run every 30 seconds
    scheduler.add_job(update_all_vehicle_locations, "interval", seconds=30)

    # Start the scheduler thread
    scheduler.start()
    print("🚛 Vehicle tracking scheduler started...")

    # Keep the main thread alive so the background worker can run
    try:
        while True:
            time.sleep(10)
    except (KeyboardInterrupt, SystemExit):
        # Gracefully shut down the scheduler when exiting
        scheduler.shutdown()
        print("🛑 Vehicle tracking scheduler stopped.")

