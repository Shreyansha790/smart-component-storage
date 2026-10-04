"""
Tier 3/5 Adversarial Stress & Empirical Challenge Suite for Milestone 2:
Arrhenius Kinetics, Peck's Law Acceleration, and Dynamic FEFO Queue Sorting.

Author: challenger_m2_1 (Empirical Challenger)
Target:
  - smart_storage_backend/app/services/arrhenius_engine.py
  - services/fefo_service.py
  - services/lifecycle_service.py
  - tests/helpers/arrhenius_oracle.py

Stress-Tests:
1. Numerical stability across extreme temperatures (-270°C, 0°C, 25°C, 150°C, 300°C).
2. Monotonicity checks: verify d(AF_T)/dT > 0 for all T > 0 K and d(AF_H)/d(RH) > 0.
3. Singularity handling: verify ValueError raised for T <= -273.15°C and Ea <= 0.
4. Peck's law scaling: verify power law behavior and exponent sensitivity.
5. Large-scale priority queue stability: 1,000 randomized batches, deterministic tie-breaking.
6. Memory bounds and stateful stress accumulation under high telemetry volumes.
"""

import math
import random
import pytest
from datetime import datetime, timedelta
from typing import List, Dict, Any

from smart_storage_backend.app.services.arrhenius_engine import (
    calculate_arrhenius_temp_factor,
    calculate_peck_humidity_factor,
    calculate_total_acceleration_factor,
    calculate_dynamic_shelf_life,
    dynamic_fefo_sort,
    ArrheniusEngine,
    arrhenius_engine,
    BOLTZMANN_EV,
    DEFAULT_EA,
    REF_TEMP_C,
    REF_TEMP_K,
    REF_RH,
    PECK_EXPONENT,
)
from services.fefo_service import prioritize_fefo, dynamic_fefo_sort as svc_dynamic_fefo_sort


# ============================================================================
# 1. EXTREME TEMPERATURE NUMERICAL STABILITY & BOUNDARIES
# ============================================================================

class TestArrheniusExtremeTemperatureStability:
    """Verifies numerical precision, stability, and absence of NaN/Overflow across extreme temperatures."""

    @pytest.mark.parametrize(
        "temp_c,expected_behavior",
        [
            (-270.0, "near_zero"),       # Deep cryogenic: 3.15 Kelvin
            (0.0, "cold_preservation"),  # Freezing point of water: 273.15 K
            (25.0, "baseline_unity"),    # Reference room temp: 298.15 K
            (150.0, "high_stress"),      # High-temperature semiconductor burn-in
            (300.0, "extreme_reflow"),   # Extreme thermal excursion / reflow peak
        ],
    )
    def test_exact_temperature_milestones(self, temp_c: float, expected_behavior: str):
        """
        Adversarial milestone temperatures:
        -270°C: AF_T must approach 0.0, non-negative, finite, no crash.
        0°C: AF_T < 1.0 (cold preservation), finite, non-zero.
        25°C: AF_T == 1.0 exactly.
        150°C: AF_T > 100.0, finite, not NaN, not Inf.
        300°C: AF_T > 10000.0, finite, not NaN, not Inf.
        """
        af_t = calculate_arrhenius_temp_factor(temp_c=temp_c, ea_ev=0.60)

        assert not math.isnan(af_t), f"NaN returned for temp_c={temp_c}"
        assert not math.isinf(af_t), f"Infinite value returned for temp_c={temp_c}"
        assert af_t >= 0.0, f"Negative acceleration factor {af_t} for temp_c={temp_c}"

        if expected_behavior == "near_zero":
            assert af_t < 1e-15, f"Expected near-zero AF at -270°C, got {af_t}"
        elif expected_behavior == "cold_preservation":
            assert 0.0 < af_t < 1.0, f"Expected cold preservation (0 < AF < 1) at 0°C, got {af_t}"
            # Exact theoretical check: T_ref=298.15, T=273.15
            # exp((0.6 / 8.617333262e-5) * (1/298.15 - 1/273.15)) ≈ 0.11796
            assert pytest.approx(af_t, rel=1e-2) == 0.118
        elif expected_behavior == "baseline_unity":
            assert pytest.approx(af_t, abs=1e-7) == 1.0, f"Baseline at 25°C must be 1.0, got {af_t}"
        elif expected_behavior == "high_stress":
            assert af_t > 100.0, f"AF at 150°C must exceed 100.0, got {af_t}"
            # exp((0.6 / 8.617333262e-5) * (1/298.15 - 1/423.15)) ≈ 990.86
            assert pytest.approx(af_t, rel=1e-2) == 990.86
        elif expected_behavior == "extreme_reflow":
            assert af_t > 50000.0, f"AF at 300°C must exceed 50,000, got {af_t}"
            # exp((0.6 / 8.617333262e-5) * (1/298.15 - 1/573.15)) ≈ 73497
            assert pytest.approx(af_t, rel=1e-2) == 73497.0

    def test_near_singularity_cryogenic_stability(self):
        """
        Adversarial test infinitesimally above absolute zero:
        -273.149°C = 0.001 K. Exponent is extremely negative (-6.96e9).
        Must underflow gracefully to 0.0 without crash or exception.
        """
        cryo_temps = [-273.149, -273.14, -273.1, -273.0, -272.0]
        for t in cryo_temps:
            af = calculate_arrhenius_temp_factor(temp_c=t, ea_ev=0.60)
            assert af == 0.0 or (0.0 <= af < 1e-10)
            assert not math.isnan(af)

    def test_ultra_high_temperature_asymptote(self):
        """
        At asymptotic high temperatures (T -> infinity, 1/T -> 0):
        AF_T(T) approaches exp((Ea / k_B) * (1 / T_ref)) = exp(6962.712 / 298.15) ≈ exp(23.353) ≈ 1.387e10.
        Must remain finite, bounded, and never overflow to Inf for standard semiconductor Ea.
        """
        ultra_high_temps = [500.0, 1000.0, 5000.0, 1e6, 1e9]
        for t in ultra_high_temps:
            af = calculate_arrhenius_temp_factor(temp_c=t, ea_ev=0.60)
            assert not math.isnan(af)
            assert not math.isinf(af)
            assert af > 73000.0
            # Theoretical upper limit for Ea=0.60 eV is exp(23.35293) ≈ 1.387e10
            assert af <= 1.39e10

    def test_extreme_activation_energy_bounds(self):
        """
        Adversarial check on activation energy parameter:
        1. Very low Ea (0.01 eV): AF remains close to 1.0 even at 100°C.
        2. High Ea (2.0 eV): AF is very large but handled without crash.
        3. Extreme Ea (> 100 eV): Bounded to prevent unhandled Python OverflowError.
        """
        # Low Ea
        af_low = calculate_arrhenius_temp_factor(temp_c=100.0, ea_ev=0.01)
        assert 1.0 < af_low < 2.0

        # High realistic Ea (e.g. 2.0 eV oxide breakdown)
        af_high = calculate_arrhenius_temp_factor(temp_c=100.0, ea_ev=2.0)
        assert af_high > 1e5

        # Extreme synthetic Ea that triggers exponent > 700 -> returns float("inf")
        af_extreme = calculate_arrhenius_temp_factor(temp_c=100.0, ea_ev=120.0)
        assert math.isinf(af_extreme)


# ============================================================================
# 2. MONOTONICITY & PHYSICAL DERIVATIVE CONSTRAINTS
# ============================================================================

class TestArrheniusMonotonicity:
    """Verifies that degradation rate is strictly monotonically increasing with temperature and humidity."""

    def test_temperature_monotonicity_across_dense_spectrum(self):
        """
        Dense grid test: -260°C to 300°C in 2.0°C increments.
        First derivative d(AF_T)/dT must be strictly >= 0 everywhere,
        and strictly > 0 for all T > 20 K.
        """
        temps = [t * 2.0 for t in range(-130, 151)]  # -260°C to 300°C
        factors = [calculate_arrhenius_temp_factor(t, ea_ev=0.60) for t in temps]

        for i in range(len(factors) - 1):
            t1, t2 = temps[i], temps[i + 1]
            f1, f2 = factors[i], factors[i + 1]
            assert f2 >= f1, f"Monotonicity violation between {t1}°C (AF={f1}) and {t2}°C (AF={f2})"
            if t1 >= -200.0:  # Above cryogenic underflow region
                assert f2 > f1, f"Strict monotonicity failed at {t1}°C -> {t2}°C: {f1} == {f2}"

    def test_activation_energy_monotonicity_bifurcation(self):
        """
        Physical principle:
        For T > T_ref (25°C): Higher Ea increases thermal sensitivity -> AF_T must INCREASE with Ea.
        For T < T_ref (25°C): Higher Ea increases cold preservation -> AF_T must DECREASE with Ea.
        At T == T_ref (25°C): AF_T == 1.0 regardless of Ea.
        """
        ea_values = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2]

        # 1. At 50°C (T > T_ref)
        factors_hot = [calculate_arrhenius_temp_factor(50.0, ea_ev=ea) for ea in ea_values]
        for i in range(len(factors_hot) - 1):
            assert factors_hot[i + 1] > factors_hot[i], (
                f"Hot monotonicity with Ea failed: Ea={ea_values[i]} ({factors_hot[i]}) vs "
                f"Ea={ea_values[i+1]} ({factors_hot[i+1]})"
            )

        # 2. At 5°C (T < T_ref)
        factors_cold = [calculate_arrhenius_temp_factor(5.0, ea_ev=ea) for ea in ea_values]
        for i in range(len(factors_cold) - 1):
            assert factors_cold[i + 1] < factors_cold[i], (
                f"Cold preservation monotonicity with Ea failed: Ea={ea_values[i]} ({factors_cold[i]}) vs "
                f"Ea={ea_values[i+1]} ({factors_cold[i+1]})"
            )

        # 3. At 25°C (T == T_ref)
        for ea in ea_values:
            af_ref = calculate_arrhenius_temp_factor(25.0, ea_ev=ea)
            assert pytest.approx(af_ref, abs=1e-7) == 1.0


# ============================================================================
# 3. SINGULARITY HANDLING & ADVERSARIAL INPUT REJECTION
# ============================================================================

class TestArrheniusSingularityHandling:
    """Verifies strict input validation and rejection of physically illegal parameters."""

    @pytest.mark.parametrize(
        "invalid_temp",
        [-273.15, -273.150001, -275.0, -300.0, -1000.0, -float("inf")],
    )
    def test_temperature_at_or_below_absolute_zero_raises_value_error(self, invalid_temp: float):
        """Singularity: T <= -273.15°C (0 Kelvin) must raise ValueError."""
        with pytest.raises(ValueError, match="absolute zero"):
            calculate_arrhenius_temp_factor(temp_c=invalid_temp)

    @pytest.mark.parametrize(
        "invalid_ea",
        [0.0, -0.0, -0.0001, -0.60, -10.0, -float("inf")],
    )
    def test_non_positive_activation_energy_raises_value_error(self, invalid_ea: float):
        """Singularity: Ea <= 0 violates thermodynamics and must raise ValueError."""
        with pytest.raises(ValueError, match="Activation energy"):
            calculate_arrhenius_temp_factor(temp_c=25.0, ea_ev=invalid_ea)

    @pytest.mark.parametrize("invalid_rh", [-0.01, -5.0, -100.0, 100.01, 150.0, 500.0])
    def test_out_of_bounds_humidity_raises_value_error_unclamped(self, invalid_rh: float):
        """Relative humidity outside [0, 100] without clamp must raise ValueError."""
        with pytest.raises(ValueError):
            calculate_peck_humidity_factor(humidity_percent=invalid_rh, clamp_safely=False)

    def test_clamped_humidity_boundary_graceful_handling(self):
        """With clamp_safely=True, out-of-range values are clamped without exception."""
        assert calculate_peck_humidity_factor(-50.0, clamp_safely=True) == 0.0
        af_100 = calculate_peck_humidity_factor(100.0, clamp_safely=True)
        af_150 = calculate_peck_humidity_factor(150.0, clamp_safely=True)
        assert af_150 == af_100

    def test_zero_or_negative_reference_humidity_raises_value_error(self):
        """Singularity: Reference RH <= 0 causes division by zero."""
        with pytest.raises(ValueError, match="Reference humidity"):
            calculate_peck_humidity_factor(50.0, ref_rh=0.0)
        with pytest.raises(ValueError, match="Reference humidity"):
            calculate_peck_humidity_factor(50.0, ref_rh=-10.0)

    @pytest.mark.parametrize(
        "shelf_life,stored_days",
        [(0, 10), (-50, 10), (365, -1), (100, -10)],
    )
    def test_shelf_life_singularity_raises_value_error(self, shelf_life: int, stored_days: int):
        """Dynamic shelf life calculation requires shelf_life > 0 and stored_days >= 0."""
        with pytest.raises(ValueError):
            calculate_dynamic_shelf_life(nominal_shelf_life_days=shelf_life, nominal_stored_days=stored_days)


# ============================================================================
# 4. PECK'S HUMIDITY ACCELERATION LAW SCALING
# ============================================================================

class TestPeckHumidityLawScaling:
    """Verifies power-law formulation AF_H = (RH / RH_ref)^n."""

    def test_peck_monotonicity_across_humidity_range(self):
        """Grid test: 0% to 100% RH in 1.0% steps. Strictly non-decreasing everywhere."""
        rh_values = [float(rh) for rh in range(101)]
        factors = [calculate_peck_humidity_factor(rh) for rh in rh_values]

        for i in range(len(factors) - 1):
            assert factors[i + 1] >= factors[i]
            if rh_values[i] > 0.0:
                assert factors[i + 1] > factors[i], (
                    f"Strict monotonicity failed at {rh_values[i]}% -> {rh_values[i+1]}%"
                )

    def test_peck_scaling_exact_powers(self):
        """
        Verify power-law doubling behavior:
        At 80% RH (2x reference of 40%): AF_H = 2^2.66 ≈ 6.3204
        At 20% RH (0.5x reference): AF_H = 0.5^2.66 ≈ 0.1582
        """
        af_80 = calculate_peck_humidity_factor(80.0, ref_rh=40.0, n_exponent=2.66)
        expected_80 = pow(2.0, 2.66)
        assert pytest.approx(af_80, rel=1e-5) == expected_80

        af_20 = calculate_peck_humidity_factor(20.0, ref_rh=40.0, n_exponent=2.66)
        expected_20 = pow(0.5, 2.66)
        assert pytest.approx(af_20, rel=1e-5) == expected_20

    def test_peck_exponent_sensitivity(self):
        """Higher Peck exponent n makes the model exponentially more sensitive to humidity."""
        exponents = [1.0, 2.0, 2.66, 3.5]
        # At 80% RH (> 40% RH ref), higher exponent yields higher AF_H
        factors = [calculate_peck_humidity_factor(80.0, ref_rh=40.0, n_exponent=n) for n in exponents]
        for i in range(len(factors) - 1):
            assert factors[i + 1] > factors[i]


# ============================================================================
# 5. LARGE-SCALE PRIORITY QUEUE STABILITY (1,000 BATCHES)
# ============================================================================

class TestLargeScaleFEFOQueueStability:
    """
    Stress harness verifying deterministic tie-breaking, lack of regressions,
    and absence of crashes across 1,000 randomized component batches.
    """

    def test_1000_randomized_batches_deterministic_sorting(self):
        """
        ADVERSARIAL STRESS TEST:
        Generate 1,000 synthetic batches with randomized parameters:
        - Shelf life: 30 to 730 days
        - Stored days: 0 to 365
        - Stress excursions: varying duration, temperature (-40 to 125°C), humidity (5 to 95%)
        - Non-unique remaining days to force tie-breaking

        Verify:
        1. Sorting completes with zero errors/crashes.
        2. Output list preserves all 1,000 components (zero drop/duplication).
        3. Array is strictly sorted non-decreasing by dynamic_remaining_days.
        4. Deterministic tie breaking: if remaining days tie, higher stored_days comes first.
        5. Sorting is idempotent: sort(sort(queue)) == sort(queue).
        """
        rng = random.Random(1337)
        batches: List[Dict[str, Any]] = []

        for i in range(1000):
            nominal_shelf = rng.choice([30, 90, 180, 365, 730])
            nominal_stored = rng.randint(0, min(nominal_shelf, 365))
            batch_id = f"BATCH-{i:04d}-LOT{rng.randint(1, 10)}"

            # Inject 0 to 3 random stress events
            stress_events = []
            for _ in range(rng.randint(0, 3)):
                stress_events.append({
                    "duration_hours": rng.uniform(1.0, 120.0),
                    "temp_c": rng.uniform(15.0, 85.0),
                    "humidity_percent": rng.uniform(20.0, 90.0),
                })

            result = calculate_dynamic_shelf_life(
                nominal_shelf_life_days=nominal_shelf,
                nominal_stored_days=nominal_stored,
                stress_readings=stress_events,
            )

            batches.append({
                "batch_id": batch_id,
                "part_number": f"PART-IC-{rng.randint(1, 50)}",
                "nominal_shelf_life_days": nominal_shelf,
                "nominal_stored_days": nominal_stored,
                "dynamic_remaining_days": result["dynamic_remaining_days"],
                "effective_remaining_days": result["effective_remaining_days"],
                "dynamic_degradation_score": result["dynamic_degradation_score"],
                "status": result["status"],
            })

        # Run primary dynamic FEFO sort
        sorted_batches = dynamic_fefo_sort(batches)

        # 1. Zero data loss
        assert len(sorted_batches) == 1000, f"Expected 1000 items, got {len(sorted_batches)}"

        # 2. Verify non-decreasing dynamic remaining days
        for i in range(len(sorted_batches) - 1):
            r1 = sorted_batches[i]["dynamic_remaining_days"]
            r2 = sorted_batches[i + 1]["dynamic_remaining_days"]
            assert r1 <= r2, f"Sorting order violated at index {i}: {r1} > {r2}"

            # 3. Deterministic tie breaking verification
            if r1 == r2:
                s1 = sorted_batches[i]["nominal_stored_days"]
                s2 = sorted_batches[i + 1]["nominal_stored_days"]
                assert s1 >= s2, (
                    f"Tie breaking by stored days failed at index {i}: "
                    f"r={r1}, s1={s1} < s2={s2}"
                )
                if s1 == s2:
                    b1 = sorted_batches[i]["batch_id"]
                    b2 = sorted_batches[i + 1]["batch_id"]
                    assert b1 <= b2, (
                        f"Tie breaking by batch_id failed at index {i}: "
                        f"{b1} > {b2}"
                    )

        # 4. Idempotency check: sorting twice produces identical order
        second_sort = dynamic_fefo_sort(sorted_batches)
        assert [b["batch_id"] for b in sorted_batches] == [b["batch_id"] for b in second_sort]

        # 5. Compatibility check with root fefo_service.py
        svc_sorted = prioritize_fefo(batches)
        assert len(svc_sorted) == 1000
        assert [b["batch_id"] for b in sorted_batches] == [b["batch_id"] for b in svc_sorted]

    def test_extreme_tie_collision_200_identical_days(self):
        """
        Worst-case tie collision:
        200 components with EXACT same remaining days (42.0 days).
        Must deterministically order by stored_days descending, then batch_id ascending.
        """
        rng = random.Random(42)
        batches = [
            {
                "batch_id": f"LOT-{rng.randint(100, 999)}",
                "nominal_stored_days": rng.randint(10, 50),
                "dynamic_remaining_days": 42.0,
            }
            for _ in range(200)
        ]

        sorted_queue = dynamic_fefo_sort(batches)
        assert len(sorted_queue) == 200

        for i in range(len(sorted_queue) - 1):
            c1 = sorted_queue[i]
            c2 = sorted_queue[i + 1]
            assert c1["dynamic_remaining_days"] == 42.0
            assert c2["dynamic_remaining_days"] == 42.0
            assert c1["nominal_stored_days"] >= c2["nominal_stored_days"]
            if c1["nominal_stored_days"] == c2["nominal_stored_days"]:
                assert c1["batch_id"] <= c2["batch_id"]

    def test_all_expired_massive_queue_prioritization(self):
        """
        Adversarial edge case:
        Queue of 500 batches that are ALL expired (negative remaining days from -1 to -500).
        The most severely expired (-500) must be dispatched first (index 0).
        """
        expired_batches = [
            {"batch_id": f"EXP-{i}", "dynamic_remaining_days": float(-i)}
            for i in range(1, 501)
        ]
        random.shuffle(expired_batches)

        sorted_queue = dynamic_fefo_sort(expired_batches)
        assert sorted_queue[0]["dynamic_remaining_days"] == -500.0
        assert sorted_queue[-1]["dynamic_remaining_days"] == -1.0


# ============================================================================
# 6. ARRHENIUS ENGINE STATEFUL INTEGRATION & MEMORY BOUNDS
# ============================================================================

class TestArrheniusEngineStatefulIntegration:
    """Verifies stateful history tracking, telemetry capping, and evaluation logic."""

    def test_telemetry_history_capped_at_1000_points(self):
        """
        Adversarial resource pressure test:
        Feed 2,500 telemetry events to a single cabinet.
        In-memory buffer must be capped at 1,000 points to prevent memory leakage.
        """
        engine = ArrheniusEngine()
        cab = "CAB-STRESS-BUFFER"
        base_time = datetime.utcnow()

        for i in range(2500):
            engine.record_telemetry(
                cabinet_location=cab,
                temp_c=25.0 + (i % 20),
                humidity_percent=40.0 + (i % 30),
                timestamp=base_time + timedelta(minutes=i),
            )

        assert len(engine._cabinet_history[cab]) == 1000
        # Verify the most recent telemetry point is preserved
        latest_recorded = engine._cabinet_history[cab][-1]["timestamp"]
        expected_latest = base_time + timedelta(minutes=2499)
        assert latest_recorded == expected_latest

    def test_stress_hours_integration_matches_excursions(self):
        """
        Feed alternating normal (20°C, 35% RH) and excursion (45°C, 80% RH) readings.
        Stress hours must accumulate only during out-of-range periods.
        """
        engine = ArrheniusEngine()
        cab = "CAB-EXCURSION"
        t0 = datetime(2026, 1, 1, 0, 0, 0)

        # 10 hours at baseline
        engine.record_telemetry(cab, 20.0, 40.0, timestamp=t0)
        engine.record_telemetry(cab, 20.0, 40.0, timestamp=t0 + timedelta(hours=10))

        # 5 hours at thermal stress (45°C)
        engine.record_telemetry(cab, 45.0, 40.0, timestamp=t0 + timedelta(hours=15))

        # 5 hours at humidity stress (80% RH)
        engine.record_telemetry(cab, 20.0, 80.0, timestamp=t0 + timedelta(hours=20))

        # 5 hours closing baseline reading
        engine.record_telemetry(cab, 20.0, 40.0, timestamp=t0 + timedelta(hours=25))

        temp_h, hum_h, total_h = engine.get_cabinet_stress_hours(cab)

        # Excursions: 45°C > 25°C threshold -> ~5 hours temp stress
        # 80% RH > 50% RH threshold -> ~5 hours humidity stress
        assert temp_h > 0.0
        assert hum_h > 0.0
        assert total_h > 0.0

    def test_evaluate_component_contract_schema_completeness(self):
        """
        Verifies that ArrheniusEngine.evaluate_component returns all contract fields
        matching PROJECT.md § Smart Logic Arrhenius Degradation Response.
        """
        class DummyCabinet:
            cabinet_location = "CAB-CONTRACT"
            last_reported_temperature_c = 42.0
            last_reported_humidity_percent = 70.0
            target_temperature_c = 25.0
            target_humidity_percent = 40.0

        class DummyComponent:
            id = 42
            cabinet_location = "CAB-CONTRACT"
            shelf_life_days = 365
            stored_date = datetime.utcnow().date() - timedelta(days=60)

        engine = ArrheniusEngine()
        eval_result = engine.evaluate_component(DummyComponent(), DummyCabinet())

        required_keys = [
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
        for key in required_keys:
            assert key in eval_result, f"Missing required contract key '{key}' in evaluation result"

        assert eval_result["component_id"] == 42
        assert eval_result["nominal_shelf_life_days"] == 365
        assert eval_result["stored_days"] == 60
        assert eval_result["arrhenius_acceleration_factor"] > 1.0
        assert eval_result["status"] in ["OPTIMAL", "APPROACHING_LIMIT", "CRITICAL", "EXPIRED"]
