from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import StockBasic
from ..schemas import FactorSyncRequest, StockSyncRequest
from ..serializers import model_to_dict
from ..services.market_data import daily_frame, factor_frame, sync_daily_prices, sync_factors

router = APIRouter(prefix="/stocks", tags=["stocks"])
data_router = APIRouter(prefix="/data", tags=["data"])


@router.get("")
def list_stocks(db: Session = Depends(get_db)):
    rows = db.scalars(select(StockBasic).order_by(StockBasic.stock_code)).all()
    return {"rows": [model_to_dict(row) for row in rows]}


@router.get("/{stock_code}")
def get_stock(stock_code: str, db: Session = Depends(get_db)):
    row = db.scalar(select(StockBasic).where(StockBasic.stock_code == stock_code))
    if not row:
        raise HTTPException(status_code=404, detail="Stock not found.")
    return model_to_dict(row)


@router.get("/{stock_code}/daily")
def get_stock_daily(stock_code: str, limit: int = 260, db: Session = Depends(get_db)):
    frame = daily_frame(db, stock_code)
    if frame.empty:
        raise HTTPException(status_code=404, detail="No daily prices. Sync data first.")
    return {"stock_code": stock_code, "rows": frame.tail(limit).to_dict(orient="records")}


@router.get("/{stock_code}/factors")
def get_stock_factors(stock_code: str, limit: int = 260, db: Session = Depends(get_db)):
    frame = factor_frame(db, stock_code)
    if frame.empty:
        raise HTTPException(status_code=404, detail="No factors. Sync factors first.")
    return {"stock_code": stock_code, "rows": frame.tail(limit).to_dict(orient="records")}


@data_router.post("/sync/daily")
def sync_daily(payload: StockSyncRequest, db: Session = Depends(get_db)):
    return sync_daily_prices(db, payload.stock_code, payload.stock_name, payload.start)


@data_router.post("/sync/factors")
def sync_factor(payload: FactorSyncRequest, db: Session = Depends(get_db)):
    return sync_factors(db, payload.stock_code, payload.feature_version)

