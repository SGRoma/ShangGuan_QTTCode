from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DataModelDefinition
from ..schemas import DataModelBatchRunRequest, DataModelCreate, DataModelRunRequest
from ..serializers import model_to_dict
from ..services.model_runtime import ensure_default_models, run_data_model

router = APIRouter(prefix="/data-models", tags=["data-models"])


@router.get("")
def list_data_models(db: Session = Depends(get_db)):
    ensure_default_models(db)
    rows = db.scalars(select(DataModelDefinition).order_by(DataModelDefinition.created_at.desc())).all()
    return {"rows": [model_to_dict(row) for row in rows]}


@router.post("")
def create_data_model(payload: DataModelCreate, db: Session = Depends(get_db)):
    row = DataModelDefinition(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return model_to_dict(row)


@router.get("/{model_id}")
def get_data_model(model_id: int, db: Session = Depends(get_db)):
    row = db.get(DataModelDefinition, model_id)
    if not row:
        raise HTTPException(status_code=404, detail="Data model not found.")
    return model_to_dict(row)


@router.post("/{model_id}/run")
def run_model(model_id: int, payload: DataModelRunRequest, db: Session = Depends(get_db)):
    model = db.get(DataModelDefinition, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Data model not found.")
    result = run_data_model(db, payload.stock_code, model, payload.start, payload.generate_dataset)
    model.last_run_at = datetime.utcnow()
    model.last_run_summary_json = result
    db.commit()
    db.refresh(model)
    return {"model": model_to_dict(model), "result": result}


@router.post("/batch-run")
def run_models(payload: DataModelBatchRunRequest, db: Session = Depends(get_db)):
    if not payload.stock_code.strip():
        raise HTTPException(status_code=400, detail="Stock code is required.")
    if not payload.data_model_ids:
        raise HTTPException(status_code=400, detail="Select at least one data model.")
    results = []
    for model_id in payload.data_model_ids:
        model = db.get(DataModelDefinition, model_id)
        if not model:
            raise HTTPException(status_code=404, detail=f"Data model {model_id} not found.")
        result = run_data_model(db, payload.stock_code, model, payload.start, payload.generate_dataset)
        model.last_run_at = datetime.utcnow()
        model.last_run_summary_json = result
        db.commit()
        db.refresh(model)
        results.append({"model": model_to_dict(model), "result": result})
    return {"stock_code": payload.stock_code, "results": results, "run_count": len(results)}
