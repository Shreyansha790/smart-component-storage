"""
Alert Throttling & Asynchronous Notification Service.

Guarantees resilient alert delivery with a strict cooldown window
(default 15 minutes) to eliminate email flooding vulnerabilities
during environmental condition violations.
Offloads all SMTP transmissions to background tasks to keep HTTP response times < 20ms.
"""

from datetime import datetime, timedelta
import logging
import re
from typing import Dict, List, Optional, Tuple

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.services.email_service import send_email, build_condition_violation_email

logger = logging.getLogger("alert_throttler")


class AlertThrottler:
    """
    Manages in-memory and database-backed rate-limiting for automated alerts.
    """

    def __init__(self, cooldown_minutes: Optional[int] = None):
        self.cooldown_minutes = cooldown_minutes or getattr(settings, "ALERT_COOLDOWN_MINUTES", 15)
        # In-memory map: key -> last_alert_sent_at (datetime)
        self._last_alert_time: Dict[str, datetime] = {}

    def _get_cache_key(self, cabinet_location: str, alert_type: str) -> str:
        return f"{cabinet_location}:{alert_type}"

    def is_in_cooldown(
        self,
        db: Session,
        cabinet_location: str,
        alert_type: models.AlertType = models.AlertType.condition_violation,
    ) -> bool:
        """
        Determines whether an alert for this cabinet is currently throttled by the cooldown window.
        Checks both fast in-memory timestamps and database AlertLog history.
        """
        now = datetime.utcnow()
        cache_key = self._get_cache_key(cabinet_location, alert_type.value)

        # 1. Check in-memory timestamp
        if cache_key in self._last_alert_time:
            elapsed = (now - self._last_alert_time[cache_key]).total_seconds()
            if elapsed < self.cooldown_minutes * 60:
                logger.info(
                    "Alert throttled in-memory for %s (elapsed %.1fs < %ds)",
                    cabinet_location,
                    elapsed,
                    self.cooldown_minutes * 60,
                )
                return True

        # 2. Check database AlertLog table with structured boundaries
        cutoff = now - timedelta(minutes=self.cooldown_minutes)
        candidate_logs = (
            db.query(models.AlertLog)
            .filter(
                models.AlertLog.alert_type == alert_type,
                models.AlertLog.message.like(f"%{cabinet_location}%"),
                models.AlertLog.sent_at >= cutoff,
            )
            .order_by(models.AlertLog.sent_at.desc())
            .all()
        )

        # Match exact boundary so CAB-1 does not match CAB-10, CAB-11, etc.
        escaped_loc = re.escape(cabinet_location)
        boundary_pattern = re.compile(rf"(?<![A-Za-z0-9_-]){escaped_loc}(?![A-Za-z0-9_-])")

        recent_log = None
        for log in candidate_logs:
            if boundary_pattern.search(log.message):
                recent_log = log
                break

        if recent_log:
            self._last_alert_time[cache_key] = recent_log.sent_at
            logger.info(
                "Alert throttled by DB record for %s (logged at %s)",
                cabinet_location,
                recent_log.sent_at,
            )
            return True

        return False

    # Alias for API consistency
    is_alert_throttled = is_in_cooldown

    def mark_alert_sent(
        self,
        cabinet_location: str,
        alert_type: models.AlertType = models.AlertType.condition_violation,
        sent_at: Optional[datetime] = None,
    ):
        """Updates the cooldown tracker timestamp."""
        cache_key = self._get_cache_key(cabinet_location, alert_type.value)
        self._last_alert_time[cache_key] = sent_at or datetime.utcnow()

    def reset(self, cabinet_location: Optional[str] = None):
        """Resets the in-memory cooldown cache."""
        if cabinet_location:
            keys_to_remove = [k for k in self._last_alert_time if k.startswith(f"{cabinet_location}:")]
            for k in keys_to_remove:
                self._last_alert_time.pop(k, None)
        else:
            self._last_alert_time.clear()


# Global singleton instance
alert_throttler = AlertThrottler()


def is_alert_throttled(
    db: Session,
    cabinet_location: str,
    alert_type: models.AlertType = models.AlertType.condition_violation,
) -> bool:
    """Convenience helper to check if alerts are throttled for a cabinet."""
    return alert_throttler.is_in_cooldown(db, cabinet_location, alert_type)


def background_send_condition_alerts(
    recipients: List[str],
    subject: str,
    body_html: str,
):
    """
    Background worker task executed outside the HTTP request lifecycle.
    Iterates through recipient email addresses without blocking the API.
    """
    for email in recipients:
        try:
            success = send_email(email, subject, body_html)
            if success:
                logger.info("Background alert email delivered to %s", email)
            else:
                logger.warning("Background alert email delivery failed or skipped for %s", email)
        except Exception as exc:
            logger.error("Exception during background email delivery to %s: %s", email, exc)


def handle_condition_violation(
    cabinet_location: str,
    current_temp: float,
    current_humidity: float,
    target_temp: float,
    target_humidity: float,
    db: Session,
    background_tasks: Optional[BackgroundTasks] = None,
) -> bool:
    """
    Evaluates out-of-range condition violation, verifies cooldown, logs to AlertLog,
    and schedules non-blocking background emails.

    Returns True if an alert was triggered, False if throttled or no recipients.
    """
    if alert_throttler.is_in_cooldown(db, cabinet_location, models.AlertType.condition_violation):
        return False

    # Find distinct owners of components stored in this cabinet
    owners = (
        db.query(models.User)
        .join(models.Component, models.Component.owner_id == models.User.id)
        .filter(models.Component.cabinet_location == cabinet_location)
        .distinct()
        .all()
    )

    recipient_emails = [u.email for u in owners if u.email]
    if not recipient_emails:
        logger.info("No recipient emails found for components in cabinet %s", cabinet_location)
        # Still mark throttled so we don't query repeatedly on every POST
        alert_throttler.mark_alert_sent(cabinet_location)
        return False

    # Record in AlertLog for auditability and persistent deduplication
    now = datetime.utcnow()
    # Find any component in this cabinet to associate the log with (optional foreign key)
    first_comp = (
        db.query(models.Component)
        .filter(models.Component.cabinet_location == cabinet_location)
        .first()
    )
    comp_id = first_comp.id if first_comp else None

    for email in recipient_emails:
        log_entry = models.AlertLog(
            component_id=comp_id,
            alert_type=models.AlertType.condition_violation,
            message=(
                f"Storage condition violation in [{cabinet_location}]: "
                f"Temp={current_temp}°C (Target {target_temp}°C), "
                f"Humidity={current_humidity}% (Target {target_humidity}%)"
            ),
            sent_at=now,
            email_sent_to=email,
        )
        db.add(log_entry)

    db.commit()
    alert_throttler.mark_alert_sent(cabinet_location, sent_at=now)

    subject, body_html = build_condition_violation_email(
        cabinet_location,
        current_temp,
        current_humidity,
        target_temp,
        target_humidity,
    )

    if background_tasks is not None:
        background_tasks.add_task(background_send_condition_alerts, recipient_emails, subject, body_html)
    else:
        # Fallback if no background_tasks provided (e.g. direct sync call)
        background_send_condition_alerts(recipient_emails, subject, body_html)

    return True
