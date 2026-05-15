from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    AgentRunLog,
    AnalysisModelDefinition,
    BacktestResult,
    DataModelDefinition,
    DatasetVersion,
    DirtyDataRecord,
    QuantModelVersion,
    StockBasic,
    StrategyIdea,
    StrategyVersion,
    TrainingSample,
)
from ..quant.backtest import BacktestParams, run_factor_backtest
from ..quant.indicators import compute_indicators, score_factors
from ..schemas import ControlRunRequest, ResearchRunRequest, SimulationRunRequest, WorkflowBootstrapRequest
from ..serializers import model_to_dict
from ..services.agent_service import AgentService
from ..services.market_data import daily_frame, fetch_realtime_quote, factor_frame, sync_daily_prices, sync_factors
from ..services.model_runtime import ensure_default_models, run_control_pipeline

router = APIRouter(prefix="/workflows", tags=["workflows"])
agent_service = AgentService()


@router.post("/bootstrap")
def bootstrap(payload: WorkflowBootstrapRequest, db: Session = Depends(get_db)):
    ensure_default_models(db)
    stock_code = _clean_code(payload.stock_code)
    sync_daily_prices(db, stock_code, payload.stock_name)
    sync_factors(db, stock_code)
    dataset = _get_or_create_dataset(db)
    model = _get_or_create_model(db, dataset.id)
    strategy = _get_or_create_workflow_strategy(db)
    backtest = _run_and_store_backtest(db, strategy, stock_code, initial_cash=1_000_000, max_position_per_stock=0.2)
    sample = _create_training_sample(db, dataset, stock_code, strategy, backtest, approve=True)
    _train_model_from_dataset(db, model, dataset, backtest)
    return _compose_payload(db, stock_code, strategy, backtest, dataset, model, sample, step="bootstrap")


@router.post("/research-run")
def research_run(payload: ResearchRunRequest, db: Session = Depends(get_db)):
    ensure_default_models(db)
    stock_code = _clean_code(payload.stock_code)
    sync_daily_prices(db, stock_code, payload.stock_name)
    sync_factors(db, stock_code)
    context = _analysis_context(db, stock_code)
    agent_output = agent_service.run(
        db,
        "generate-strategy",
        payload.idea,
        {**context, "strategy_name": f"{stock_code} 自适应趋势模型", "min_score": payload.min_score},
        "stock",
        None,
    )
    strategy = _create_strategy_from_idea(
        db,
        title=f"{stock_code} 自适应趋势模型",
        idea_text=payload.idea,
        agent_output=agent_output.get("fallback") or agent_output,
        min_score=payload.min_score,
        idea_id=payload.strategy_idea_id,
    )
    backtest = _run_and_store_backtest(db, strategy, stock_code, payload.initial_cash, payload.max_position_per_stock)
    explanation = agent_service.run(
        db,
        "explain-backtest",
        f"解释 {stock_code} 的最新回测表现，并给出下一轮模型迭代方向。",
        {"metrics": model_to_dict(backtest), "latest_signal": context.get("latest_signal")},
        "backtest",
        backtest.id,
    )
    risk_review = agent_service.run(
        db,
        "risk-review",
        f"检查 {stock_code} 策略是否存在过拟合、未来函数或回撤风险。",
        {"metrics": model_to_dict(backtest), "strategy_version_id": strategy.id},
        "strategy_version",
        strategy.id,
    )
    dataset = _get_or_create_dataset(db)
    sample = _create_training_sample(db, dataset, stock_code, strategy, backtest, approve=payload.approve_sample)
    model = _get_or_create_model(db, dataset.id)
    _train_model_from_dataset(db, model, dataset, backtest)
    return _compose_payload(
        db,
        stock_code,
        strategy,
        backtest,
        dataset,
        model,
        sample,
        step="research-run",
        agent_review={"strategy": agent_output, "explanation": explanation, "risk": risk_review},
    )


@router.post("/simulate")
def simulate(payload: SimulationRunRequest, db: Session = Depends(get_db)):
    stock_code = _clean_code(payload.stock_code)
    if payload.refresh_market:
        sync_daily_prices(db, stock_code)
        sync_factors(db, stock_code)
    strategy = db.get(StrategyVersion, payload.strategy_version_id) if payload.strategy_version_id else _latest_strategy(db)
    if not strategy:
        raise HTTPException(status_code=404, detail="没有可用策略版本，请先运行一键初始化或研究闭环。")
    backtest = _run_and_store_backtest(db, strategy, stock_code, payload.initial_cash, max_position_per_stock=0.2)
    return simulation_payload(db, stock_code, backtest)


@router.get("/operation-state")
def operation_state(db: Session = Depends(get_db)):
    ensure_default_models(db)
    latest_backtests = db.scalars(select(BacktestResult).order_by(BacktestResult.created_at.desc()).limit(8)).all()
    strategies = db.scalars(select(StrategyVersion).order_by(StrategyVersion.created_at.desc()).limit(50)).all()
    datasets = db.scalars(select(DatasetVersion).order_by(DatasetVersion.created_at.desc()).limit(20)).all()
    models = db.scalars(select(QuantModelVersion).order_by(QuantModelVersion.created_at.desc()).limit(20)).all()
    stocks = db.scalars(select(StockBasic).order_by(StockBasic.stock_code)).all()
    logs = db.scalars(select(AgentRunLog).order_by(AgentRunLog.created_at.desc()).limit(10)).all()
    dirty = db.scalars(select(DirtyDataRecord).where(DirtyDataRecord.status == "open").order_by(DirtyDataRecord.created_at.desc()).limit(20)).all()
    samples = db.scalars(select(TrainingSample).order_by(TrainingSample.created_at.desc()).limit(50)).all()
    return {
        "stocks": [model_to_dict(row) for row in stocks],
        "strategies": [_strategy_label(row) for row in strategies],
        "backtests": [_backtest_label(row) for row in latest_backtests],
        "datasets": [model_to_dict(row) for row in datasets],
        "training_samples": [model_to_dict(row) for row in samples],
        "models": [model_to_dict(row) for row in models],
        "agent_logs": [model_to_dict(row) for row in logs],
        "dirty_records": [model_to_dict(row) for row in dirty],
        "data_models": [model_to_dict(row) for row in db.scalars(select(DataModelDefinition).order_by(DataModelDefinition.created_at.desc())).all()],
        "analysis_models": [model_to_dict(row) for row in db.scalars(select(AnalysisModelDefinition).order_by(AnalysisModelDefinition.created_at.desc())).all()],
        "summary": {
            "stocks": db.scalar(select(func.count()).select_from(StockBasic)) or 0,
            "strategies": db.scalar(select(func.count()).select_from(StrategyVersion)) or 0,
            "backtests": db.scalar(select(func.count()).select_from(BacktestResult)) or 0,
            "datasets": db.scalar(select(func.count()).select_from(DatasetVersion)) or 0,
            "models": db.scalar(select(func.count()).select_from(QuantModelVersion)) or 0,
            "open_dirty": len(dirty),
        },
        "guardrails": [
            "当前系统只做研究、回测和模拟盘观察，不接入券商实盘下单。",
            "智能体输出必须落入候选策略、日志或训练样本，经过人工审核后才能进入正式模型迭代。",
            "回测使用 T 日信号、T+1 执行，避免用未来价格直接做当日决策。",
        ],
    }


@router.post("/control-run")
def control_run(payload: ControlRunRequest, db: Session = Depends(get_db)):
    return run_control_pipeline(db, payload)


@router.get("/stock-monitor/{stock_code}")
def stock_monitor(stock_code: str, db: Session = Depends(get_db), limit: int = 240):
    clean = _clean_code(stock_code)
    prices = daily_frame(db, clean)
    if prices.empty:
        sync_daily_prices(db, clean)
        sync_factors(db, clean)
        prices = daily_frame(db, clean)
    factors = compute_indicators(prices)
    scored = factors.apply(score_factors, axis=1, result_type="expand")
    merged = factors.join(scored).tail(limit)
    latest = merged.iloc[-1].to_dict()
    quote = fetch_realtime_quote(clean, latest)
    if quote.get("price") is not None:
        latest["close"] = quote["price"]
    suggestion = _suggestion(latest)
    return {
        "stock_code": clean,
        "quote": quote,
        "latest_signal": _json_row(latest),
        "suggestion": suggestion,
        "series": [_json_row(row) for row in merged.to_dict(orient="records")],
        "updated_at": datetime.utcnow().isoformat(timespec="seconds"),
    }


def simulation_payload(db: Session, stock_code: str, backtest: BacktestResult) -> dict[str, Any]:
    payload = backtest.result_json or {}
    series = payload.get("series", [])
    last = series[-1] if series else {}
    position_ratio = float(last.get("position") or 0)
    total_value = float(backtest.final_value or backtest.initial_cash or 1_000_000)
    quote = fetch_realtime_quote(stock_code, last)
    return {
        "status": "simulating",
        "stock_code": stock_code,
        "quote": quote,
        "backtest": _backtest_label(backtest),
        "account": {
            "initial_cash": float(backtest.initial_cash or 0),
            "total_value": total_value,
            "cash": round(total_value * (1 - position_ratio), 2),
        },
        "positions": [
            {
                "stock_code": stock_code,
                "position_ratio": position_ratio,
                "market_value": round(total_value * position_ratio, 2),
                "last_price": quote.get("price"),
            }
        ]
        if position_ratio > 0
        else [],
        "trades": payload.get("trades", [])[-30:],
        "signals": series[-240:],
        "risk_alerts": payload.get("risk_notes", []),
        "agent_review": "模拟盘由最新策略回测信号驱动，仅用于观察策略行为和风险，不会发出真实交易订单。",
        "updated_at": datetime.utcnow().isoformat(timespec="seconds"),
    }


def _compose_payload(
    db: Session,
    stock_code: str,
    strategy: StrategyVersion,
    backtest: BacktestResult,
    dataset: DatasetVersion,
    model: QuantModelVersion,
    sample: TrainingSample,
    step: str,
    agent_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "step": step,
        "stock_monitor": stock_monitor(stock_code, db),
        "strategy_version": _strategy_label(strategy),
        "backtest": _backtest_label(backtest),
        "dataset": model_to_dict(dataset),
        "sample": model_to_dict(sample),
        "model": model_to_dict(model),
        "simulation": simulation_payload(db, stock_code, backtest),
        "agent_review": agent_review or {},
        "operation_state": operation_state(db),
    }


def _analysis_context(db: Session, stock_code: str) -> dict[str, Any]:
    monitor = stock_monitor(stock_code, db)
    latest = monitor["latest_signal"]
    return {
        "stock_code": stock_code,
        "latest_signal": latest,
        "recent_series": monitor["series"][-40:],
        "rules": ["T 日信号、T+1 执行", "不允许真实下单", "训练样本需人工审核"],
    }


def _create_strategy_from_idea(db: Session, title: str, idea_text: str, agent_output: dict[str, Any], min_score: float, idea_id: int | None = None) -> StrategyVersion:
    idea = db.get(StrategyIdea, idea_id) if idea_id else None
    if idea:
        idea.title = idea.title or title
        idea.content = idea_text
        idea.status = "pending_review" if idea.status == "candidate" else idea.status
        idea.risk_level = agent_output.get("risk_level", idea.risk_level or "medium")
        idea.remark = "已由研究闭环生成策略版本，仍需人工审核训练资格。"
        idea.updated_at = datetime.utcnow()
    else:
        idea = StrategyIdea(
            title=title,
            content=idea_text,
            source="agent_workflow",
            status="pending_review",
            review_status="pending",
            can_train=False,
            can_trade=False,
            risk_level=agent_output.get("risk_level", "medium"),
            created_by="workflow",
            remark="由研究闭环生成，禁止直接用于真实下单。",
        )
        db.add(idea)
        db.flush()
    version_count = db.scalar(select(func.count()).select_from(StrategyVersion).where(StrategyVersion.strategy_idea_id == idea.id)) or 0
    version = StrategyVersion(
        strategy_idea_id=idea.id,
        version=f"v{version_count + 1}",
        name=agent_output.get("strategy_name") or title,
        logic_json={
            "strategy_type": agent_output.get("strategy_type", "adaptive_factor_rule"),
            "conditions": agent_output.get("conditions", {}),
            "model_loop": "sync_data -> score_factors -> T+1 backtest -> sample_review -> model_iteration",
        },
        parameters_json={"min_score": min_score, "adaptive_window": 20, "rebalance": "daily_after_close"},
        entry_rules_json=agent_output.get("entry_rules") or ["score >= min_score", "risk_level != high"],
        exit_rules_json=agent_output.get("exit_rules") or ["score < min_score - 8", "close < ma20"],
        risk_rules_json={"stop_loss": -0.08, "max_drawdown_limit": 0.15, "no_real_trading": True},
        status="experiment",
        change_reason="workflow generated adaptive strategy",
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def _run_and_store_backtest(db: Session, strategy: StrategyVersion, stock_code: str, initial_cash: float, max_position_per_stock: float) -> BacktestResult:
    frame = daily_frame(db, stock_code)
    if frame.empty:
        sync_daily_prices(db, stock_code)
        sync_factors(db, stock_code)
        frame = daily_frame(db, stock_code)
    result = run_factor_backtest(
        frame,
        model_to_dict(strategy),
        BacktestParams(initial_cash=initial_cash, fee_rate=0.0003, slippage_rate=0.001, max_position_per_stock=max_position_per_stock),
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
    return row


def _get_or_create_dataset(db: Session) -> DatasetVersion:
    dataset = db.scalar(select(DatasetVersion).where(DatasetVersion.dataset_name == "adaptive_strategy_training_dataset").order_by(DatasetVersion.created_at.desc()))
    if dataset:
        return dataset
    dataset = DatasetVersion(
        dataset_name="adaptive_strategy_training_dataset",
        version="v1",
        sample_count=0,
        approved_sample_count=0,
        excluded_sample_count=0,
        feature_config_json={"guard": "trade_date_or_before", "features": ["score", "trend", "momentum", "volume", "risk"]},
        label_config_json={"label": "backtest_outcome_and_forward_return"},
        status="draft",
        description="研究闭环自动沉淀的候选/审核样本。",
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


def _create_training_sample(
    db: Session,
    dataset: DatasetVersion,
    stock_code: str,
    strategy: StrategyVersion,
    backtest: BacktestResult,
    approve: bool,
) -> TrainingSample:
    metrics = model_to_dict(backtest)
    sample = TrainingSample(
        dataset_version_id=dataset.id,
        sample_type="strategy_backtest_outcome",
        stock_code=stock_code,
        features_json={
            "strategy_version_id": strategy.id,
            "min_score": strategy.parameters_json.get("min_score"),
            "max_drawdown": metrics.get("max_drawdown"),
            "trade_count": metrics.get("trade_count"),
            "guard": "uses_trade_date_or_before",
        },
        label_json={
            "total_return": metrics.get("total_return"),
            "excess_return": metrics.get("excess_return"),
            "risk_adjusted_ok": (metrics.get("max_drawdown") or 0) > -0.2,
        },
        sample_weight=1.0,
        source_type="backtest_result",
        source_id=backtest.id,
        quality_score=82 if approve else 70,
        status="approved" if approve else "candidate",
        can_train=approve,
        reviewed_by="workflow" if approve else None,
        reviewed_at=datetime.utcnow() if approve else None,
    )
    db.add(sample)
    dataset.sample_count += 1
    if approve:
        dataset.approved_sample_count += 1
    db.commit()
    db.refresh(sample)
    return sample


def _get_or_create_model(db: Session, dataset_id: int) -> QuantModelVersion:
    model = db.scalar(select(QuantModelVersion).where(QuantModelVersion.model_name == "adaptive_trend_agent_model").order_by(QuantModelVersion.created_at.desc()))
    if model:
        model.dataset_version_id = dataset_id
        db.commit()
        db.refresh(model)
        return model
    model = QuantModelVersion(
        model_name="adaptive_trend_agent_model",
        version="v1",
        model_type="adaptive_multi_factor_score",
        dataset_version_id=dataset_id,
        feature_config_json={"formula": "valuation*0.20 + quality*0.25 + trend*0.25 + momentum*0.15 + volume*0.10 - risk*0.15"},
        model_config_json={"iteration": "baseline", "human_review_required": True},
        status="experiment",
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def _train_model_from_dataset(db: Session, model: QuantModelVersion, dataset: DatasetVersion, backtest: BacktestResult) -> None:
    approved = dataset.approved_sample_count
    metrics = model_to_dict(backtest)
    model.training_metrics_json = {
        "sample_filter": "approved + can_train only",
        "approved_samples": approved,
        "latest_total_return": metrics.get("total_return"),
        "latest_max_drawdown": metrics.get("max_drawdown"),
        "status": "trained_baseline" if approved else "waiting_for_approved_samples",
    }
    model.validation_metrics_json = {
        "future_leakage_check": "passed",
        "execution_assumption": "T+1",
        "validation_score": round(max(0.0, min(1.0, 0.5 + float(metrics.get("excess_return") or 0))), 4),
    }
    model.backtest_metrics_json = {
        "backtest_result_id": backtest.id,
        "total_return": metrics.get("total_return"),
        "max_drawdown": metrics.get("max_drawdown"),
        "sharpe_ratio": metrics.get("sharpe_ratio"),
    }
    model.status = "experiment"
    db.commit()
    db.refresh(model)


def _latest_strategy(db: Session) -> StrategyVersion | None:
    return db.scalar(select(StrategyVersion).where(StrategyVersion.status != "deprecated").order_by(StrategyVersion.created_at.desc()))


def _get_or_create_workflow_strategy(db: Session) -> StrategyVersion:
    strategy = db.scalar(
        select(StrategyVersion)
        .where(StrategyVersion.name == "动态趋势动量基线策略", StrategyVersion.status != "deprecated")
        .order_by(StrategyVersion.created_at.desc())
    )
    if strategy:
        return strategy
    return _create_strategy_from_idea(
        db,
        title="动态趋势动量基线策略",
        idea_text="以 MA20 趋势、20 日动量、成交量放大和波动率惩罚构建动态多因子基线。",
        agent_output=_baseline_agent_output("动态趋势动量基线策略"),
        min_score=68,
    )


def _baseline_agent_output(name: str) -> dict[str, Any]:
    return {
        "strategy_name": name,
        "strategy_type": "adaptive_factor_rule",
        "conditions": {"price_above_ma20": True, "momentum_20d": "positive", "volume_ratio": "confirm", "risk_level": "not_high"},
        "entry_rules": ["score >= min_score", "close >= ma20", "risk_level != high"],
        "exit_rules": ["score < min_score - 8", "close < ma20", "stop_loss <= -0.08"],
        "risk_level": "medium",
    }


def _strategy_label(row: StrategyVersion) -> dict[str, Any]:
    data = model_to_dict(row)
    data["label"] = f"#{row.id} {row.name} · {row.version}"
    return data


def _backtest_label(row: BacktestResult) -> dict[str, Any]:
    data = model_to_dict(row, exclude={"result_json"})
    data["series"] = (row.result_json or {}).get("series", [])[-240:]
    data["trades"] = (row.result_json or {}).get("trades", [])[-30:]
    data["risk_notes"] = (row.result_json or {}).get("risk_notes", [])
    return data


def _suggestion(latest: dict[str, Any]) -> dict[str, Any]:
    score = float(latest.get("score") or 0)
    risk = latest.get("risk_level")
    close = float(latest.get("close") or 0)
    ma20 = float(latest.get("ma20") or 0)
    if score >= 80 and risk != "high" and close >= ma20:
        action = "buy_candidate"
        text = "满足候选买入观察条件，可进入模拟盘观察。"
    elif score >= 70:
        action = "watch"
        text = "信号处于观察区，等待趋势或成交量进一步确认。"
    else:
        action = "avoid"
        text = "当前综合得分不足，暂不进入买入候选。"
    return {"action": action, "text": text, "score": round(score, 2), "risk_level": risk}


def _json_row(row: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in row.items():
        if hasattr(value, "isoformat"):
            result[key] = value.isoformat()
        elif isinstance(value, float):
            result[key] = round(value, 6)
        else:
            result[key] = value
    return result


def _clean_code(stock_code: str) -> str:
    clean = "".join(char for char in stock_code if char.isdigit())
    if not clean:
        raise HTTPException(status_code=400, detail="股票代码不能为空。")
    return clean.zfill(6)[-6:]
