from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import BacktestResult, StrategyVersion
from ..quant.backtest import BacktestParams, run_factor_backtest
from ..schemas import BacktestRunRequest
from ..serializers import model_to_dict
from ..services.market_data import daily_frame, sync_daily_prices, sync_factors

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.post("/run")
def run_backtest(payload: BacktestRunRequest, db: Session = Depends(get_db)):
    strategy = db.get(StrategyVersion, payload.strategy_version_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy version not found.")
    frame = daily_frame(db, payload.stock_code)
    if frame.empty:
        sync_daily_prices(db, payload.stock_code)
        sync_factors(db, payload.stock_code)
        frame = daily_frame(db, payload.stock_code)
    if payload.start_date:
        frame = frame[frame["trade_date"] >= payload.start_date]
    if payload.end_date:
        frame = frame[frame["trade_date"] <= payload.end_date]
    result = run_factor_backtest(
        frame,
        model_to_dict(strategy),
        BacktestParams(payload.initial_cash, payload.fee_rate, payload.slippage_rate, payload.max_position_per_stock),
    )
    metrics = result["metrics"]
    row = BacktestResult(
        strategy_version_id=strategy.id,
        start_date=frame["trade_date"].iloc[0],
        end_date=frame["trade_date"].iloc[-1],
        initial_cash=metrics["initial_cash"],
        final_value=metrics["final_value"],
        total_return=metrics["total_return"],
        annual_return=metrics["annual_return"],
        max_drawdown=metrics["max_drawdown"],
        sharpe_ratio=metrics["sharpe_ratio"],
        win_rate=metrics["win_rate"],
        profit_loss_ratio=metrics["profit_loss_ratio"],
        trade_count=metrics["trade_count"],
        turnover_rate=metrics["turnover_rate"],
        benchmark_return=metrics["benchmark_return"],
        excess_return=metrics["excess_return"],
        result_json=result,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return model_to_dict(row)


@router.get("/{backtest_id}")
def get_backtest(backtest_id: int, db: Session = Depends(get_db)):
    row = db.get(BacktestResult, backtest_id)
    if not row:
        raise HTTPException(status_code=404, detail="Backtest not found.")
    return model_to_dict(row)


@router.get("/by-strategy/{strategy_version_id}")
def list_by_strategy(strategy_version_id: int, db: Session = Depends(get_db)):
    rows = db.scalars(select(BacktestResult).where(BacktestResult.strategy_version_id == strategy_version_id).order_by(BacktestResult.created_at.desc())).all()
    return {"rows": [model_to_dict(row) for row in rows]}
