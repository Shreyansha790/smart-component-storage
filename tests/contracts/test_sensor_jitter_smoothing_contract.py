"""
Tier 3 IoT Subsystem Contract Tests: Sensor Jitter Smoothing & Outlier Rejection.

Derivation Source: ORIGINAL_REQUEST § R2 & PROJECT.md § Feature 4:
"Resilient sensor jitter smoothing (median + exponential moving average)".
"""

import pytest
from app.services.jitter_filter import (
    JitterFilter,
    calculate_median,
    calculate_ema,
)


class TestSensorJitterSmoothingContract:
    """Verifies that impulse sensor glitches are rejected and environmental telemetry is smoothed."""

    def test_impulse_glitch_spike_rejection(self):
        """
        IMPULSE NOISE TEST:
        A hardware glitch causes a single reading to jump from 22.0°C to 85.0°C.
        The 5-sample median filter MUST reject this spike completely, preventing
        false alarm condition violations.
        """
        filter_instance = JitterFilter(window_size=5, alpha=0.25)
        cabinet = "CAB-TEST-SMOOTH"

        # Prime with nominal readings
        filter_instance.smooth_reading(cabinet, 22.0, 45.0)
        filter_instance.smooth_reading(cabinet, 22.1, 45.1)

        # Single-sample massive glitch spike
        temp_spike, hum_spike = filter_instance.smooth_reading(cabinet, 85.0, 99.0)

        # The spike must NOT contaminate the smoothed temperature above 25.0°C
        assert temp_spike < 25.0, f"Glitch spike leaked through filter: {temp_spike}°C"
        assert hum_spike < 55.0, f"Glitch humidity leaked through filter: {hum_spike}%"

        # Subsequent nominal readings keep it stable
        temp_after, hum_after = filter_instance.smooth_reading(cabinet, 22.2, 45.0)
        assert abs(temp_after - 22.1) < 0.5

    def test_ema_step_response_tracking(self):
        """
        When temperature legitimately steps from 20.0°C to 30.0°C,
        EMA must smoothly track towards 30.0°C according to alpha = 0.25.
        """
        filter_instance = JitterFilter(window_size=3, alpha=0.25)
        cabinet = "CAB-STEP"

        # Initial steady state at 20°C
        for _ in range(3):
            filter_instance.smooth_reading(cabinet, 20.0, 40.0)

        # Sustained shift to 30°C
        t1, _ = filter_instance.smooth_reading(cabinet, 30.0, 40.0)
        t2, _ = filter_instance.smooth_reading(cabinet, 30.0, 40.0)
        t3, _ = filter_instance.smooth_reading(cabinet, 30.0, 40.0)

        # On 1st step sample: window [20, 20, 30] has median 20.0, so filter holds 20.0 (rejecting potential spike)
        assert t1 == 20.0
        # On 2nd step sample: window [20, 30, 30] confirms sustained step (median 30.0), EMA begins rising
        assert t2 > 20.0
        # On 3rd step sample: window [30, 30, 30] continues exponential convergence towards 30.0
        assert t3 > t2
        assert t3 <= 30.0

    def test_physical_limits_clamping(self):
        """
        Sensors reporting values outside physical hardware operating envelopes
        (-40°C to 85°C, 0% to 100% RH) must be clamped to safe boundary values.
        """
        filter_instance = JitterFilter(min_temp_c=-40.0, max_temp_c=85.0, min_humidity_pct=0.0, max_humidity_pct=100.0)
        cabinet = "CAB-BOUND"

        # Extreme negative reading
        t_low, h_low = filter_instance.smooth_reading(cabinet, -150.0, -20.0)
        assert t_low >= -40.0
        assert h_low >= 0.0

        # Extreme positive reading
        filter_instance.reset(cabinet)
        t_high, h_high = filter_instance.smooth_reading(cabinet, 200.0, 150.0)
        assert t_high <= 85.0
        assert h_high <= 100.0

    def test_multi_cabinet_filter_isolation(self):
        """
        Telemetry posted for CAB-1 must not pollute or alter the rolling state of CAB-2.
        """
        filter_instance = JitterFilter()

        # Prime CAB-HOT at 60°C
        for _ in range(5):
            filter_instance.smooth_reading("CAB-HOT", 60.0, 80.0)

        # CAB-COLD at 5°C
        t_cold, _ = filter_instance.smooth_reading("CAB-COLD", 5.0, 30.0)

        # CAB-COLD should reflect its own reading, not influenced by CAB-HOT
        assert t_cold == 5.0

    def test_helper_functions_median_and_ema(self):
        """Unit checks for standalone calculate_median and calculate_ema helpers."""
        assert calculate_median([1.0, 5.0, 2.0, 8.0, 3.0]) == 3.0
        with pytest.raises(ValueError):
            calculate_median([])

        # First EMA step with None previous value returns current value
        assert calculate_ema(10.0, None) == 10.0
        # Subsequent step: alpha*current + (1-alpha)*prev
        # 0.25 * 20.0 + 0.75 * 10.0 = 5.0 + 7.5 = 12.5
        assert pytest.approx(calculate_ema(20.0, 10.0, alpha=0.25)) == 12.5

    def test_nan_and_inf_reading_fallback(self):
        """
        Sensors reporting float('nan') or float('inf') must not poison rolling statistics,
        and must safely fall back to the last known smoothed reading.
        """
        import math
        filter_instance = JitterFilter()
        cabinet = "CAB-NAN-TEST"

        # Prime with nominal reading
        t_init, h_init = filter_instance.smooth_reading(cabinet, 22.0, 45.0)
        assert t_init == 22.0
        assert h_init == 45.0

        # Feed NaN temperature
        t_nan, h_valid = filter_instance.smooth_reading(cabinet, float("nan"), 46.0)
        assert not math.isnan(t_nan)
        assert not math.isinf(t_nan)
        assert t_nan == 22.0

        # Feed Inf humidity
        t_valid, h_inf = filter_instance.smooth_reading(cabinet, 23.0, float("inf"))
        assert not math.isnan(h_inf)
        assert not math.isinf(h_inf)

        # Feed both NaN and Inf
        t_both, h_both = filter_instance.smooth_reading(cabinet, float("nan"), float("-inf"))
        assert not math.isnan(t_both) and not math.isinf(t_both)
        assert not math.isnan(h_both) and not math.isinf(h_both)

