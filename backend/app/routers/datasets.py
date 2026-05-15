from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DatasetVersion, TrainingSample
from ..schemas import DatasetCreate, SampleReviewRequest, TrainingSampleCreate
from ..serializers import model_to_dict

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("")
def create_dataset(payload: DatasetCreate, db: Session = Depends(get_db)):
    row = DatasetVersion(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return model_to_dict(row)


@router.get("")
def list_datasets(db: Session = Depends(get_db)):
    rows = db.scalars(select(DatasetVersion).order_by(DatasetVersion.created_at.desc())).all()
    return {"rows": [model_to_dict(row) for row in rows]}


@router.get("/{dataset_id}")
def get_dataset(dataset_id: int, db: Session = Depends(get_db)):
    row = db.get(DatasetVersion, dataset_id)
    if not row:
        raise HTTPException(status_code=404, detail="Dataset version not found.")
    data = model_to_dict(row)
    data["samples"] = [model_to_dict(sample) for sample in row.samples[-200:]]
    return data


@router.post("/{dataset_id}/samples")
def add_sample(dataset_id: int, payload: TrainingSampleCreate, db: Session = Depends(get_db)):
    dataset = db.get(DatasetVersion, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset version not found.")
    row = TrainingSample(dataset_version_id=dataset_id, **payload.model_dump())
    db.add(row)
    dataset.sample_count += 1
    if row.status == "approved" and row.can_train:
        dataset.approved_sample_count += 1
    db.commit()
    db.refresh(row)
    return model_to_dict(row)


@router.post("/{dataset_id}/generate-from-strategy")
def generate_from_strategy(dataset_id: int, strategy_version_id: int, db: Session = Depends(get_db)):
    dataset = db.get(DatasetVersion, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset version not found.")
    sample = TrainingSample(
        dataset_version_id=dataset_id,
        sample_type="strategy_outcome",
        features_json={"strategy_version_id": strategy_version_id, "feature_guard": "uses_trade_date_or_before"},
        label_json={"label": "pending_human_review"},
        source_type="strategy_version",
        source_id=strategy_version_id,
        quality_score=75,
        status="candidate",
        can_train=False,
    )
    db.add(sample)
    dataset.sample_count += 1
    db.commit()
    db.refresh(sample)
    return {"created": model_to_dict(sample), "rule": "Generated samples are candidate only; human approval is required before training."}


@router.post("/{dataset_id}/approve-samples")
def approve_samples(dataset_id: int, payload: SampleReviewRequest, db: Session = Depends(get_db)):
    return _review_samples(dataset_id, payload, db, force_status="approved", force_can_train=True)


@router.post("/{dataset_id}/exclude-samples")
def exclude_samples(dataset_id: int, payload: SampleReviewRequest, db: Session = Depends(get_db)):
    return _review_samples(dataset_id, payload, db, force_status=payload.status, force_can_train=False)


def _review_samples(dataset_id: int, payload: SampleReviewRequest, db: Session, force_status: str, force_can_train: bool):
    dataset = db.get(DatasetVersion, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset version not found.")
    rows = db.scalars(select(TrainingSample).where(TrainingSample.dataset_version_id == dataset_id, TrainingSample.id.in_(payload.sample_ids))).all()
    for row in rows:
        row.status = force_status
        row.can_train = force_can_train and force_status == "approved"
        row.reviewed_by = payload.reviewed_by
        row.reviewed_at = datetime.utcnow()
    dataset.approved_sample_count = sum(1 for row in dataset.samples if row.status == "approved" and row.can_train)
    dataset.excluded_sample_count = sum(1 for row in dataset.samples if row.status in {"rejected", "negative_sample", "invalid", "deprecated"})
    db.commit()
    return {"updated": len(rows), "dataset": model_to_dict(dataset)}

