from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import auth, models
from app.models import Component, CabinetSetting
from app.services.smart_logic_adapter import analyze_backend_component


router = APIRouter(
    prefix="/smart-logic",
    tags=["Smart Logic"]
)


@router.get("/component/{component_id}")
def analyze_component_with_smart_logic(
    component_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    component = (
        db.query(Component)
        .filter(Component.id == component_id)
        .first()
    )

    if component is None:
        raise HTTPException(
            status_code=404,
            detail="Component not found"
        )

    cabinet = (
        db.query(CabinetSetting)
        .filter(
            CabinetSetting.cabinet_location
            == component.cabinet_location
        )
        .first()
    )

    if cabinet is None:
        raise HTTPException(
            status_code=404,
            detail="Cabinet not found"
        )

    return analyze_backend_component(
        component,
        cabinet
    )