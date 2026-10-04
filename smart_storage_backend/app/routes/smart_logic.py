from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import auth, models, schemas
from app.models import Component, CabinetSetting
from app.services.arrhenius_engine import arrhenius_engine


router = APIRouter(
    prefix="/smart-logic",
    tags=["Smart Logic"]
)


@router.get("/component/{component_id}", response_model=schemas.ArrheniusDegradationOut)
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

    eval_result = arrhenius_engine.evaluate_component(
        component=component,
        cabinet=cabinet,
    )

    return schemas.ArrheniusDegradationOut(**eval_result)