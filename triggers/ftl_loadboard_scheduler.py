"""
ftl_loadboard_scheduler.py

Background scheduler for expiring FTL loadboard entries.

It:
- Queries the loadboard for shipments still marked Available
- Checks whether the pickup window has already passed
- Calls the reversal service for each expired shipment

Install dependency:
    pip install apscheduler

Update the import paths below to match your backend structure.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
from db.database import SessionLocal
from models.brokerage.loadboard import Ftl_Load_Board
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session
from services.loadboard_updater import run_ftl_load_expiry
from fastapi import APIRouter, Request, HTTPException, status, Response, Depends
from services.broadcaster.daily_loadboard_email_service import (
    send_daily_loadboard_broadcast,
)



router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

scheduler: Optional[BackgroundScheduler] = None


def run_ftl_expiry_job():
    """
    APScheduler wrapper.
    Simply runs the expiry service.
    """

    print("")
    print("=" * 80)
    print("STARTING FTL LOAD EXPIRY JOB")
    print("=" * 80)

    try:

        result = run_ftl_load_expiry()

        print("")
        print("FTL Expiry Result")
        print(result)

    except Exception as e:

        print("")
        print("=" * 80)
        print("FTL EXPIRY JOB FAILED")
        print("=" * 80)
        print(str(e))

def run_daily_email_job():
    """
    APScheduler wrapper for the daily transporter broadcast.
    """

    print("")
    print("=" * 80)
    print("STARTING DAILY LOADBOARD EMAIL BROADCAST")
    print("=" * 80)

    db = SessionLocal()

    try:
        send_daily_loadboard_broadcast(db)

        print("")
        print("=" * 80)
        print("DAILY LOADBOARD EMAIL BROADCAST COMPLETE")
        print("=" * 80)

    except Exception as e:

        print("")
        print("=" * 80)
        print("DAILY LOADBOARD EMAIL FAILED")
        print("=" * 80)
        print(str(e))

    finally:
        db.close()

def start_ftl_loadboard_scheduler(interval_minutes: int = 1):

    global scheduler

    if scheduler and scheduler.running:
        return scheduler

    scheduler = BackgroundScheduler(
        timezone=ZoneInfo("Africa/Johannesburg")
    )

    # Load expiry job
    scheduler.add_job(
        func=run_ftl_expiry_job,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="ftl_load_expiry",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Daily broadcast job
    scheduler.add_job(
        func=run_daily_email_job,
        trigger="cron",
        hour=18,
        minute=18,
        id="daily_loadboard_email",
        replace_existing=True,
    )

    scheduler.start()

    print("")
    print("=" * 80)
    print("REGISTERED APSCHEDULER JOBS")
    print("=" * 80)

    for job in scheduler.get_jobs():
        print(f"Job ID      : {job.id}")
        print(f"Next Run    : {job.next_run_time}")
        print(f"Trigger     : {job.trigger}")
        print("-" * 80)

    return scheduler


def stop_ftl_loadboard_scheduler():

    global scheduler

    if scheduler and scheduler.running:

        scheduler.shutdown(wait=False)

        scheduler = None

        print("")
        print("=" * 80)
        print("FTL LOAD EXPIRY SCHEDULER STOPPED")
        print("=" * 80)


if __name__ == "__main__":

    start_ftl_loadboard_scheduler(1)

    try:
        import time

        while True:
            time.sleep(60)

    except KeyboardInterrupt:
        stop_ftl_loadboard_scheduler()