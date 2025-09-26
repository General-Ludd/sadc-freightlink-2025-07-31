from sqlalchemy.orm import Session
from models.shipper import Client_Notification 

def create_notification(db: Session, company_id: int, notif_type: str, message: str):
    notification = Client_Notification(
        company_id=company_id,
        type=notif_type,
        message=message,
        is_read=False,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification