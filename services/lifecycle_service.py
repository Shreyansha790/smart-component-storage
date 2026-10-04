from typing import Optional, List, Dict, Any
import math
from utils.date_utils import calculate_days_between

BOLTZMANN_EV = 8.617333262e-5
DEFAULT_EA = 0.60
REF_TEMP_C = 25.0
REF_RH = 40.0
PECK_EXPONENT = 2.66


def calculate_lifecycle(
    component: Dict[str, Any],
    current_date: str,
    stress_readings: Optional[List[Dict[str, float]]] = None,
) -> Dict[str, Any]:
    """
    Calculates the remaining shelf life of a component, optionally incorporating
    dynamic Arrhenius thermal and Peck humidity environmental stress history.
    """

    required_fields = [
        "batchId",
        "partNumber",
        "manufacturer",
        "category",
        "storedDate",
        "shelfLife"
    ]

    for field in required_fields:
        if field not in component or component[field] is None:
            return {
                "batchId": component.get("batchId"),
                "partNumber": component.get("partNumber"),
                "status": "Invalid Data",
                "error": f"Missing {field}"
            }

    try:
        stored_days = calculate_days_between(
            component["storedDate"],
            current_date
        )

        shelf_life = component["shelfLife"]

        effective_stress = (
            stress_readings
            or component.get("stressReadings")
            or component.get("stress_readings")
        )

        cumulative_stress_hours = 0.0
        effective_stored_days = float(stored_days)

        if effective_stress:
            for entry in effective_stress:
                duration_h = float(entry.get("duration_hours", entry.get("durationHours", 1.0)))
                temp_c = float(entry.get("temp_c", entry.get("temperature", REF_TEMP_C)))
                rh = float(entry.get("humidity_percent", entry.get("humidity", REF_RH)))

                t_ref_k = REF_TEMP_C + 273.15
                t_act_k = temp_c + 273.15
                if t_act_k > 0:
                    exp_val = (DEFAULT_EA / BOLTZMANN_EV) * ((1.0 / t_ref_k) - (1.0 / t_act_k))
                    af_t = math.exp(min(700.0, exp_val))
                else:
                    af_t = 1.0

                af_h = math.pow(max(0.0, min(100.0, rh)) / REF_RH, PECK_EXPONENT) if rh > 0 else 0.0
                af = af_t * af_h

                if af > 1.0:
                    cumulative_stress_hours += duration_h
                    additional_days = (duration_h * (af - 1.0)) / 24.0
                    effective_stored_days += additional_days

            remaining_days = round(shelf_life - effective_stored_days, 2)
            degradation_score = round(min(1.0, max(0.0, effective_stored_days / shelf_life)), 4)
        else:
            remaining_days = shelf_life - stored_days
            degradation_score = round(min(1.0, max(0.0, stored_days / shelf_life)), 4)

        if remaining_days < 0:
            status = "Shelf Life Exceeded"
        elif remaining_days <= shelf_life * 0.10:
            status = "Critical"
        elif remaining_days <= shelf_life * 0.30:
            status = "Approaching Limit"
        else:
            status = "Safe"

        return {
            "batchId": component["batchId"],
            "partNumber": component["partNumber"],
            "storedDays": stored_days,
            "remainingDays": remaining_days,
            "status": status,
            "dynamic_remaining_days": remaining_days,
            "dynamic_degradation_score": degradation_score,
            "cumulative_stress_hours": round(cumulative_stress_hours, 2),
        }

    except (ValueError, TypeError):
        return {
            "batchId": component.get("batchId"),
            "partNumber": component.get("partNumber"),
            "status": "Invalid Data",
            "error": "Invalid date or shelf life"
        }