"""
Tier 1 Unit Tests: Physics-Informed Arrhenius Degradation Model & Kinetic Equations.

Derivation Source: PROJECT.md § Feature 8, 9, 10 and explorer_survey_testing_1/report.md § 3.7.
Formula:
  k(T) = A * exp(-Ea / (k_B * T))
  AF_T = exp((Ea / k_B) * (1 / T_ref - 1 / T_actual))
  AF_H = (RH_actual / RH_ref) ^ n
  AF_total = AF_T * AF_H
"""

import pytest
from tests.helpers.arrhenius_oracle import (
    calculate_arrhenius_temp_factor,
    calculate_peck_humidity_factor,
    calculate_total_acceleration_factor,
    calculate_dynamic_shelf_life,
    REF_TEMP_C,
    REF_RH,
    BOLTZMANN_EV,
    DEFAULT_EA,
)


class TestArrheniusKineticEquations:
    """Verifies precision and physical accuracy of Arrhenius and Peck degradation models."""

    def test_baseline_environmental_condition_yields_unity(self):
        """
        At reference baseline (25°C, 40% RH), acceleration factors MUST exactly equal 1.0.
        Nominal calendar aging matches effective aging.
        """
        af_t = calculate_arrhenius_temp_factor(temp_c=REF_TEMP_C, ea_ev=DEFAULT_EA)
        af_h = calculate_peck_humidity_factor(humidity_percent=REF_RH)
        af_total = calculate_total_acceleration_factor(temp_c=REF_TEMP_C, humidity_percent=REF_RH)

        assert pytest.approx(af_t, rel=1e-5) == 1.0
        assert pytest.approx(af_h, rel=1e-5) == 1.0
        assert pytest.approx(af_total, rel=1e-5) == 1.0

    def test_thermal_stress_exponential_acceleration(self):
        """
        At elevated temperature (45°C), Arrhenius factor must be significantly > 1.0.
        Mathematical derivation:
          T_ref = 298.15 K, T_actual = 318.15 K
          1/298.15 - 1/318.15 = 0.000210853
          Ea / k_B = 0.60 / 8.617333262e-5 = 6962.712
          exponent = 6962.712 * 0.000210853 = 1.4681
          exp(1.4681) ≈ 4.341
        """
        af_t_45 = calculate_arrhenius_temp_factor(temp_c=45.0, ea_ev=0.60)
        assert pytest.approx(af_t_45, rel=1e-3) == 4.341

        # Higher thermal stress (60°C) must accelerate even further
        af_t_60 = calculate_arrhenius_temp_factor(temp_c=60.0, ea_ev=0.60)
        assert af_t_60 > af_t_45
        assert af_t_60 > 10.0

    def test_peck_humidity_power_law_scaling(self):
        """
        Peck's law scales with (RH / 40)^2.66.
        At 80% RH (double reference):
          (80 / 40) ^ 2.66 = 2 ^ 2.66 ≈ 6.32
        """
        af_h_80 = calculate_peck_humidity_factor(humidity_percent=80.0, ref_rh=40.0, n_exponent=2.66)
        expected_peck = pow(2.0, 2.66)
        assert pytest.approx(af_h_80, rel=1e-4) == expected_peck

    def test_combined_thermal_and_humidity_stress(self):
        """
        Combined stress multiplying thermal and humidity factors:
        At 45°C and 80% RH:
          AF_total = AF_T(45°C) * AF_H(80% RH) ≈ 4.341 * 6.32 ≈ 27.4
        """
        af_total = calculate_total_acceleration_factor(temp_c=45.0, humidity_percent=80.0, ea_ev=0.60)
        expected = 4.341 * pow(2.0, 2.66)
        assert pytest.approx(af_total, rel=1e-2) == expected
        assert af_total > 25.0

    def test_cold_preservation_slows_degradation(self):
        """
        Sub-ambient temperatures (e.g. 5°C cold storage) must reduce degradation rate (AF_T < 1.0).
        Component ages slower than calendar time.
        """
        af_cold = calculate_arrhenius_temp_factor(temp_c=5.0, ea_ev=0.60)
        assert 0.0 < af_cold < 1.0
        assert af_cold < 0.25  # Substantial preservation effect

    def test_activation_energy_sensitivity(self):
        """
        Components with higher activation energy (Ea = 0.9 eV) are more sensitive
        to thermal stress than lower activation energy components (Ea = 0.4 eV).
        """
        af_low_ea = calculate_arrhenius_temp_factor(temp_c=50.0, ea_ev=0.40)
        af_high_ea = calculate_arrhenius_temp_factor(temp_c=50.0, ea_ev=0.90)
        assert af_high_ea > af_low_ea


class TestCumulativeStressAndDynamicShelfLife:
    """Verifies cumulative stress integration and remaining shelf life calculation."""

    def test_unstressed_component_matches_linear_shelf_life(self):
        """
        A component stored under optimal baseline conditions for 60 days
        with 365-day shelf life must have 305 remaining days and score ~ 0.164.
        """
        result = calculate_dynamic_shelf_life(
            nominal_shelf_life_days=365,
            nominal_stored_days=60,
            stress_readings=[],
        )
        assert result["cumulative_stress_hours"] == 0.0
        assert result["dynamic_remaining_days"] == 305.0
        assert pytest.approx(result["dynamic_degradation_score"], rel=1e-3) == 60 / 365
        assert result["status"] == "OPTIMAL"

    def test_thermal_stress_hours_accelerates_aging(self):
        """
        A component subjected to 72 hours of high thermal stress (50°C):
        Must accumulate 72 stress hours and reduce remaining shelf life by more than 3 days.
        """
        stress_event = [{"duration_hours": 72.0, "temp_c": 50.0, "humidity_percent": 40.0}]
        result = calculate_dynamic_shelf_life(
            nominal_shelf_life_days=180,
            nominal_stored_days=30,
            stress_readings=stress_event,
        )
        assert result["cumulative_stress_hours"] == 72.0
        # Effective stored days must exceed nominal stored days (30)
        assert result["effective_stored_days"] > 30.0
        # Dynamic remaining days must be less than nominal (180 - 30 = 150)
        assert result["dynamic_remaining_days"] < 150.0

    def test_status_transitions_from_optimal_to_expired(self):
        """
        Tests status threshold transitions:
          - Remaining > 30%: OPTIMAL
          - 10% < Remaining <= 30%: APPROACHING_LIMIT
          - 0 < Remaining <= 10%: CRITICAL
          - Remaining <= 0: EXPIRED
        """
        nominal = 100
        # 1. Optimal: 80 days remaining
        res_opt = calculate_dynamic_shelf_life(nominal, 20)
        assert res_opt["status"] == "OPTIMAL"

        # 2. Approaching limit: 25 days remaining (<= 30%)
        res_app = calculate_dynamic_shelf_life(nominal, 75)
        assert res_app["status"] == "APPROACHING_LIMIT"

        # 3. Critical: 8 days remaining (<= 10%)
        res_crit = calculate_dynamic_shelf_life(nominal, 92)
        assert res_crit["status"] == "CRITICAL"

        # 4. Expired: 0 or negative days remaining
        res_exp = calculate_dynamic_shelf_life(nominal, 105)
        assert res_exp["status"] == "EXPIRED"
        assert res_exp["dynamic_degradation_score"] == 1.0
