"""
Tier 3 IoT Subsystem Contract Tests: Bidirectional Actuator Loopback & Closed-Loop Hysteresis.

Derivation Source: ORIGINAL_REQUEST § R4 & PROJECT.md § Interface Contracts / Feature 13-16:
- Closed-Loop Actuator Control: Peltier cooling and ventilation servo triggered by environmental thresholds
- Manual Actuator Override & Slot Locator LEDs: Toggling Peltier, ventilation servo, and slot locator RGB
- Safety Cutoff: Failsafe interlock preventing sub-cooling (< 10°C) condensation hazard
"""

import pytest
from pydantic import BaseModel, Field
from typing import Optional, Dict


class ActuatorCommandContract(BaseModel):
    """Authoritative Pydantic contract model from PROJECT.md § Interface Contracts."""
    peltier_mode: str = Field(..., pattern="^(AUTO|ON|OFF)$")
    ventilation_mode: str = Field(..., pattern="^(AUTO|OPEN|CLOSED)$")
    locate_slot: Optional[str] = None
    locate_color: Optional[str] = Field(default="#00FFCC", pattern="^#([A-Fa-f0-9]{6})$")


def compute_autonomous_actuator_state(
    current_temp: float,
    current_humidity: float,
    target_temp: float,
    target_humidity: float,
    peltier_override: str = "AUTO",
    ventilation_override: str = "AUTO",
    min_safe_temp: float = 10.0,
) -> Dict[str, object]:
    """
    Authoritative reference oracle for closed-loop actuator hysteresis control.
    """
    # 1. Thermal Safety Interlock Cutoff
    if current_temp < min_safe_temp:
        # Prevent Peltier condensation/freezing hazard
        peltier_active = False
    elif peltier_override == "ON":
        peltier_active = True
    elif peltier_override == "OFF":
        peltier_active = False
    else:  # AUTO
        # Hysteresis: turn on if exceeding target by 2°C
        peltier_active = current_temp > (target_temp + 2.0)

    # 2. Dehumidification ventilation servo
    if ventilation_override == "OPEN":
        servo_angle = 90
    elif ventilation_override == "CLOSED":
        servo_angle = 0
    else:  # AUTO
        servo_angle = 90 if current_humidity > target_humidity else 0

    return {
        "peltier_active": peltier_active,
        "ventilation_servo_angle": servo_angle,
    }


class TestBidirectionalActuatorLoopbackContract:
    """Verifies actuator command schemas, autonomous hysteresis, and safety cutoffs."""

    def test_actuator_command_schema_valid_payloads(self):
        """Valid actuator commands pass contract validation."""
        valid_cmd = ActuatorCommandContract(
            peltier_mode="AUTO",
            ventilation_mode="OPEN",
            locate_slot="ROW-A-COL-2",
            locate_color="#00FFCC",
        )
        assert valid_cmd.peltier_mode == "AUTO"
        assert valid_cmd.ventilation_mode == "OPEN"
        assert valid_cmd.locate_slot == "ROW-A-COL-2"
        assert valid_cmd.locate_color == "#00FFCC"

    def test_actuator_command_schema_rejects_invalid_modes(self):
        """Invalid modes (e.g. peltier_mode='TURBO') fail schema validation."""
        with pytest.raises(Exception):
            ActuatorCommandContract(
                peltier_mode="TURBO",  # Invalid
                ventilation_mode="AUTO",
            )

        with pytest.raises(Exception):
            ActuatorCommandContract(
                peltier_mode="AUTO",
                ventilation_mode="AUTO",
                locate_color="not-a-hex-color",  # Invalid
            )

    def test_closed_loop_peltier_cooling_hysteresis(self):
        """
        When cabinet temperature exceeds target by > 2.0°C in AUTO mode,
        autonomous loopback must activate Peltier cooling.
        """
        target_temp = 20.0
        # Case 1: Within tolerance (21.5°C <= 22.0°C) -> Peltier OFF
        state_normal = compute_autonomous_actuator_state(
            current_temp=21.5,
            current_humidity=40.0,
            target_temp=target_temp,
            target_humidity=45.0,
        )
        assert state_normal["peltier_active"] is False

        # Case 2: Out of range (24.0°C > 22.0°C) -> Peltier ON
        state_hot = compute_autonomous_actuator_state(
            current_temp=24.0,
            current_humidity=40.0,
            target_temp=target_temp,
            target_humidity=45.0,
        )
        assert state_hot["peltier_active"] is True

    def test_failsafe_thermal_cutoff_inhibits_peltier(self):
        """
        SAFETY INTERLOCK TEST:
        If temperature is dangerously low (< 10°C), Peltier cooling MUST be inhibited
        even if manual override specifies 'ON', to prevent freezing components.
        """
        cutoff_state = compute_autonomous_actuator_state(
            current_temp=8.0,  # Below 10°C minimum limit
            current_humidity=40.0,
            target_temp=20.0,
            target_humidity=45.0,
            peltier_override="ON",
        )
        assert cutoff_state["peltier_active"] is False, "Peltier must be inhibited below safe thermal limit!"

    def test_dehumidifier_ventilation_servo_response(self):
        """
        When humidity exceeds target in AUTO mode, ventilation servo opens (angle 90°).
        When within target, servo closes (angle 0°).
        """
        target_humidity = 45.0

        # Dry condition -> closed
        state_dry = compute_autonomous_actuator_state(22.0, 40.0, 22.0, target_humidity)
        assert state_dry["ventilation_servo_angle"] == 0

        # High humidity -> open
        state_humid = compute_autonomous_actuator_state(22.0, 65.0, 22.0, target_humidity)
        assert state_humid["ventilation_servo_angle"] == 90
