"""
Alert endpoints for querying active system alerts and manually triggering
shelf-life email alerts.
"""

from datetime import date, datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import auth, models
from app.services.scheduler import check_shelf_life_and_alert

router = APIRouter(tags=["Alerts"])


class AlertResponse(BaseModel):
    id: str
    title: str
    message: str
    level: str  # 'critical' | 'warning' | 'info'
    timestamp: str
    read: bool = False


def generate_inventory_alerts(db: Session, user: Optional[models.User] = None) -> List[dict]:
    query = db.query(models.Component)
    # Only filter by owner if user is NOT an admin
    if user and getattr(user, "role", None) != models.UserRole.admin and getattr(user, "role", None) != "admin":
        query = query.filter(models.Component.owner_id == user.id)
    components = query.all()

    today = date.today()
    alerts = []

    for comp in components:
        # Expiry calculation
        if comp.stored_date and comp.shelf_life_days is not None:
            expiry_date = comp.stored_date + timedelta(days=comp.shelf_life_days)
            days_left = (expiry_date - today).days

            if days_left < 0:
                alerts.append({
                    "id": f"exp-{comp.id}",
                    "title": "Expired Component",
                    "message": f"Batch {comp.batch_id} ({comp.part_number}) expired {abs(days_left)} day(s) ago.",
                    "level": "critical",
                    "timestamp": datetime.utcnow().isoformat(),
                    "read": False,
                })
            elif days_left <= 7:
                alerts.append({
                    "id": f"near-exp-{comp.id}",
                    "title": "Shelf-Life Warning",
                    "message": f"Batch {comp.batch_id} ({comp.part_number}) will expire in {days_left} day(s).",
                    "level": "warning",
                    "timestamp": datetime.utcnow().isoformat(),
                    "read": False,
                })

        # Low stock check
        if comp.quantity is not None and comp.quantity <= 5:
            alerts.append({
                "id": f"low-stock-{comp.id}",
                "title": "Low Stock Warning",
                "message": f"Part {comp.part_number} (Batch {comp.batch_id}) has low stock ({comp.quantity} remaining).",
                "level": "warning",
                "timestamp": datetime.utcnow().isoformat(),
                "read": False,
            })

    return alerts


@router.get("/alerts", response_model=List[AlertResponse])
@router.get("/api/alerts", response_model=List[AlertResponse])
def get_alerts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Return active dynamic alerts for the authenticated user's components."""
    return generate_inventory_alerts(db, user=current_user)


@router.patch("/alerts/{alert_id}/read")
@router.patch("/api/alerts/{alert_id}/read")
def mark_alert_read(alert_id: str):
    return {"status": "ok", "id": alert_id, "read": True}


@router.post("/alerts/mark-all-read")
@router.post("/api/alerts/mark-all-read")
def mark_all_alerts_read():
    return {"status": "ok", "message": "All alerts marked as read"}


@router.post("/api/alerts/send-email")
def send_alert_emails(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Manually trigger the shelf-life alert checker."""
    check_shelf_life_and_alert()
    return {
        "status": "success",
        "message": "Shelf-life alert check completed."
    }