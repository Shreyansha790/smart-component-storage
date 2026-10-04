"""
Tier 2 Integration Tests: Resilient Alert Throttling & Scheduler Idempotency.

Derivation Source: ORIGINAL_REQUEST § Acceptance:
"Background scheduler operates safely with resilient state handling and no duplicate email dispatching."
PROJECT.md § Feature 6.
"""

from datetime import datetime, timedelta
import smtplib
from unittest.mock import patch, MagicMock
import pytest

from app import models
from app.services.alert_throttler import AlertThrottler, handle_condition_violation
from app.services.scheduler import check_shelf_life_and_alert, _already_alerted_today
from tests.conftest import TestingSessionLocal


class TestSchedulerIdempotencyAndAlertThrottling:
    """Verifies that automated alerts are deduplicated and email flooding is prevented."""

    def test_alert_throttler_cooldown_prevents_flooding(self, db_session, test_cabinet, test_component):
        """
        Consecutive condition violations within the cooldown window (e.g. 15 min)
        must trigger exactly 1 alert, silencing the rest.
        """
        throttler = AlertThrottler(cooldown_minutes=15)

        # 1. First violation: must NOT be in cooldown
        assert throttler.is_in_cooldown(db_session, test_cabinet.cabinet_location) is False

        # Mark sent
        now = datetime.utcnow()
        throttler.mark_alert_sent(test_cabinet.cabinet_location, sent_at=now)

        # 2. Immediate second violation: MUST be in cooldown
        assert throttler.is_in_cooldown(db_session, test_cabinet.cabinet_location) is True

        # 3. Violation after 10 minutes (still < 15 min): MUST be in cooldown
        with patch("app.services.alert_throttler.datetime") as mock_dt:
            mock_dt.utcnow.return_value = now + timedelta(minutes=10)
            assert throttler.is_in_cooldown(db_session, test_cabinet.cabinet_location) is True

        # 4. Violation after 16 minutes (past cooldown window): Cooldown expires
        with patch("app.services.alert_throttler.datetime") as mock_dt:
            mock_dt.utcnow.return_value = now + timedelta(minutes=16)
            assert throttler.is_in_cooldown(db_session, test_cabinet.cabinet_location) is False

    def test_repeated_telemetry_violations_generate_only_one_alert_log(
        self, db_session, test_cabinet, test_component
    ):
        """
        Simulate 10 consecutive sensor readings arriving in 1 minute, all reporting
        an extreme heat spike (45°C). Exactly ONE alert must be logged in AlertLog.
        """
        # Ensure fresh state
        from app.services.alert_throttler import alert_throttler
        alert_throttler.reset()

        dispatched_count = 0
        for _ in range(10):
            triggered = handle_condition_violation(
                cabinet_location=test_cabinet.cabinet_location,
                current_temp=45.0,
                current_humidity=50.0,
                target_temp=test_cabinet.target_temperature_c,
                target_humidity=test_cabinet.target_humidity_percent,
                db=db_session,
                background_tasks=None,
            )
            if triggered:
                dispatched_count += 1

        assert dispatched_count == 1, f"Expected exactly 1 alert dispatch, got {dispatched_count}!"

        # Query AlertLog entries in DB
        logs = (
            db_session.query(models.AlertLog)
            .filter(models.AlertLog.alert_type == models.AlertType.condition_violation)
            .all()
        )
        assert len(logs) == 1
        assert "45.0" in logs[0].message

    def test_scheduler_idempotency_no_duplicate_daily_alerts(self, db_session, test_user, test_cabinet):
        """
        Running the shelf-life alert scheduler multiple times on the same day
        MUST NOT dispatch duplicate emails for the same component and alert type.
        """
        # Create a component approaching its limit (stored 340 days out of 365 days)
        comp = models.Component(
            batch_id="BATCH-APPROACHING-001",
            part_number="CAP-100UF",
            manufacturer="TDK",
            category="Capacitors",
            cabinet_location=test_cabinet.cabinet_location,
            quantity=100,
            stored_date=datetime.utcnow() - timedelta(days=361),
            min_temperature_c=10.0,
            max_temperature_c=30.0,
            max_humidity_percent=60.0,
            shelf_life_days=365,
            owner_id=test_user.id,
        )
        db_session.add(comp)
        db_session.commit()

        comp_id = comp.id
        # Test direct helper first
        assert _already_alerted_today(db_session, comp_id, models.AlertType.shelf_life_approaching) is False

        with patch("app.services.scheduler.SessionLocal", side_effect=TestingSessionLocal), \
             patch("app.services.scheduler.send_email", return_value=True) as mock_send:
            # First scheduler scan
            check_shelf_life_and_alert()
            first_run_calls = mock_send.call_count
            assert first_run_calls >= 1, "Expected at least 1 alert email on first scan"

            fresh_session = TestingSessionLocal()
            try:
                assert _already_alerted_today(fresh_session, comp_id, models.AlertType.shelf_life_approaching) is True

                # Immediate second scheduler scan
                check_shelf_life_and_alert()
                second_run_calls = mock_send.call_count
                assert second_run_calls == first_run_calls, (
                    f"Scheduler dispatched duplicate emails! Initial: {first_run_calls}, After 2nd scan: {second_run_calls}"
                )
            finally:
                fresh_session.close()

    def test_smtp_connection_failure_handled_gracefully(self, db_session, test_cabinet, test_component):
        """
        If the SMTP server raises an unhandled connection error, the alert service
        must catch and log the failure without crashing the application process.
        """
        from app.services.alert_throttler import alert_throttler, background_send_condition_alerts
        alert_throttler.reset()

        with patch("app.services.alert_throttler.send_email", side_effect=smtplib.SMTPConnectError(111, "Connection refused")):
            # Should not raise exception
            background_send_condition_alerts(
                recipients=["test@example.com"],
                subject="Test Alert",
                body_html="<p>Test</p>",
            )

    def test_cross_cabinet_alert_throttling_isolation(self, db_session):
        """
        Verify that alert in CAB-10 does NOT throttle CAB-1 (no substring collision).
        Both throttler.is_in_cooldown and is_alert_throttled must operate independently.
        """
        from app.services.alert_throttler import AlertThrottler, is_alert_throttled
        throttler = AlertThrottler(cooldown_minutes=15)
        throttler.reset()

        # Log alert for CAB-10
        msg_cab10 = "Storage condition violation in [CAB-10]: Temp=45°C (Target 20°C), Humidity=60% (Target 40%)"
        log10 = models.AlertLog(
            alert_type=models.AlertType.condition_violation,
            message=msg_cab10,
            sent_at=datetime.utcnow(),
            email_sent_to="test@example.com",
        )
        db_session.add(log10)
        db_session.commit()

        # CAB-10 must be throttled
        assert throttler.is_in_cooldown(db_session, "CAB-10") is True
        assert is_alert_throttled(db_session, "CAB-10") is True

        # CAB-1 must NOT be throttled by CAB-10
        assert throttler.is_in_cooldown(db_session, "CAB-1") is False
        assert is_alert_throttled(db_session, "CAB-1") is False

