"""
Cabinet endpoints — this is where the app lets the user customise the
temperature/humidity setpoint for a cabinet/location according to whatever
component is stored there, and where the ESP32 posts live sensor readings.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas, auth
from app.services.jitter_filter import jitter_filter
from app.services.websocket_manager import ws_manager
from app.services.alert_throttler import handle_condition_violation
from app.services.arrhenius_engine import arrhenius_engine
from app.services.actuator_service import actuator_service


router = APIRouter(prefix="/cabinet", tags=["Cabinet Control"])


def _condition_status(setting: models.CabinetSetting) -> str:
    if setting.last_reported_temperature_c is None or setting.last_reported_humidity_percent is None:
        return "NO_DATA"

    temp_ok = abs(setting.last_reported_temperature_c - setting.target_temperature_c) <= 2.0
    humidity_ok = setting.last_reported_humidity_percent <= setting.target_humidity_percent
    return "OK" if (temp_ok and humidity_ok) else "OUT_OF_RANGE"


def _to_cabinet_setting_out(
    cabinet: models.CabinetSetting,
    reading: Optional[schemas.CabinetTelemetryIn] = None,
    actuator_commands: Optional[Dict[str, Any]] = None,
) -> schemas.CabinetSettingOut:
    status_ = _condition_status(cabinet)
    status_label = "NORMAL" if status_ == "OK" else status_
    return schemas.CabinetSettingOut(
        id=cabinet.id,
        cabinet_location=cabinet.cabinet_location,
        target_temperature_c=cabinet.target_temperature_c,
        target_humidity_percent=cabinet.target_humidity_percent,
        last_reported_temperature_c=cabinet.last_reported_temperature_c,
        last_reported_humidity_percent=cabinet.last_reported_humidity_percent,
        last_reading_at=cabinet.last_reading_at,
        condition_status=status_,
        status=status_label,
        temperature_c=reading.temperature_c if reading else cabinet.last_reported_temperature_c,
        humidity_percent=reading.humidity_percent if reading else cabinet.last_reported_humidity_percent,
        door_open=bool(getattr(reading, "door_open", False)),
        actuator_commands=actuator_commands,
    )


@router.post("", response_model=schemas.CabinetSettingOut, status_code=201)
def create_or_get_cabinet(
    payload: schemas.CabinetSettingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    existing = (
        db.query(models.CabinetSetting)
        .filter(models.CabinetSetting.cabinet_location == payload.cabinet_location)
        .first()
    )
    if existing:
        raise HTTPException(400, "Cabinet location already configured — use PATCH to update it")

    cabinet = models.CabinetSetting(**payload.model_dump())
    db.add(cabinet)
    db.commit()
    db.refresh(cabinet)
    return _to_cabinet_setting_out(cabinet)


@router.get("", response_model=List[schemas.CabinetSettingOut])
def list_cabinets(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    cabinets = db.query(models.CabinetSetting).all()
    return [_to_cabinet_setting_out(c) for c in cabinets]


@router.patch("/{cabinet_location}", response_model=schemas.CabinetSettingOut)
def update_cabinet_setpoint(
    cabinet_location: str,
    payload: schemas.CabinetSettingUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """User customises target temperature/humidity to suit whatever is now stored there."""
    cabinet = (
        db.query(models.CabinetSetting)
        .filter(models.CabinetSetting.cabinet_location == cabinet_location)
        .first()
    )
    if not cabinet:
        raise HTTPException(404, "Cabinet not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(cabinet, field, value)

    db.commit()
    db.refresh(cabinet)
    return _to_cabinet_setting_out(cabinet)


@router.post("/{cabinet_location}/telemetry", response_model=schemas.CabinetSettingOut)
async def post_telemetry(
    cabinet_location: str,
    reading: schemas.CabinetTelemetryIn,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    _device_auth: bool = Depends(auth.verify_device_hmac),
):
    """
    Ingests live telemetry from authenticated ESP32 devices via HMAC-SHA256 signature
    or device token.
    Applies jitter smoothing (median + EMA), throttles condition alerts to prevent email
    flooding, schedules background email delivery, and broadcasts instantaneous WebSocket frames.
    """
    cabinet = (
        db.query(models.CabinetSetting)
        .filter(models.CabinetSetting.cabinet_location == cabinet_location)
        .first()
    )
    if not cabinet:
        raise HTTPException(404, "Cabinet not found")

    # 1. Apply sensor jitter smoothing (median + exponential moving average)
    smoothed_temp, smoothed_humidity = jitter_filter.smooth_reading(
        cabinet_location,
        reading.temperature_c,
        reading.humidity_percent,
    )

    # 2. Update database record with smoothed environmental metrics
    cabinet.last_reported_temperature_c = smoothed_temp
    cabinet.last_reported_humidity_percent = smoothed_humidity
    cabinet.last_reading_at = datetime.utcnow()
    db.commit()
    db.refresh(cabinet)

    # Record telemetry for cumulative Arrhenius stress hours tracking
    arrhenius_engine.record_telemetry(
        cabinet_location=cabinet_location,
        temp_c=smoothed_temp,
        humidity_percent=smoothed_humidity,
        timestamp=cabinet.last_reading_at,
    )

    status_ = _condition_status(cabinet)

    # 3. Resilient Alert Throttling & Asynchronous Notification Dispatch
    if status_ == "OUT_OF_RANGE":
        handle_condition_violation(
            cabinet_location=cabinet_location,
            current_temp=reading.temperature_c,
            current_humidity=reading.humidity_percent,
            target_temp=cabinet.target_temperature_c,
            target_humidity=cabinet.target_humidity_percent,
            db=db,
            background_tasks=background_tasks,
        )

    # 4. Closed-Loop Actuator Evaluation using smoothed environmental metrics
    actuator_commands = actuator_service.evaluate_actuators(
        cabinet_location=cabinet_location,
        current_temp=smoothed_temp,
        current_humidity=smoothed_humidity,
        target_temp=cabinet.target_temperature_c,
        target_humidity=cabinet.target_humidity_percent,
    )

    # 5. Instantaneous Real-Time Broadcast via WebSocket /ws/telemetry
    broadcast_payload = {
        "type": "TELEMETRY_UPDATE",
        "timestamp": int(datetime.utcnow().timestamp()),
        "cabinet_location": cabinet_location,
        "telemetry": {
            "temperature_c": round(reading.temperature_c, 2),
            "humidity_percent": round(reading.humidity_percent, 2),
            "smoothed_temp": round(smoothed_temp, 2),
            "smoothed_humidity": round(smoothed_humidity, 2),
            "door_open": bool(reading.door_open),
        },
        "actuators": actuator_commands,
    }
    await ws_manager.broadcast(broadcast_payload)

    # 6. Construct Downlink Response returning dynamic actuator commands
    return _to_cabinet_setting_out(
        cabinet,
        reading=reading,
        actuator_commands=actuator_commands,
    )

