from apscheduler.schedulers.background import BackgroundScheduler
from services.tracking_updater import update_all_vehicle_locations
import time

def start_tracking_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_all_vehicle_locations, 'interval', seconds=30)
    scheduler.start()
    print("🚛 Vehicle tracking scheduler started...")

    try:
        while True:
            time.sleep(10)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()