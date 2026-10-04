"""
Actuator Control & Closed-Loop Hysteresis Service.

Manages autonomous and manual actuator states per cabinet location:
1. Closed-Loop Peltier Cooling Hysteresis:
   - Activated when current_temp > (target_temp + 2.0°C) in AUTO mode.
   - Manual override options: AUTO, ON, OFF.
2. Thermal Safety Interlock:
   - Mandatory cutoff: If current_temp < 10.0°C, peltier_active MUST be False unconditionally
     (inhibits sub-cooling and condensation/freezing hazard even if override is ON).
3. Dehumidifier Ventilation Servo:
   - Servo opens to 90° when current_humidity > target_humidity in AUTO mode.
   - Servo closes to 0° when current_humidity <= target_humidity in AUTO mode.
   - Manual override options: AUTO, OPEN (90°), CLOSED (0°).
4. Slot RGB Locator LEDs:
   - Tracks active slot locators mapping slot IDs (e.g. "ROW-A-COL-2") to hex color strings.
   - Provides methods to set, update, and clear active slot locators.
"""

from typing import Dict, Optional, Any
import threading


# Thermal Safety Limits & Control Thresholds
MIN_SAFE_TEMP_C: float = 10.0
COOLING_HYSTERESIS_DELTA_C: float = 2.0
SERVO_OPEN_ANGLE: int = 90
SERVO_CLOSED_ANGLE: int = 0
DEFAULT_LOCATE_COLOR: str = "#00FFCC"


def compute_autonomous_actuator_state(
    current_temp: float,
    current_humidity: float,
    target_temp: float,
    target_humidity: float,
    peltier_override: str = "AUTO",
    ventilation_override: str = "AUTO",
    min_safe_temp: float = MIN_SAFE_TEMP_C,
) -> Dict[str, Any]:
    """
    Authoritative reference oracle for closed-loop actuator hysteresis control and safety interlock.
    Matches tests/contracts/test_bidirectional_actuator_loopback.py contract logic.
    """
    # 1. Thermal Safety Interlock Cutoff
    if current_temp < min_safe_temp:
        # Prevent Peltier condensation/freezing hazard below minimum safe threshold
        peltier_active = False
    elif peltier_override == "ON":
        peltier_active = True
    elif peltier_override == "OFF":
        peltier_active = False
    else:  # AUTO
        # Hysteresis: turn on if exceeding target setpoint by > 2.0°C
        peltier_active = current_temp > (target_temp + COOLING_HYSTERESIS_DELTA_C)

    # 2. Dehumidification ventilation servo
    if ventilation_override == "OPEN":
        servo_angle = SERVO_OPEN_ANGLE
    elif ventilation_override == "CLOSED":
        servo_angle = SERVO_CLOSED_ANGLE
    else:  # AUTO
        servo_angle = SERVO_OPEN_ANGLE if current_humidity > target_humidity else SERVO_CLOSED_ANGLE

    return {
        "peltier_active": peltier_active,
        "ventilation_servo_angle": servo_angle,
    }


class CabinetActuatorState:
    """Internal state representation for a physical cabinet's actuators."""

    def __init__(self, cabinet_location: str):
        self.cabinet_location: str = cabinet_location
        self.peltier_mode: str = "AUTO"          # "AUTO", "ON", "OFF"
        self.ventilation_mode: str = "AUTO"      # "AUTO", "OPEN", "CLOSED"
        self.slot_rgb_active: Dict[str, str] = {} # e.g. {"ROW-A-COL-1": "#00FFCC"}
        self.last_peltier_active: bool = False
        self.last_ventilation_servo_angle: int = SERVO_CLOSED_ANGLE


class ActuatorService:
    """
    Thread-safe actuator state & closed-loop hysteresis control service.
    """

    def __init__(self):
        self._states: Dict[str, CabinetActuatorState] = {}
        self._lock = threading.Lock()

    def reset(self) -> None:
        """Resets all cabinet actuator states (used in test fixtures)."""
        with self._lock:
            self._states.clear()

    def _get_or_create_state(self, cabinet_location: str) -> CabinetActuatorState:
        if cabinet_location not in self._states:
            self._states[cabinet_location] = CabinetActuatorState(cabinet_location)
        return self._states[cabinet_location]

    def evaluate_actuators(
        self,
        cabinet_location: str,
        current_temp: float,
        current_humidity: float,
        target_temp: float,
        target_humidity: float,
    ) -> Dict[str, Any]:
        """
        Evaluates dynamic actuator outputs using live sensor telemetry.
        Updates state and returns actuator command payload for telemetry downlink.
        """
        with self._lock:
            state = self._get_or_create_state(cabinet_location)

            outputs = compute_autonomous_actuator_state(
                current_temp=current_temp,
                current_humidity=current_humidity,
                target_temp=target_temp,
                target_humidity=target_humidity,
                peltier_override=state.peltier_mode,
                ventilation_override=state.ventilation_mode,
                min_safe_temp=MIN_SAFE_TEMP_C,
            )

            state.last_peltier_active = outputs["peltier_active"]
            state.last_ventilation_servo_angle = outputs["ventilation_servo_angle"]

            return {
                "peltier_active": state.last_peltier_active,
                "ventilation_servo_angle": state.last_ventilation_servo_angle,
                "slot_rgb_active": dict(state.slot_rgb_active),
                "peltier_mode": state.peltier_mode,
                "ventilation_mode": state.ventilation_mode,
            }

    def update_actuator_command(
        self,
        cabinet_location: str,
        peltier_mode: str,
        ventilation_mode: str,
        locate_slot: Optional[str] = None,
        locate_color: Optional[str] = DEFAULT_LOCATE_COLOR,
        clear_slots: bool = False,
        current_temp: Optional[float] = None,
        current_humidity: Optional[float] = None,
        target_temp: float = 25.0,
        target_humidity: float = 40.0,
    ) -> Dict[str, Any]:
        """
        Updates actuator operating modes and slot locators for a cabinet.
        Computes instantaneous physical outputs and returns full actuator state response.
        """
        with self._lock:
            state = self._get_or_create_state(cabinet_location)

            state.peltier_mode = peltier_mode
            state.ventilation_mode = ventilation_mode

            if clear_slots:
                state.slot_rgb_active.clear()

            if locate_slot:
                color = locate_color if (locate_color and locate_color.startswith("#")) else DEFAULT_LOCATE_COLOR
                state.slot_rgb_active[locate_slot] = color

            temp_to_use = current_temp if current_temp is not None else target_temp
            humidity_to_use = current_humidity if current_humidity is not None else target_humidity

            outputs = compute_autonomous_actuator_state(
                current_temp=temp_to_use,
                current_humidity=humidity_to_use,
                target_temp=target_temp,
                target_humidity=target_humidity,
                peltier_override=state.peltier_mode,
                ventilation_override=state.ventilation_mode,
                min_safe_temp=MIN_SAFE_TEMP_C,
            )

            state.last_peltier_active = outputs["peltier_active"]
            state.last_ventilation_servo_angle = outputs["ventilation_servo_angle"]

            return {
                "cabinet_location": state.cabinet_location,
                "peltier_mode": state.peltier_mode,
                "ventilation_mode": state.ventilation_mode,
                "peltier_active": state.last_peltier_active,
                "ventilation_servo_angle": state.last_ventilation_servo_angle,
                "slot_rgb_active": dict(state.slot_rgb_active),
            }

    def get_actuator_state(
        self,
        cabinet_location: str,
        current_temp: Optional[float] = None,
        current_humidity: Optional[float] = None,
        target_temp: float = 25.0,
        target_humidity: float = 40.0,
    ) -> Dict[str, Any]:
        """
        Retrieves the current actuator configuration and calculated outputs for a cabinet.
        """
        with self._lock:
            state = self._get_or_create_state(cabinet_location)

            if current_temp is not None and current_humidity is not None:
                outputs = compute_autonomous_actuator_state(
                    current_temp=current_temp,
                    current_humidity=current_humidity,
                    target_temp=target_temp,
                    target_humidity=target_humidity,
                    peltier_override=state.peltier_mode,
                    ventilation_override=state.ventilation_mode,
                    min_safe_temp=MIN_SAFE_TEMP_C,
                )
                state.last_peltier_active = outputs["peltier_active"]
                state.last_ventilation_servo_angle = outputs["ventilation_servo_angle"]

            return {
                "cabinet_location": state.cabinet_location,
                "peltier_mode": state.peltier_mode,
                "ventilation_mode": state.ventilation_mode,
                "peltier_active": state.last_peltier_active,
                "ventilation_servo_angle": state.last_ventilation_servo_angle,
                "slot_rgb_active": dict(state.slot_rgb_active),
            }

    def clear_slot_locators(self, cabinet_location: str) -> None:
        """Clears all active slot locators for the given cabinet."""
        with self._lock:
            if cabinet_location in self._states:
                self._states[cabinet_location].slot_rgb_active.clear()

    def set_slot_locator(self, cabinet_location: str, slot: str, color: str = DEFAULT_LOCATE_COLOR) -> None:
        """Sets a slot RGB locator LED to a specific hex color."""
        with self._lock:
            state = self._get_or_create_state(cabinet_location)
            state.slot_rgb_active[slot] = color


actuator_service = ActuatorService()
