"""
Authoritative Mathematical Reference Oracle for Arrhenius Kinetics & Peck Humidity Stress.

Derived from physics-informed degradation equations specified in PROJECT.md § Feature 8-11
and explorer_survey_testing_1/report.md § 3.7.
"""

import math
from typing import List, Dict, Any, Optional

# Physical constants
BOLTZMANN_EV = 8.617333262e-5  # eV / K
DEFAULT_EA = 0.60              # Activation energy in eV (typical for semiconductors)
REF_TEMP_C = 25.0             # Reference temperature in °C
REF_TEMP_K = 298.15           # Reference temperature in Kelvin
REF_RH = 40.0                 # Reference relative humidity %
PECK_EXPONENT = 2.66          # Peck moisture exponent for epoxy encapsulation


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
    # Bound the exponent to prevent overflow in extreme tests
    if exponent > 700.0:
        return float("inf")
    return float(math.exp(exponent))


def calculate_peck_humidity_factor(
    humidity_percent: float,
    ref_rh: float = REF_RH,
    n_exponent: float = PECK_EXPONENT,
) -> float:
    """
    Computes Peck's Relative Humidity Acceleration Factor:
    AF_H = (RH_actual / RH_ref) ^ n
    """
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
) -> float:
    """
    Computes combined Acceleration Factor:
    AF_total = AF_T * AF_H
    """
    af_t = calculate_arrhenius_temp_factor(temp_c, ea_ev, ref_temp_c)
    af_h = calculate_peck_humidity_factor(humidity_percent, ref_rh, n_exponent)
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
    accumulated_effective_days = float(nominal_stored_days)

    if stress_readings:
        for entry in stress_readings:
            duration_h = float(entry.get("duration_hours", 1.0))
            temp_c = float(entry.get("temp_c", REF_TEMP_C))
            rh = float(entry.get("humidity_percent", REF_RH))

            af = calculate_total_acceleration_factor(temp_c, rh, ea_ev)
            if af > 1.0:
                # Excursion beyond baseline adds stress hours
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
        "dynamic_remaining_days": round(remaining_days, 2),
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
            c.get("dynamic_remaining_days", float("inf")),
            -c.get("nominal_stored_days", 0),
            c.get("batch_id", ""),
        ),
    )
