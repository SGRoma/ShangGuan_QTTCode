from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AnalysisModelDefinition
from ..schemas import AnalysisModelCreate, ControlRunRequest
from ..serializers import model_to_dict
from ..services.model_runtime import ensure_default_models, run_control_pipeline

router = APIRouter(prefix="/analysis-models", tags=["analysis-models"])


@router.get("")
def list_analysis_models(db: Session = Depends(get_db)):
    ensure_default_models(db)
    rows = db.scalars(select(AnalysisModelDefinition).order_by(AnalysisModelDefinition.created_at.desc())).all()
    return {"rows": [model_to_dict(row) for row in rows]}


@router.post("")
def create_analysis_model(payload: AnalysisModelCreate, db: Session = Depends(get_db)):
    row = AnalysisModelDefinition(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return model_to_dict(row)


@router.get("/{model_id}")
def get_analysis_model(model_id: int, db: Session = Depends(get_db)):
    row = db.get(AnalysisModelDefinition, model_id)
    if not row:
        raise HTTPException(status_code=404, detail="Analysis model not found.")
    return model_to_dict(row)


@router.post("/{model_id}/run")
def run_analysis_model(model_id: int, payload: ControlRunRequest, db: Session = Depends(get_db)):
    if model_id != payload.analysis_model_id:
        payload.analysis_model_id = model_id
    return run_control_pipeline(db, payload)
