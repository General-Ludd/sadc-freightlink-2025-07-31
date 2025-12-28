# tasks.py (Celery tasks)
from celery import Celery
from database import SessionLocal
from services.nexus.customs_assignment_service import CustomsEventAssigner

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