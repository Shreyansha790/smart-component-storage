"""
Tier 2 Integration Tests: Authentication Lifecycle, Password Hashing, JWT Issuance & Verification.

Derivation Source: PROJECT.md § Feature 7 & ORIGINAL_REQUEST § Acceptance (Zero missing auth headers).
"""

import pytest
from app import auth


class TestAuthLifecycle:
    """Verifies end-to-end user registration, credential verification, and token access."""

    def test_register_new_user_success(self, client):
        """Registering a new account hashes the password and returns 201 with token and user."""
        payload = {
            "full_name": "Marcus Kane",
            "email": "marcus.kane@iot-vault.io",
            "password": "SecurePassword2026!",
            "role": "technician",
        }
        response = client.post("/auth/signup", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        user_data = data["user"]
        assert user_data["email"] == payload["email"]
        assert user_data["full_name"] == payload["full_name"]
        assert user_data["role"] == payload["role"]
        assert "password" not in user_data
        assert "hashed_password" not in user_data

    def test_register_duplicate_email_rejected(self, client, test_user):
        """Attempting to register with an already existing email returns 400 Bad Request."""
        payload = {
            "full_name": "Duplicate User",
            "email": test_user.email,
            "password": "Password123!",
            "role": "technician",
        }
        response = client.post("/auth/signup", json=payload)
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    def test_login_valid_credentials_issues_jwt(self, client, test_user):
        """Logging in with valid username and password returns a valid Bearer token."""
        form_data = {
            "username": test_user.email,
            "password": "Password123!",
        }
        response = client.post("/auth/login", data=form_data)
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"].lower() == "bearer"
        assert len(data["access_token"]) > 20

    def test_login_invalid_password_returns_401(self, client, test_user):
        """Supplying an incorrect password returns 401 Unauthorized."""
        form_data = {
            "username": test_user.email,
            "password": "WrongPassword!",
        }
        response = client.post("/auth/login", data=form_data)
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    def test_login_nonexistent_user_returns_401(self, client):
        """Supplying a non-existent email returns 401 Unauthorized."""
        form_data = {
            "username": "ghost.user@unknown.com",
            "password": "Password123!",
        }
        response = client.post("/auth/login", data=form_data)
        assert response.status_code == 401

    def test_get_current_user_profile_success(self, client, auth_headers, test_user):
        """Accessing /auth/me with a valid Bearer token returns the user profile."""
        response = client.get("/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["id"] == test_user.id

    def test_access_with_tampered_token_returns_401(self, client):
        """Sending a tampered JWT token returns 401 Unauthorized."""
        headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.tampered.signature"}
        response = client.get("/auth/me", headers=headers)
        assert response.status_code == 401
        assert "credentials" in response.json()["detail"].lower()
