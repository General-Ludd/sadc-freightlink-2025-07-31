# tasks.py (Celery tasks)
from celery import Celery
from database import SessionLocal
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models.nexus.clearing_agencies import CustomsBrokerageFirm
from models.nexus.customs import ShipmentCustomsEvent
from sevices.nexus.customs_assignment_service import CustomsEventAssigner

# Initialize Celery
celery_app = Celery('customs_tasks', broker='redis://localhost:6379/0')

@celery_app.task(name='assign_pending_customs_events')
def assign_pending_customs_events_task(limit=50):
    """Celery task for assigning pending customs events"""
    db = SessionLocal()
    try:
        assigner = CustomsEventAssigner(db)
        results = assigner.assign_pending_events(limit=limit)
        
        # Log summary
        successful = sum(1 for r in results if r.success)
        total = len(results)
        
        return {
            'success': True,
            'assigned': successful,
            'total_processed': total,
            'results': [
                {
                    'event_id': r.event_id,
                    'success': r.success,
                    'reason': r.reason,
                    'firm_id': r.firm_id
                }
                for r in results
            ]
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        db.close()

# Schedule the task to run every 5 minutes
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'assign-customs-events-every-5-minutes': {
        'task': 'assign_pending_customs_events',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
        'args': (50,)
    },
}


@router.get("/assignment-stats")
def get_assignment_statistics(db: Session = Depends(get_db)):
    """Get statistics about customs event assignments"""
    
    # Total events by status
    status_counts = db.query(
        ShipmentCustomsEvent.status,
        func.count(ShipmentCustomsEvent.id).label('count')
    ).group_by(ShipmentCustomsEvent.status).all()
    
    # Events by firm
    firm_counts = db.query(
        CustomsBrokerageFirm.legal_name,
        func.count(ShipmentCustomsEvent.id).label('count')
    ).join(
        ShipmentCustomsEvent,
        CustomsBrokerageFirm.id == ShipmentCustomsEvent.assigned_firm_id
    ).group_by(CustomsBrokerageFirm.id, CustomsBrokerageFirm.legal_name).all()
    
    # Unassigned events by country
    unassigned_by_country = db.query(
        ShipmentCustomsEvent.country_code,
        func.count(ShipmentCustomsEvent.id).label('count')
    ).filter(
        ShipmentCustomsEvent.assigned_firm_id.is_(None),
        ShipmentCustomsEvent.shipper_handled == False
    ).group_by(ShipmentCustomsEvent.country_code).all()
    
    return {
        "status_distribution": dict(status_counts),
        "firm_workloads": [{"firm": f[0], "count": f[1]} for f in firm_counts],
        "unassigned_by_country": dict(unassigned_by_country)
    }