from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import StrategyIdea, StrategyVersion
from ..schemas import StrategyIdeaCreate, StrategyIdeaUpdate, StrategyReviewRequest, StrategyVersionCreate
from ..serializers import model_to_dict

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.post("/ideas")
def create_idea(payload: StrategyIdeaCreate, db: Session = Depends(get_db)):
    row = StrategyIdea(**payload.model_dump(), status="candidate", review_status="pending", can_train=False, can_trade=False)
    db.add(row)
    db.commit()
    db.refresh(row)
    return model_to_dict(row)


@router.get("/ideas")
def list_ideas(db: Session = Depends(get_db)):
    rows = db.scalars(select(StrategyIdea).order_by(StrategyIdea.created_at.desc())).all()
    return {"rows": [model_to_dict(row) for row in rows]}


@router.get("/ideas/{idea_id}")
def get_idea(idea_id: int, db: Session = Depends(get_db)):
    row = db.get(StrategyIdea, idea_id)
    if not row:
        raise HTTPException(status_code=404, detail="Strategy idea not found.")
    data = model_to_dict(row)
    data["versions"] = [model_to_dict(version) for version in row.versions]
    return data


@router.post("/ideas/{idea_id}/review")
def review_idea(idea_id: int, payload: StrategyReviewRequest, db: Session = Depends(get_db)):
    row = db.get(StrategyIdea, idea_id)
    if not row:
        raise HTTPException(status_code=404, detail="Strategy idea not found.")
    row.status = payload.status
    row.review_status = "reviewed"
    row.can_train = payload.can_train and payload.status == "approved"
    row.can_trade = payload.can_trade and payload.status == "approved"
    row.risk_level = payload.risk_level
    row.remark = payload.remark
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return model_to_dict(row)


@router.patch("/ideas/{idea_id}")
def update_idea(idea_id: int, payload: StrategyIdeaUpdate, db: Session = Depends(get_db)):
    row = db.get(StrategyIdea, idea_id)
    if not row:
        raise HTTPException(status_code=404, detail="Strategy idea not found.")
    changes = payload.model_dump(exclude_unset=True)
    for field in ("title", "content", "status", "risk_level", "remark"):
        if field in changes:
            setattr(row, field, changes[field])
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return model_to_dict(row)


@router.post("/versions")
def create_version(payload: StrategyVersionCreate, db: Session = Depends(get_db)):
    if payload.strategy_idea_id and not db.get(StrategyIdea, payload.strategy_idea_id):
        raise HTTPException(status_code=404, detail="Strategy idea not found.")
    row = StrategyVersion(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return model_to_dict(row)


@router.get("/versions/{version_id}")
def get_version(version_id: int, db: Session = Depends(get_db)):
    row = db.get(StrategyVersion, version_id)
    if not row:
        raise HTTPException(status_code=404, detail="Strategy version not found.")
    return model_to_dict(row)


@router.post("/versions/{version_id}/deprecate")
def deprecate_version(version_id: int, db: Session = Depends(get_db)):
    row = db.get(StrategyVersion, version_id)
    if not row:
        raise HTTPException(status_code=404, detail="Strategy version not found.")
    row.status = "deprecated"
    row.updated_at = datetime.utcnow()
    db.commit()
    return model_to_dict(row)
