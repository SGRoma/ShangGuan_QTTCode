from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import BacktestResult, DatasetVersion, DirtyDataRecord, QuantModelVersion, StockBasic, StrategyIdea, StrategyVersion, TrainingSample
from ..serializers import model_to_dict

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary(db: Session = Depends(get_db)):
    latest_backtests = db.scalars(select(BacktestResult).order_by(BacktestResult.created_at.desc()).limit(5)).all()
    dirty_open = db.scalar(select(func.count()).select_from(DirtyDataRecord).where(DirtyDataRecord.status == "open")) or 0
    return {
        "cards": {
            "stocks": db.scalar(select(func.count()).select_from(StockBasic)) or 0,
            "strategy_ideas": db.scalar(select(func.count()).select_from(StrategyIdea)) or 0,
            "strategy_versions": db.scalar(select(func.count()).select_from(StrategyVersion)) or 0,
            "datasets": db.scalar(select(func.count()).select_from(DatasetVersion)) or 0,
            "approved_samples": db.scalar(select(func.count()).select_from(TrainingSample).where(TrainingSample.status == "approved", TrainingSample.can_train.is_(True))) or 0,
            "models": db.scalar(select(func.count()).select_from(QuantModelVersion)) or 0,
            "dirty_open": dirty_open,
        },
        "latest_backtests": [model_to_dict(row) for row in latest_backtests],
        "guardrails": [
            "系统不存在真实下单接口。",
            "智能体输出只进入 agent_run_log 和候选区，不能直接替换正式策略或模型。",
            "训练样本必须 approved + can_train=true 才能进入正式训练数据集。",
        ],
    }


@router.get("/simulation")
def simulation_dashboard(db: Session = Depends(get_db)):
    latest = db.scalar(select(BacktestResult).order_by(BacktestResult.created_at.desc()))
    if not latest:
        return {
            "status": "watching",
            "account": {"initial_cash": 1_000_000, "total_value": 1_000_000, "cash": 1_000_000},
            "positions": [],
            "trades": [],
            "signals": [],
            "risk_alerts": ["尚未执行回测，模拟盘处于观察状态。"],
            "agent_review": "等待回测结果后生成复盘。",
        }
    payload = latest.result_json or {}
    series = payload.get("series", [])
    last = series[-1] if series else {}
    position_ratio = float(last.get("position") or 0)
    total_value = float(latest.final_value or latest.initial_cash or 1_000_000)
    return {
        "status": "simulating",
        "account": {"initial_cash": float(latest.initial_cash or 0), "total_value": total_value, "cash": total_value * (1 - position_ratio)},
        "positions": [{"stock_code": "MVP", "position_ratio": position_ratio, "market_value": total_value * position_ratio}],
        "trades": payload.get("trades", [])[-20:],
        "signals": series[-20:],
        "risk_alerts": payload.get("risk_notes", []),
        "agent_review": "模拟交易看板基于最近一次回测结果生成，不涉及真实资金和真实下单。",
    }

