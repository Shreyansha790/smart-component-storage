"""
Tier 1 Unit Tests: Arrhenius Boundary Value Analysis, Singularity & Extreme Value Testing.

Validates robust mathematical behavior across physical singularities, zero-divisions,
and boundary conditions.
"""

import pytest
import math
from tests.helpers.arrhenius_oracle import (
    calculate_arrhenius_temp_factor,
    calculate_peck_humidity_factor,
    calculate_total_acceleration_factor,
    calculate_dynamic_shelf_life,
)


class TestArrheniusBoundaryConditions:
    """Boundary Value Analysis (BVA) for Arrhenius degradation functions."""

    def test_absolute_zero_singularity_raises_value_error(self):
        """
        Temperature at or below absolute zero (-273.15°C or 0 Kelvin)
        leads to division by zero in 1/T. Must raise ValueError.
        """
        with pytest.raises(ValueError, match="absolute zero"):
            calculate_arrhenius_temp_factor(-273.15)

        with pytest.raises(ValueError, match="absolute zero"):
            calculate_arrhenius_temp_factor(-300.0)

    def test_near_absolute_zero_approaches_zero_degradation(self):
        """
        Just above absolute zero (-270°C = 3.15 K), chemical degradation rate
        is practically zero.
        """
        af_near_zero = calculate_arrhenius_temp_factor(-270.0)
        assert af_near_zero < 1e-10

    def test_negative_activation_energy_rejected(self):
        """
        Activation energy Ea represents an endothermic barrier and must be positive.
        Negative or zero Ea violates physics and must raise ValueError.
        """
        with pytest.raises(ValueError, match="Activation energy"):
            calculate_arrhenius_temp_factor(25.0, ea_ev=0.0)

        with pytest.raises(ValueError, match="Activation energy"):
            calculate_arrhenius_temp_factor(25.0, ea_ev=-0.5)

    def test_extreme_high_temperature_boundary(self):
        """
        At extreme semiconductor testing temperatures (125°C, 150°C),
        function must compute a huge acceleration factor without NaN or crash.
        """
        af_125 = calculate_arrhenius_temp_factor(125.0, ea_ev=0.60)
        assert af_125 > 100.0
        assert not math.isnan(af_125)
        assert not math.isinf(af_125)

    def test_relative_humidity_zero_boundary(self):
        """
        At 0% relative humidity (dry nitrogen purge), moisture degradation factor
        must equal 0.0 without ZeroDivisionError.
        """
        af_dry = calculate_peck_humidity_factor(0.0)
        assert af_dry == 0.0

    def test_relative_humidity_100_percent_boundary(self):
        """
        At 100% relative humidity (saturated condensation point),
        Peck factor must calculate accurately: (100 / 40)^2.66 ≈ 11.38.
        """
        af_saturated = calculate_peck_humidity_factor(100.0)
        expected = pow(100.0 / 40.0, 2.66)
        assert pytest.approx(af_saturated, rel=1e-4) == expected

    def test_negative_humidity_raises_value_error(self):
        """Negative relative humidity is physically impossible."""
        with pytest.raises(ValueError, match="negative"):
            calculate_peck_humidity_factor(-5.0)

    def test_excess_humidity_raises_value_error(self):
        """Relative humidity exceeding 100% must be rejected."""
        with pytest.raises(ValueError, match="exceed 100%"):
            calculate_peck_humidity_factor(100.5)

    def test_invalid_shelf_life_parameters_rejected(self):
        """Shelf life must be positive; stored days cannot be negative."""
        with pytest.raises(ValueError, match="positive"):
            calculate_dynamic_shelf_life(nominal_shelf_life_days=0, nominal_stored_days=10)

        with pytest.raises(ValueError, match="negative"):
            calculate_dynamic_shelf_life(nominal_shelf_life_days=100, nominal_stored_days=-1)

    def test_shelf_life_zero_stored_days_initial_state(self):
        """Brand new batch (stored 0 days): remaining = nominal, score = 0.0."""
        res = calculate_dynamic_shelf_life(nominal_shelf_life_days=365, nominal_stored_days=0)
        assert res["dynamic_remaining_days"] == 365.0
        assert res["dynamic_degradation_score"] == 0.0
        assert res["status"] == "OPTIMAL"

    def test_massive_degradation_clamping_score_to_one(self):
        """Components stored far past expiration clamp score to 1.0 (not > 1.0)."""
        res = calculate_dynamic_shelf_life(nominal_shelf_life_days=30, nominal_stored_days=300)
        assert res["dynamic_remaining_days"] < 0
        assert res["dynamic_degradation_score"] == 1.0
        assert res["status"] == "EXPIRED"
