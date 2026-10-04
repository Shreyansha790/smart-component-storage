"""
Tier 2 Integration Tests: Exhaustive Protected Route Security Sweep.

Derivation Source: ORIGINAL_REQUEST § Acceptance:
"Zero unhandled API exceptions or missing authentication headers on protected routes."
PROJECT.md § Feature 7 & Feature 22.
"""

import pytest


PROTECTED_ROUTES = [
    ("GET", "/inventory"),
    ("POST", "/inventory", {"batch_id": "B-TEST", "part_number": "P1", "manufacturer": "M1", "category": "Passive", "cabinet_location": "CAB-A", "quantity": 10, "stored_date": "2026-01-01T00:00:00", "min_temperature_c": 10, "max_temperature_c": 30, "max_humidity_percent": 60, "shelf_life_days": 180}),
    ("GET", "/inventory/fefo"),
    ("GET", "/inventory/export"),
    ("GET", "/inventory/1"),
    ("PATCH", "/inventory/1", {"quantity": 25}),
    ("DELETE", "/inventory/1"),
    ("GET", "/cabinet"),
    ("POST", "/cabinet", {"cabinet_location": "CAB-SWEEP-1", "target_temperature_c": 20.0, "target_humidity_percent": 45.0}),
    ("PATCH", "/cabinet/CAB-A", {"target_temperature_c": 21.5}),
    ("GET", "/alerts"),
    ("GET", "/auth/me"),
]


class TestProtectedRoutesSweep:
    """Verifies that all protected endpoints strictly enforce authentication."""

    @pytest.mark.parametrize("method,path,payload", [
        (item[0], item[1], item[2] if len(item) > 2 else None)
        for item in PROTECTED_ROUTES
    ])
    def test_unauthenticated_request_is_rejected_with_401(self, client, method, path, payload):
        """
        Any call to a protected endpoint without an Authorization header MUST return 401 Unauthorized.
        Zero endpoints should be left open or leak internal server errors (500).
        """
        if method == "GET":
            response = client.get(path)
        elif method == "POST":
            response = client.post(path, json=payload or {})
        elif method == "PATCH":
            response = client.patch(path, json=payload or {})
        elif method == "DELETE":
            response = client.delete(path)
        else:
            pytest.fail(f"Unhandled method {method}")

        assert response.status_code == 401, (
            f"Endpoint {method} {path} returned {response.status_code} instead of 401 Unauthorized! "
            f"Response: {response.text}"
        )
        # Ensure error payload is structured JSON, not raw HTML/stacktrace
        json_data = response.json()
        assert "detail" in json_data or "error" in json_data

    def test_authenticated_access_is_permitted(self, client, auth_headers, test_cabinet):
        """
        The same protected endpoints succeed (200 / 201) when supplied with a valid Bearer token.
        """
        # Test cabinet list
        resp_cab = client.get("/cabinet", headers=auth_headers)
        assert resp_cab.status_code == 200

        # Test inventory list
        resp_inv = client.get("/inventory", headers=auth_headers)
        assert resp_inv.status_code == 200

        # Test alerts list
        resp_alerts = client.get("/alerts", headers=auth_headers)
        assert resp_alerts.status_code == 200
