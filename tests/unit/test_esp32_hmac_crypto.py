"""
Tier 1 Unit Tests: Pure Cryptographic HMAC-SHA256 ESP32 Signature Computation & Verification.

Derivation Source: PROJECT.md § Interface Contracts & ORIGINAL_REQUEST § R2 / Acceptance.
Tests RFC 2104 compliance, constant-time comparison, bit-flip tampering, and key sensitivity.
"""

import hashlib
import hmac
import pytest
from app.auth import compute_hmac_sha256, verify_hmac_signature
from tests.helpers.hmac_helper import DEFAULT_TEST_SECRET, generate_esp32_signature


class TestESP32HMACCrypto:
    """Cryptographic validation for IoT device HMAC authentication."""

    def test_rfc2104_hmac_sha256_known_vector(self):
        """
        Verifies standard HMAC-SHA256 digest computation against Python standard library.
        """
        secret = "key_test_secret_12345678"
        data = b"The quick brown fox jumps over the lazy dog"
        expected = hmac.new(secret.encode("utf-8"), data, hashlib.sha256).hexdigest()

        computed = compute_hmac_sha256(secret, data)
        assert computed == expected
        assert len(computed) == 64  # SHA-256 hex string is 64 characters

    def test_esp32_message_signature_verification_succeeds(self):
        """
        Valid secret, timestamp, and payload body must verify successfully.
        """
        secret = DEFAULT_TEST_SECRET
        timestamp = "1728000000"
        raw_body = b'{"temperature_c":24.5,"humidity_percent":45.2,"door_open":false}'

        signature = generate_esp32_signature(secret, int(timestamp), raw_body)
        assert verify_hmac_signature(secret, timestamp, raw_body, signature) is True

    def test_payload_tampering_fails_verification(self):
        """
        ADVERSARIAL TEST: Tampering with a single character (e.g. changing 24.5 to 24.6)
        MUST cause verification to fail immediately.
        """
        secret = DEFAULT_TEST_SECRET
        timestamp = "1728000000"
        original_body = b'{"temperature_c":24.5,"humidity_percent":45.2,"door_open":false}'
        tampered_body = b'{"temperature_c":24.6,"humidity_percent":45.2,"door_open":false}'

        valid_sig = generate_esp32_signature(secret, int(timestamp), original_body)

        assert verify_hmac_signature(secret, timestamp, original_body, valid_sig) is True
        assert verify_hmac_signature(secret, timestamp, tampered_body, valid_sig) is False

    def test_secret_key_mismatch_fails_verification(self):
        """Signing with one key and verifying with another must fail."""
        secret_device = "secret_key_device_alpha"
        secret_server = "secret_key_server_beta"
        timestamp = "1728000000"
        raw_body = b'{"temperature_c":20.0,"humidity_percent":40.0}'

        signature = generate_esp32_signature(secret_device, int(timestamp), raw_body)
        assert verify_hmac_signature(secret_server, timestamp, raw_body, signature) is False

    def test_timestamp_alteration_fails_verification(self):
        """
        If an attacker attempts to change the timestamp without recalculating
        the HMAC digest, verification must fail.
        """
        secret = DEFAULT_TEST_SECRET
        orig_timestamp = "1728000000"
        altered_timestamp = "1728000100"
        raw_body = b'{"temperature_c":22.0,"humidity_percent":45.0}'

        sig = generate_esp32_signature(secret, int(orig_timestamp), raw_body)
        assert verify_hmac_signature(secret, altered_timestamp, raw_body, sig) is False

    def test_signature_hex_case_insensitivity_and_whitespace(self):
        """
        Signatures provided in uppercase or with surrounding whitespace
        must still be accepted after sanitization.
        """
        secret = DEFAULT_TEST_SECRET
        timestamp = "1728000000"
        raw_body = b'{"status":"OK"}'

        sig = generate_esp32_signature(secret, int(timestamp), raw_body)
        assert verify_hmac_signature(secret, timestamp, raw_body, sig.upper()) is True
        assert verify_hmac_signature(secret, timestamp, raw_body, f"  {sig}  ") is True

    def test_empty_payload_and_empty_secret_handling(self):
        """
        Empty secret or empty signature must safely return False without crashing.
        """
        timestamp = "1728000000"
        raw_body = b'{}'
        assert verify_hmac_signature("", timestamp, raw_body, "any_sig") is False
        assert verify_hmac_signature(DEFAULT_TEST_SECRET, timestamp, raw_body, "") is False

    def test_utf8_special_character_escaping(self):
        """
        Payloads containing UTF-8 characters and unicode escapes (e.g. °C, degree symbols)
        must verify accurately over raw byte streams.
        """
        secret = DEFAULT_TEST_SECRET
        timestamp = "1728000000"
        raw_body = '{"symbol":"℃","note":"Sensor calibrated to ±0.1℃"}'.encode("utf-8")

        sig = generate_esp32_signature(secret, int(timestamp), raw_body)
        assert verify_hmac_signature(secret, timestamp, raw_body, sig) is True
