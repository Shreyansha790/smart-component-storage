"""
Empirical Integration Challenge Suite for Milestone 2:
Arrhenius Kinetic Smart Logic & Dynamic FEFO Priority Queue.

Adversarial stress-testing of:
1. Exact Schema & Data Type Contract Compliance on GET /smart-logic/component/{id}
2. Multi-Cabinet Excursion Simulations (Thermal spikes > 25°C, Moisture spikes > 50%, Baseline)
3. Dynamic FEFO Priority Inversion (Heat-stressed newer batch prioritized ahead of older pristine batch)
4. Error Handling & Edge Cases (404 on missing component, non-existent cabinet fallback, auth gates)
5. Concurrent Queries & Race Condition Resilience under load
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from typing import Dict, Any
import pytest

from app import models
from app.services.arrhenius_engine import arrhenius_engine
from tests.helpers.hmac_helper import create_esp32_telemetry_request


@pytest.fixture
def multi_cabinet_setup(db_session, test_user):
    """
    Sets up 3 cabinets with distinct environmental profiles and associated test components.
    """
    today = date.today()

    # 1. Baseline Cabinet
    cab_baseline = models.CabinetSetting(
        cabinet_location="CAB-CHALLENGE-BASE",
        target_temperature_c=22.0,
        target_humidity_percent=40.0,
        last_reported_temperature_c=22.0,
        last_reported_humidity_percent=40.0,
        last_reading_at=datetime.utcnow(),
    )

    # 2. Thermal Stress Cabinet
    cab_thermal = models.CabinetSetting(
        cabinet_location="CAB-CHALLENGE-HEAT",
        target_temperature_c=25.0,
        target_humidity_percent=40.0,
        last_reported_temperature_c=45.0,
        last_reported_humidity_percent=40.0,
        last_reading_at=datetime.utcnow(),
    )

    # 3. Moisture Stress Cabinet
    cab_moisture = models.CabinetSetting(
        cabinet_location="CAB-CHALLENGE-HUMID",
        target_temperature_c=22.0,
        target_humidity_percent=40.0,
        last_reported_temperature_c=22.0,
        last_reported_humidity_percent=85.0,
        last_reading_at=datetime.utcnow(),
    )

    db_session.add_all([cab_baseline, cab_thermal, cab_moisture])

    # Component Baseline (stored 45 days ago, shelf life 365)
    comp_base = models.Component(
        batch_id="BATCH-BASE-001",
        part_number="STM32F405",
        manufacturer="STMicroelectronics",
        category="Microcontroller",
        cabinet_location="CAB-CHALLENGE-BASE",
        quantity=100,
        stored_date=today - timedelta(days=45),
        min_temperature_c=-40.0,
        max_temperature_c=85.0,
        max_humidity_percent=90.0,
        shelf_life_days=365,
        owner_id=test_user.id,
    )

    # Component Heat (stored 10 days ago, shelf life 365)
    comp_heat = models.Component(
        batch_id="BATCH-HEAT-002",
        part_number="STM32F405",
        manufacturer="STMicroelectronics",
        category="Microcontroller",
        cabinet_location="CAB-CHALLENGE-HEAT",
        quantity=50,
        stored_date=today - timedelta(days=10),
        min_temperature_c=-40.0,
        max_temperature_c=85.0,
        max_humidity_percent=90.0,
        shelf_life_days=365,
        owner_id=test_user.id,
    )

    # Component Humid (stored 20 days ago, shelf life 365)
    comp_humid = models.Component(
        batch_id="BATCH-HUMID-003",
        part_number="SHT31-DIS",
        manufacturer="Sensirion",
        category="Sensor",
        cabinet_location="CAB-CHALLENGE-HUMID",
        quantity=25,
        stored_date=today - timedelta(days=20),
        min_temperature_c=-40.0,
        max_temperature_c=125.0,
        max_humidity_percent=100.0,
        shelf_life_days=365,
        owner_id=test_user.id,
    )

    db_session.add_all([comp_base, comp_heat, comp_humid])
    db_session.commit()

    for item in [cab_baseline, cab_thermal, cab_moisture, comp_base, comp_heat, comp_humid]:
        db_session.refresh(item)

    return {
        "cab_baseline": cab_baseline,
        "cab_thermal": cab_thermal,
        "cab_moisture": cab_moisture,
        "comp_base": comp_base,
        "comp_heat": comp_heat,
        "comp_humid": comp_humid,
    }


class TestSmartLogicContractAndDataTypes:
    """Verifies strict contract compliance and exact data types for GET /smart-logic/component/{id}."""

    def test_contract_schema_and_types_exact_match(self, client, auth_headers, multi_cabinet_setup):
        """
        Verify all 9 contract fields, their exact types, and boundary sanity:
        component_id: int
        nominal_shelf_life_days: int
        stored_days: int
        cumulative_temp_stress_hours: float
        cumulative_humidity_stress_hours: float
        arrhenius_acceleration_factor: float
        dynamic_degradation_score: float
        effective_remaining_days: float
        status: str ('OPTIMAL' | 'APPROACHING_LIMIT' | 'CRITICAL' | 'EXPIRED')
        """
        comp = multi_cabinet_setup["comp_base"]
        response = client.get(f"/smart-logic/component/{comp.id}", headers=auth_headers)

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        # Contract field presence
        required_fields = {
            "component_id",
            "nominal_shelf_life_days",
            "stored_days",
            "cumulative_temp_stress_hours",
            "cumulative_humidity_stress_hours",
            "arrhenius_acceleration_factor",
            "dynamic_degradation_score",
            "effective_remaining_days",
            "status",
        }
        missing = required_fields - set(data.keys())
        assert not missing, f"Missing required fields: {missing}"

        # Exact type checks
        assert isinstance(data["component_id"], int)
        assert data["component_id"] == comp.id

        assert isinstance(data["nominal_shelf_life_days"], int)
        assert data["nominal_shelf_life_days"] == 365

        assert isinstance(data["stored_days"], int)
        assert data["stored_days"] == 45

        assert isinstance(data["cumulative_temp_stress_hours"], (float, int))
        assert isinstance(data["cumulative_humidity_stress_hours"], (float, int))
        assert isinstance(data["arrhenius_acceleration_factor"], (float, int))
        assert isinstance(data["dynamic_degradation_score"], (float, int))
        assert isinstance(data["effective_remaining_days"], (float, int))
        assert isinstance(data["status"], str)

        # Baseline value sanity
        assert data["cumulative_temp_stress_hours"] == 0.0
        assert data["cumulative_humidity_stress_hours"] == 0.0
        # At 22°C (below 25°C ref) and 40% RH, acceleration factor <= 1.0
        assert data["arrhenius_acceleration_factor"] <= 1.0
        assert data["effective_remaining_days"] == 320.0  # 365 - 45
        assert data["status"] == "OPTIMAL"
        assert 0.0 <= data["dynamic_degradation_score"] <= 1.0


class TestMultiCabinetExcursionSimulations:
    """Stress-tests telemetry history recording and multi-cabinet stress excursion tracking."""

    def test_thermal_and_humidity_stress_accumulates_independently(
        self, client, auth_headers, multi_cabinet_setup
    ):
        """
        Simulate realistic telemetry history across cabinets:
        1. CAB-CHALLENGE-HEAT receives 48 hours of 45°C thermal excursions (humidity normal at 40%).
        2. CAB-CHALLENGE-HUMID receives 36 hours of 80% RH moisture excursions (temp normal at 22°C).
        3. CAB-CHALLENGE-BASE receives pristine baseline conditions.
        """
        now = datetime.utcnow()

        # Inject heat excursions into CAB-CHALLENGE-HEAT: 4 readings across 48 hours
        arrhenius_engine.record_telemetry(
            cabinet_location="CAB-CHALLENGE-HEAT",
            temp_c=45.0,
            humidity_percent=40.0,
            timestamp=now - timedelta(hours=48),
        )
        arrhenius_engine.record_telemetry(
            cabinet_location="CAB-CHALLENGE-HEAT",
            temp_c=48.0,
            humidity_percent=40.0,
            timestamp=now - timedelta(hours=24),
        )
        arrhenius_engine.record_telemetry(
            cabinet_location="CAB-CHALLENGE-HEAT",
            temp_c=42.0,
            humidity_percent=40.0,
            timestamp=now,
        )

        # Inject humidity excursions into CAB-CHALLENGE-HUMID: 3 readings across 36 hours
        arrhenius_engine.record_telemetry(
            cabinet_location="CAB-CHALLENGE-HUMID",
            temp_c=22.0,
            humidity_percent=80.0,
            timestamp=now - timedelta(hours=36),
        )
        arrhenius_engine.record_telemetry(
            cabinet_location="CAB-CHALLENGE-HUMID",
            temp_c=22.0,
            humidity_percent=85.0,
            timestamp=now - timedelta(hours=12),
        )
        arrhenius_engine.record_telemetry(
            cabinet_location="CAB-CHALLENGE-HUMID",
            temp_c=22.0,
            humidity_percent=82.0,
            timestamp=now,
        )

        # 1. Query thermal stressed component
        comp_heat = multi_cabinet_setup["comp_heat"]
        res_heat = client.get(f"/smart-logic/component/{comp_heat.id}", headers=auth_headers)
        assert res_heat.status_code == 200
        data_heat = res_heat.json()

        assert data_heat["cumulative_temp_stress_hours"] >= 24.0, (
            f"Expected >= 24h temp stress, got {data_heat['cumulative_temp_stress_hours']}"
        )
        assert data_heat["cumulative_humidity_stress_hours"] == 0.0, (
            f"Expected 0h humidity stress, got {data_heat['cumulative_humidity_stress_hours']}"
        )
        assert data_heat["arrhenius_acceleration_factor"] > 1.0
        # Accelerated aging must reduce effective remaining days below nominal calendar days (365 - 10 = 355)
        assert data_heat["effective_remaining_days"] < 355.0

        # 2. Query humidity stressed component
        comp_humid = multi_cabinet_setup["comp_humid"]
        res_humid = client.get(f"/smart-logic/component/{comp_humid.id}", headers=auth_headers)
        assert res_humid.status_code == 200
        data_humid = res_humid.json()

        assert data_humid["cumulative_humidity_stress_hours"] >= 24.0, (
            f"Expected >= 24h humidity stress, got {data_humid['cumulative_humidity_stress_hours']}"
        )
        assert data_humid["cumulative_temp_stress_hours"] == 0.0, (
            f"Expected 0h temp stress, got {data_humid['cumulative_temp_stress_hours']}"
        )
        assert data_humid["arrhenius_acceleration_factor"] > 1.0
        # Accelerated aging must reduce effective remaining days below nominal calendar days (365 - 20 = 345)
        assert data_humid["effective_remaining_days"] < 345.0

        # 3. Query baseline component
        comp_base = multi_cabinet_setup["comp_base"]
        res_base = client.get(f"/smart-logic/component/{comp_base.id}", headers=auth_headers)
        assert res_base.status_code == 200
        data_base = res_base.json()

        assert data_base["cumulative_temp_stress_hours"] == 0.0
        assert data_base["cumulative_humidity_stress_hours"] == 0.0
        assert data_base["effective_remaining_days"] == 320.0

    def test_live_esp32_telemetry_post_feeds_arrhenius_history(
        self, client, auth_headers, multi_cabinet_setup
    ):
        """
        Verify that POST /cabinet/{loc}/telemetry with HMAC signature directly registers
        into Arrhenius stress hours tracking.
        """
        cab = multi_cabinet_setup["cab_baseline"]
        comp = multi_cabinet_setup["comp_base"]

        # Post an out-of-range thermal reading via authenticated ESP32 telemetry endpoint
        headers, body = create_esp32_telemetry_request(
            cabinet_location=cab.cabinet_location,
            temperature_c=50.0,
            humidity_percent=40.0,
        )
        post_resp = client.post(
            f"/cabinet/{cab.cabinet_location}/telemetry",
            content=body,
            headers=headers,
        )
        assert post_resp.status_code == 200

        # Now query GET /smart-logic/component/{id}
        resp = client.get(f"/smart-logic/component/{comp.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()

        # Instantaneous acceleration factor must reflect 50°C
        assert data["arrhenius_acceleration_factor"] > 3.0


class TestDynamicFefoPriorityInversionEmpirical:
    """Empirical verification of Dynamic FEFO queue reordering & priority inversion."""

    def test_heat_stressed_newer_batch_overtakes_older_batch_in_fefo(
        self, client, auth_headers, multi_cabinet_setup
    ):
        """
        EMPIRICAL ORACLE TEST:
        - Batch BASE: Stored 45 days ago, shelf life 365 days. Nominal remaining = 320 days.
        - Batch HEAT: Stored only 10 days ago, shelf life 365 days. Nominal remaining = 355 days.

        Under static calendar FEFO:
          Batch BASE (320 days) MUST appear before Batch HEAT (355 days).

        Under sustained severe thermal excursion (55°C, 70% RH for 300 hours) on Batch HEAT:
          Arrhenius kinetic acceleration degrades Batch HEAT drastically.
          Effective remaining days for Batch HEAT drops below 200 days (< 320 days).

        Mathematical oracle for FEFO queue:
          Batch HEAT MUST dynamically invert and appear ahead of Batch BASE!
        """
        comp_base = multi_cabinet_setup["comp_base"]
        comp_heat = multi_cabinet_setup["comp_heat"]

        # 1. Before stress: verify calendar order in /inventory?sort_by_fefo=true
        res_before = client.get("/inventory?sort_by_fefo=true", headers=auth_headers)
        assert res_before.status_code == 200
        items_before = res_before.json()
        batches_before = [item["batch_id"] for item in items_before]

        assert batches_before.index("BATCH-BASE-001") < batches_before.index("BATCH-HEAT-002"), (
            f"Expected BATCH-BASE-001 before BATCH-HEAT-002 initially, got {batches_before}"
        )

        # 2. Inject heavy stress into comp_heat: 300 hours of 55°C, 75% RH
        arrhenius_engine.add_component_stress_event(
            component_id=comp_heat.id,
            duration_hours=300.0,
            temp_c=55.0,
            humidity_percent=75.0,
        )

        # Verify degradation metrics via smart-logic endpoint
        heat_logic = client.get(f"/smart-logic/component/{comp_heat.id}", headers=auth_headers).json()
        assert heat_logic["effective_remaining_days"] < 320.0, (
            f"Expected effective remaining < 320, got {heat_logic['effective_remaining_days']}"
        )

        # 3. Test GET /inventory?sort_by_fefo=true after stress
        res_after_param = client.get("/inventory?sort_by_fefo=true", headers=auth_headers)
        assert res_after_param.status_code == 200
        items_after_param = res_after_param.json()
        batches_after_param = [item["batch_id"] for item in items_after_param]

        idx_heat = batches_after_param.index("BATCH-HEAT-002")
        idx_base = batches_after_param.index("BATCH-BASE-001")
        assert idx_heat < idx_base, (
            f"Priority inversion failed on ?sort_by_fefo=true! Expected BATCH-HEAT-002 before BATCH-BASE-001, got {batches_after_param}"
        )

        # 4. Test GET /inventory/fefo dedicated endpoint
        res_fefo_endpoint = client.get("/inventory/fefo", headers=auth_headers)
        assert res_fefo_endpoint.status_code == 200
        items_fefo_endpoint = res_fefo_endpoint.json()
        batches_fefo = [item["batch_id"] for item in items_fefo_endpoint]

        idx_fefo_heat = batches_fefo.index("BATCH-HEAT-002")
        idx_fefo_base = batches_fefo.index("BATCH-BASE-001")
        assert idx_fefo_heat < idx_fefo_base, (
            f"Priority inversion failed on /inventory/fefo! Expected BATCH-HEAT-002 before BATCH-BASE-001, got {batches_fefo}"
        )

    def test_inventory_fefo_filtered_by_category_and_cabinet(
        self, client, auth_headers, multi_cabinet_setup
    ):
        """Verify GET /inventory/fefo respects category and cabinet_location query parameters."""
        # Filter by Microcontroller category
        res_cat = client.get("/inventory/fefo?category=Microcontroller", headers=auth_headers)
        assert res_cat.status_code == 200
        items_cat = res_cat.json()
        assert len(items_cat) >= 2
        for item in items_cat:
            assert item["category"] == "Microcontroller"

        # Filter by Cabinet location
        res_loc = client.get("/inventory/fefo?cabinet_location=CAB-CHALLENGE-HEAT", headers=auth_headers)
        assert res_loc.status_code == 200
        items_loc = res_loc.json()
        assert len(items_loc) == 1
        assert items_loc[0]["cabinet_location"] == "CAB-CHALLENGE-HEAT"


class TestErrorHandlingAndEdgeCases:
    """Stress-tests non-existent entities, unauthenticated access, and boundary conditions."""

    def test_nonexistent_component_returns_404(self, client, auth_headers):
        """GET /smart-logic/component/999999 must return 404 with helpful error detail."""
        res = client.get("/smart-logic/component/999999", headers=auth_headers)
        assert res.status_code == 404
        assert "not found" in res.json().get("detail", "").lower()

    def test_negative_component_id_returns_404(self, client, auth_headers):
        """GET /smart-logic/component/-1 must return 404."""
        res = client.get("/smart-logic/component/-1", headers=auth_headers)
        assert res.status_code == 404

    def test_non_integer_component_id_returns_422(self, client, auth_headers):
        """GET /smart-logic/component/invalid-alpha must return 422 Unprocessable Entity."""
        res = client.get("/smart-logic/component/invalid-alpha", headers=auth_headers)
        assert res.status_code == 422

    def test_unauthenticated_requests_return_401(self, client, multi_cabinet_setup):
        """Protected endpoints must reject requests lacking Authorization header."""
        comp = multi_cabinet_setup["comp_base"]

        # GET /smart-logic/component/{id}
        res_logic = client.get(f"/smart-logic/component/{comp.id}")
        assert res_logic.status_code == 401

        # GET /inventory/fefo
        res_fefo = client.get("/inventory/fefo")
        assert res_fefo.status_code == 401

    def test_component_in_nonexistent_cabinet_falls_back_safely(
        self, client, db_session, test_user, auth_headers
    ):
        """
        If a component references a cabinet_location with no CabinetSetting row,
        GET /smart-logic/component/{id} must not crash (no 500), but fall back to
        nominal baseline conditions safely.
        """
        ghost_comp = models.Component(
            batch_id="BATCH-GHOST-CAB",
            part_number="TEST-IC-01",
            manufacturer="Generic",
            category="IC",
            cabinet_location="CAB-GHOST-DOES-NOT-EXIST",
            quantity=10,
            stored_date=date.today() - timedelta(days=20),
            min_temperature_c=0.0,
            max_temperature_c=50.0,
            max_humidity_percent=80.0,
            shelf_life_days=100,
            owner_id=test_user.id,
        )
        db_session.add(ghost_comp)
        db_session.commit()
        db_session.refresh(ghost_comp)

        res = client.get(f"/smart-logic/component/{ghost_comp.id}", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["component_id"] == ghost_comp.id
        assert data["stored_days"] == 20
        assert data["nominal_shelf_life_days"] == 100
        assert data["effective_remaining_days"] == 80.0
        assert data["status"] == "OPTIMAL"

    def test_expired_component_lifecycle_boundary(
        self, client, db_session, test_user, auth_headers
    ):
        """
        Verify status and degradation score when component has exceeded shelf life:
        effective_remaining_days == 0.0, dynamic_degradation_score == 1.0, status == 'EXPIRED'.
        """
        expired_comp = models.Component(
            batch_id="BATCH-EXPIRED-99",
            part_number="OLD-CAPACITOR",
            manufacturer="Nichicon",
            category="Capacitor",
            cabinet_location="CAB-CHALLENGE-BASE",
            quantity=5,
            stored_date=date.today() - timedelta(days=400),
            min_temperature_c=-20.0,
            max_temperature_c=85.0,
            max_humidity_percent=90.0,
            shelf_life_days=365,
            owner_id=test_user.id,
        )
        db_session.add(expired_comp)
        db_session.commit()
        db_session.refresh(expired_comp)

        res = client.get(f"/smart-logic/component/{expired_comp.id}", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()

        assert data["effective_remaining_days"] == 0.0
        assert data["dynamic_degradation_score"] == 1.0
        assert data["status"] == "EXPIRED"

    def test_critical_and_approaching_limit_lifecycle_boundaries(
        self, client, db_session, test_user, auth_headers
    ):
        """
        Verify status boundaries:
        - <= 10% remaining -> 'CRITICAL'
        - <= 30% remaining -> 'APPROACHING_LIMIT'
        - > 30% remaining -> 'OPTIMAL'
        """
        # Comp 1: 95% consumed -> 5% remaining (CRITICAL)
        comp_critical = models.Component(
            batch_id="BATCH-CRIT-01",
            part_number="CRIT-IC",
            manufacturer="TI",
            category="IC",
            cabinet_location="CAB-CHALLENGE-BASE",
            quantity=10,
            stored_date=date.today() - timedelta(days=95),
            min_temperature_c=-20.0,
            max_temperature_c=85.0,
            max_humidity_percent=90.0,
            shelf_life_days=100,
            owner_id=test_user.id,
        )

        # Comp 2: 80% consumed -> 20% remaining (APPROACHING_LIMIT)
        comp_limit = models.Component(
            batch_id="BATCH-LIMIT-02",
            part_number="LIMIT-IC",
            manufacturer="TI",
            category="IC",
            cabinet_location="CAB-CHALLENGE-BASE",
            quantity=10,
            stored_date=date.today() - timedelta(days=80),
            min_temperature_c=-20.0,
            max_temperature_c=85.0,
            max_humidity_percent=90.0,
            shelf_life_days=100,
            owner_id=test_user.id,
        )

        db_session.add_all([comp_critical, comp_limit])
        db_session.commit()
        db_session.refresh(comp_critical)
        db_session.refresh(comp_limit)

        data_crit = client.get(f"/smart-logic/component/{comp_critical.id}", headers=auth_headers).json()
        assert data_crit["status"] == "CRITICAL"
        assert data_crit["effective_remaining_days"] == 5.0

        data_limit = client.get(f"/smart-logic/component/{comp_limit.id}", headers=auth_headers).json()
        assert data_limit["status"] == "APPROACHING_LIMIT"
        assert data_limit["effective_remaining_days"] == 20.0


class TestConcurrentQueriesAndRaceConditions:
    """Stress-tests concurrent reads and interleaved telemetry updates."""

    def test_concurrent_smart_logic_and_fefo_queries_under_load(
        self, client, auth_headers, multi_cabinet_setup
    ):
        """
        Spawn 8 parallel threads executing 40 concurrent queries across:
        - GET /smart-logic/component/{id}
        - GET /inventory/fefo
        - GET /inventory?sort_by_fefo=true

        Asserts 100% success rate (200 OK) with zero deadlocks or unhandled exceptions.
        """
        comp = multi_cabinet_setup["comp_base"]
        endpoints = [
            f"/smart-logic/component/{comp.id}",
            "/inventory/fefo",
            "/inventory?sort_by_fefo=true",
        ]

        def worker_query(url: str) -> int:
            resp = client.get(url, headers=auth_headers)
            return resp.status_code

        futures = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            for i in range(40):
                target_url = endpoints[i % len(endpoints)]
                futures.append(executor.submit(worker_query, target_url))

            results = [f.result() for f in as_completed(futures)]

        assert len(results) == 40
        assert all(status == 200 for status in results), (
            f"Some concurrent queries failed! Status distribution: {set(results)}"
        )

    def test_concurrent_telemetry_writes_interleaved_with_fefo_reads(
        self, client, auth_headers, multi_cabinet_setup
    ):
        """
        Adversarial Concurrency Stress:
        Interleave concurrent telemetry writes to arrhenius_engine while reading
        from GET /smart-logic/component/{id} and arrhenius_engine.evaluate_component.
        Verifies thread safety of arrhenius_engine._cabinet_history and prevents
        'RuntimeError: dictionary changed size during iteration' under rapid streaming.
        """
        comp = multi_cabinet_setup["comp_heat"]
        cab = multi_cabinet_setup["cab_thermal"]

        def write_worker(idx: int):
            now = datetime.utcnow()
            arrhenius_engine.record_telemetry(
                cabinet_location=cab.cabinet_location,
                temp_c=30.0 + (idx % 20),
                humidity_percent=40.0 + (idx % 40),
                timestamp=now + timedelta(seconds=idx),
            )
            return True

        def read_worker():
            eval_res = arrhenius_engine.evaluate_component(component=comp, cabinet=cab)
            return eval_res["status"]

        futures = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            for i in range(100):
                if i % 2 == 0:
                    futures.append(executor.submit(write_worker, i))
                else:
                    futures.append(executor.submit(read_worker))

            results = [f.result() for f in as_completed(futures)]

        assert len(results) == 100, f"Expected 100 results, got {len(results)}"



class TestAdversarialKineticEdgeCases:
    """Stress-tests mathematical boundaries, extreme inputs, and runtime mutations."""

    def test_subzero_and_extreme_high_temperature_stability(
        self, client, auth_headers, multi_cabinet_setup
    ):
        """
        Adversarial physical boundaries:
        - Subzero (-20°C): AF < 1.0 must never produce negative stress hours or increase remaining days.
        - High Heat (85°C): AF ~ 140x must smoothly clamp degradation to EXPIRED (score 1.0, remaining 0.0)
          without NaN, Infinity, or JSON serialization errors.
        """
        comp = multi_cabinet_setup["comp_base"]

        # Subzero test: inject cold event
        arrhenius_engine.add_component_stress_event(
            component_id=comp.id,
            duration_hours=50.0,
            temp_c=-20.0,
            humidity_percent=30.0,
        )
        res_cold = client.get(f"/smart-logic/component/{comp.id}", headers=auth_headers).json()
        assert res_cold["cumulative_temp_stress_hours"] == 0.0, "Subzero temp must not count as temp stress"
        assert res_cold["effective_remaining_days"] <= 320.0, "Cold must not increase shelf life"
        assert res_cold["dynamic_degradation_score"] >= 0.0

        # High heat test: inject extreme heat
        arrhenius_engine.add_component_stress_event(
            component_id=comp.id,
            duration_hours=500.0,
            temp_c=85.0,
            humidity_percent=90.0,
        )
        res_hot = client.get(f"/smart-logic/component/{comp.id}", headers=auth_headers).json()
        assert res_hot["effective_remaining_days"] == 0.0
        assert res_hot["dynamic_degradation_score"] == 1.0
        assert res_hot["status"] == "EXPIRED"

    def test_multi_batch_complex_4way_fefo_priority_oracle(
        self, client, auth_headers, db_session, test_user
    ):
        """
        ORACLE TEST: 4-Way Complex Dynamic FEFO Priority Inversion.
        Create 4 batches:
        - B1: Stored 100 days ago, shelf life 200 days, 0 stress -> nominal remaining = 100d.
        - B2: Stored 50 days ago, shelf life 200 days, severe heat stress -> effective remaining = 40d.
        - B3: Stored 10 days ago, shelf life 200 days, catastrophic heat stress -> effective remaining = 10d.
        - B4: Stored 5 days ago, shelf life 200 days, 0 stress -> nominal remaining = 195d.

        Naive calendar order:
          [B1 (100d), B2 (150d), B3 (190d), B4 (195d)]

        Empirical Dynamic FEFO order:
          MUST strictly be [B3 (10d), B2 (40d), B1 (100d), B4 (195d)]!
        """
        today = date.today()
        batches = [
            ("BATCH-4WAY-B1", 100, 200),
            ("BATCH-4WAY-B2", 50, 200),
            ("BATCH-4WAY-B3", 10, 200),
            ("BATCH-4WAY-B4", 5, 200),
        ]
        comp_objs = []
        for batch_id, stored_d, shelf_life in batches:
            c = models.Component(
                batch_id=batch_id,
                part_number="PART-4WAY",
                manufacturer="OracleSemi",
                category="IC",
                cabinet_location="CAB-CHALLENGE-BASE",
                quantity=10,
                stored_date=today - timedelta(days=stored_d),
                min_temperature_c=0.0,
                max_temperature_c=70.0,
                max_humidity_percent=85.0,
                shelf_life_days=shelf_life,
                owner_id=test_user.id,
            )
            comp_objs.append(c)
            db_session.add(c)
        db_session.commit()
        for c in comp_objs:
            db_session.refresh(c)

        # Inject severe stress on B2: 50 nominal stored + 110 effective aging days = 160d stored -> 40d remaining
        # (duration 70h at 50°C, 60% RH -> AF ~ 14.5 -> additional aging = 70 * 13.5 / 24 = ~39.4 days)
        arrhenius_engine.add_component_stress_event(
            component_id=comp_objs[1].id,
            duration_hours=195.0,
            temp_c=50.0,
            humidity_percent=60.0,
        )

        # Inject catastrophic stress on B3: 10 nominal stored + 180 effective aging days = 190d stored -> 10d remaining
        arrhenius_engine.add_component_stress_event(
            component_id=comp_objs[2].id,
            duration_hours=320.0,
            temp_c=55.0,
            humidity_percent=75.0,
        )

        # Query GET /inventory/fefo
        res = client.get("/inventory/fefo?search=PART-4WAY", headers=auth_headers)
        assert res.status_code == 200
        items = res.json()
        ordered_batches = [item["batch_id"] for item in items]

        assert ordered_batches == [
            "BATCH-4WAY-B3",
            "BATCH-4WAY-B2",
            "BATCH-4WAY-B1",
            "BATCH-4WAY-B4",
        ], f"Dynamic 4-Way FEFO sorting mismatch! Got {ordered_batches}"

    def test_dynamic_recalculation_on_cabinet_relocation_patch(
        self, client, auth_headers, multi_cabinet_setup
    ):
        """
        Verify that relocating a component via PATCH /inventory/{id} immediately
        causes GET /smart-logic/component/{id} to re-evaluate under the new cabinet.
        """
        comp = multi_cabinet_setup["comp_base"]

        # Initially in baseline cabinet
        r1 = client.get(f"/smart-logic/component/{comp.id}", headers=auth_headers).json()
        assert r1["arrhenius_acceleration_factor"] <= 1.0

        # Move to thermal stress cabinet (CAB-CHALLENGE-HEAT at 45°C)
        patch_res = client.patch(
            f"/inventory/{comp.id}",
            json={"cabinet_location": "CAB-CHALLENGE-HEAT"},
            headers=auth_headers,
        )
        assert patch_res.status_code == 200

        # Re-query smart logic: acceleration factor must immediately reflect 45°C (> 2.0)
        r2 = client.get(f"/smart-logic/component/{comp.id}", headers=auth_headers).json()
        assert r2["arrhenius_acceleration_factor"] > 2.0

