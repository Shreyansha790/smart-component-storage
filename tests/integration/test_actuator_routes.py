"""
Tier 2 Integration Tests: Actuator Control Endpoints & Bidirectional Loopback.

Derivation Source: ORIGINAL_REQUEST § R4 & PROJECT.md § Feature 13-16 / Interface Contracts:
- POST /cabinet/{cabinet_location}/actuators: Mode overrides, slot locators, WebSocket fanout
- GET /cabinet/{cabinet_location}/actuators: Query instantaneous actuator states
- DELETE /cabinet/{cabinet_location}/actuators/slots: Clear slot locators
- Telemetry downlink integration returning dynamic actuator commands
"""

import pytest
from app import models
from app.services.actuator_service import actuator_service
from tests.helpers.hmac_helper import create_esp32_telemetry_request, DEFAULT_TEST_SECRET


@pytest.fixture(autouse=True)
def reset_actuators():
    """Ensure clean actuator state before each test run."""
    actuator_service.reset()
    yield
    actuator_service.reset()


class TestActuatorRouteAuthentication:
    """Verifies that actuator endpoints strictly enforce authentication."""

    def test_unauthenticated_requests_return_401(self, client, test_cabinet):
        """All actuator endpoints require valid JWT authentication."""
        # GET
        resp_get = client.get(f"/cabinet/{test_cabinet.cabinet_location}/actuators")
        assert resp_get.status_code == 401

        # POST
        resp_post = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={"peltier_mode": "ON", "ventilation_mode": "OPEN"},
        )
        assert resp_post.status_code == 401

        # DELETE
        resp_del = client.delete(f"/cabinet/{test_cabinet.cabinet_location}/actuators/slots")
        assert resp_del.status_code == 401


class TestActuatorRouteValidation:
    """Verifies input validation and 404 handling."""

    def test_nonexistent_cabinet_returns_404(self, client, auth_headers):
        """Accessing or modifying actuators for an unknown cabinet returns 404 Not Found."""
        resp_get = client.get("/cabinet/CAB-GHOST-404/actuators", headers=auth_headers)
        assert resp_get.status_code == 404
        assert "not found" in resp_get.json()["detail"].lower()

        resp_post = client.post(
            "/cabinet/CAB-GHOST-404/actuators",
            json={"peltier_mode": "AUTO", "ventilation_mode": "AUTO"},
            headers=auth_headers,
        )
        assert resp_post.status_code == 404

        resp_del = client.delete("/cabinet/CAB-GHOST-404/actuators/slots", headers=auth_headers)
        assert resp_del.status_code == 404

    def test_invalid_actuator_modes_and_colors_return_422(self, client, auth_headers, test_cabinet):
        """Invalid enum modes or invalid hex colors must trigger 422 Unprocessable Entity."""
        # Invalid peltier_mode
        resp1 = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={"peltier_mode": "FREEZE", "ventilation_mode": "AUTO"},
            headers=auth_headers,
        )
        assert resp1.status_code == 422

        # Invalid ventilation_mode
        resp2 = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={"peltier_mode": "AUTO", "ventilation_mode": "BLOW"},
            headers=auth_headers,
        )
        assert resp2.status_code == 422

        # Invalid hex color pattern
        resp3 = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={
                "peltier_mode": "AUTO",
                "ventilation_mode": "AUTO",
                "locate_slot": "ROW-A-COL-1",
                "locate_color": "not-a-hex",
            },
            headers=auth_headers,
        )
        assert resp3.status_code == 422


class TestActuatorStateTransitions:
    """Verifies manual mode overrides, autonomous hysteresis, safety cutoff, and slot LEDs."""

    def test_get_initial_default_actuator_state(self, client, auth_headers, test_cabinet):
        """GET returns default AUTO operating modes and inactive outputs."""
        resp = client.get(f"/cabinet/{test_cabinet.cabinet_location}/actuators", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["cabinet_location"] == test_cabinet.cabinet_location
        assert data["peltier_mode"] == "AUTO"
        assert data["ventilation_mode"] == "AUTO"
        assert data["slot_rgb_active"] == {}

    def test_manual_peltier_cooling_overrides(self, client, auth_headers, test_cabinet):
        """Operators can manually force Peltier cooling ON or OFF."""
        # Force ON
        resp_on = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={"peltier_mode": "ON", "ventilation_mode": "AUTO"},
            headers=auth_headers,
        )
        assert resp_on.status_code == 200
        data_on = resp_on.json()
        assert data_on["peltier_mode"] == "ON"
        assert data_on["peltier_active"] is True

        # Force OFF
        resp_off = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={"peltier_mode": "OFF", "ventilation_mode": "AUTO"},
            headers=auth_headers,
        )
        assert resp_off.status_code == 200
        data_off = resp_off.json()
        assert data_off["peltier_mode"] == "OFF"
        assert data_off["peltier_active"] is False

    def test_failsafe_thermal_interlock_cutoff_at_low_temperature(
        self, client, auth_headers, db_session, test_cabinet
    ):
        """
        THERMAL SAFETY INTERLOCK:
        When cabinet temperature is below 10.0°C, Peltier cooling MUST remain False
        even when manual override is ON, protecting stored parts from sub-cooling condensation.
        """
        # Set cabinet temperature below safety threshold (8.5°C)
        test_cabinet.last_reported_temperature_c = 8.5
        db_session.commit()

        resp = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={"peltier_mode": "ON", "ventilation_mode": "AUTO"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["peltier_mode"] == "ON"
        assert data["peltier_active"] is False, "Safety interlock must inhibit Peltier below 10°C!"

    def test_ventilation_servo_overrides(self, client, auth_headers, test_cabinet):
        """Manual OPEN (90°) and CLOSED (0°) overrides."""
        # OPEN
        resp_open = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={"peltier_mode": "AUTO", "ventilation_mode": "OPEN"},
            headers=auth_headers,
        )
        assert resp_open.status_code == 200
        assert resp_open.json()["ventilation_servo_angle"] == 90

        # CLOSED
        resp_closed = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={"peltier_mode": "AUTO", "ventilation_mode": "CLOSED"},
            headers=auth_headers,
        )
        assert resp_closed.status_code == 200
        assert resp_closed.json()["ventilation_servo_angle"] == 0

    def test_slot_rgb_locator_led_lifecycle(self, client, auth_headers, test_cabinet):
        """Adding slot locators, inspecting active locators, and clearing slots."""
        # 1. Locate slot 1
        resp1 = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={
                "peltier_mode": "AUTO",
                "ventilation_mode": "AUTO",
                "locate_slot": "ROW-A-COL-1",
                "locate_color": "#00FFCC",
            },
            headers=auth_headers,
        )
        assert resp1.status_code == 200
        assert resp1.json()["slot_rgb_active"] == {"ROW-A-COL-1": "#00FFCC"}

        # 2. Locate slot 2 (accumulates)
        resp2 = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={
                "peltier_mode": "AUTO",
                "ventilation_mode": "AUTO",
                "locate_slot": "ROW-B-COL-3",
                "locate_color": "#FF007F",
            },
            headers=auth_headers,
        )
        assert resp2.status_code == 200
        slots = resp2.json()["slot_rgb_active"]
        assert slots["ROW-A-COL-1"] == "#00FFCC"
        assert slots["ROW-B-COL-3"] == "#FF007F"

        # 3. Clear via DELETE endpoint
        resp_del = client.delete(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators/slots",
            headers=auth_headers,
        )
        assert resp_del.status_code == 200
        assert resp_del.json()["slot_rgb_active"] == {}


class TestBidirectionalDownlinkAndWebSocket:
    """Verifies WebSocket broadcast upon actuator update and bidirectional telemetry downlink."""

    def test_actuator_post_broadcasts_via_websocket(self, client, auth_headers, test_cabinet):
        """Updating actuator commands broadcasts ACTUATOR_UPDATE frame to subscribers."""
        with client.websocket_connect("/ws/telemetry") as ws:
            post_resp = client.post(
                f"/cabinet/{test_cabinet.cabinet_location}/actuators",
                json={
                    "peltier_mode": "ON",
                    "ventilation_mode": "OPEN",
                    "locate_slot": "ROW-C-COL-2",
                    "locate_color": "#FFD700",
                },
                headers=auth_headers,
            )
            assert post_resp.status_code == 200

            frame = ws.receive_json()
            assert frame["type"] == "ACTUATOR_UPDATE"
            assert frame["cabinet_location"] == test_cabinet.cabinet_location
            assert "actuators" in frame
            actuators = frame["actuators"]
            assert actuators["peltier_mode"] == "ON"
            assert actuators["ventilation_mode"] == "OPEN"
            assert actuators["peltier_active"] is True
            assert actuators["ventilation_servo_angle"] == 90
            assert actuators["slot_rgb_active"] == {"ROW-C-COL-2": "#FFD700"}

    def test_bidirectional_telemetry_downlink_carries_actuator_state(
        self, client, auth_headers, test_cabinet
    ):
        """
        When ESP32 posts telemetry, the HTTP downlink response contains active slot LEDs
        and dynamic autonomous hysteresis control decisions.
        """
        # 1. Dashboard configures slot locator and Peltier in AUTO
        client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/actuators",
            json={
                "peltier_mode": "AUTO",
                "ventilation_mode": "AUTO",
                "locate_slot": "ROW-A-COL-4",
                "locate_color": "#00FF55",
            },
            headers=auth_headers,
        )

        # 2. ESP32 sends telemetry with high temperature (28.0°C > target 22.0 + 2.0)
        # and high humidity (60% > target 45%)
        headers, raw_body = create_esp32_telemetry_request(
            cabinet_location=test_cabinet.cabinet_location,
            temperature_c=28.0,
            humidity_percent=60.0,
            door_open=False,
            secret=DEFAULT_TEST_SECRET,
        )

        resp = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
            content=raw_body,
            headers=headers,
        )
        assert resp.status_code == 200
        downlink = resp.json()

        assert "actuator_commands" in downlink
        cmds = downlink["actuator_commands"]
        assert cmds["peltier_active"] is True, "Autonomous Peltier cooling must trigger on high temp"
        assert cmds["ventilation_servo_angle"] == 90, "Autonomous servo must open on high humidity"
        assert cmds["slot_rgb_active"] == {"ROW-A-COL-4": "#00FF55"}
