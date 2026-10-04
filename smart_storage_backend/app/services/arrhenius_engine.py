"""
Physics-Informed Arrhenius Degradation Model & Environmental Stress Engine.

Implements:
1. Arrhenius Thermal Reaction Rate Acceleration:
     k(T) = A * exp(-E_a / (k_B * T))
     AF_T(T) = exp( (E_a / k_B) * (1 / T_ref - 1 / T) )
   where:
     E_a = 0.60 eV (activation energy for semiconductor/passives aging)
     k_B = 8.617333262e-5 eV/K (Boltzmann constant)
     T_ref = 25°C = 298.15 K
     T = T_C + 273.15 K

2. Peck's Relative Humidity Acceleration Law:
     AF_H(RH) = ( max(1.0, RH) / RH_ref ) ^ n
   where:
     RH_ref = 40.0%
     n = 2.66 (moisture ingress exponent for epoxy packaging)

3. Combined Instantaneous Acceleration Factor:
     AF_combined = AF_T * AF_H

4. Cumulative Stress Hours Tracking:
     Thermal stress: T > 25°C
     Humidity stress: RH > 50%
     Effective aging:
       effective_age_days = nominal_stored_days + sum((AF - 1.0) * delta_t_hours) / 24.0 (for AF > 1.0)

5. Dynamic Degradation Scoring & Expiry:
     D = min(1.0, max(0.0, effective_age_days / nominal_shelf_life_days))
     effective_remaining_days = max(0.0, nominal_shelf_life_days - effective_age_days)
     Status:
       D <= 0.70: "OPTIMAL"
       0.70 < D <= 0.90: "APPROACHING_LIMIT"
       0.90 < D < 1.0: "CRITICAL"
       D >= 1.0: "EXPIRED"

6. Stress-Aware FEFO Queue Priority Sorting:
     Sort by effective_remaining_days ascending, then stored_days descending, then batch_id.
"""

import math
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple

# Physical constants
BOLTZMANN_EV = 8.617333262e-5  # eV / K
DEFAULT_EA = 0.60              # Activation energy in eV
REF_TEMP_C = 25.0             # Reference temperature in °C
REF_TEMP_K = 298.15           # Reference temperature in Kelvin
REF_RH = 40.0                 # Reference relative humidity %
PECK_EXPONENT = 2.66          # Peck moisture exponent for epoxy encapsulation

STRESS_TEMP_THRESHOLD_C = 25.0      # Temperature excursion stress threshold (°C)
STRESS_HUMIDITY_THRESHOLD_RH = 50.0  # Humidity excursion stress threshold (%)


def calculate_arrhenius_temp_factor(
    temp_c: float,
    ea_ev: float = DEFAULT_EA,
    ref_temp_c: float = REF_TEMP_C,
) -> float:
    """
    Computes Arrhenius Thermal Acceleration Factor (AF_T):
    AF_T = exp((Ea / k_B) * (1 / T_ref_K - 1 / T_actual_K))
    """
    if temp_c <= -273.15:
        raise ValueError("Temperature cannot be at or below absolute zero (-273.15°C)")
    if ea_ev <= 0.0:
        raise ValueError("Activation energy must be strictly positive")

    t_ref_k = ref_temp_c + 273.15
    t_act_k = temp_c + 273.15

    exponent = (ea_ev / BOLTZMANN_EV) * ((1.0 / t_ref_k) - (1.0 / t_act_k))
    if exponent > 700.0:
        return float("inf")
    return float(math.exp(exponent))


def calculate_peck_humidity_factor(
    humidity_percent: float,
    ref_rh: float = REF_RH,
    n_exponent: float = PECK_EXPONENT,
    clamp_safely: bool = False,
) -> float:
    """
    Computes Peck's Relative Humidity Acceleration Factor:
    AF_H = (RH_actual / RH_ref) ^ n
    """
    if clamp_safely:
        humidity_percent = max(0.0, min(100.0, float(humidity_percent)))
    else:
        if humidity_percent < 0.0:
            raise ValueError("Relative humidity cannot be negative")
        if humidity_percent > 100.0:
            raise ValueError("Relative humidity cannot exceed 100%")

    if ref_rh <= 0.0:
        raise ValueError("Reference humidity must be strictly positive")

    if humidity_percent == 0.0:
        return 0.0

    ratio = humidity_percent / ref_rh
    return float(math.pow(ratio, n_exponent))


def calculate_total_acceleration_factor(
    temp_c: float,
    humidity_percent: float,
    ea_ev: float = DEFAULT_EA,
    ref_temp_c: float = REF_TEMP_C,
    ref_rh: float = REF_RH,
    n_exponent: float = PECK_EXPONENT,
    clamp_humidity: bool = False,
) -> float:
    """
    Computes combined Acceleration Factor:
    AF_total = AF_T * AF_H
    """
    af_t = calculate_arrhenius_temp_factor(temp_c, ea_ev, ref_temp_c)
    af_h = calculate_peck_humidity_factor(humidity_percent, ref_rh, n_exponent, clamp_safely=clamp_humidity)
    return float(af_t * af_h)


def calculate_dynamic_shelf_life(
    nominal_shelf_life_days: int,
    nominal_stored_days: int,
    stress_readings: Optional[List[Dict[str, float]]] = None,
    ea_ev: float = DEFAULT_EA,
) -> Dict[str, Any]:
    """
    Calculates dynamic degradation score and remaining shelf life incorporating
    cumulative thermal and humidity stress hours.

    stress_readings: list of dicts with keys:
      'duration_hours': float
      'temp_c': float
      'humidity_percent': float
    """
    if nominal_shelf_life_days <= 0:
        raise ValueError("Nominal shelf life must be positive")
    if nominal_stored_days < 0:
        raise ValueError("Nominal stored days cannot be negative")

    cumulative_stress_hours = 0.0
    cumulative_temp_stress_hours = 0.0
    cumulative_humidity_stress_hours = 0.0
    accumulated_effective_days = float(nominal_stored_days)

    if stress_readings:
        for entry in stress_readings:
            duration_h = float(entry.get("duration_hours", 1.0))
            temp_c = float(entry.get("temp_c", REF_TEMP_C))
            rh = float(entry.get("humidity_percent", REF_RH))

            if temp_c > STRESS_TEMP_THRESHOLD_C:
                cumulative_temp_stress_hours += duration_h
            if rh > STRESS_HUMIDITY_THRESHOLD_RH:
                cumulative_humidity_stress_hours += duration_h

            af = calculate_total_acceleration_factor(temp_c, rh, ea_ev)
            if af > 1.0:
                # Excursion beyond baseline adds total stress hours
                cumulative_stress_hours += duration_h
                # Additional effective aging days beyond nominal calendar time
                additional_aging_days = (duration_h * (af - 1.0)) / 24.0
                accumulated_effective_days += additional_aging_days

    remaining_days = nominal_shelf_life_days - accumulated_effective_days
    degradation_score = min(1.0, max(0.0, accumulated_effective_days / nominal_shelf_life_days))

    if remaining_days <= 0.0:
        status = "EXPIRED"
    elif remaining_days <= nominal_shelf_life_days * 0.10:
        status = "CRITICAL"
    elif remaining_days <= nominal_shelf_life_days * 0.30:
        status = "APPROACHING_LIMIT"
    else:
        status = "OPTIMAL"

    return {
        "nominal_shelf_life_days": nominal_shelf_life_days,
        "nominal_stored_days": nominal_stored_days,
        "effective_stored_days": round(accumulated_effective_days, 2),
        "cumulative_stress_hours": round(cumulative_stress_hours, 2),
        "cumulative_temp_stress_hours": round(cumulative_temp_stress_hours, 2),
        "cumulative_humidity_stress_hours": round(cumulative_humidity_stress_hours, 2),
        "dynamic_remaining_days": round(remaining_days, 2),
        "effective_remaining_days": round(max(0.0, remaining_days), 2),
        "dynamic_degradation_score": round(degradation_score, 4),
        "status": status,
    }


def dynamic_fefo_sort(components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sorts components by least dynamic remaining days (First Expired, First Out).
    Ties broken deterministically by nominal_stored_days descending, then batch_id.
    """
    return sorted(
        components,
        key=lambda c: (
            c.get("dynamic_remaining_days", c.get("effective_remaining_days", c.get("remainingDays", float("inf")))),
            -c.get("nominal_stored_days", c.get("storedDays", 0)),
            c.get("batch_id", c.get("batchId", "")),
        ),
    )


class ArrheniusEngine:
    """
    Stateful engine tracking telemetry history per cabinet location,
    accumulating stress excursions, and computing dynamic degradation profiles.
    """

    def __init__(self):
        # cabinet_location -> list of (timestamp: datetime, temp_c: float, humidity_percent: float)
        self._cabinet_history: Dict[str, List[Dict[str, Any]]] = {}
        # component_id -> list of custom stress readings
        self._component_stress_events: Dict[int, List[Dict[str, float]]] = {}

    def reset(self):
        self._cabinet_history.clear()
        self._component_stress_events.clear()

    def record_telemetry(
        self,
        cabinet_location: str,
        temp_c: float,
        humidity_percent: float,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Records a telemetry reading for stress hours integration."""
        if timestamp is None:
            timestamp = datetime.utcnow()

        if cabinet_location not in self._cabinet_history:
            self._cabinet_history[cabinet_location] = []

        history = self._cabinet_history[cabinet_location]
        history.append({
            "timestamp": timestamp,
            "temp_c": float(temp_c),
            "humidity_percent": float(humidity_percent),
        })

        # Cap in-memory history to last 1000 points per cabinet to prevent unbounded memory growth
        if len(history) > 1000:
            self._cabinet_history[cabinet_location] = history[-1000:]

    def add_component_stress_event(
        self,
        component_id: int,
        duration_hours: float,
        temp_c: float,
        humidity_percent: float,
    ) -> None:
        """Injects a specific stress duration event for a component."""
        if component_id not in self._component_stress_events:
            self._component_stress_events[component_id] = []
        self._component_stress_events[component_id].append({
            "duration_hours": float(duration_hours),
            "temp_c": float(temp_c),
            "humidity_percent": float(humidity_percent),
        })

    def get_cabinet_stress_hours(
        self, cabinet_location: str
    ) -> Tuple[float, float, float]:
        """
        Calculates (temp_stress_hours, humidity_stress_hours, total_stress_hours)
        from telemetry history recorded for the cabinet.
        """
        history = self._cabinet_history.get(cabinet_location, [])
        if not history:
            return 0.0, 0.0, 0.0

        temp_hours = 0.0
        humidity_hours = 0.0
        total_stress_hours = 0.0

        if len(history) == 1:
            point = history[0]
            # Assume 1.0 hour sample if single reading
            if point["temp_c"] > STRESS_TEMP_THRESHOLD_C:
                temp_hours += 1.0
            if point["humidity_percent"] > STRESS_HUMIDITY_THRESHOLD_RH:
                humidity_hours += 1.0
            af = calculate_total_acceleration_factor(point["temp_c"], point["humidity_percent"], clamp_humidity=True)
            if af > 1.0:
                total_stress_hours += 1.0
            return temp_hours, humidity_hours, total_stress_hours

        for i in range(len(history) - 1):
            t1 = history[i]["timestamp"]
            t2 = history[i + 1]["timestamp"]
            delta_h = max(0.01, min(24.0, (t2 - t1).total_seconds() / 3600.0))
            curr = history[i]

            if curr["temp_c"] > STRESS_TEMP_THRESHOLD_C:
                temp_hours += delta_h
            if curr["humidity_percent"] > STRESS_HUMIDITY_THRESHOLD_RH:
                humidity_hours += delta_h

            af = calculate_total_acceleration_factor(curr["temp_c"], curr["humidity_percent"], clamp_humidity=True)
            if af > 1.0:
                total_stress_hours += delta_h

        return round(temp_hours, 2), round(humidity_hours, 2), round(total_stress_hours, 2)

    def evaluate_component(
        self,
        component: Any,
        cabinet: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Full dynamic degradation evaluation for a Component model object.
        Returns interface-contract-compliant degradation metrics.
        """
        today = date.today()
        stored_date = getattr(component, "stored_date", today)
        if isinstance(stored_date, datetime):
            stored_date = stored_date.date()
        stored_days = max(0, (today - stored_date).days)
        shelf_life_days = int(getattr(component, "shelf_life_days", 365) or 365)
        component_id = int(getattr(component, "id", 0) or 0)
        cab_loc = getattr(component, "cabinet_location", "")

        # 1. Determine instantaneous environmental conditions
        current_temp = REF_TEMP_C
        current_humidity = REF_RH
        if cabinet is not None:
            if getattr(cabinet, "last_reported_temperature_c", None) is not None:
                current_temp = float(cabinet.last_reported_temperature_c)
            elif getattr(cabinet, "target_temperature_c", None) is not None:
                current_temp = float(cabinet.target_temperature_c)

            if getattr(cabinet, "last_reported_humidity_percent", None) is not None:
                current_humidity = float(cabinet.last_reported_humidity_percent)
            elif getattr(cabinet, "target_humidity_percent", None) is not None:
                current_humidity = float(cabinet.target_humidity_percent)

        current_humidity = max(0.0, min(100.0, current_humidity))
        af_instantaneous = calculate_total_acceleration_factor(
            current_temp, current_humidity, clamp_humidity=True
        )

        # 2. Gather stress readings from history and specific events
        stress_readings: List[Dict[str, float]] = []

        # Injected events
        if component_id in self._component_stress_events:
            stress_readings.extend(self._component_stress_events[component_id])

        # Cabinet history
        cab_history = self._cabinet_history.get(cab_loc, [])
        if len(cab_history) >= 2:
            for i in range(len(cab_history) - 1):
                t1 = cab_history[i]["timestamp"]
                t2 = cab_history[i + 1]["timestamp"]
                delta_h = max(0.01, min(24.0, (t2 - t1).total_seconds() / 3600.0))
                stress_readings.append({
                    "duration_hours": delta_h,
                    "temp_c": cab_history[i]["temp_c"],
                    "humidity_percent": cab_history[i]["humidity_percent"],
                })
        elif cab_history:
            point = cab_history[-1]
            stress_readings.append({
                "duration_hours": 1.0,
                "temp_c": point["temp_c"],
                "humidity_percent": point["humidity_percent"],
            })
        elif af_instantaneous > 1.0 and stored_days > 0:
            # If no fine-grained time-series exists but current environment is in stress,
            # calculate cumulative stress based on current exposure over storage days
            stress_readings.append({
                "duration_hours": float(stored_days * 24.0),
                "temp_c": current_temp,
                "humidity_percent": current_humidity,
            })

        # 3. Calculate dynamic shelf life
        degradation = calculate_dynamic_shelf_life(
            nominal_shelf_life_days=shelf_life_days,
            nominal_stored_days=stored_days,
            stress_readings=stress_readings,
            ea_ev=DEFAULT_EA,
        )

        effective_remaining = degradation["effective_remaining_days"]
        degradation_score = degradation["dynamic_degradation_score"]
        status = degradation["status"]

        # Ensure cumulative stress hours reflect excursions
        temp_stress_h = degradation.get("cumulative_temp_stress_hours", 0.0)
        hum_stress_h = degradation.get("cumulative_humidity_stress_hours", 0.0)

        return {
            "component_id": component_id,
            "nominal_shelf_life_days": shelf_life_days,
            "stored_days": stored_days,
            "cumulative_temp_stress_hours": round(temp_stress_h, 2),
            "cumulative_humidity_stress_hours": round(hum_stress_h, 2),
            "arrhenius_acceleration_factor": round(af_instantaneous, 2),
            "dynamic_degradation_score": round(degradation_score, 4),
            "effective_remaining_days": round(effective_remaining, 2),
            "status": status,
        }


# Global singleton instance
arrhenius_engine = ArrheniusEngine()
