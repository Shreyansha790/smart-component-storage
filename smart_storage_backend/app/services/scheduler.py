"""
Background job (APScheduler) that periodically scans the inventory and
emails the owning user and all admins when a component is approaching (or has exceeded)
its manufacturer shelf-life limit.

Duplicate-alert protection: for each (component, alert_type) we only send
one email per calendar day, tracked via AlertLog.
"""

import logging
from datetime import date, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.config import settings
from app import models
from app.services.email_service import send_email, build_shelf_life_email

logger = logging.getLogger("scheduler")

scheduler = BackgroundScheduler()


def _already_alerted_today(db: Session, component_id: int, alert_type: models.AlertType) -> bool:
    today_start = datetime.combine(date.today(), datetime.min.time())
    existing = (
        db.query(models.AlertLog)
        .filter(
            models.AlertLog.component_id == component_id,
            models.AlertLog.alert_type == alert_type,
            models.AlertLog.sent_at >= today_start,
        )
        .first()
    )
    return existing is not None


def check_shelf_life_and_alert():
    """Scans all components; emails the owner and all admins if nearing/over shelf-life limit."""
    db: Session = SessionLocal()
    try:
        components = db.query(models.Component).all()
        today = date.today()

        for component in components:
            if not component.stored_date or component.shelf_life_days is None:
                continue

            # Safe date normalization (handles str, datetime, or date)
            stored = component.stored_date
            if isinstance(stored, str):
                stored = datetime.strptime(stored[:10], "%Y-%m-%d").date()
            elif isinstance(stored, datetime):
                stored = stored.date()

            days_in_storage = (today - stored).days
            days_remaining = component.shelf_life_days - days_in_storage

            if days_remaining > settings.SHELF_LIFE_ALERT_THRESHOLD_DAYS:
                continue  # Not close enough yet

            alert_type = (
                models.AlertType.shelf_life_exceeded
                if days_remaining <= 0
                else models.AlertType.shelf_life_approaching
            )

            if _already_alerted_today(db, component.id, alert_type):
                continue

            # 1. Collect recipient emails: Component Owner + All Admins
            recipients = set()

            owner = component.owner
            if owner is None and component.owner_id is not None:
                owner = db.query(models.User).filter(models.User.id == component.owner_id).first()

            if owner and owner.email:
                recipients.add(owner.email)

            # Query all registered admin users
            admins = db.query(models.User).filter(models.User.role == "admin").all()
            for admin in admins:
                if admin.email:
                    recipients.add(admin.email)

            if not recipients:
                logger.warning("Component %s has no recipients (no owner or admin email) — skipping alert", component.id)
                continue

            subject, body_html = build_shelf_life_email(component, days_in_storage, days_remaining)

            # 2. Dispatch email to each recipient and log
            for recipient_email in recipients:
                sent = send_email(recipient_email, subject, body_html)

                if sent:
                    log_entry = models.AlertLog(
                        component_id=component.id,
                        alert_type=alert_type,
                        message=f"{days_in_storage} days stored / {component.shelf_life_days} day limit "
                                f"({days_remaining} day(s) remaining)",
                        email_sent_to=recipient_email,
                    )
                    db.add(log_entry)
                    logger.info("Alert email sent successfully to %s for component %s", recipient_email, component.part_number)

            db.commit()
    except Exception:
        logger.exception("check_shelf_life_and_alert failed")
    finally:
        db.close()


def start_scheduler():
    interval_hours = settings.ALERT_CHECK_INTERVAL_HOURS
    scheduler.add_job(
        check_shelf_life_and_alert,
        "interval",
        hours=interval_hours,
        id="shelf_life_check",
        replace_existing=True,
        next_run_time=datetime.now(),  # run once immediately on startup
    )
    scheduler.start()
    logger.info("Scheduler started — checking shelf life every %s hour(s)", interval_hours)


def stop_scheduler():
    scheduler.shutdown(wait=False)