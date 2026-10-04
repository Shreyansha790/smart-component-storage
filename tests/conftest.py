"""
Pytest configuration and shared fixtures for Smart Component Storage test suite.
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure project root and smart_storage_backend are in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PROJECT_ROOT / "smart_storage_backend"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Set test environment variables before importing app modules
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test_secret_key_for_testing_purposes_only_32bytes"
os.environ["DEVICE_HMAC_SECRET"] = "esp32_super_secret_hmac_key_production_2026"
os.environ["ALERT_COOLDOWN_MINUTES"] = "15"

# Now import backend app components
from app.database import Base, get_db
from app.main import app
from app import models, auth
from app.services.jitter_filter import jitter_filter
from app.services.alert_throttler import alert_throttler
from app.services.arrhenius_engine import arrhenius_engine


# In-memory test engine using StaticPool so all connections share the same in-memory DB
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


@pytest.fixture(autouse=True)
def setup_database_and_reset_services():
    """
    Creates fresh database tables before each test and resets stateful service singletons.
    """
    Base.metadata.create_all(bind=TEST_ENGINE)
    jitter_filter.reset()
    alert_throttler.reset()
    arrhenius_engine.reset()
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture
def db_session():
    """Yields an isolated database session for direct model queries."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    """
    FastAPI TestClient with overridden get_db dependency and mocked external email sender.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Mock send_email globally so no test attempts SMTP connections
    with patch("app.services.email_service.send_email", return_value=True) as mock_send:
        with patch("app.services.alert_throttler.send_email", return_value=True):
            test_client = TestClient(app)
            test_client.mock_send_email = mock_send
            yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    """Creates a standard verified user account in the database."""
    hashed = auth.hash_password("Password123!")
    user = models.User(
        full_name="Dr. Eleanor Vance",
        email="eleanor.vance@cryo-storage.org",
        hashed_password=hashed,
        role="technician",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_token(test_user):
    """Generates a valid JWT access token for the test user."""
    return auth.create_access_token({"sub": str(test_user.id)})


@pytest.fixture
def auth_headers(auth_token):
    """HTTP authorization headers dict with Bearer token."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def test_cabinet(db_session):
    """Creates a standard configured cabinet setting."""
    cabinet = models.CabinetSetting(
        cabinet_location="CAB-A",
        target_temperature_c=22.0,
        target_humidity_percent=45.0,
        last_reported_temperature_c=22.1,
        last_reported_humidity_percent=44.8,
        last_reading_at=datetime.utcnow(),
    )
    db_session.add(cabinet)
    db_session.commit()
    db_session.refresh(cabinet)
    return cabinet


@pytest.fixture
def test_component(db_session, test_user, test_cabinet):
    """Creates an inventory component stored in the test cabinet."""
    comp = models.Component(
        batch_id="BATCH-STM32-001",
        part_number="STM32F407VGT6",
        manufacturer="STMicroelectronics",
        category="Microcontrollers",
        cabinet_location=test_cabinet.cabinet_location,
        quantity=50,
        stored_date=datetime.utcnow() - timedelta(days=30),
        last_accessed_date=datetime.utcnow() - timedelta(days=5),
        min_temperature_c=15.0,
        max_temperature_c=25.0,
        max_humidity_percent=50.0,
        shelf_life_days=365,
        owner_id=test_user.id,
    )
    db_session.add(comp)
    db_session.commit()
    db_session.refresh(comp)
    return comp
