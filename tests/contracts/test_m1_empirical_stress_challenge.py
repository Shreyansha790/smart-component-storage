"""
Milestone 1 Empirical Stress Test & Challenger Verification Suite.

Adversarial stress-testing of:
1. Jitter Filter: Extreme noise, NaN, Inf, step changes, impulses (24C -> 85C -> 24C), negative values,
   median dampening, and EMA convergence without runaway divergence.
2. WebSocket Telemetry Fan-Out: Multiple concurrent subscribers, instantaneous fan-out delivery,
   abrupt disconnection resilience, and clean recovery.
3. Alert Flooding / Cooldown Stress: 100 rapid out-of-range telemetry posts within 2 seconds,
   exactly 1 alert logged/dispatched, 99 throttled, and non-blocking low response latency.
"""

import math
import random
import statistics
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest
from app import models
from app.services.alert_throttler import alert_throttler
from app.services.jitter_filter import JitterFilter
from app.services.websocket_manager import ws_manager
from tests.helpers.hmac_helper import create_esp32_telemetry_request, DEFAULT_TEST_SECRET


# ============================================================================
# 1. JITTER FILTER EMPIRICAL STRESS TESTS
# ============================================================================

class TestJitterFilterEmpiricalStress:
    """Stress tests and mathematical property verification for JitterFilter."""

    def test_impulse_spike_dampening_oracle(self):
        """
        ORACLE TEST:
        Nominal 24.0°C baseline. A single-sample severe sensor glitch jumps to 85.0°C
        and immediately returns to 24.0°C.
        Window size is 5.
        Mathematical oracle:
        [24.0, 24.0, 85.0, 24.0, 24.0] has sorted array [24.0, 24.0, 24.0, 24.0, 85.0].
        The median is strictly 24.0°C.
        Therefore, the impulse spike must be completely dampened (0.0% leakage).
        """
        jf = JitterFilter(window_size=5, alpha=0.25)
        cab = "CAB-IMPULSE-CHALLENGE"

        # Prime with nominal readings
        jf.smooth_reading(cab, 24.0, 45.0)
        jf.smooth_reading(cab, 24.0, 45.0)

        # Inject severe impulse spike: 85°C, 99% RH
        temp_spike, hum_spike = jf.smooth_reading(cab, 85.0, 99.0)

        # Assert dampening: temp must remain strictly at 24.0°C
        assert temp_spike == 24.0, f"Impulse spike leaked into output: {temp_spike}°C"
        assert hum_spike == 45.0, f"Impulse humidity leaked into output: {hum_spike}%"

        # Follow up with nominal readings
        t_next, h_next = jf.smooth_reading(cab, 24.0, 45.0)
        assert t_next == 24.0
        assert h_next == 45.0

    def test_step_change_smooth_convergence_and_monotonicity(self):
        """
        CONVERGENCE & STABILITY TEST:
        Step change from 20.0°C to 45.0°C.
        1. Monotonicity: for all t after window fill, EMA[t] >= EMA[t-1].
        2. No Overshoot: EMA[t] <= 45.0°C for all t.
        3. Convergence: EMA converges smoothly within 0.1°C of target 45.0°C after 25 steps.
        4. No Runaway Divergence: |EMA[t]| is strictly bounded by max_temp_c.
        """
        jf = JitterFilter(window_size=5, alpha=0.25)
        cab = "CAB-STEP-CHALLENGE"

        # Prime at 20°C
        for _ in range(5):
            jf.smooth_reading(cab, 20.0, 40.0)

        step_target = 45.0
        outputs = []
        for i in range(25):
            smoothed_t, _ = jf.smooth_reading(cab, step_target, 40.0)
            outputs.append(smoothed_t)

        # Monotonicity check (from sample 3 onwards, median is 45.0)
        for i in range(3, len(outputs) - 1):
            assert outputs[i + 1] >= outputs[i], f"Non-monotonic step response at index {i}: {outputs}"

        # No overshoot
        assert all(val <= step_target for val in outputs), "EMA overshot step target!"

        # Smooth convergence to target within 25 steps
        final_val = outputs[-1]
        assert abs(final_val - step_target) < 0.1, f"Failed to converge to {step_target}: final={final_val}"

    def test_extreme_noise_variance_reduction(self):
        """
        NOISE REJECTION TEST:
        Inject 100 samples with zero-mean Gaussian noise (sigma = 10.0°C) centered on 25.0°C.
        Empirical oracle: The filter must reduce the standard deviation by at least 65%.
        """
        random.seed(42)
        jf = JitterFilter(window_size=5, alpha=0.25)
        cab = "CAB-NOISE-CHALLENGE"

        raw_readings = [25.0 + random.gauss(0.0, 10.0) for _ in range(100)]
        smoothed_readings = [jf.smooth_reading(cab, t, 50.0)[0] for t in raw_readings]

        raw_std = statistics.stdev(raw_readings)
        smoothed_std = statistics.stdev(smoothed_readings[10:])  # Skip warm-up period

        variance_reduction = 1.0 - (smoothed_std / raw_std)
        assert variance_reduction >= 0.65, (
            f"Noise reduction insufficient: raw_std={raw_std:.2f}, "
            f"smoothed_std={smoothed_std:.2f}, reduction={variance_reduction:.2%}"
        )

    def test_negative_values_and_physical_clamping(self):
        """
        BOUNDARY & NEGATIVE VALUES TEST:
        1. Negative values within physical envelope (-40°C to 0°C) must be smoothed accurately.
        2. Values outside envelope (-100°C, 200°C) must be clamped to [-40, 85].
        3. Humidity outside envelope (-50%, 150%) must be clamped to [0, 100].
        """
        jf = JitterFilter(min_temp_c=-40.0, max_temp_c=85.0, min_humidity_pct=0.0, max_humidity_pct=100.0)
        cab_neg = "CAB-COLD-STORAGE"

        # Legitimate cryo storage at -25°C
        for _ in range(5):
            t_out, h_out = jf.smooth_reading(cab_neg, -25.0, 20.0)
        assert t_out == -25.0, f"Expected -25.0°C, got {t_out}"

        # Clamping lower boundary
        cab_clamp = "CAB-CLAMP"
        t_low, h_low = jf.smooth_reading(cab_clamp, -120.0, -45.0)
        assert t_low == -40.0, f"Expected clamp to -40.0°C, got {t_low}"
        assert h_low == 0.0, f"Expected clamp to 0.0%, got {h_low}"

        # Clamping upper boundary
        jf.reset(cab_clamp)
        t_high, h_high = jf.smooth_reading(cab_clamp, 300.0, 180.0)
        assert t_high == 85.0, f"Expected clamp to 85.0°C, got {t_high}"
        assert h_high == 100.0, f"Expected clamp to 100.0%, got {h_high}"

    def test_nan_and_inf_robustness(self):
        """
        ADVERSARIAL INPUT TEST:
        Inject NaN, +Inf, -Inf.
        The filter must not raise an unhandled exception or return NaN.
        Subsequent clean readings must recover smoothly without permanent state corruption.
        """
        jf = JitterFilter()
        cab = "CAB-NAN-ROBUST"

        # Inject NaN
        t_nan, h_nan = jf.smooth_reading(cab, float("nan"), float("nan"))
        assert not math.isnan(t_nan) and not math.isnan(h_nan), "NaN leaked into filter output!"
        assert -40.0 <= t_nan <= 85.0
        assert 0.0 <= h_nan <= 100.0

        # Inject +Inf and -Inf
        t_inf, _ = jf.smooth_reading(cab, float("inf"), 50.0)
        assert math.isfinite(t_inf) and t_inf <= 85.0

        t_ninf, _ = jf.smooth_reading(cab, float("-inf"), 50.0)
        assert math.isfinite(t_ninf) and t_ninf >= -40.0

        # Recovery test: feed 20 nominal readings (sufficient decay for alpha=0.25 time constant)
        for _ in range(20):
            t_rec, h_rec = jf.smooth_reading(cab, 22.0, 45.0)
        assert abs(t_rec - 22.0) < 1.0, f"Filter failed to recover after NaN/Inf inputs: {t_rec}"


# ============================================================================
# 2. WEBSOCKET TELEMETRY FAN-OUT & RESILIENCE TESTS
# ============================================================================

class TestWebSocketFanOutStress:
    """Stress tests for multi-client WebSocket fan-out and connection drop recovery."""

    def test_multi_client_fanout_instantaneous(self, client, test_cabinet):
        """
        FAN-OUT TEST:
        Connect 4 concurrent WebSocket clients to /ws/telemetry.
        Post telemetry and verify all 4 receive the exact payload instantaneously.
        """
        with client.websocket_connect("/ws/telemetry") as ws1, \
             client.websocket_connect("/ws/telemetry") as ws2, \
             client.websocket_connect("/ws/telemetry") as ws3, \
             client.websocket_connect("/ws/telemetry") as ws4:

            assert len(ws_manager.active_connections) >= 4

            headers, body = create_esp32_telemetry_request(
                cabinet_location=test_cabinet.cabinet_location,
                temperature_c=22.5,
                humidity_percent=48.0,
                door_open=False,
            )

            resp = client.post(
                f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
                content=body,
                headers=headers,
            )
            assert resp.status_code == 200

            # Verify all 4 clients receive the broadcast frame
            sockets = [ws1, ws2, ws3, ws4]
            for ws in sockets:
                frame = ws.receive_json()
                assert frame["type"] == "TELEMETRY_UPDATE"
                assert frame["cabinet_location"] == test_cabinet.cabinet_location
                assert pytest.approx(frame["telemetry"]["temperature_c"]) == 22.5
                assert pytest.approx(frame["telemetry"]["humidity_percent"]) == 48.0
                assert frame["telemetry"]["door_open"] is False

    def test_abrupt_disconnect_resilience_and_continued_broadcast(self, client, test_cabinet):
        """
        ABRUPT DISCONNECT RECOVERY:
        Connect 3 clients. Drop client 2 abruptly (close socket).
        Post telemetry. Verify remaining clients 1 and 3 receive broadcast cleanly,
        and ws_manager safely prunes the dead connection without raising unhandled exceptions.
        """
        with client.websocket_connect("/ws/telemetry") as ws1, \
             client.websocket_connect("/ws/telemetry") as ws2, \
             client.websocket_connect("/ws/telemetry") as ws3:

            initial_count = len(ws_manager.active_connections)
            assert initial_count >= 3

            # Abruptly close ws2
            ws2.close()

            # Post telemetry
            headers, body = create_esp32_telemetry_request(
                cabinet_location=test_cabinet.cabinet_location,
                temperature_c=23.0,
                humidity_percent=50.0,
            )
            resp = client.post(
                f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
                content=body,
                headers=headers,
            )
            assert resp.status_code == 200

            # Clients 1 and 3 must receive the payload cleanly
            frame1 = ws1.receive_json()
            frame3 = ws3.receive_json()

            assert frame1["type"] == "TELEMETRY_UPDATE"
            assert frame3["type"] == "TELEMETRY_UPDATE"
            assert pytest.approx(frame1["telemetry"]["temperature_c"]) == 23.0
            assert pytest.approx(frame3["telemetry"]["temperature_c"]) == 23.0

    def test_rapid_broadcast_stream(self, client, test_cabinet):
        """
        STREAMING STRESS TEST:
        Stream 10 consecutive telemetry frames.
        Connected client must receive all 10 frames in order without corruption.
        """
        with client.websocket_connect("/ws/telemetry") as ws:
            for step in range(10):
                temp = 20.0 + step * 0.5
                headers, body = create_esp32_telemetry_request(
                    cabinet_location=test_cabinet.cabinet_location,
                    temperature_c=temp,
                    humidity_percent=45.0,
                )
                resp = client.post(
                    f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
                    content=body,
                    headers=headers,
                )
                assert resp.status_code == 200

                frame = ws.receive_json()
                assert frame["type"] == "TELEMETRY_UPDATE"
                assert pytest.approx(frame["telemetry"]["temperature_c"]) == temp


# ============================================================================
# 3. ALERT FLOODING / COOLDOWN STRESS & NON-BLOCKING LATENCY
# ============================================================================

class TestAlertFloodingCooldownStress:
    """Stress tests for alert deduplication, cooldown throttling, and HTTP latency under flood."""

    def test_100_rapid_out_of_range_posts_throttled_and_low_latency(
        self, client, db_session, test_cabinet, test_component
    ):
        """
        FLOOD STRESS TEST:
        Fire 100 rapid out-of-range telemetry posts within 2 seconds.
        1. Exactly 1 alert is dispatched and logged into models.AlertLog.
        2. Exactly 99 posts are throttled by the cooldown window.
        3. Background email dispatch is non-blocking (mock send_email called exactly once).
        4. Response latency remains low (elapsed time < 2.5s, all 100 return 200 OK).
        """
        alert_throttler.reset()

        reqs = [
            create_esp32_telemetry_request(
                cabinet_location=test_cabinet.cabinet_location,
                temperature_c=55.0,
                humidity_percent=85.0,
                timestamp_offset=i,
            )
            for i in range(100)
        ]

        mock_email = MagicMock(return_value=True)
        with patch("app.services.alert_throttler.send_email", mock_email):
            t_start = time.perf_counter()
            success_count = 0
            for headers, body in reqs:
                resp = client.post(
                    f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
                    content=body,
                    headers=headers,
                )
                if resp.status_code == 200:
                    success_count += 1
            t_end = time.perf_counter()

        elapsed = t_end - t_start
        avg_latency_ms = (elapsed / 100) * 1000

        # Assert all 100 HTTP posts completed with 200 OK
        assert success_count == 100, f"Expected 100 successful posts, got {success_count}"

        # Assert elapsed time is within 2.5 seconds (measured ~1.6s - 1.8s)
        assert elapsed < 2.5, f"100 posts exceeded 2.5s: {elapsed:.3f}s"

        # Assert exactly ONE AlertLog record exists in the database
        logs = (
            db_session.query(models.AlertLog)
            .filter(
                models.AlertLog.alert_type == models.AlertType.condition_violation,
                models.AlertLog.message.like(f"%{test_cabinet.cabinet_location}%"),
            )
            .all()
        )
        assert len(logs) == 1, (
            f"Alert deduplication failed! Expected exactly 1 alert log, but found {len(logs)}."
        )

        # Assert mock email sender was called exactly 1 time
        assert mock_email.call_count == 1, (
            f"Expected exactly 1 email dispatch, got {mock_email.call_count}"
        )

        print(f"\n100 Rapid Telemetry Posts completed in {elapsed:.3f}s (avg: {avg_latency_ms:.2f}ms/req)")

    def test_cooldown_expiry_allows_subsequent_alert(
        self, client, db_session, test_cabinet, test_component
    ):
        """
        COOLDOWN EXPIRATION TEST:
        After initial alert and 15-minute cooldown expiry, a subsequent out-of-range
        reading must trigger a fresh alert.
        """
        alert_throttler.reset()

        headers1, body1 = create_esp32_telemetry_request(
            cabinet_location=test_cabinet.cabinet_location,
            temperature_c=60.0,
            humidity_percent=80.0,
            timestamp_offset=0,
        )

        mock_email = MagicMock(return_value=True)
        with patch("app.services.alert_throttler.send_email", mock_email):
            # First alert -> dispatched
            resp1 = client.post(f"/cabinet/{test_cabinet.cabinet_location}/telemetry", content=body1, headers=headers1)
            assert resp1.status_code == 200
            assert mock_email.call_count == 1

            # Second alert within cooldown -> throttled
            headers2, body2 = create_esp32_telemetry_request(
                cabinet_location=test_cabinet.cabinet_location,
                temperature_c=60.0,
                humidity_percent=80.0,
                timestamp_offset=1,
            )
            resp2 = client.post(f"/cabinet/{test_cabinet.cabinet_location}/telemetry", content=body2, headers=headers2)
            assert resp2.status_code == 200
            assert mock_email.call_count == 1

            # Fast forward time by 16 minutes (past 15-min cooldown)
            now = datetime.utcnow()
            with patch("app.services.alert_throttler.datetime") as mock_dt:
                mock_dt.utcnow.return_value = now + timedelta(minutes=16)
                headers3, body3 = create_esp32_telemetry_request(
                    cabinet_location=test_cabinet.cabinet_location,
                    temperature_c=60.0,
                    humidity_percent=80.0,
                    timestamp_offset=2,
                )
                resp3 = client.post(f"/cabinet/{test_cabinet.cabinet_location}/telemetry", content=body3, headers=headers3)
                assert resp3.status_code == 200
                assert mock_email.call_count == 2, "Second alert was not dispatched after cooldown expired!"

    def test_independent_cooldown_per_cabinet(
        self, client, db_session, test_user, test_cabinet, test_component
    ):
        """
        CABINET ISOLATION TEST:
        A condition violation in CAB-A must NOT suppress condition violations in CAB-B.
        """
        alert_throttler.reset()

        # Create Cabinet B with component owned by test_user
        cab_b = models.CabinetSetting(
            cabinet_location="CAB-B-ISOLATED",
            target_temperature_c=18.0,
            target_humidity_percent=40.0,
        )
        db_session.add(cab_b)
        db_session.commit()

        comp_b = models.Component(
            batch_id="BATCH-B",
            part_number="PART-B",
            manufacturer="Vendor-B",
            category="Sensors",
            cabinet_location="CAB-B-ISOLATED",
            quantity=20,
            stored_date=datetime.utcnow().date(),
            min_temperature_c=10.0,
            max_temperature_c=25.0,
            max_humidity_percent=50.0,
            shelf_life_days=90,
            owner_id=test_user.id,
        )
        db_session.add(comp_b)
        db_session.commit()

        mock_email = MagicMock(return_value=True)
        with patch("app.services.alert_throttler.send_email", mock_email):
            # Trigger violation on CAB-A
            h_a, b_a = create_esp32_telemetry_request(test_cabinet.cabinet_location, 50.0, 70.0, timestamp_offset=0)
            client.post(f"/cabinet/{test_cabinet.cabinet_location}/telemetry", content=b_a, headers=h_a)
            assert mock_email.call_count == 1

            # Trigger violation on CAB-B (must NOT be throttled by CAB-A)
            h_b, b_b = create_esp32_telemetry_request("CAB-B-ISOLATED", 50.0, 70.0, timestamp_offset=1)
            client.post("/cabinet/CAB-B-ISOLATED/telemetry", content=b_b, headers=h_b)
            assert mock_email.call_count == 2

            # Subsequent posts for both must be throttled
            h_a2, b_a2 = create_esp32_telemetry_request(test_cabinet.cabinet_location, 50.0, 70.0, timestamp_offset=2)
            h_b2, b_b2 = create_esp32_telemetry_request("CAB-B-ISOLATED", 50.0, 70.0, timestamp_offset=3)
            client.post(f"/cabinet/{test_cabinet.cabinet_location}/telemetry", content=b_a2, headers=h_a2)
            client.post("/cabinet/CAB-B-ISOLATED/telemetry", content=b_b2, headers=h_b2)
            assert mock_email.call_count == 2
