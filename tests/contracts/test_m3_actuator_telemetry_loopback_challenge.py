"""
Tier 3 Empirical Integration Challenge Suite for Milestone 3:
Bidirectional Two-Way Actuator Controls, Real-Time WebSocket Telemetry Broadcast,
and Downlink Hysteresis Loopback.

Empirically challenges:
1. Telemetry Downlink Closed-Loop Hysteresis & Failsafe Boundary Dynamics (temperatures above, at, below threshold, < 10°C interlock)
2. Real-Time WebSocket Telemetry Fanout & Synchronized Actuator State Matching
3. Manual Actuator Mode Overrides & Multi-Cycle Downlink Loopback Verification
4. Strict Authentication & Cryptographic Gate Enforcement (401 on unauthenticated or tampered requests)
5. Multi-Cabinet Environmental & Actuator State Encapsulation / Leak Prevention
6. Slot RGB Locator LED Accumulation, Persistence Across Telemetry Ingestion, and Cleardown
7. Input Validation & Fault Tolerance on Malformed Modes and Colors
"""

import pytest
from datetime import datetime
from app import models, auth
from app.services.actuator_service import actuator_service
from tests.helpers.hmac_helper import create_esp32_telemetry_request, DEFAULT_TEST_SECRET


@pytest.fixture(autouse=True)
def reset_actuators_state():
    """Ensure clean actuator state and auth replay cache before and after each challenge test."""
    actuator_service.reset()
    auth.seen_signatures.clear()
    auth._signature_timestamps.clear()
    yield
    actuator_service.reset()
    auth.seen_signatures.clear()
    auth._signature_timestamps.clear()


@pytest.fixture
def multi_cabinet_fixture(db_session):
    """
    Sets up two distinct cabinets for state isolation testing:
    - CAB-ALPHA: Target 22.0°C, 45.0% humidity
    - CAB-BETA:  Target 18.0°C, 35.0% humidity
    """
    cab_alpha = models.CabinetSetting(
        cabinet_location="CAB-ALPHA",
        target_temperature_c=22.0,
        target_humidity_percent=45.0,
        last_reported_temperature_c=22.0,
        last_reported_humidity_percent=45.0,
        last_reading_at=datetime.utcnow(),
    )
    cab_beta = models.CabinetSetting(
        cabinet_location="CAB-BETA",
        target_temperature_c=18.0,
        target_humidity_percent=35.0,
        last_reported_temperature_c=18.0,
        last_reported_humidity_percent=35.0,
        last_reading_at=datetime.utcnow(),
    )
    db_session.add_all([cab_alpha, cab_beta])
    db_session.commit()
    db_session.refresh(cab_alpha)
    db_session.refresh(cab_beta)
    return {"alpha": cab_alpha, "beta": cab_beta}


class TestTelemetryDownlinkHysteresisAndThresholds:
    """
    Empirically challenges autonomous closed-loop hysteresis control over HTTP telemetry downlink.
    Evaluates exact boundary transitions and the mandatory < 10.0°C thermal cutoff.
    """

    def test_telemetry_downlink_below_cooling_threshold(self, client, test_cabinet):
        """
        When temperature is within normal setpoint tolerance (23.5°C <= 22.0 + 2.0°C),
        Peltier cooling MUST remain deactivated (False) in the HTTP response downlink.
        """
        headers, body = create_esp32_telemetry_request(
            cabinet_location=test_cabinet.cabinet_location,
            temperature_c=23.5,
            humidity_percent=40.0,
            door_open=False,
            secret=DEFAULT_TEST_SECRET,
        )
        resp = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
            content=body,
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "actuator_commands" in data
        actuators = data["actuator_commands"]
        assert actuators["peltier_active"] is False
        assert actuators["ventilation_servo_angle"] == 0

    def test_telemetry_downlink_at_exact_cooling_boundary(self, client, test_cabinet):
        """
        Boundary condition: Target 22.0°C + 2.0°C = 24.0°C.
        The hysteresis rule is strictly `temp > (target + 2.0)`.
        At exactly 24.0°C, Peltier cooling MUST remain False (no false triggers on boundary).
        """
        headers, body = create_esp32_telemetry_request(
            cabinet_location=test_cabinet.cabinet_location,
            temperature_c=24.0,
            humidity_percent=40.0,
            door_open=False,
            secret=DEFAULT_TEST_SECRET,
        )
        resp = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
            content=body,
            headers=headers,
        )
        assert resp.status_code == 200
        actuators = resp.json()["actuator_commands"]
        assert actuators["peltier_active"] is False

    def test_telemetry_downlink_above_cooling_threshold(self, client, test_cabinet):
        """
        When temperature exceeds target + 2.0°C (24.5°C > 24.0°C),
        autonomous closed-loop logic MUST activate Peltier cooling in the HTTP downlink.
        """
        headers, body = create_esp32_telemetry_request(
            cabinet_location=test_cabinet.cabinet_location,
            temperature_c=24.5,
            humidity_percent=40.0,
            door_open=False,
            secret=DEFAULT_TEST_SECRET,
        )
        resp = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
            content=body,
            headers=headers,
        )
        assert resp.status_code == 200
        actuators = resp.json()["actuator_commands"]
        assert actuators["peltier_active"] is True
        assert actuators["ventilation_servo_angle"] == 0

    def test_telemetry_downlink_thermal_safety_interlock_cutoff(self, client, test_cabinet):
        """
        THERMAL SAFETY INTERLOCK:
        When cabinet temperature drops below 10.0°C (e.g. 9.5°C), Peltier cooling
        MUST be deactivated regardless of target setpoint to prevent freezing hazard.
        """
        headers, body = create_esp32_telemetry_request(
            cabinet_location=test_cabinet.cabinet_location,
            temperature_c=9.5,
            humidity_percent=40.0,
            door_open=False,
            secret=DEFAULT_TEST_SECRET,
        )
        resp = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
            content=body,
            headers=headers,
        )
        assert resp.status_code == 200
        actuators = resp.json()["actuator_commands"]
        assert actuators["peltier_active"] is False, "Thermal safety interlock must force Peltier OFF below 10°C!"

    def test_telemetry_downlink_humidity_boundary(self, client, test_cabinet):
        """
        Ventilation servo angle boundary testing:
        Target humidity is 45.0%.
        - At 45.0%: Servo angle MUST be 0° (closed).
        - At 45.1%: Servo angle MUST be 90° (open for dehumidification).
        """
        # Step 1: At exact target (45.0%)
        headers1, body1 = create_esp32_telemetry_request(
            cabinet_location=test_cabinet.cabinet_location,
            temperature_c=22.0,
            humidity_percent=45.0,
            door_open=False,
            secret=DEFAULT_TEST_SECRET,
        )
        resp1 = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
            content=body1,
            headers=headers1,
        )
        assert resp1.status_code == 200
        assert resp1.json()["actuator_commands"]["ventilation_servo_angle"] == 0

        # Step 2: Slightly above target (45.5%)
        headers2, body2 = create_esp32_telemetry_request(
            cabinet_location=test_cabinet.cabinet_location,
            temperature_c=22.0,
            humidity_percent=45.5,
            door_open=False,
            secret=DEFAULT_TEST_SECRET,
        )
        resp2 = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
            content=body2,
            headers=headers2,
        )
        assert resp2.status_code == 200
        assert resp2.json()["actuator_commands"]["ventilation_servo_angle"] == 90


class TestWebSocketTelemetryBroadcastAndFanout:
    """
    Empirically challenges real-time WebSocket fan-out and synchronicity with the HTTP downlink.
    """

    def test_websocket_broadcast_actuators_matches_http_downlink(self, client, test_cabinet):
        """
        When ESP32 posts telemetry, the WebSocket frame broadcast to /ws/telemetry
        must contain an `actuators` object that matches the HTTP response `actuator_commands` downlink.
        """
        with client.websocket_connect("/ws/telemetry") as ws:
            headers, body = create_esp32_telemetry_request(
                cabinet_location=test_cabinet.cabinet_location,
                temperature_c=26.0,
                humidity_percent=55.0,
                door_open=True,
                secret=DEFAULT_TEST_SECRET,
            )
            resp = client.post(
                f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
                content=body,
                headers=headers,
            )
            assert resp.status_code == 200
            http_downlink = resp.json()["actuator_commands"]

            ws_frame = ws.receive_json()
            assert ws_frame["type"] == "TELEMETRY_UPDATE"
            assert ws_frame["cabinet_location"] == test_cabinet.cabinet_location
            assert "actuators" in ws_frame

            ws_actuators = ws_frame["actuators"]
            assert ws_actuators["peltier_active"] == http_downlink["peltier_active"]
            assert ws_actuators["ventilation_servo_angle"] == http_downlink["ventilation_servo_angle"]
            assert ws_actuators["slot_rgb_active"] == http_downlink["slot_rgb_active"]
            assert ws_actuators["peltier_active"] is True
            assert ws_actuators["ventilation_servo_angle"] == 90

    def test_websocket_multi_client_fanout_synchronization(self, client, test_cabinet):
        """
        Multiple connected WebSocket subscribers simultaneously receive identical
        actuator and telemetry payloads upon telemetry ingestion.
        """
        with client.websocket_connect("/ws/telemetry") as ws1:
            with client.websocket_connect("/ws/telemetry") as ws2:
                with client.websocket_connect("/ws/telemetry") as ws3:
                    headers, body = create_esp32_telemetry_request(
                        cabinet_location=test_cabinet.cabinet_location,
                        temperature_c=21.0,
                        humidity_percent=38.0,
                        door_open=False,
                        secret=DEFAULT_TEST_SECRET,
                    )
                    resp = client.post(
                        f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
                        content=body,
                        headers=headers,
                    )
                    assert resp.status_code == 200

                    f1 = ws1.receive_json()
                    f2 = ws2.receive_json()
                    f3 = ws3.receive_json()

                    for frame in (f1, f2, f3):
                        assert frame["type"] == "TELEMETRY_UPDATE"
                        assert frame["actuators"]["peltier_active"] is False
                        assert frame["actuators"]["ventilation_servo_angle"] == 0


class TestManualOverridesAndSubsequentTelemetryDownlink:
    """
    Empirically challenges manual actuator overrides configured via POST /cabinet/{loc}/actuators
    and verifies that subsequent ESP32 telemetry downlink cycles accurately reflect the overrides.
    """

    def test_manual_peltier_on_override_persists_in_telemetry_downlink(
        self, client, auth_headers, test_cabinet
    ):
        """
        1. Set manual Peltier mode to ON via dashboard POST /cabinet/{loc}/actuators.
        2. Post normal-temperature telemetry (21.0°C <= 24.0°C, which would be OFF in AUTO).
        3. Telemetry downlink and WebSocket frame MUST report peltier_active=True due to manual override.
        """
        # Step 1: Set override ON
        override_resp = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={"peltier_mode": "ON", "ventilation_mode": "AUTO"},
            headers=auth_headers,
        )
        assert override_resp.status_code == 200
        assert override_resp.json()["peltier_active"] is True

        # Step 2 & 3: Post telemetry and check downlink
        with client.websocket_connect("/ws/telemetry") as ws:
            headers, body = create_esp32_telemetry_request(
                cabinet_location=test_cabinet.cabinet_location,
                temperature_c=21.0,
                humidity_percent=40.0,
                secret=DEFAULT_TEST_SECRET,
            )
            telem_resp = client.post(
                f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
                content=body,
                headers=headers,
            )
            assert telem_resp.status_code == 200
            downlink = telem_resp.json()["actuator_commands"]
            assert downlink["peltier_mode"] == "ON"
            assert downlink["peltier_active"] is True, "Manual ON override must keep Peltier active at 21°C"

            ws_frame = ws.receive_json()
            assert ws_frame["actuators"]["peltier_active"] is True

    def test_manual_peltier_on_overridden_by_failsafe_interlock_under_10c(
        self, client, auth_headers, test_cabinet
    ):
        """
        CRITICAL SAFETY VERIFICATION:
        Even when manual override is ON, if live telemetry arrives with temp < 10.0°C (e.g. 7.2°C),
        the thermal safety interlock MUST override manual mode and set peltier_active=False.
        """
        # 1. Force ON via dashboard
        client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={"peltier_mode": "ON", "ventilation_mode": "AUTO"},
            headers=auth_headers,
        )

        # 2. ESP32 reports sub-zero or low temperature (7.2°C)
        headers, body = create_esp32_telemetry_request(
            cabinet_location=test_cabinet.cabinet_location,
            temperature_c=7.2,
            humidity_percent=40.0,
            secret=DEFAULT_TEST_SECRET,
        )
        resp = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
            content=body,
            headers=headers,
        )
        assert resp.status_code == 200
        downlink = resp.json()["actuator_commands"]
        assert downlink["peltier_mode"] == "ON"
        assert downlink["peltier_active"] is False, "Failsafe interlock must override manual ON below 10°C!"

    def test_manual_peltier_off_override_blocks_cooling_during_overheat(
        self, client, auth_headers, test_cabinet
    ):
        """
        When manual Peltier override is OFF, overheating telemetry (38.0°C) MUST NOT
        activate Peltier cooling.
        """
        client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={"peltier_mode": "OFF", "ventilation_mode": "AUTO"},
            headers=auth_headers,
        )

        headers, body = create_esp32_telemetry_request(
            cabinet_location=test_cabinet.cabinet_location,
            temperature_c=38.0,
            humidity_percent=40.0,
            secret=DEFAULT_TEST_SECRET,
        )
        resp = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
            content=body,
            headers=headers,
        )
        assert resp.status_code == 200
        downlink = resp.json()["actuator_commands"]
        assert downlink["peltier_mode"] == "OFF"
        assert downlink["peltier_active"] is False

    def test_manual_ventilation_overrides_reflect_in_downlink(
        self, client, auth_headers, test_cabinet
    ):
        """
        Tests manual ventilation overrides (OPEN 90° and CLOSED 0°) persisting into telemetry downlink.
        """
        # 1. Manual OPEN during low humidity (20%)
        client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={"peltier_mode": "AUTO", "ventilation_mode": "OPEN"},
            headers=auth_headers,
        )
        headers1, body1 = create_esp32_telemetry_request(
            cabinet_location=test_cabinet.cabinet_location,
            temperature_c=22.0,
            humidity_percent=20.0,
            secret=DEFAULT_TEST_SECRET,
        )
        resp1 = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
            content=body1,
            headers=headers1,
        )
        assert resp1.status_code == 200
        assert resp1.json()["actuator_commands"]["ventilation_servo_angle"] == 90

        # 2. Manual CLOSED during high humidity (85%)
        client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={"peltier_mode": "AUTO", "ventilation_mode": "CLOSED"},
            headers=auth_headers,
        )
        headers2, body2 = create_esp32_telemetry_request(
            cabinet_location=test_cabinet.cabinet_location,
            temperature_c=22.0,
            humidity_percent=85.0,
            secret=DEFAULT_TEST_SECRET,
        )
        resp2 = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
            content=body2,
            headers=headers2,
        )
        assert resp2.status_code == 200
        assert resp2.json()["actuator_commands"]["ventilation_servo_angle"] == 0

    def test_slot_locator_led_persistence_and_clearing(
        self, client, auth_headers, test_cabinet
    ):
        """
        Configuring slot RGB locator LEDs propagates into telemetry downlink responses
        and clears cleanly when requested.
        """
        # 1. Set locator LED for slot ROW-A-COL-1
        resp_act = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={
                "peltier_mode": "AUTO",
                "ventilation_mode": "AUTO",
                "locate_slot": "ROW-A-COL-1",
                "locate_color": "#00FFCC",
            },
            headers=auth_headers,
        )
        assert resp_act.status_code == 200
        assert resp_act.json()["slot_rgb_active"] == {"ROW-A-COL-1": "#00FFCC"}

        # 2. Add second slot locator
        resp_act2 = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={
                "peltier_mode": "AUTO",
                "ventilation_mode": "AUTO",
                "locate_slot": "ROW-B-COL-5",
                "locate_color": "#FF0055",
            },
            headers=auth_headers,
        )
        assert resp_act2.status_code == 200
        slots = resp_act2.json()["slot_rgb_active"]
        assert slots["ROW-A-COL-1"] == "#00FFCC"
        assert slots["ROW-B-COL-5"] == "#FF0055"

        # 3. Post telemetry and assert slot locators are included in downlink
        headers, body = create_esp32_telemetry_request(
            cabinet_location=test_cabinet.cabinet_location,
            temperature_c=22.0,
            humidity_percent=40.0,
            secret=DEFAULT_TEST_SECRET,
        )
        telem_resp = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
            content=body,
            headers=headers,
        )
        assert telem_resp.status_code == 200
        downlink_slots = telem_resp.json()["actuator_commands"]["slot_rgb_active"]
        assert downlink_slots["ROW-A-COL-1"] == "#00FFCC"
        assert downlink_slots["ROW-B-COL-5"] == "#FF0055"

        # 4. Clear slot locators via DELETE endpoint
        del_resp = client.delete(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators/slots",
            headers=auth_headers,
        )
        assert del_resp.status_code == 200
        assert del_resp.json()["slot_rgb_active"] == {}

        # 5. Subsequent telemetry downlink has empty slot_rgb_active
        headers2, body2 = create_esp32_telemetry_request(
            cabinet_location=test_cabinet.cabinet_location,
            temperature_c=22.0,
            humidity_percent=40.0,
            secret=DEFAULT_TEST_SECRET,
            timestamp_offset=2,
        )
        telem_resp2 = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
            content=body2,
            headers=headers2,
        )
        assert telem_resp2.status_code == 200
        assert telem_resp2.json()["actuator_commands"]["slot_rgb_active"] == {}

    def test_reverting_to_auto_restores_autonomous_closed_loop(
        self, client, auth_headers, test_cabinet
    ):
        """
        Transitioning from manual override back to AUTO immediately restores
        closed-loop hysteresis evaluation.
        """
        # Step 1: Force Peltier ON
        client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={"peltier_mode": "ON", "ventilation_mode": "OPEN"},
            headers=auth_headers,
        )

        # Step 2: Revert to AUTO
        revert_resp = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={"peltier_mode": "AUTO", "ventilation_mode": "AUTO"},
            headers=auth_headers,
        )
        assert revert_resp.status_code == 200
        assert revert_resp.json()["peltier_mode"] == "AUTO"

        # Step 3: Normal telemetry (22.0°C <= 24.0°C, 40% <= 45%) -> Peltier OFF, servo 0°
        headers, body = create_esp32_telemetry_request(
            cabinet_location=test_cabinet.cabinet_location,
            temperature_c=22.0,
            humidity_percent=40.0,
            secret=DEFAULT_TEST_SECRET,
        )
        telem_resp = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
            content=body,
            headers=headers,
        )
        assert telem_resp.status_code == 200
        actuators = telem_resp.json()["actuator_commands"]
        assert actuators["peltier_active"] is False
        assert actuators["ventilation_servo_angle"] == 0


class TestActuatorRouteAuthenticationAndSecurityGates:
    """
    Empirically verifies that all actuator control routes and telemetry endpoints
    strictly enforce authentication gates, rejecting unauthenticated or forged requests.
    """

    def test_unauthenticated_actuator_routes_return_401(self, client, test_cabinet):
        """All actuator endpoints require valid JWT authentication."""
        # GET without auth
        resp_get = client.get(f"/cabinet/{test_cabinet.cabinet_location}/actuators")
        assert resp_get.status_code == 401

        # POST without auth
        resp_post = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={"peltier_mode": "ON", "ventilation_mode": "OPEN"},
        )
        assert resp_post.status_code == 401

        # DELETE without auth
        resp_del = client.delete(f"/cabinet/{test_cabinet.cabinet_location}/actuators/slots")
        assert resp_del.status_code == 401

    def test_forged_or_invalid_jwt_returns_401(self, client, test_cabinet):
        """Providing an invalid Bearer token returns 401 Unauthorized."""
        bad_headers = {"Authorization": "Bearer forged.invalid.token"}
        resp = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={"peltier_mode": "ON", "ventilation_mode": "OPEN"},
            headers=bad_headers,
        )
        assert resp.status_code == 401

    def test_forged_esp32_hmac_signature_rejected_with_401(self, client, test_cabinet):
        """
        Telemetry posts with invalid/tampered HMAC signature are rejected with 401 Unauthorized.
        """
        headers, body = create_esp32_telemetry_request(
            cabinet_location=test_cabinet.cabinet_location,
            temperature_c=25.0,
            humidity_percent=40.0,
            secret=DEFAULT_TEST_SECRET,
            tamper_signature=True,
        )
        resp = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
            content=body,
            headers=headers,
        )
        assert resp.status_code == 401

    def test_replayed_esp32_telemetry_rejected_with_401(self, client, test_cabinet):
        """
        Telemetry posts with stale timestamps (beyond 300s anti-replay window) are rejected with 401.
        """
        headers, body = create_esp32_telemetry_request(
            cabinet_location=test_cabinet.cabinet_location,
            temperature_c=25.0,
            humidity_percent=40.0,
            secret=DEFAULT_TEST_SECRET,
            timestamp_offset=-3600,  # 1 hour in the past
        )
        resp = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
            content=body,
            headers=headers,
        )
        assert resp.status_code == 401


class TestMultiCabinetStateIsolation:
    """
    Empirically verifies that actuator states, manual overrides, and slot locators
    are strictly isolated between distinct cabinet locations.
    """

    def test_state_isolation_between_cabinets(self, client, auth_headers, multi_cabinet_fixture):
        """
        Setting overrides on CAB-ALPHA must not leak to CAB-BETA.
        """
        cab_alpha = multi_cabinet_fixture["alpha"]
        cab_beta = multi_cabinet_fixture["beta"]

        # 1. Override CAB-ALPHA: Peltier ON, slot locator SLOT-ALPHA-1 = #00FF00
        client.post(
            f"/cabinet/{cab_alpha.cabinet_location}/actuators",
            json={
                "peltier_mode": "ON",
                "ventilation_mode": "OPEN",
                "locate_slot": "SLOT-ALPHA-1",
                "locate_color": "#00FF00",
            },
            headers=auth_headers,
        )

        # 2. Check CAB-BETA: must remain default AUTO and empty slots
        beta_resp = client.get(
            f"/cabinet/{cab_beta.cabinet_location}/actuators",
            headers=auth_headers,
        )
        assert beta_resp.status_code == 200
        beta_data = beta_resp.json()
        assert beta_data["peltier_mode"] == "AUTO"
        assert beta_data["ventilation_mode"] == "AUTO"
        assert beta_data["slot_rgb_active"] == {}

        # 3. Post telemetry to CAB-BETA: downlink must NOT contain CAB-ALPHA's locators or modes
        headers_b, body_b = create_esp32_telemetry_request(
            cabinet_location=cab_beta.cabinet_location,
            temperature_c=18.0,  # normal for beta (target 18.0)
            humidity_percent=30.0,
            secret=DEFAULT_TEST_SECRET,
        )
        telem_b = client.post(
            f"/cabinet/{cab_beta.cabinet_location}/telemetry",
            content=body_b,
            headers=headers_b,
        )
        assert telem_b.status_code == 200
        b_downlink = telem_b.json()["actuator_commands"]
        assert b_downlink["peltier_mode"] == "AUTO"
        assert b_downlink["peltier_active"] is False
        assert b_downlink["slot_rgb_active"] == {}

        # 4. Post telemetry to CAB-ALPHA: downlink reflects CAB-ALPHA's ON override
        headers_a, body_a = create_esp32_telemetry_request(
            cabinet_location=cab_alpha.cabinet_location,
            temperature_c=22.0,
            humidity_percent=40.0,
            secret=DEFAULT_TEST_SECRET,
        )
        telem_a = client.post(
            f"/cabinet/{cab_alpha.cabinet_location}/telemetry",
            content=body_a,
            headers=headers_a,
        )
        assert telem_a.status_code == 200
        a_downlink = telem_a.json()["actuator_commands"]
        assert a_downlink["peltier_mode"] == "ON"
        assert a_downlink["peltier_active"] is True
        assert a_downlink["slot_rgb_active"] == {"SLOT-ALPHA-1": "#00FF00"}


class TestInputValidationAndEdgeCases:
    """
    Stress-tests schema validation, boundary regex patterns, and invalid endpoints.
    """

    def test_nonexistent_cabinet_returns_404(self, client, auth_headers):
        """Querying or updating an unconfigured cabinet returns 404 Not Found."""
        resp = client.post(
            "/cabinet/CAB-NONEXISTENT/actuators",
            json={"peltier_mode": "AUTO", "ventilation_mode": "AUTO"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.parametrize("invalid_peltier_mode", ["auto", "on", "off", "COOL", "MAX", "", "1"])
    def test_invalid_peltier_mode_returns_422(self, client, auth_headers, test_cabinet, invalid_peltier_mode):
        """Lowercase or arbitrary strings for peltier_mode must return 422 Unprocessable Entity."""
        resp = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={"peltier_mode": invalid_peltier_mode, "ventilation_mode": "AUTO"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.parametrize("invalid_vent_mode", ["open", "closed", "auto", "FAN", "90", ""])
    def test_invalid_ventilation_mode_returns_422(self, client, auth_headers, test_cabinet, invalid_vent_mode):
        """Lowercase or arbitrary strings for ventilation_mode must return 422 Unprocessable Entity."""
        resp = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={"peltier_mode": "AUTO", "ventilation_mode": invalid_vent_mode},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.parametrize("invalid_color", ["#FFF", "#GGGGGG", "red", "00FFCC", "#1234567", "#12345"])
    def test_invalid_hex_color_returns_422(self, client, auth_headers, test_cabinet, invalid_color):
        """Colors that do not match ^#([A-Fa-f0-9]{6})$ must return 422."""
        resp = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={
                "peltier_mode": "AUTO",
                "ventilation_mode": "AUTO",
                "locate_slot": "ROW-A-COL-1",
                "locate_color": invalid_color,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_clear_slots_flag_in_post_payload(self, client, auth_headers, test_cabinet):
        """Sending clear_slots=True in POST /cabinet/{loc}/actuators clears previously set slots."""
        # 1. Set a slot
        client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={
                "peltier_mode": "AUTO",
                "ventilation_mode": "AUTO",
                "locate_slot": "ROW-C-COL-3",
                "locate_color": "#AABBCC",
            },
            headers=auth_headers,
        )

        # 2. Post with clear_slots=True
        resp = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={
                "peltier_mode": "AUTO",
                "ventilation_mode": "AUTO",
                "clear_slots": True,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["slot_rgb_active"] == {}
