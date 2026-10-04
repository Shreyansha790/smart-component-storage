"""
Tier 2 Integration Tests: Input Fuzzing, Edge Case Stress, and Zero Unhandled Exceptions (500).

Derivation Source: ORIGINAL_REQUEST § Acceptance:
"Zero unhandled API exceptions or missing authentication headers on protected routes."
"""

import pytest


class TestUnhandledExceptionsAndFuzzing:
    """Verifies that malformed, hostile, or out-of-range inputs produce structured errors, never 500."""

    def test_malformed_json_body_returns_422_not_500(self, client, auth_headers):
        """Malformed JSON payload must return 422 Unprocessable Entity without crashing."""
        raw_broken_json = b'{"batch_id": "B1", "broken": '
        response = client.post(
            "/inventory",
            data=raw_broken_json,
            headers={**auth_headers, "Content-Type": "application/json"},
        )
        assert response.status_code == 422
        assert response.headers.get("content-type", "").startswith("application/json")
        assert "detail" in response.json()

    def test_empty_json_body_for_create_returns_422(self, client, auth_headers):
        """Posting an empty JSON object when required fields are missing returns 422."""
        response = client.post("/inventory", json={}, headers=auth_headers)
        assert response.status_code == 422
        assert "detail" in response.json()

    def test_nonexistent_inventory_id_returns_404_not_500(self, client, auth_headers):
        """Looking up or patching a non-existent component ID returns 404."""
        response_get = client.get("/inventory/999999", headers=auth_headers)
        assert response_get.status_code == 404
        assert "not found" in response_get.json()["detail"].lower()

        response_patch = client.patch("/inventory/999999", json={"quantity": 10}, headers=auth_headers)
        assert response_patch.status_code == 404

    def test_nonexistent_cabinet_setpoint_patch_returns_404(self, client, auth_headers):
        """Updating setpoints for a cabinet that does not exist returns 404."""
        response = client.patch(
            "/cabinet/CAB-NONEXISTENT-999",
            json={"target_temperature_c": 20.0},
            headers=auth_headers,
        )
        assert response.status_code == 404
        assert "cabinet not found" in response.json()["detail"].lower()

    def test_string_passed_to_integer_path_param_returns_422(self, client, auth_headers):
        """Passing alphanumeric text into an integer path parameter returns 422."""
        response = client.get("/inventory/invalid-alpha-id", headers=auth_headers)
        assert response.status_code == 422
        assert "detail" in response.json()

    def test_sql_injection_attempt_in_search_query_handled_safely(self, client, auth_headers):
        """
        Adversarial SQL injection string in query parameter must be safely escaped
        by SQLAlchemy ORM and not trigger SQL syntax errors or unhandled 500s.
        """
        sql_payload = "' OR 1=1; DROP TABLE components; --"
        response = client.get(f"/inventory?search={sql_payload}", headers=auth_headers)
        assert response.status_code == 200
        # The database must remain intact and return a normal JSON response list
        data = response.json()
        assert isinstance(data, list)

    def test_extreme_and_negative_pagination_params_handled(self, client, auth_headers):
        """Negative page or zero limit should either clamp or return validation error, never 500."""
        response = client.get("/inventory?page=-5&limit=0", headers=auth_headers)
        assert response.status_code in (200, 422)
        if response.status_code == 200:
            assert isinstance(response.json(), list)

    def test_unregistered_endpoint_returns_404_not_500(self, client):
        """Requesting an invalid route returns 404 Not Found."""
        response = client.get("/api/v1/ghost/nonexistent/service")
        assert response.status_code == 404
