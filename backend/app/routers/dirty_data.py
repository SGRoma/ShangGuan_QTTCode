from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DatasetVersion, DirtyDataRecord, QuantModelVersion, StrategyIdea, TrainingSample
from ..schemas import DirtyDataMarkRequest
from ..serializers import model_to_dict

router = APIRouter(prefix="/dirty-data", tags=["dirty-data"])


@router.post("/mark")
def mark_dirty_data(payload: DirtyDataMarkRequest, db: Session = Depends(get_db)):
    row = DirtyDataRecord(**payload.model_dump(), status="open")
    db.add(row)
    _apply_dirty_status(db, payload.target_type, payload.target_id, payload.action)
    db.commit()
    db.refresh(row)
    return {"record": model_to_dict(row), "impact": impact_for(row.id, db)}


@router.get("")
def list_dirty_data(db: Session = Depends(get_db)):
    rows = db.scalars(select(DirtyDataRecord).order_by(DirtyDataRecord.created_at.desc())).all()
    return {"rows": [model_to_dict(row) for row in rows]}


@router.get("/{record_id}/impact")
def impact_for(record_id: int, db: Session = Depends(get_db)):
    row = db.get(DirtyDataRecord, record_id)
    if not row:
        raise HTTPException(status_code=404, detail="Dirty data record not found.")
    affected_datasets: list[dict] = []
    affected_models: list[dict] = []
    if row.target_type in {"training_sample", "sample"}:
        sample = db.get(TrainingSample, row.target_id)
        if sample and sample.dataset_version_id:
            dataset = db.get(DatasetVersion, sample.dataset_version_id)
            if dataset:
                affected_datasets.append(model_to_dict(dataset))
            models = db.scalars(select(QuantModelVersion).where(QuantModelVersion.dataset_version_id == sample.dataset_version_id)).all()
            for model in models:
                affected_models.append(model_to_dict(model))
    if row.target_type in {"dataset", "dataset_version"}:
        dataset = db.get(DatasetVersion, row.target_id)
        if dataset:
            affected_datasets.append(model_to_dict(dataset))
        models = db.scalars(select(QuantModelVersion).where(QuantModelVersion.dataset_version_id == row.target_id)).all()
        for model in models:
            affected_models.append(model_to_dict(model))
    if row.target_type in {"model", "quant_model_version"}:
        model = db.get(QuantModelVersion, row.target_id)
        if model:
            affected_models.append(model_to_dict(model))
    return {"dirty_record": model_to_dict(row), "affected_datasets": affected_datasets, "affected_models": affected_models}


@router.post("/{record_id}/resolve")
def resolve_dirty_data(record_id: int, resolved_by: str = "human_reviewer", db: Session = Depends(get_db)):
    row = db.get(DirtyDataRecord, record_id)
    if not row:
        raise HTTPException(status_code=404, detail="Dirty data record not found.")
    row.status = "resolved"
    row.resolved_by = resolved_by
    row.resolved_at = datetime.utcnow()
    db.commit()
    return model_to_dict(row)


@router.post("/rebuild-dataset")
def rebuild_dataset(dataset_id: int, db: Session = Depends(get_db)):
    dataset = db.get(DatasetVersion, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset version not found.")
    clean_samples = [s for s in dataset.samples if s.status == "approved" and s.can_train]
    next_version = f"{dataset.version}_clean_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    rebuilt = DatasetVersion(
        dataset_name=dataset.dataset_name,
        version=next_version,
        sample_count=len(clean_samples),
        approved_sample_count=len(clean_samples),
        excluded_sample_count=max(0, dataset.sample_count - len(clean_samples)),
        feature_config_json=dataset.feature_config_json,
        label_config_json=dataset.label_config_json,
        status="draft",
        description=f"Rebuilt from dataset {dataset.id} after dirty data review.",
    )
    db.add(rebuilt)
    db.commit()
    db.refresh(rebuilt)
    return model_to_dict(rebuilt)


@router.post("/retrain-affected-models")
def retrain_affected_models(dataset_id: int, db: Session = Depends(get_db)):
    models = db.scalars(select(QuantModelVersion).where(QuantModelVersion.dataset_version_id == dataset_id)).all()
    for model in models:
        model.data_contaminated = True
        model.status = "deprecated"
    db.commit()
    return {"updated_models": [model_to_dict(model) for model in models], "rule": "Affected models are marked contaminated; replacement requires human approval."}


def _apply_dirty_status(db: Session, target_type: str, target_id: int, action: str) -> None:
    status = action if action in {"invalid", "negative_sample", "deprecated"} else "invalid"
    if target_type in {"training_sample", "sample"}:
        row = db.get(TrainingSample, target_id)
        if row:
            row.status = status
            row.can_train = False
    elif target_type in {"strategy_idea", "strategy"}:
        row = db.get(StrategyIdea, target_id)
        if row:
            row.status = status
            row.can_train = False
            row.can_trade = False
    elif target_type in {"model", "quant_model_version"}:
        row = db.get(QuantModelVersion, target_id)
        if row:
            row.data_contaminated = True
            row.status = "deprecated"

