"""
Tier 3 IoT Subsystem Contract Tests: ESP32 HMAC-SHA256 Telemetry Ingestion & Anti-Replay Protection.

Derivation Source: ORIGINAL_REQUEST § Acceptance & PROJECT.md § Interface Contracts:
- Endpoint: POST /cabinet/{cabinet_location}/telemetry
- Headers:
  - X-ESP32-Signature: hex(hmac_sha256(secret_key, timestamp + "." + body_json))
  - X-ESP32-Timestamp: Unix epoch seconds string
- Replay Window: +/- 300 seconds
"""

import time
import pytest
from tests.helpers.hmac_helper import create_esp32_telemetry_request, DEFAULT_TEST_SECRET


class TestESP32TelemetryContract:
    """Verifies strict hardware authentication, replay window enforcement, and tamper detection."""

    def test_valid_signed_telemetry_ingestion_succeeds(self, client, test_cabinet):
        """
        An authentic ESP32 request signed with valid HMAC-SHA256 and fresh timestamp
        returns 200 OK and updates cabinet telemetry.
        """
        headers, raw_body = create_esp32_telemetry_request(
            cabinet_location=test_cabinet.cabinet_location,
            temperature_c=22.5,
            humidity_percent=44.0,
            door_open=False,
            secret=DEFAULT_TEST_SECRET,
        )

        response = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
            content=raw_body,
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["cabinet_location"] == test_cabinet.cabinet_location
        assert data["last_reported_temperature_c"] is not None
        assert data["last_reported_humidity_percent"] is not None

    def test_stale_timestamp_triggers_replay_attack_rejection(self, client, test_cabinet):
        """
        SECURITY / REPLAY ATTACK TEST:
        Telemetry signed with a valid key but with a timestamp 400s in the past (> 300s window)
        MUST be rejected with 401 Unauthorized.
        """
        headers, raw_body = create_esp32_telemetry_request(
            cabinet_location=test_cabinet.cabinet_location,
            temperature_c=22.5,
            humidity_percent=44.0,
            secret=DEFAULT_TEST_SECRET,
            timestamp_offset=-400,  # 400 seconds ago
        )

        response = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
            content=raw_body,
            headers=headers,
        )
        assert response.status_code == 401
        assert "replay attack" in response.json()["detail"].lower()

    def test_future_timestamp_triggers_replay_attack_rejection(self, client, test_cabinet):
        """
        SECURITY TEST:
        Telemetry with a timestamp 400s in the future (> 300s window)
        MUST be rejected with 401 Unauthorized.
        """
        headers, raw_body = create_esp32_telemetry_request(
            cabinet_location=test_cabinet.cabinet_location,
            temperature_c=22.5,
            humidity_percent=44.0,
            secret=DEFAULT_TEST_SECRET,
            timestamp_offset=400,  # 400 seconds into the future
        )

        response = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
            content=raw_body,
            headers=headers,
        )
        assert response.status_code == 401
        assert "replay attack" in response.json()["detail"].lower()

    def test_tampered_payload_rejected_with_401(self, client, test_cabinet):
        """
        INTEGRITY TEST:
        Payload whose temperature was modified in flight without recalculating the HMAC
        MUST be rejected with 401 Unauthorized (signature mismatch).
        """
        headers, raw_body = create_esp32_telemetry_request(
            cabinet_location=test_cabinet.cabinet_location,
            temperature_c=22.5,
            humidity_percent=44.0,
            secret=DEFAULT_TEST_SECRET,
            tamper_body=True,  # Modifies body to 99.9°C while keeping old signature
        )

        response = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
            content=raw_body,
            headers=headers,
        )
        assert response.status_code == 401
        assert "signature mismatch" in response.json()["detail"].lower()

    def test_missing_signature_headers_rejected_with_401(self, client, test_cabinet):
        """
        Calling the telemetry endpoint without signature headers returns 401.
        """
        body = b'{"temperature_c": 22.0, "humidity_percent": 45.0, "door_open": false}'
        response = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 401
        assert "missing" in response.json()["detail"].lower()

    def test_fallback_device_token_authentication(self, client, test_cabinet):
        """
        Devices supporting token-based fallback authentication (X-Device-Token)
        succeed when the token matches the configured secret.
        """
        valid_headers = {
            "Content-Type": "application/json",
            "X-Device-Token": DEFAULT_TEST_SECRET,
        }
        body = b'{"temperature_c": 23.0, "humidity_percent": 46.0, "door_open": false}'

        response = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
            content=body,
            headers=valid_headers,
        )
        assert response.status_code == 200

    def test_invalid_fallback_device_token_rejected_with_401(self, client, test_cabinet):
        """Invalid device token returns 401 Unauthorized."""
        invalid_headers = {
            "Content-Type": "application/json",
            "X-Device-Token": "invalid_wrong_token_12345",
        }
        body = b'{"temperature_c": 23.0, "humidity_percent": 46.0, "door_open": false}'

        response = client.post(
            f"/cabinet/{test_cabinet.cabinet_location}/telemetry",
            content=body,
            headers=invalid_headers,
        )
        assert response.status_code == 401
        assert "invalid device token" in response.json()["detail"].lower()
