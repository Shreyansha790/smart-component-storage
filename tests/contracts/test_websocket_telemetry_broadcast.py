"""
Tier 3 IoT Subsystem Contract Tests: Real-Time WebSocket Telemetry Broadcast Fan-Out.

Derivation Source: ORIGINAL_REQUEST § R2 & PROJECT.md § Interface Contracts:
- Endpoint: ws://localhost:8000/ws/telemetry
- Messages:
  {
    "type": "TELEMETRY_UPDATE",
    "timestamp": 1728000000,
    "cabinet_location": "CAB-A",
    "telemetry": {
      "temperature_c": 24.5,
      "humidity_percent": 45.2,
      "smoothed_temp": 24.4,
      "smoothed_humidity": 45.1,
      "door_open": false
    },
    "actuators": {
      "peltier_active": false,
      "ventilation_servo_angle": 0,
      "slot_rgb_active": {}
    }
  }
"""

import pytest
from tests.helpers.hmac_helper import create_esp32_telemetry_request, DEFAULT_TEST_SECRET
from app.services.websocket_manager import ws_manager


class TestWebSocketTelemetryBroadcast:
    """Verifies that live sensor posts trigger instantaneous WebSocket broadcasts across subscribers."""

    def test_websocket_client_connection_lifecycle(self, client):
        """A client can establish a persistent WebSocket connection to /ws/telemetry."""
        initial_connections = len(ws_manager.active_connections)
        with client.websocket_connect("/ws/telemetry") as ws:
            assert len(ws_manager.active_connections) == initial_connections + 1
            # Send client ping / message
            ws.send_json({"type": "PING"})

        # After exiting context manager, connection is cleanly disconnected
        assert len(ws_manager.active_connections) == initial_connections

    def test_telemetry_post_broadcasts_to_connected_client(self, client, test_cabinet):
        """
        When ESP32 posts valid telemetry via HTTP POST, the connected WebSocket
        client receives an instantaneous TELEMETRY_UPDATE broadcast frame.
        """
        with client.websocket_connect("/ws/telemetry") as ws:
            # Post telemetry reading from simulated ESP32
            headers, raw_body = create_esp32_telemetry_request(
                cabinet_location=test_cabinet.cabinet_location,
                temperature_c=23.4,
                humidity_percent=42.1,
                door_open=False,
                secret=DEFAULT_TEST_SECRET,
            )

            post_resp = client.post(
                f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
                content=raw_body,
                headers=headers,
            )
            assert post_resp.status_code == 200

            # Receive broadcast frame from WebSocket
            frame = ws.receive_json()
            assert frame["type"] == "TELEMETRY_UPDATE"
            assert frame["cabinet_location"] == test_cabinet.cabinet_location
            assert "timestamp" in frame

            # Verify telemetry payload contract
            telemetry = frame["telemetry"]
            assert pytest.approx(telemetry["temperature_c"], rel=1e-2) == 23.4
            assert pytest.approx(telemetry["humidity_percent"], rel=1e-2) == 42.1
            assert "smoothed_temp" in telemetry
            assert "smoothed_humidity" in telemetry
            assert telemetry["door_open"] is False

            # Verify actuators payload contract
            assert "actuators" in frame
            assert "peltier_active" in frame["actuators"]
            assert "ventilation_servo_angle" in frame["actuators"]

    def test_broadcast_fan_out_multiple_subscribers(self, client, test_cabinet):
        """
        FAN-OUT TEST:
        When multiple browser clients (e.g. 2 dashboard tabs) are connected simultaneously,
        both receive the broadcast message upon telemetry arrival.
        """
        with client.websocket_connect("/ws/telemetry") as ws1:
            with client.websocket_connect("/ws/telemetry") as ws2:
                headers, raw_body = create_esp32_telemetry_request(
                    cabinet_location=test_cabinet.cabinet_location,
                    temperature_c=25.0,
                    humidity_percent=40.0,
                    door_open=True,
                    secret=DEFAULT_TEST_SECRET,
                )

                post_resp = client.post(
                    f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
                    content=raw_body,
                    headers=headers,
                )
                assert post_resp.status_code == 200

                frame1 = ws1.receive_json()
                frame2 = ws2.receive_json()

                assert frame1["type"] == "TELEMETRY_UPDATE"
                assert frame2["type"] == "TELEMETRY_UPDATE"
                assert frame1["telemetry"]["door_open"] is True
                assert frame2["telemetry"]["door_open"] is True

    def test_broadcast_concurrent_timeout_and_error_handling(self):
        """
        Verify that ws_manager.broadcast concurrently sends messages and cleanly
        prunes connections that raise TimeoutError or other exceptions without failing.
        """
        import asyncio
        from unittest.mock import AsyncMock
        from app.services.websocket_manager import ConnectionManager

        async def _test():
            mgr = ConnectionManager()
            good_ws = AsyncMock()
            stalled_ws = AsyncMock()

            async def slow_send(msg):
                await asyncio.sleep(2.0)

            stalled_ws.send_json.side_effect = slow_send
            failing_ws = AsyncMock()
            failing_ws.send_json.side_effect = RuntimeError("Socket reset")

            mgr.active_connections = [good_ws, stalled_ws, failing_ws]

            # Broadcast should complete cleanly despite slow and failing sockets
            await mgr.broadcast({"test": "data"})

            # Good socket received message
            good_ws.send_json.assert_called_once_with({"test": "data"})

            # Stalled and failing sockets are pruned from active_connections
            assert stalled_ws not in mgr.active_connections
            assert failing_ws not in mgr.active_connections
            assert good_ws in mgr.active_connections

        asyncio.run(_test())


