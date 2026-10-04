"""
Tier 3 IoT Contract & Security Challenge: Empirical HMAC Verification & Route Auth Sweep.

Derivation Source: Milestone 1 Mandatory Objective:
1. Valid signature with valid timestamp -> 200 OK
2. Tampered payload byte -> 401 Unauthorized
3. Replay attack with expired timestamp (+301s, -301s) -> 401 Unauthorized
4. Future timestamp spoofing -> 401 Unauthorized
5. Missing headers (no signature, no timestamp) -> 401 Unauthorized
6. Malformed signature hex strings -> 401 Unauthorized (no 500 error!)
7. Invalid JSON payload -> 422 Unprocessable Entity
8. Protected alert and smart logic routes reject requests without Authorization Bearer tokens with 401.
"""

import json
import time
import pytest

from app.config import settings
from tests.helpers.hmac_helper import generate_esp32_signature, DEFAULT_TEST_SECRET


TEST_SECRET = getattr(settings, "DEVICE_HMAC_SECRET", DEFAULT_TEST_SECRET)
TEST_CABINET = "CAB-A"


class TestM1HMACEmpiricalSecurity:
    """Adversarial stress-test suite for ESP32 HMAC-SHA256 authentication."""

    def test_valid_signature_with_valid_timestamp_returns_200(self, client, test_cabinet):
        """Valid HMAC signature + fresh timestamp must ingest cleanly with 200 OK."""
        now_ts = int(time.time())
        payload = {"temperature_c": 24.5, "humidity_percent": 45.2, "door_open": False}
        body_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        sig = generate_esp32_signature(TEST_SECRET, now_ts, body_bytes)

        headers = {
            "Content-Type": "application/json",
            "X-ESP32-Signature": sig,
            "X-ESP32-Timestamp": str(now_ts),
        }
        resp = client.post(f"/cabinet/{TEST_CABINET}/telemetry", content=body_bytes, headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["cabinet_location"] == TEST_CABINET
        assert data["status"] in ("NORMAL", "OK", "OUT_OF_RANGE")
        assert "actuator_commands" in data

    def test_tampered_payload_byte_returns_401(self, client, test_cabinet):
        """Tampering with a single character/byte in the JSON payload must be rejected with 401."""
        now_ts = int(time.time())
        original_payload = {"temperature_c": 24.5, "humidity_percent": 45.2, "door_open": False}
        original_bytes = json.dumps(original_payload, separators=(",", ":")).encode("utf-8")
        sig = generate_esp32_signature(TEST_SECRET, now_ts, original_bytes)

        # Tamper payload: change 24.5 to 24.6
        tampered_payload = {"temperature_c": 24.6, "humidity_percent": 45.2, "door_open": False}
        tampered_bytes = json.dumps(tampered_payload, separators=(",", ":")).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "X-ESP32-Signature": sig,
            "X-ESP32-Timestamp": str(now_ts),
        }
        resp = client.post(f"/cabinet/{TEST_CABINET}/telemetry", content=tampered_bytes, headers=headers)
        assert resp.status_code == 401, f"Expected 401 for tampered payload, got {resp.status_code}: {resp.text}"
        assert "mismatch" in resp.json().get("detail", "").lower() or "failed" in resp.json().get("detail", "").lower()

    @pytest.mark.parametrize("offset,desc", [
        (-301, "Past timestamp expired by 301 seconds"),
        (-600, "Past timestamp expired by 600 seconds"),
        (-86400, "Past timestamp expired by 1 day"),
    ])
    def test_replay_attack_expired_past_timestamp_returns_401(self, client, test_cabinet, offset, desc):
        """Signatures with timestamps older than 300 seconds must trigger 401 anti-replay."""
        past_ts = int(time.time()) + offset
        payload = {"temperature_c": 24.5, "humidity_percent": 45.2, "door_open": False}
        body_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        sig = generate_esp32_signature(TEST_SECRET, past_ts, body_bytes)

        headers = {
            "Content-Type": "application/json",
            "X-ESP32-Signature": sig,
            "X-ESP32-Timestamp": str(past_ts),
        }
        resp = client.post(f"/cabinet/{TEST_CABINET}/telemetry", content=body_bytes, headers=headers)
        assert resp.status_code == 401, f"Expected 401 for {desc}, got {resp.status_code}: {resp.text}"
        assert "replay" in resp.json().get("detail", "").lower() or "exceeds" in resp.json().get("detail", "").lower()

    @pytest.mark.parametrize("offset,desc", [
        (301, "Future timestamp spoofed by +301 seconds"),
        (600, "Future timestamp spoofed by +600 seconds"),
        (86400, "Future timestamp spoofed by +1 day"),
        (1000000, "Extreme future timestamp"),
    ])
    def test_future_timestamp_spoofing_returns_401(self, client, test_cabinet, offset, desc):
        """Signatures with timestamps more than 300s into the future must be rejected with 401."""
        future_ts = int(time.time()) + offset
        payload = {"temperature_c": 24.5, "humidity_percent": 45.2, "door_open": False}
        body_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        sig = generate_esp32_signature(TEST_SECRET, future_ts, body_bytes)

        headers = {
            "Content-Type": "application/json",
            "X-ESP32-Signature": sig,
            "X-ESP32-Timestamp": str(future_ts),
        }
        resp = client.post(f"/cabinet/{TEST_CABINET}/telemetry", content=body_bytes, headers=headers)
        assert resp.status_code == 401, f"Expected 401 for {desc}, got {resp.status_code}: {resp.text}"
        assert "replay" in resp.json().get("detail", "").lower() or "exceeds" in resp.json().get("detail", "").lower()

    def test_missing_headers_returns_401(self, client, test_cabinet):
        """Missing signature or timestamp headers must return 401."""
        now_ts = int(time.time())
        payload = {"temperature_c": 24.5, "humidity_percent": 45.2, "door_open": False}
        body_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        sig = generate_esp32_signature(TEST_SECRET, now_ts, body_bytes)

        # 1. No headers at all
        r1 = client.post(f"/cabinet/{TEST_CABINET}/telemetry", content=body_bytes, headers={"Content-Type": "application/json"})
        assert r1.status_code == 401, f"Expected 401 for missing all headers, got {r1.status_code}"

        # 2. Signature present, timestamp missing
        r2 = client.post(
            f"/cabinet/{TEST_CABINET}/telemetry",
            content=body_bytes,
            headers={"Content-Type": "application/json", "X-ESP32-Signature": sig},
        )
        assert r2.status_code == 401, f"Expected 401 for missing timestamp header, got {r2.status_code}"

        # 3. Timestamp present, signature missing
        r3 = client.post(
            f"/cabinet/{TEST_CABINET}/telemetry",
            content=body_bytes,
            headers={"Content-Type": "application/json", "X-ESP32-Timestamp": str(now_ts)},
        )
        assert r3.status_code == 401, f"Expected 401 for missing signature header, got {r3.status_code}"

    @pytest.mark.parametrize("malformed_sig,case_name", [
        ("not-a-valid-hex-signature-abcdefghijklmnopqrstuvwxyz1234567890", "non_hex_string"),
        ("abc", "odd_length_short_hex"),
        ("0123456789abcdef", "truncated_16_hex"),
        ("!@#$%^&*()_+=-~`{}[]|;:,.<>?", "special_characters"),
        ("a" * 10000, "buffer_overflow_10k_chars"),
        ("   ", "whitespace_only"),
        ("0x" + "a" * 64, "0x_prefixed_hex"),
        ("INVALID_HEX_DIGEST_ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ", "invalid_chars_upper"),
    ])
    def test_malformed_signature_hex_strings_returns_401_no_500(self, client, test_cabinet, malformed_sig, case_name):
        """Malformed signature strings MUST return 401 Unauthorized without crashing into 500."""
        now_ts = int(time.time())
        payload = {"temperature_c": 24.5, "humidity_percent": 45.2, "door_open": False}
        body_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "X-ESP32-Signature": malformed_sig,
            "X-ESP32-Timestamp": str(now_ts),
        }
        resp = client.post(f"/cabinet/{TEST_CABINET}/telemetry", content=body_bytes, headers=headers)
        assert resp.status_code == 401, (
            f"Malformed signature case '{case_name}' returned {resp.status_code} instead of 401! "
            f"Response body: {resp.text}"
        )

    def test_invalid_json_payload_returns_422(self, client, test_cabinet):
        """
        When signature is valid for the raw body bytes, but body has invalid JSON syntax
        or schema validation errors, FastAPI must return 422 Unprocessable Entity, not 500.
        """
        now_ts = int(time.time())

        # Subtest A: Syntactically broken JSON signed with valid HMAC
        broken_json = b'{"temperature_c": 24.5, "humidity_percent": '
        sig_a = generate_esp32_signature(TEST_SECRET, now_ts, broken_json)
        headers_a = {
            "Content-Type": "application/json",
            "X-ESP32-Signature": sig_a,
            "X-ESP32-Timestamp": str(now_ts),
        }
        resp_a = client.post(f"/cabinet/{TEST_CABINET}/telemetry", content=broken_json, headers=headers_a)
        assert resp_a.status_code == 422, f"Expected 422 for broken JSON, got {resp_a.status_code}: {resp_a.text}"

        # Subtest B: Schema violation (missing required field temperature_c)
        missing_field_json = b'{"door_open": false}'
        sig_b = generate_esp32_signature(TEST_SECRET, now_ts, missing_field_json)
        headers_b = {
            "Content-Type": "application/json",
            "X-ESP32-Signature": sig_b,
            "X-ESP32-Timestamp": str(now_ts),
        }
        resp_b = client.post(f"/cabinet/{TEST_CABINET}/telemetry", content=missing_field_json, headers=headers_b)
        assert resp_b.status_code == 422, f"Expected 422 for missing fields, got {resp_b.status_code}: {resp_b.text}"

        # Subtest C: Schema type mismatch (temperature_c as string)
        type_mismatch_json = b'{"temperature_c": "very_hot", "humidity_percent": 45.0}'
        sig_c = generate_esp32_signature(TEST_SECRET, now_ts, type_mismatch_json)
        headers_c = {
            "Content-Type": "application/json",
            "X-ESP32-Signature": sig_c,
            "X-ESP32-Timestamp": str(now_ts),
        }
        resp_c = client.post(f"/cabinet/{TEST_CABINET}/telemetry", content=type_mismatch_json, headers=headers_c)
        assert resp_c.status_code == 422, f"Expected 422 for type mismatch, got {resp_c.status_code}: {resp_c.text}"


class TestM1RouteAuthHardening:
    """Verifies that all protected alert and smart logic routes reject unauthenticated requests with 401."""

    UNAUTHENTICATED_ROUTES = [
        ("GET", "/alerts", None),
        ("GET", "/api/alerts", None),
        ("PATCH", "/alerts/1/read", None),
        ("PATCH", "/api/alerts/1/read", None),
        ("POST", "/alerts/mark-all-read", None),
        ("POST", "/api/alerts/mark-all-read", None),
        ("POST", "/api/alerts/send-email", None),
        ("GET", "/smart-logic/component/1", None),
        ("GET", "/cabinet", None),
        ("POST", "/cabinet", {"cabinet_location": "TEST", "target_temperature_c": 20.0, "target_humidity_percent": 40.0}),
        ("PATCH", "/cabinet/CAB-A", {"target_temperature_c": 21.0}),
    ]

    @pytest.mark.parametrize("method,path,payload", UNAUTHENTICATED_ROUTES)
    def test_unauthenticated_requests_strictly_rejected_with_401(self, client, method, path, payload):
        """Endpoints requiring authentication must return 401 when no token is supplied."""
        if method == "GET":
            resp = client.get(path)
        elif method == "POST":
            resp = client.post(path, json=payload or {})
        elif method == "PATCH":
            resp = client.patch(path, json=payload or {})
        else:
            pytest.fail(f"Unsupported method: {method}")

        assert resp.status_code == 401, (
            f"Unauthenticated request to {method} {path} returned {resp.status_code} instead of 401! "
            f"Response body: {resp.text}"
        )

    @pytest.mark.parametrize("bad_token", [
        "Bearer invalid_token_xyz_123",
        "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.corrupted.signature",
        "Bearer ",
        "Basic dXNlcjpwYXNz",
    ])
    def test_forged_or_malformed_bearer_tokens_rejected_with_401(self, client, bad_token):
        """Malformed or forged Authorization headers must return 401, never 500."""
        headers = {"Authorization": bad_token}
        resp = client.get("/smart-logic/component/1", headers=headers)
        assert resp.status_code == 401, f"Bad token '{bad_token}' returned {resp.status_code} instead of 401"

    def test_signature_replay_within_window_rejected_with_401(self, client, test_cabinet):
        """
        Submitting the identical valid signature a second time within the active window
        must be caught by the replay cache and rejected with 401 Unauthorized.
        """
        from app import auth
        auth.reset_signature_cache()

        now_ts = int(time.time())
        payload = {"temperature_c": 21.0, "humidity_percent": 43.0, "door_open": False}
        body_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        sig = generate_esp32_signature(TEST_SECRET, now_ts, body_bytes)

        headers = {
            "Content-Type": "application/json",
            "X-ESP32-Signature": sig,
            "X-ESP32-Timestamp": str(now_ts),
        }

        # 1. First presentation of signature -> 200 OK
        resp1 = client.post(f"/cabinet/{TEST_CABINET}/telemetry", content=body_bytes, headers=headers)
        assert resp1.status_code == 200, f"First request failed: {resp1.status_code}: {resp1.text}"

        # 2. Replay of identical signature within window -> 401 Unauthorized
        resp2 = client.post(f"/cabinet/{TEST_CABINET}/telemetry", content=body_bytes, headers=headers)
        assert resp2.status_code == 401, f"Replay request was not rejected with 401: {resp2.status_code}"
        assert resp2.json().get("detail") == "Replay attack detected: signature already used"

    def test_signature_replay_cache_ttl_purge(self):
        """
        Verify that signatures older than 300s are automatically purged from seen_signatures.
        """
        from app import auth
        auth.reset_signature_cache()

        old_ts = time.time() - 350
        auth.seen_signatures.add("old_sig_123")
        auth._signature_timestamps["old_sig_123"] = old_ts

        fresh_ts = time.time() - 50
        auth.seen_signatures.add("fresh_sig_456")
        auth._signature_timestamps["fresh_sig_456"] = fresh_ts

        assert "old_sig_123" in auth.seen_signatures
        assert "fresh_sig_456" in auth.seen_signatures

        # Purge
        auth.purge_expired_signatures()

        assert "old_sig_123" not in auth.seen_signatures
        assert "fresh_sig_456" in auth.seen_signatures
        auth.reset_signature_cache()

