"""
Actuator Control API endpoints.

Allows dashboard operators to:
1. POST /cabinet/{cabinet_location}/actuators: Set actuator operating modes (AUTO, ON, OFF / OPEN, CLOSED),
   trigger slot RGB locator LEDs, evaluate instantaneous physical states, broadcast live via WebSocket,
   and return the resulting actuator status.
2. GET /cabinet/{cabinet_location}/actuators: Inspect current actuator modes and physical states.
3. DELETE /cabinet/{cabinet_location}/actuators/slots: Clear all active slot locators for the cabinet.
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import auth, models, schemas
from app.services.actuator_service import actuator_service
from app.services.websocket_manager import ws_manager

router = APIRouter(prefix="/cabinet", tags=["Actuators"])


@router.post("/{cabinet_location}/actuators", response_model=schemas.ActuatorStateResponse)
async def update_cabinet_actuators(
    cabinet_location: str,
    payload: schemas.ActuatorCommandRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Sets actuator operating modes and slot RGB locator LEDs for a cabinet.
    Evaluates instantaneous physical output states (incorporating thermal safety interlocks)
    and broadcasts updates to connected WebSocket subscribers.
    """
    cabinet = (
        db.query(models.CabinetSetting)
        .filter(models.CabinetSetting.cabinet_location == cabinet_location)
        .first()
    )
    if not cabinet:
        raise HTTPException(status_code=404, detail="Cabinet not found")

    state_dict = actuator_service.update_actuator_command(
        cabinet_location=cabinet_location,
        peltier_mode=payload.peltier_mode,
        ventilation_mode=payload.ventilation_mode,
        locate_slot=payload.locate_slot,
        locate_color=payload.locate_color,
        clear_slots=bool(payload.clear_slots),
        current_temp=cabinet.last_reported_temperature_c,
        current_humidity=cabinet.last_reported_humidity_percent,
        target_temp=cabinet.target_temperature_c,
        target_humidity=cabinet.target_humidity_percent,
    )

    # Broadcast instantaneous update to connected WebSocket clients
    broadcast_payload = {
        "type": "ACTUATOR_UPDATE",
        "timestamp": int(datetime.utcnow().timestamp()),
        "cabinet_location": cabinet_location,
        "actuators": {
            "peltier_mode": state_dict["peltier_mode"],
            "ventilation_mode": state_dict["ventilation_mode"],
            "peltier_active": state_dict["peltier_active"],
            "ventilation_servo_angle": state_dict["ventilation_servo_angle"],
            "slot_rgb_active": state_dict["slot_rgb_active"],
        },
    }
    await ws_manager.broadcast(broadcast_payload)

    return schemas.ActuatorStateResponse(**state_dict)


@router.get("/{cabinet_location}/actuators", response_model=schemas.ActuatorStateResponse)
def get_cabinet_actuators(
    cabinet_location: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Retrieves current actuator settings, active slot locators, and calculated outputs for a cabinet.
    """
    cabinet = (
        db.query(models.CabinetSetting)
        .filter(models.CabinetSetting.cabinet_location == cabinet_location)
        .first()
    )
    if not cabinet:
        raise HTTPException(status_code=404, detail="Cabinet not found")

    state_dict = actuator_service.get_actuator_state(
        cabinet_location=cabinet_location,
        current_temp=cabinet.last_reported_temperature_c,
        current_humidity=cabinet.last_reported_humidity_percent,
        target_temp=cabinet.target_temperature_c,
        target_humidity=cabinet.target_humidity_percent,
    )

    return schemas.ActuatorStateResponse(**state_dict)


@router.delete("/{cabinet_location}/actuators/slots", response_model=schemas.ActuatorStateResponse)
async def clear_cabinet_slot_locators(
    cabinet_location: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Clears all active slot RGB locator LEDs for a cabinet.
    """
    cabinet = (
        db.query(models.CabinetSetting)
        .filter(models.CabinetSetting.cabinet_location == cabinet_location)
        .first()
    )
    if not cabinet:
        raise HTTPException(status_code=404, detail="Cabinet not found")

    actuator_service.clear_slot_locators(cabinet_location)

    state_dict = actuator_service.get_actuator_state(
        cabinet_location=cabinet_location,
        current_temp=cabinet.last_reported_temperature_c,
        current_humidity=cabinet.last_reported_humidity_percent,
        target_temp=cabinet.target_temperature_c,
        target_humidity=cabinet.target_humidity_percent,
    )

    broadcast_payload = {
        "type": "ACTUATOR_UPDATE",
        "timestamp": int(datetime.utcnow().timestamp()),
        "cabinet_location": cabinet_location,
        "actuators": {
            "peltier_mode": state_dict["peltier_mode"],
            "ventilation_mode": state_dict["ventilation_mode"],
            "peltier_active": state_dict["peltier_active"],
            "ventilation_servo_angle": state_dict["ventilation_servo_angle"],
            "slot_rgb_active": state_dict["slot_rgb_active"],
        },
    }
    await ws_manager.broadcast(broadcast_payload)

    return schemas.ActuatorStateResponse(**state_dict)
