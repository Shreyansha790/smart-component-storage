"""
Tier 2 Integration Tests: Arrhenius Degradation Model & Smart Logic / Inventory Routes.

Verifies:
1. GET /smart-logic/component/{component_id} returns ArrheniusDegradationOut matching PROJECT.md § Interface Contracts.
2. GET /inventory returns effective_remaining_days and dynamic_degradation_score on ComponentOut.
3. GET /inventory with sort_by_fefo=True and GET /inventory/fefo prioritize dynamically degraded components.
4. Cumulative stress tracking via telemetry ingestion accelerates aging and updates degradation metrics.
"""

from datetime import date, timedelta
import pytest
from app import models
from app.services.arrhenius_engine import arrhenius_engine


@pytest.fixture
def test_cabinet_and_components(db_session, test_user):
    """Sets up a cabinet and test components with different baseline and stressed shelf life."""
    cab = models.CabinetSetting(
        cabinet_location="CAB-ARR-1",
        target_temperature_c=25.0,
        target_humidity_percent=40.0,
        last_reported_temperature_c=25.0,
        last_reported_humidity_percent=40.0,
    )
    db_session.add(cab)

    today = date.today()

    # Component A: Stored 60 days ago, nominal shelf life 180 days
    comp_a = models.Component(
        batch_id="BATCH-A-NOMINAL",
        part_number="STM32F401",
        manufacturer="STMicroelectronics",
        category="Microcontroller",
        cabinet_location="CAB-ARR-1",
        quantity=50,
        stored_date=today - timedelta(days=60),
        min_temperature_c=0.0,
        max_temperature_c=70.0,
        max_humidity_percent=85.0,
        shelf_life_days=180,
        owner_id=test_user.id,
    )

    # Component B: Stored 30 days ago, nominal shelf life 180 days
    comp_b = models.Component(
        batch_id="BATCH-B-HEAT",
        part_number="STM32F401",
        manufacturer="STMicroelectronics",
        category="Microcontroller",
        cabinet_location="CAB-ARR-1",
        quantity=30,
        stored_date=today - timedelta(days=30),
        min_temperature_c=0.0,
        max_temperature_c=70.0,
        max_humidity_percent=85.0,
        shelf_life_days=180,
        owner_id=test_user.id,
    )

    db_session.add(comp_a)
    db_session.add(comp_b)
    db_session.commit()
    db_session.refresh(comp_a)
    db_session.refresh(comp_b)
    db_session.refresh(cab)

    return cab, comp_a, comp_b


class TestArrheniusSmartLogicRoutes:
    """Verifies Smart Logic endpoint compliance with Arrhenius degradation contracts."""

    def test_smart_logic_returns_arrhenius_degradation_contract(
        self, client, auth_headers, test_cabinet_and_components
    ):
        """GET /smart-logic/component/{id} must return exact ArrheniusDegradationOut schema."""
        _, comp_a, _ = test_cabinet_and_components

        response = client.get(
            f"/smart-logic/component/{comp_a.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()

        # Contract fields validation
        expected_fields = [
            "component_id",
            "nominal_shelf_life_days",
            "stored_days",
            "cumulative_temp_stress_hours",
            "cumulative_humidity_stress_hours",
            "arrhenius_acceleration_factor",
            "dynamic_degradation_score",
            "effective_remaining_days",
            "status",
        ]
        for field in expected_fields:
            assert field in data, f"Missing expected contract field: {field}"

        assert data["component_id"] == comp_a.id
        assert data["nominal_shelf_life_days"] == 180
        assert data["stored_days"] == 60
        assert data["arrhenius_acceleration_factor"] == 1.0  # At 25°C, 40% RH baseline
        assert data["effective_remaining_days"] == 120.0
        assert pytest.approx(data["dynamic_degradation_score"], rel=1e-2) == 60 / 180
        assert data["status"] == "OPTIMAL"

    def test_smart_logic_nonexistent_component_returns_404(self, client, auth_headers):
        """GET /smart-logic/component/999999 returns 404."""
        response = client.get("/smart-logic/component/999999", headers=auth_headers)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_smart_logic_reflects_thermal_stress_hours(
        self, client, auth_headers, test_cabinet_and_components
    ):
        """Component with injected stress events shows elevated acceleration and reduced remaining days."""
        _, _, comp_b = test_cabinet_and_components

        # Inject 72 hours of 50°C thermal stress
        arrhenius_engine.add_component_stress_event(
            component_id=comp_b.id,
            duration_hours=72.0,
            temp_c=50.0,
            humidity_percent=40.0,
        )

        response = client.get(
            f"/smart-logic/component/{comp_b.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()

        assert data["component_id"] == comp_b.id
        assert data["cumulative_temp_stress_hours"] == 72.0
        # Effective remaining days must be less than nominal (180 - 30 = 150)
        assert data["effective_remaining_days"] < 150.0
        assert data["dynamic_degradation_score"] > (30 / 180)

    def test_inventory_list_includes_dynamic_degradation_fields(
        self, client, auth_headers, test_cabinet_and_components
    ):
        """GET /inventory returns ComponentOut with dynamic degradation fields."""
        response = client.get("/inventory", headers=auth_headers)
        assert response.status_code == 200
        items = response.json()
        assert len(items) >= 2

        for item in items:
            assert "effective_remaining_days" in item
            assert "dynamic_degradation_score" in item
            assert item["effective_remaining_days"] is not None
            assert item["dynamic_degradation_score"] is not None

    def test_dynamic_fefo_sorting_inversion_via_routes(
        self, client, auth_headers, test_cabinet_and_components
    ):
        """
        Under naive FEFO:
          Batch A (stored 60d, remaining 120d) comes BEFORE Batch B (stored 30d, remaining 150d).
        With severe thermal stress on Batch B:
          Batch B degrades faster, dynamic remaining days drops below Batch A,
          so Batch B is dispatched FIRST!
        """
        _, comp_a, comp_b = test_cabinet_and_components

        # Inject extreme stress on comp_b so its effective remaining days drops below comp_a
        arrhenius_engine.add_component_stress_event(
            component_id=comp_b.id,
            duration_hours=700.0,
            temp_c=55.0,
            humidity_percent=70.0,
        )

        # 1. Test GET /inventory?sort_by_fefo=true
        resp_fefo_param = client.get("/inventory?sort_by_fefo=true", headers=auth_headers)
        assert resp_fefo_param.status_code == 200
        fefo_items = resp_fefo_param.json()

        # Comp B must appear before Comp A because of Arrhenius degradation!
        batch_ids = [item["batch_id"] for item in fefo_items]
        idx_b = batch_ids.index("BATCH-B-HEAT")
        idx_a = batch_ids.index("BATCH-A-NOMINAL")
        assert idx_b < idx_a, f"Expected BATCH-B-HEAT before BATCH-A-NOMINAL in FEFO queue, got {batch_ids}"

        # 2. Test GET /inventory/fefo dedicated endpoint
        resp_fefo_route = client.get("/inventory/fefo", headers=auth_headers)
        assert resp_fefo_route.status_code == 200
        route_items = resp_fefo_route.json()
        route_batch_ids = [item["batch_id"] for item in route_items]
        assert route_batch_ids.index("BATCH-B-HEAT") < route_batch_ids.index("BATCH-A-NOMINAL")
