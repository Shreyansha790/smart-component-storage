"""
Sensor Jitter Smoothing Service.

Applies a sliding-window Median Filter (outlier & impulse spike rejection)
combined with an Exponential Moving Average (EMA) filter to provide smooth,
physically plausible environmental telemetry for cabinets.
"""

from collections import deque
import math
import statistics
from typing import Dict, Tuple, Optional, List


class JitterFilter:
    """
    Stateful jitter filter maintaining rolling windows and EMA states per cabinet location.
    """

    def __init__(
        self,
        window_size: int = 5,
        alpha: float = 0.25,
        min_temp_c: float = -40.0,
        max_temp_c: float = 85.0,
        min_humidity_pct: float = 0.0,
        max_humidity_pct: float = 100.0,
    ):
        self.window_size = window_size
        self.alpha = alpha
        self.min_temp_c = min_temp_c
        self.max_temp_c = max_temp_c
        self.min_humidity_pct = min_humidity_pct
        self.max_humidity_pct = max_humidity_pct

        # Per-cabinet history: {cabinet_location: deque(maxlen=window_size)}
        self._temp_windows: Dict[str, deque] = {}
        self._humidity_windows: Dict[str, deque] = {}

        # Per-cabinet latest EMA: {cabinet_location: float}
        self._temp_ema: Dict[str, float] = {}
        self._humidity_ema: Dict[str, float] = {}

    def _clamp_temperature(self, temp_c: float) -> float:
        if not isinstance(temp_c, (int, float)) or math.isnan(temp_c) or math.isinf(temp_c):
            return 22.0
        return max(self.min_temp_c, min(self.max_temp_c, float(temp_c)))

    def _clamp_humidity(self, humidity_pct: float) -> float:
        if not isinstance(humidity_pct, (int, float)) or math.isnan(humidity_pct) or math.isinf(humidity_pct):
            return 45.0
        return max(self.min_humidity_pct, min(self.max_humidity_pct, float(humidity_pct)))

    def smooth_reading(
        self,
        cabinet_location: str,
        temperature_c: float,
        humidity_percent: float,
    ) -> Tuple[float, float]:
        """
        Ingests a raw sensor reading for a cabinet and returns the smoothed (temperature_c, humidity_percent).
        Validates against NaN and Inf floats; falls back to the last known smoothed reading if invalid.
        """
        invalid_temp = not isinstance(temperature_c, (int, float)) or math.isnan(temperature_c) or math.isinf(temperature_c)
        invalid_humidity = not isinstance(humidity_percent, (int, float)) or math.isnan(humidity_percent) or math.isinf(humidity_percent)

        if invalid_temp or invalid_humidity:
            latest = self.get_latest_smoothed(cabinet_location)
            if latest is not None:
                if invalid_temp and invalid_humidity:
                    return latest
                if invalid_temp:
                    temperature_c = latest[0]
                if invalid_humidity:
                    humidity_percent = latest[1]
            else:
                if invalid_temp:
                    temperature_c = 22.0
                if invalid_humidity:
                    humidity_percent = 45.0

        clamped_temp = self._clamp_temperature(temperature_c)
        clamped_humidity = self._clamp_humidity(humidity_percent)

        if cabinet_location not in self._temp_windows:
            self._temp_windows[cabinet_location] = deque(maxlen=self.window_size)
            self._humidity_windows[cabinet_location] = deque(maxlen=self.window_size)

        temp_win = self._temp_windows[cabinet_location]
        humidity_win = self._humidity_windows[cabinet_location]

        temp_win.append(clamped_temp)
        humidity_win.append(clamped_humidity)

        # 1. Median filter over recent sliding window
        median_temp = float(statistics.median(temp_win))
        median_humidity = float(statistics.median(humidity_win))

        # 2. Exponential Moving Average (EMA)
        if cabinet_location not in self._temp_ema:
            ema_temp = median_temp
            ema_humidity = median_humidity
        else:
            prev_temp_ema = self._temp_ema[cabinet_location]
            prev_humidity_ema = self._humidity_ema[cabinet_location]
            ema_temp = self.alpha * median_temp + (1.0 - self.alpha) * prev_temp_ema
            ema_humidity = self.alpha * median_humidity + (1.0 - self.alpha) * prev_humidity_ema

        self._temp_ema[cabinet_location] = ema_temp
        self._humidity_ema[cabinet_location] = ema_humidity

        return round(ema_temp, 2), round(ema_humidity, 2)

    def get_latest_smoothed(self, cabinet_location: str) -> Optional[Tuple[float, float]]:
        """Returns the latest smoothed reading for a cabinet if available."""
        if cabinet_location in self._temp_ema and cabinet_location in self._humidity_ema:
            return round(self._temp_ema[cabinet_location], 2), round(self._humidity_ema[cabinet_location], 2)
        return None

    def reset(self, cabinet_location: Optional[str] = None):
        """Clears filter state for a specific cabinet or all cabinets."""
        if cabinet_location:
            self._temp_windows.pop(cabinet_location, None)
            self._humidity_windows.pop(cabinet_location, None)
            self._temp_ema.pop(cabinet_location, None)
            self._humidity_ema.pop(cabinet_location, None)
        else:
            self._temp_windows.clear()
            self._humidity_windows.clear()
            self._temp_ema.clear()
            self._humidity_ema.clear()


# Global singleton instance for app-wide telemetry filtering
jitter_filter = JitterFilter()


def calculate_median(values: List[float]) -> float:
    """Helper to compute median of a list of floats."""
    if not values:
        raise ValueError("Cannot calculate median of empty list")
    return float(statistics.median(values))


def calculate_ema(current_value: float, previous_ema: Optional[float], alpha: float = 0.25) -> float:
    """Helper to compute single-step exponential moving average."""
    if previous_ema is None:
        return float(current_value)
    return float(alpha * current_value + (1.0 - alpha) * previous_ema)
