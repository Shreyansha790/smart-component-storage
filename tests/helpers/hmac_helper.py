"""
Helper utilities for ESP32 HMAC-SHA256 signature generation and payload tampering tests.
"""

import hashlib
import hmac
import json
import time
from typing import Dict, Any, Tuple


DEFAULT_TEST_SECRET = "esp32_super_secret_hmac_key_production_2026"


def generate_esp32_signature(
    secret: str,
    timestamp: int,
    payload_bytes: bytes,
) -> str:
    """
    Computes hexadecimal HMAC-SHA256 signature over:
    f"{timestamp}." + payload_bytes
    """
    msg = f"{timestamp}.".encode("utf-8") + payload_bytes
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def create_esp32_telemetry_request(
    cabinet_location: str = "CAB-A",
    temperature_c: float = 24.5,
    humidity_percent: float = 45.2,
    door_open: bool = False,
    secret: str = DEFAULT_TEST_SECRET,
    timestamp_offset: int = 0,
    tamper_body: bool = False,
    tamper_signature: bool = False,
) -> Tuple[Dict[str, str], bytes]:
    """
    Constructs headers and raw JSON body for a signed ESP32 telemetry request.
    Allows injecting timestamp offsets or bit-flips to test tampering and replay attacks.
    """
    timestamp = int(time.time()) + timestamp_offset
    body_data = {
        "temperature_c": temperature_c,
        "humidity_percent": humidity_percent,
        "door_open": door_open,
    }
    raw_body = json.dumps(body_data, separators=(",", ":")).encode("utf-8")

    signature = generate_esp32_signature(secret, timestamp, raw_body)

    if tamper_body:
        # Mutate the body payload while keeping original signature
        tampered_data = dict(body_data)
        tampered_data["temperature_c"] = 99.9
        raw_body = json.dumps(tampered_data, separators=(",", ":")).encode("utf-8")

    if tamper_signature:
        # Flip a character in the signature
        char = "0" if signature[0] != "0" else "1"
        signature = char + signature[1:]

    headers = {
        "Content-Type": "application/json",
        "X-ESP32-Signature": signature,
        "X-ESP32-Timestamp": str(timestamp),
    }

    return headers, raw_body
