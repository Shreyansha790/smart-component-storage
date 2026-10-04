"""
Pydantic (v2) schemas used for request validation and API responses.
"""

from datetime import date, datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.models import UserRole, AlertType


# ---------------- Auth / User ----------------

class UserCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr                     # this is the address alert emails go to
    password: str = Field(..., min_length=6)
    role: UserRole = UserRole.technician


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: EmailStr
    role: UserRole
    is_active: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------------- Component / Inventory ----------------

class ComponentBase(BaseModel):
    batch_id: str = Field(..., max_length=80)
    part_number: str = Field(..., max_length=120)
    manufacturer: str = Field(..., max_length=120)
    category: str = Field(..., max_length=80)
    cabinet_location: str = Field(..., max_length=80)
    quantity: int = Field(..., ge=0)
    stored_date: date
    last_accessed_date: Optional[date] = None
    min_temperature_c: float
    max_temperature_c: float
    max_humidity_percent: float = Field(..., ge=0, le=100)
    shelf_life_days: int = Field(..., gt=0)
    notes: Optional[str] = None


class ComponentCreate(ComponentBase):
    pass


class ComponentUpdate(BaseModel):
    """All fields optional -> supports partial PATCH updates."""
    batch_id: Optional[str] = None
    part_number: Optional[str] = None
    manufacturer: Optional[str] = None
    category: Optional[str] = None
    cabinet_location: Optional[str] = None
    quantity: Optional[int] = Field(None, ge=0)
    stored_date: Optional[date] = None
    last_accessed_date: Optional[date] = None
    min_temperature_c: Optional[float] = None
    max_temperature_c: Optional[float] = None
    max_humidity_percent: Optional[float] = Field(None, ge=0, le=100)
    shelf_life_days: Optional[int] = Field(None, gt=0)
    notes: Optional[str] = None


class ComponentOut(ComponentBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner_id: int
    days_in_storage: int
    days_until_shelf_life: int
    status: str  # OK / APPROACHING_LIMIT / EXPIRED
    effective_remaining_days: Optional[float] = None
    dynamic_degradation_score: Optional[float] = None


class ArrheniusDegradationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    component_id: int
    nominal_shelf_life_days: int
    stored_days: int
    cumulative_temp_stress_hours: float
    cumulative_humidity_stress_hours: float
    arrhenius_acceleration_factor: float
    dynamic_degradation_score: float
    effective_remaining_days: float
    status: str


# ---------------- Cabinet settings & Telemetry ----------------

class CabinetSettingBase(BaseModel):
    target_temperature_c: float
    target_humidity_percent: float = Field(..., ge=0, le=100)


class CabinetSettingCreate(CabinetSettingBase):
    cabinet_location: str = Field(..., max_length=80)


class CabinetSettingUpdate(BaseModel):
    target_temperature_c: Optional[float] = None
    target_humidity_percent: Optional[float] = Field(None, ge=0, le=100)


class CabinetTelemetryIn(BaseModel):
    """Payload the ESP32 posts periodically."""
    temperature_c: float
    humidity_percent: float = Field(..., ge=0, le=100)
    door_open: Optional[bool] = False


class CabinetSettingOut(CabinetSettingBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cabinet_location: str
    last_reported_temperature_c: Optional[float]
    last_reported_humidity_percent: Optional[float]
    last_reading_at: Optional[datetime]
    condition_status: str  # OK / OUT_OF_RANGE / NO_DATA
    status: Optional[str] = None
    temperature_c: Optional[float] = None
    humidity_percent: Optional[float] = None
    door_open: Optional[bool] = False
    actuator_commands: Optional[Dict[str, Any]] = None


# ---------------- Alerts ----------------

class AlertLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    component_id: Optional[int] = None
    alert_type: AlertType
    message: str
    sent_at: datetime
    email_sent_to: EmailStr


# ---------------- Actuators ----------------

class ActuatorCommandRequest(BaseModel):
    peltier_mode: str = Field(..., pattern="^(AUTO|ON|OFF)$")
    ventilation_mode: str = Field(..., pattern="^(AUTO|OPEN|CLOSED)$")
    locate_slot: Optional[str] = None
    locate_color: Optional[str] = Field(default="#00FFCC", pattern="^#([A-Fa-f0-9]{6})$")
    clear_slots: Optional[bool] = False


class ActuatorCommands(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    peltier_active: bool
    ventilation_servo_angle: int
    slot_rgb_active: Dict[str, str] = Field(default_factory=dict)


class ActuatorStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    cabinet_location: str
    peltier_mode: str
    ventilation_mode: str
    peltier_active: bool
    ventilation_servo_angle: int
    slot_rgb_active: Dict[str, str] = Field(default_factory=dict)

