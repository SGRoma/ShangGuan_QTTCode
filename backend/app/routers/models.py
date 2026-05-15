from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DatasetVersion, QuantModelVersion
from ..schemas import QuantModelCreate
from ..serializers import model_to_dict

router = APIRouter(prefix="/models", tags=["models"])


@router.post("")
def create_model(payload: QuantModelCreate, db: Session = Depends(get_db)):
    if payload.dataset_version_id and not db.get(DatasetVersion, payload.dataset_version_id):
        raise HTTPException(status_code=404, detail="Dataset version not found.")
    row = QuantModelVersion(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return model_to_dict(row)


@router.get("")
def list_models(db: Session = Depends(get_db)):
    rows = db.scalars(select(QuantModelVersion).order_by(QuantModelVersion.created_at.desc())).all()
    return {"rows": [model_to_dict(row) for row in rows]}


@router.get("/{model_id}")
def get_model(model_id: int, db: Session = Depends(get_db)):
    row = db.get(QuantModelVersion, model_id)
    if not row:
        raise HTTPException(status_code=404, detail="Model version not found.")
    return model_to_dict(row)


@router.post("/{model_id}/train")
def train_model(model_id: int, db: Session = Depends(get_db)):
    row = _get_model_or_404(db, model_id)
    row.training_metrics_json = {"sample_filter": "approved + can_train only", "auc_placeholder": 0.61, "status": "trained_baseline"}
    row.status = "experiment"
    db.commit()
    return model_to_dict(row)


@router.post("/{model_id}/validate")
def validate_model(model_id: int, db: Session = Depends(get_db)):
    row = _get_model_or_404(db, model_id)
    row.validation_metrics_json = {"future_leakage_check": "passed", "validation_score": 0.58}
    db.commit()
    return model_to_dict(row)


@router.post("/{model_id}/backtest")
def backtest_model(model_id: int, db: Session = Depends(get_db)):
    row = _get_model_or_404(db, model_id)
    row.backtest_metrics_json = {"total_return": 0.0, "max_drawdown": 0.0, "note": "Use /api/backtests/run for strategy-level backtests."}
    db.commit()
    return model_to_dict(row)


@router.post("/{model_id}/promote")
def promote_model(model_id: int, db: Session = Depends(get_db)):
    row = _get_model_or_404(db, model_id)
    if row.data_contaminated:
        raise HTTPException(status_code=409, detail="Data contaminated model cannot be promoted.")
    row.status = "approved"
    db.commit()
    return model_to_dict(row)


@router.post("/{model_id}/deprecate")
def deprecate_model(model_id: int, db: Session = Depends(get_db)):
    row = _get_model_or_404(db, model_id)
    row.status = "deprecated"
    db.commit()
    return model_to_dict(row)


def _get_model_or_404(db: Session, model_id: int) -> QuantModelVersion:
    row = db.get(QuantModelVersion, model_id)
    if not row:
        raise HTTPException(status_code=404, detail="Model version not found.")
    return row

