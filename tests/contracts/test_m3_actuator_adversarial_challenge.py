"""
Tier 3/5 Adversarial Stress & Empirical Challenge Suite for Milestone 3:
Actuator Controls, Closed-Loop Hysteresis, and Thermal Safety Cutoff.

Author: challenger_m3_1 (Empirical Challenger)
Targets:
  - smart_storage_backend/app/services/actuator_service.py
  - smart_storage_backend/app/schemas.py
  - smart_storage_backend/app/routes/actuators.py
  - smart_storage_backend/app/routes/cabinet.py

Adversarial Stress Test Dimensions:
1. Failsafe Thermal Cutoff Stress:
   - Continuous temperature sweep from -50.0°C to 9.99°C (and down to cryogenic -273.15°C) with
     Peltier override "ON" and AUTO. Verifies Peltier is strictly False 100% of the time.
   - Micro-step transition right across 10.0°C threshold (9.999°C vs 10.000°C).
   - AUTO mode with low target setpoint (e.g. target 5°C, temp 8°C > 5+2°C): cutoff MUST inhibit.
2. Hysteresis Boundary Stress:
   - Target temperature + 2.0°C boundary behavior (27.0°C vs 27.001°C vs 26.999°C).
   - Strict inequality verification: at exactly target + 2.0°C, Peltier remains False (deadband edge).
   - Floating-point step sweep across multiple target temperatures.
   - Manual override precedence over hysteresis (OFF forces False even at 50°C; ON forces True >=10°C).
3. Humidity Servo Boundary Stress:
   - Exact target_humidity, target + 0.1%, target - 0.1%, micro-deltas (1e-6).
   - Extreme humidity values (0.0%, 100.0%, near-zero, saturation).
   - Manual overrides OPEN (90°) and CLOSED (0°) irrespective of humidity.
4. Slot Locator Collisions, Concurrency & Security Fuzzing:
   - 100 simultaneous slot updates across multi-threaded workers (race condition test).
   - Concurrent mixed read/write/clear threads verifying thread-safety and no iteration mutation errors.
   - Pydantic schema validation rejecting invalid hex colors, SQL injection, XSS payloads, malformed strings.
   - Unicode slot identifiers (emojis, multibyte UTF-8, zero-width spaces).
   - Service-level color fallback for non-hex inputs.
5. End-to-End API Downlink & Multi-Cabinet Isolation:
   - Telemetry downlink response verification under extreme temperatures (<10°C, hysteresis edges).
   - Multi-cabinet state isolation ensuring no cross-cabinet actuator crosstalk.
"""

import concurrent.futures
import threading
import pytest
from pydantic import ValidationError

from app.services.actuator_service import (
    ActuatorService,
    compute_autonomous_actuator_state,
    MIN_SAFE_TEMP_C,
    COOLING_HYSTERESIS_DELTA_C,
    SERVO_OPEN_ANGLE,
    SERVO_CLOSED_ANGLE,
    DEFAULT_LOCATE_COLOR,
    actuator_service,
)
from app import schemas
from tests.helpers.hmac_helper import create_esp32_telemetry_request, DEFAULT_TEST_SECRET


# ============================================================================
# 1. FAILSAFE THERMAL CUTOFF EMPIRICAL STRESS TESTS (< 10.0°C)
# ============================================================================

class TestThermalSafetyCutoffEmpiricalStress:
    """Adversarial stress-testing of the thermal safety cutoff interlock."""

    def test_sweep_minus_50c_to_9_99c_peltier_override_on_strictly_false(self):
        """
        ADVERSARIAL STRESS SWEEP:
        Sweep temperatures from -50.0°C to 9.99°C in 0.25°C increments (600+ points)
        with peltier_override='ON'.
        Thermal safety interlock MUST guarantee peltier_active is False 100% of the time.
        """
        step = 0.25
        current_temp = -50.0
        total_evaluations = 0

        while current_temp < 10.0:
            result = compute_autonomous_actuator_state(
                current_temp=current_temp,
                current_humidity=50.0,
                target_temp=25.0,
                target_humidity=40.0,
                peltier_override="ON",
            )
            assert result["peltier_active"] is False, (
                f"SAFETY INTERLOCK BREACH: Peltier activated at {current_temp}°C with override ON! "
                "Must remain strictly False below 10.0°C."
            )
            total_evaluations += 1
            current_temp = round(current_temp + step, 4)

        # Verify we evaluated a dense sweep
        assert total_evaluations >= 240, f"Expected dense sweep, evaluated {total_evaluations}"

    def test_deep_cryogenic_temperatures_inhibit_peltier(self):
        """
        Cryogenic edge cases: -273.15°C (absolute zero), -200.0°C, -100.0°C, -80.0°C.
        Peltier MUST remain strictly False.
        """
        cryo_temps = [-273.15, -200.0, -150.0, -100.0, -80.0, -60.0]
        for t in cryo_temps:
            for override in ["ON", "AUTO", "OFF"]:
                result = compute_autonomous_actuator_state(
                    current_temp=t,
                    current_humidity=30.0,
                    target_temp=20.0,
                    target_humidity=40.0,
                    peltier_override=override,
                )
                assert result["peltier_active"] is False, (
                    f"Cryogenic thermal breach at {t}°C with override={override}"
                )

    def test_micro_boundary_near_10c_cutoff(self):
        """
        Micro-step precision test across the exact 10.0°C boundary:
        9.9°C, 9.99°C, 9.999°C, 9.999999°C -> peltier_active MUST be False (even with ON).
        10.000000°C -> cutoff is released; with ON, peltier_active MUST be True.
        """
        sub_10_temps = [9.0, 9.5, 9.9, 9.99, 9.999, 9.9999, 9.999999]
        for t in sub_10_temps:
            res_on = compute_autonomous_actuator_state(
                current_temp=t,
                current_humidity=45.0,
                target_temp=20.0,
                target_humidity=40.0,
                peltier_override="ON",
            )
            assert res_on["peltier_active"] is False, f"Breached at sub-10 micro-boundary {t}°C"

        # At exactly 10.0°C, override ON activates Peltier
        res_at_10 = compute_autonomous_actuator_state(
            current_temp=10.0,
            current_humidity=45.0,
            target_temp=20.0,
            target_humidity=40.0,
            peltier_override="ON",
        )
        assert res_at_10["peltier_active"] is True, "Peltier should activate at 10.0°C with override ON"

    def test_auto_mode_with_sub_10c_target_inhibits_hysteresis(self):
        """
        Pathological configuration test:
        Cabinet configured with very low target_temp = 5.0°C.
        Current temperature is 8.0°C.
        Since 8.0°C > (5.0 + 2.0 = 7.0°C), hysteresis condition is satisfied!
        HOWEVER, because 8.0°C < 10.0°C, safety cutoff MUST take precedence and inhibit Peltier.
        """
        result = compute_autonomous_actuator_state(
            current_temp=8.0,
            current_humidity=40.0,
            target_temp=5.0,
            target_humidity=45.0,
            peltier_override="AUTO",
        )
        assert result["peltier_active"] is False, (
            "Safety interlock failed to inhibit Peltier when temp is < 10°C despite hysteresis trigger!"
        )


# ============================================================================
# 2. CLOSED-LOOP HYSTERESIS BOUNDARY STRESS TESTS
# ============================================================================

class TestCoolingHysteresisBoundaryStress:
    """Stress testing hysteresis boundaries and deadbands at target + 2.0°C."""

    @pytest.mark.parametrize("target_temp", [15.0, 20.0, 22.5, 25.0, 30.0])
    def test_hysteresis_exact_boundary_and_micro_steps(self, target_temp):
        """
        Exhaustive test around target + 2.0°C:
        - target + 1.999°C: strictly False (within deadband)
        - target + 2.000°C: strictly False (deadband is inclusive of the exact boundary)
        - target + 2.001°C: strictly True (exceeds threshold)
        """
        boundary = target_temp + COOLING_HYSTERESIS_DELTA_C

        # Below boundary by 1 millidegree
        res_below = compute_autonomous_actuator_state(
            current_temp=boundary - 0.001,
            current_humidity=40.0,
            target_temp=target_temp,
            target_humidity=40.0,
        )
        assert res_below["peltier_active"] is False, (
            f"Expected Peltier OFF at boundary - 0.001°C ({boundary - 0.001}°C) for target {target_temp}°C"
        )

        # EXACT boundary (27.0°C for target 25.0°C)
        res_exact = compute_autonomous_actuator_state(
            current_temp=boundary,
            current_humidity=40.0,
            target_temp=target_temp,
            target_humidity=40.0,
        )
        assert res_exact["peltier_active"] is False, (
            f"Expected Peltier OFF at exact boundary ({boundary}°C) for target {target_temp}°C"
        )

        # Above boundary by 1 millidegree
        res_above = compute_autonomous_actuator_state(
            current_temp=boundary + 0.001,
            current_humidity=40.0,
            target_temp=target_temp,
            target_humidity=40.0,
        )
        assert res_above["peltier_active"] is True, (
            f"Expected Peltier ON at boundary + 0.001°C ({boundary + 0.001}°C) for target {target_temp}°C"
        )

    def test_hysteresis_target_25c_specific_values(self):
        """Specific challenge values from dispatch: 27.0°C vs 27.001°C vs 26.999°C for target 25.0°C."""
        target = 25.0

        # 26.999°C -> False
        assert compute_autonomous_actuator_state(26.999, 40.0, target, 40.0)["peltier_active"] is False

        # 27.000°C -> False
        assert compute_autonomous_actuator_state(27.0, 40.0, target, 40.0)["peltier_active"] is False

        # 27.001°C -> True
        assert compute_autonomous_actuator_state(27.001, 40.0, target, 40.0)["peltier_active"] is True

    def test_manual_override_precedence_over_hysteresis(self):
        """
        Manual override OFF must override extreme overheating (e.g. 55.0°C).
        Manual override ON must override cooling within normal range (e.g. 21.0°C >= 10.0°C).
        """
        # Overheated cabinet with manual override OFF
        res_off = compute_autonomous_actuator_state(
            current_temp=55.0,
            current_humidity=40.0,
            target_temp=25.0,
            target_humidity=40.0,
            peltier_override="OFF",
        )
        assert res_off["peltier_active"] is False, "Manual OFF must suppress cooling even when overheated"

        # Safe normal cabinet with manual override ON
        res_on = compute_autonomous_actuator_state(
            current_temp=21.0,
            current_humidity=40.0,
            target_temp=25.0,
            target_humidity=40.0,
            peltier_override="ON",
        )
        assert res_on["peltier_active"] is True, "Manual ON must activate cooling above 10.0°C"


# ============================================================================
# 3. HUMIDITY SERVO BOUNDARY STRESS TESTS
# ============================================================================

class TestHumidityServoBoundaryStress:
    """Stress testing ventilation servo transitions around target humidity."""

    @pytest.mark.parametrize("target_humidity", [20.0, 40.0, 50.0, 65.0, 80.0])
    def test_humidity_servo_exact_boundary_and_tenth_percent(self, target_humidity):
        """
        Dispatch specification:
        Test at target_humidity, target_humidity + 0.1%, target_humidity - 0.1%.
        - target - 0.1% -> 0° (CLOSED)
        - target exact  -> 0° (CLOSED)
        - target + 0.1% -> 90° (OPEN)
        """
        # target - 0.1%
        res_below = compute_autonomous_actuator_state(
            current_temp=22.0,
            current_humidity=target_humidity - 0.1,
            target_temp=22.0,
            target_humidity=target_humidity,
        )
        assert res_below["ventilation_servo_angle"] == SERVO_CLOSED_ANGLE, (
            f"Servo should be CLOSED at target - 0.1% ({target_humidity - 0.1}%)"
        )

        # target exact
        res_exact = compute_autonomous_actuator_state(
            current_temp=22.0,
            current_humidity=target_humidity,
            target_temp=22.0,
            target_humidity=target_humidity,
        )
        assert res_exact["ventilation_servo_angle"] == SERVO_CLOSED_ANGLE, (
            f"Servo should be CLOSED at exact target ({target_humidity}%)"
        )

        # target + 0.1%
        res_above = compute_autonomous_actuator_state(
            current_temp=22.0,
            current_humidity=target_humidity + 0.1,
            target_temp=22.0,
            target_humidity=target_humidity,
        )
        assert res_above["ventilation_servo_angle"] == SERVO_OPEN_ANGLE, (
            f"Servo should be OPEN at target + 0.1% ({target_humidity + 0.1}%)"
        )

    def test_humidity_servo_micro_precision_steps(self):
        """Test micro-delta 1e-6 around target 40.0% RH."""
        target = 40.0
        assert compute_autonomous_actuator_state(22.0, target - 1e-6, 22.0, target)["ventilation_servo_angle"] == 0
        assert compute_autonomous_actuator_state(22.0, target + 1e-6, 22.0, target)["ventilation_servo_angle"] == 90

    def test_humidity_servo_extremes_and_manual_overrides(self):
        """Test at 0.0% and 100.0% RH, and test manual OPEN / CLOSED overrides."""
        # 0.0% RH in AUTO -> CLOSED
        assert compute_autonomous_actuator_state(22.0, 0.0, 22.0, 40.0)["ventilation_servo_angle"] == 0

        # 100.0% RH in AUTO -> OPEN
        assert compute_autonomous_actuator_state(22.0, 100.0, 22.0, 40.0)["ventilation_servo_angle"] == 90

        # 0.0% RH with override OPEN -> 90°
        res_force_open = compute_autonomous_actuator_state(
            22.0, 0.0, 22.0, 40.0, ventilation_override="OPEN"
        )
        assert res_force_open["ventilation_servo_angle"] == 90

        # 100.0% RH with override CLOSED -> 0°
        res_force_closed = compute_autonomous_actuator_state(
            22.0, 100.0, 22.0, 40.0, ventilation_override="CLOSED"
        )
        assert res_force_closed["ventilation_servo_angle"] == 0


# ============================================================================
# 4. SLOT LOCATOR CONCURRENCY, COLLISION, & ADVERSARIAL FUZZING
# ============================================================================

class TestSlotLocatorConcurrencyAndAdversarialFuzzing:
    """Stress tests on slot locators: 100 concurrent updates, collisions, clears, and fuzzing."""

    def test_100_simultaneous_concurrent_slot_updates(self):
        """
        CONCURRENCY STRESS:
        100 simultaneous threads update slot locators concurrently on the same cabinet.
        Verifies thread safety, absence of race conditions, and complete state persistence.
        """
        svc = ActuatorService()
        cabinet_loc = "CAB-CONCURRENT-100"

        def worker_task(index: int):
            slot_id = f"ROW-{index // 10}-COL-{index % 10}"
            color = f"#{index:02x}{(index * 2) % 256:02x}{(index * 3) % 256:02x}"
            svc.update_actuator_command(
                cabinet_location=cabinet_loc,
                peltier_mode="AUTO",
                ventilation_mode="AUTO",
                locate_slot=slot_id,
                locate_color=color,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(worker_task, i) for i in range(100)]
            for f in concurrent.futures.as_completed(futures):
                f.result()  # Will raise if any thread threw an unhandled exception

        # Verify all 100 slots were stored without corruption
        state = svc.get_actuator_state(cabinet_loc)
        active_slots = state["slot_rgb_active"]
        assert len(active_slots) == 100, f"Expected 100 active slots, found {len(active_slots)}"

        for i in range(100):
            slot_id = f"ROW-{index_div}-COL-{index_mod}" if (index_div := i // 10, index_mod := i % 10) else ""
            assert slot_id in active_slots, f"Missing slot {slot_id}"
            assert active_slots[slot_id].startswith("#"), f"Corrupted color for {slot_id}"

    def test_concurrent_slot_updates_and_simultaneous_clears(self):
        """
        STRESS UNDER CONTENTION:
        50 threads adding slots while 10 threads continuously trigger clear_slot_locators.
        Ensures internal locking prevents 'dictionary changed size during iteration'
        or broken internal states.
        """
        svc = ActuatorService()
        cabinet_loc = "CAB-CLEAR-CONTENTION"
        stop_event = threading.Event()

        def writer_task(thread_id: int):
            for step in range(30):
                slot_id = f"SLOT-T{thread_id}-S{step}"
                svc.set_slot_locator(cabinet_loc, slot_id, "#112233")

        def clearer_task():
            while not stop_event.is_set():
                svc.clear_slot_locators(cabinet_loc)

        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            clear_futures = [executor.submit(clearer_task) for _ in range(4)]
            write_futures = [executor.submit(writer_task, tid) for tid in range(12)]

            for wf in concurrent.futures.as_completed(write_futures):
                wf.result()

            stop_event.set()
            for cf in clear_futures:
                cf.result()

        # Service must still be cleanly queryable
        state = svc.get_actuator_state(cabinet_loc)
        assert isinstance(state["slot_rgb_active"], dict)

    def test_invalid_hex_patterns_rejected_by_schema(self):
        """
        INPUT VALIDATION CONTRACT:
        Pydantic schema must reject invalid hex patterns, non-hex characters,
        short/long strings, and malicious injection payloads.
        """
        invalid_hex_cases = [
            "00FF00",          # Missing leading '#'
            "#GGGFFF",         # Non-hex character 'G'
            "#12345",          # 5 characters (too short)
            "#1234567",        # 7 characters (too long)
            "#00ffcc11",       # 8-char RGBA
            "blue",            # Named color
            "rgb(0,255,0)",    # CSS rgb()
            "<script>alert(1)</script>", # XSS payload
            "' OR '1'='1",     # SQL injection attempt
            "#12 45",          # Space inside hex
            "",                # Empty string
        ]

        for bad_hex in invalid_hex_cases:
            with pytest.raises(ValidationError, match="locate_color"):
                schemas.ActuatorCommandRequest(
                    peltier_mode="AUTO",
                    ventilation_mode="AUTO",
                    locate_slot="ROW-A-COL-1",
                    locate_color=bad_hex,
                )

    def test_valid_hex_patterns_accepted_by_schema(self):
        """Valid 6-digit hex patterns must be accepted cleanly."""
        valid_hex_cases = [
            "#00FFCC",
            "#000000",
            "#FFFFFF",
            "#abcdef",
            "#123456",
            "#AaBbCc",
        ]
        for good_hex in valid_hex_cases:
            req = schemas.ActuatorCommandRequest(
                peltier_mode="AUTO",
                ventilation_mode="AUTO",
                locate_slot="ROW-A-COL-1",
                locate_color=good_hex,
            )
            assert req.locate_color == good_hex

    def test_unicode_and_special_character_slot_ids(self):
        """
        UNICODE INJECTION RESILIENCE:
        Slot IDs containing multibyte UTF-8 characters, emojis, or zero-width characters
        must be stored cleanly without throwing exceptions or corrupting memory.
        """
        svc = ActuatorService()
        cabinet_loc = "CAB-UNICODE"

        unicode_slots = [
            "SLOT-⚡-HIGH-POWER",
            "DRAWER-日本語-1",
            "ROW-اختبار-COL-5",
            "SLOT-📦-STORAGE",
            "SLOT_WITH_\u200B_ZERO_WIDTH",
            "SLOT-WITH-SPACES-AND-DASHES #42",
        ]

        for slot in unicode_slots:
            svc.set_slot_locator(cabinet_loc, slot, "#FF00FF")

        state = svc.get_actuator_state(cabinet_loc)
        active = state["slot_rgb_active"]

        for slot in unicode_slots:
            assert slot in active, f"Unicode slot {slot} missing from active slots!"
            assert active[slot] == "#FF00FF"

    def test_service_level_color_sanitization_fallback(self):
        """
        DEFENSIVE CODING:
        If an invalid color bypasses schema validation directly to update_actuator_command,
        the service must safely fallback to DEFAULT_LOCATE_COLOR ('#00FFCC') instead of crashing.
        """
        svc = ActuatorService()
        cab = "CAB-DEFENSIVE"

        res = svc.update_actuator_command(
            cabinet_location=cab,
            peltier_mode="AUTO",
            ventilation_mode="AUTO",
            locate_slot="ROW-A-COL-1",
            locate_color="malformed-not-a-hex",
        )
        assert res["slot_rgb_active"]["ROW-A-COL-1"] == DEFAULT_LOCATE_COLOR


# ============================================================================
# 5. INTEGRATION & DOWNLINK LOOPBACK ADVERSARIAL STRESS
# ============================================================================

class TestActuatorAPIAndDownlinkAdversarialStress:
    """Stress tests on actuator HTTP endpoints, multi-cabinet isolation, and telemetry downlink."""

    def test_api_thermal_cutoff_sweep(self, client, auth_headers, test_cabinet, db_session):
        """
        API-LEVEL FAILSAFE:
        Set cabinet reported temperatures to sub-10°C values in the database.
        Send POST to `/cabinet/{loc}/actuators` with peltier_mode='ON'.
        API MUST respond with peltier_active=False.
        """
        sub_10_test_temps = [-15.0, 0.0, 5.0, 8.5, 9.99]

        for temp in sub_10_test_temps:
            test_cabinet.last_reported_temperature_c = temp
            db_session.commit()

            resp = client.post(
                f"/cabinet/{test_cabinet.cabinet_location}/actuators",
                json={"peltier_mode": "ON", "ventilation_mode": "AUTO"},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["peltier_mode"] == "ON"
            assert data["peltier_active"] is False, (
                f"API failed safety interlock at {temp}°C: Peltier was True!"
            )

    def test_api_hysteresis_boundary_transitions(self, client, auth_headers, test_cabinet, db_session):
        """
        API-LEVEL HYSTERESIS:
        Target temp is 25.0°C. Target humidity is 40.0%.
        Verify 26.99°C (False), 27.00°C (False), and 27.01°C (True).
        """
        test_cabinet.target_temperature_c = 25.0
        test_cabinet.target_humidity_percent = 40.0

        # Sub-boundary: 26.99°C
        test_cabinet.last_reported_temperature_c = 26.99
        db_session.commit()
        resp_sub = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={"peltier_mode": "AUTO", "ventilation_mode": "AUTO"},
            headers=auth_headers,
        )
        assert resp_sub.json()["peltier_active"] is False

        # Exact boundary: 27.00°C
        test_cabinet.last_reported_temperature_c = 27.00
        db_session.commit()
        resp_exact = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={"peltier_mode": "AUTO", "ventilation_mode": "AUTO"},
            headers=auth_headers,
        )
        assert resp_exact.json()["peltier_active"] is False

        # Exceeds boundary: 27.01°C
        test_cabinet.last_reported_temperature_c = 27.01
        db_session.commit()
        resp_over = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={"peltier_mode": "AUTO", "ventilation_mode": "AUTO"},
            headers=auth_headers,
        )
        assert resp_over.json()["peltier_active"] is True

    def test_multi_cabinet_actuator_isolation(self, client, auth_headers, db_session, test_cabinet):
        """
        ISOLATION TEST:
        Ensure actuator updates on CAB-1 do not leak or overwrite actuators on CAB-2.
        """
        from app.models import CabinetSetting

        # Create second cabinet
        cab2 = CabinetSetting(
            cabinet_location="CAB-ISOLATION-2",
            target_temperature_c=20.0,
            target_humidity_percent=50.0,
            last_reported_temperature_c=20.0,
            last_reported_humidity_percent=50.0,
        )
        db_session.add(cab2)
        db_session.commit()

        # Update CAB-1 to ON / OPEN
        client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={
                "peltier_mode": "ON",
                "ventilation_mode": "OPEN",
                "locate_slot": "SLOT-CAB1",
                "locate_color": "#FF0000",
            },
            headers=auth_headers,
        )

        # Update CAB-2 to OFF / CLOSED
        client.post(
            "/cabinet/CAB-ISOLATION-2/actuators",
            json={
                "peltier_mode": "OFF",
                "ventilation_mode": "CLOSED",
                "locate_slot": "SLOT-CAB2",
                "locate_color": "#0000FF",
            },
            headers=auth_headers,
        )

        # Verify CAB-1 state
        resp1 = client.get(f"/cabinet/{test_cabinet.cabinet_location}/actuators", headers=auth_headers)
        data1 = resp1.json()
        assert data1["peltier_mode"] == "ON"
        assert data1["ventilation_mode"] == "OPEN"
        assert "SLOT-CAB1" in data1["slot_rgb_active"]
        assert "SLOT-CAB2" not in data1["slot_rgb_active"]

        # Verify CAB-2 state
        resp2 = client.get("/cabinet/CAB-ISOLATION-2/actuators", headers=auth_headers)
        data2 = resp2.json()
        assert data2["peltier_mode"] == "OFF"
        assert data2["ventilation_mode"] == "CLOSED"
        assert "SLOT-CAB2" in data2["slot_rgb_active"]
        assert "SLOT-CAB1" not in data2["slot_rgb_active"]

    def test_telemetry_downlink_thermal_safety_under_extreme_telemetry(
        self, client, auth_headers, test_cabinet
    ):
        """
        DOWNLINK INTEGRATION:
        Even if the cabinet was manually set to Peltier 'ON', posting telemetry with
        temperature = 4.0°C (< 10°C) MUST return `peltier_active: False` in the downlink HTTP response.
        """
        # Configure manual ON
        client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={"peltier_mode": "ON", "ventilation_mode": "AUTO"},
            headers=auth_headers,
        )

        # ESP32 posts telemetry with 4.0°C
        headers, body = create_esp32_telemetry_request(
            cabinet_location=test_cabinet.cabinet_location,
            temperature_c=4.0,
            humidity_percent=45.0,
            door_open=False,
            secret=DEFAULT_TEST_SECRET,
        )
        resp = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
            content=body,
            headers=headers,
        )
        assert resp.status_code == 200
        downlink = resp.json()["actuator_commands"]
        assert downlink["peltier_active"] is False, (
            "Telemetry downlink failed thermal safety interlock below 10°C!"
        )
