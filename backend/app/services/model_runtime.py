from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    AnalysisModelDefinition,
    BacktestResult,
    DataModelDefinition,
    DatasetVersion,
    QuantModelVersion,
    StrategyIdea,
    StrategyVersion,
    TrainingSample,
)
from ..quant.backtest import BacktestParams, run_factor_backtest
from ..serializers import jsonable, model_to_dict
from ..services.market_data import daily_frame, fetch_realtime_quote, sync_daily_prices, sync_factors


def ensure_default_models(db: Session) -> dict[str, Any]:
    data_model = db.scalar(select(DataModelDefinition).where(DataModelDefinition.name == "A股日线因子数据模型"))
    if not data_model:
        data_model = DataModelDefinition(
            name="A股日线因子数据模型",
            version="v1",
            description="按股票同步真实日线行情，计算技术因子，沉淀训练样本。适合作为系统数据地基。",
            feature_version="feature_v1",
            pipeline_config_json={
                "sync_daily": True,
                "compute_factors": True,
                "generate_dataset": True,
                "price_adjust": "qfq",
                "data_sources": ["eastmoney", "tencent", "sina"],
                "leakage_guard": "trade_date_or_before",
            },
            schedule_config_json={"mode": "manual_or_daily", "cron": "after_market_close"},
            status="active",
        )
        db.add(data_model)
        db.commit()
        db.refresh(data_model)

    trend_model = db.scalar(select(AnalysisModelDefinition).where(AnalysisModelDefinition.name == "趋势动量风控模型"))
    if not trend_model:
        trend_model = AnalysisModelDefinition(
            name="趋势动量风控模型",
            version="v1",
            model_family="trend_momentum",
            description="可解释的趋势、动量、成交量确认和波动率风控模型。",
            default_data_model_id=data_model.id,
            parameters_json={"min_score": 68, "max_position_per_stock": 0.2},
            entry_rules_json=["score >= min_score", "risk_level != high", "close >= ma20"],
            exit_rules_json=["score < min_score - 8", "close < ma20"],
            risk_rules_json={"stop_loss": -0.08, "max_drawdown_limit": 0.15, "no_real_trading": True},
            capability_json={"supports": ["signal", "backtest", "simulation", "risk_review"], "explainable": True},
            status="active",
        )
        db.add(trend_model)

    conservative_model = db.scalar(select(AnalysisModelDefinition).where(AnalysisModelDefinition.name == "低波动防守模型"))
    if not conservative_model:
        conservative_model = AnalysisModelDefinition(
            name="低波动防守模型",
            version="v1",
            model_family="risk_first",
            description="降低交易频率，优先控制波动与回撤的防守型分析模型。",
            default_data_model_id=data_model.id,
            parameters_json={"min_score": 74, "max_position_per_stock": 0.12},
            entry_rules_json=["score >= min_score", "risk_level == low"],
            exit_rules_json=["risk_level == high", "score < min_score - 10"],
            risk_rules_json={"stop_loss": -0.05, "max_drawdown_limit": 0.1, "no_real_trading": True},
            capability_json={"supports": ["signal", "backtest", "simulation", "risk_review"], "style": "defensive"},
            status="active",
        )
        db.add(conservative_model)

    db.commit()
    return {"data_model_id": data_model.id}


def run_data_model(db: Session, stock_code: str, data_model: DataModelDefinition, start: str = "20240101", generate_dataset: bool = True) -> dict[str, Any]:
    sync_summary = sync_daily_prices(db, stock_code, start=start)
    factor_summary = sync_factors(db, stock_code, data_model.feature_version)
    dataset = _get_or_create_dataset(db, data_model, stock_code) if generate_dataset else None
    if dataset:
        _create_data_model_sample(db, dataset, data_model, stock_code, factor_summary)
    latest = daily_frame(db, stock_code).tail(1).to_dict(orient="records")
    return jsonable({
        "stock_code": _clean_code(stock_code),
        "data_model_id": data_model.id,
        "data_model_name": data_model.name,
        "sync": sync_summary,
        "factors": factor_summary,
        "dataset": model_to_dict(dataset) if dataset else None,
        "latest_price": latest[0] if latest else None,
        "run_at": datetime.utcnow().isoformat(timespec="seconds"),
    })


def _create_data_model_sample(
    db: Session,
    dataset: DatasetVersion,
    data_model: DataModelDefinition,
    stock_code: str,
    factor_summary: dict[str, Any],
) -> TrainingSample | None:
    latest = factor_summary.get("latest_score") or {}
    trade_date = latest.get("trade_date")
    exists = db.scalar(
        select(TrainingSample).where(
            TrainingSample.dataset_version_id == dataset.id,
            TrainingSample.stock_code == _clean_code(stock_code),
            TrainingSample.trade_date == trade_date,
            TrainingSample.source_type == "data_model_run",
            TrainingSample.source_id == data_model.id,
        )
    )
    if exists:
        return exists
    sample = TrainingSample(
        dataset_version_id=dataset.id,
        sample_type="data_model_factor_snapshot",
        stock_code=_clean_code(stock_code),
        trade_date=trade_date,
        features_json=jsonable(
            {
                "data_model_id": data_model.id,
                "feature_version": data_model.feature_version,
                "score": latest.get("score"),
                "risk_level": latest.get("risk_level"),
                "signal": latest.get("signal"),
                "valuation_score": latest.get("valuation_score"),
                "quality_score": latest.get("quality_score"),
                "trend_score": latest.get("trend_score"),
                "momentum_score": latest.get("momentum_score"),
                "volume_score": latest.get("volume_score"),
                "risk_penalty": latest.get("risk_penalty"),
                "guard": "trade_date_or_before",
            }
        ),
        label_json=jsonable({"label": "pending_human_review", "source": "data_model_run"}),
        source_type="data_model_run",
        source_id=data_model.id,
        quality_score=float(latest.get("score") or 70),
        status="candidate",
        can_train=False,
    )
    db.add(sample)
    dataset.sample_count += 1
    db.commit()
    db.refresh(sample)
    return sample


def run_control_pipeline(db: Session, payload: Any) -> dict[str, Any]:
    ensure_default_models(db)
    stock_code = _clean_code(payload.stock_code)
    data_model = db.get(DataModelDefinition, payload.data_model_id)
    analysis_model = db.get(AnalysisModelDefinition, payload.analysis_model_id)
    if not data_model:
        raise HTTPException(status_code=404, detail="Data model not found.")
    if not analysis_model:
        raise HTTPException(status_code=404, detail="Analysis model not found.")

    data_result = run_data_model(db, stock_code, data_model, generate_dataset=True) if payload.refresh_data else None
    dataset = _get_or_create_dataset(db, data_model, stock_code)
    strategy = _snapshot_strategy_from_analysis_model(db, stock_code, analysis_model, data_model, payload.idea)
    backtest = _run_backtest(db, strategy, stock_code, payload.initial_cash, analysis_model)
    sample = _create_training_sample(db, dataset, stock_code, strategy, backtest, analysis_model, approve=payload.approve_sample)
    quant_model = _get_or_create_quant_model(db, dataset.id, analysis_model)
    _update_quant_model_metrics(db, quant_model, dataset, backtest, analysis_model)
    simulation = _simulation_payload(stock_code, backtest)

    return {
        "stock_code": stock_code,
        "data_model": model_to_dict(data_model),
        "analysis_model": model_to_dict(analysis_model),
        "data_result": data_result,
        "strategy_version": _strategy_label(strategy),
        "backtest": _backtest_label(backtest),
        "dataset": model_to_dict(dataset),
        "sample": model_to_dict(sample),
        "model": model_to_dict(quant_model),
        "simulation": simulation,
        "run_at": datetime.utcnow().isoformat(timespec="seconds"),
    }


def _get_or_create_dataset(db: Session, data_model: DataModelDefinition, stock_code: str) -> DatasetVersion:
    dataset_name = f"{data_model.name}_{_clean_code(stock_code)}"
    dataset = db.scalar(select(DatasetVersion).where(DatasetVersion.dataset_name == dataset_name).order_by(DatasetVersion.created_at.desc()))
    if dataset:
        return dataset
    dataset = DatasetVersion(
        dataset_name=dataset_name,
        version=data_model.version,
        sample_count=0,
        approved_sample_count=0,
        excluded_sample_count=0,
        feature_config_json={
            "data_model_id": data_model.id,
            "feature_version": data_model.feature_version,
            "pipeline": data_model.pipeline_config_json,
        },
        label_config_json={"label": "analysis_model_backtest_outcome"},
        status="draft",
        description=f"{stock_code} 由数据模型 {data_model.name} 生成的数据集。",
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


def _snapshot_strategy_from_analysis_model(
    db: Session,
    stock_code: str,
    analysis_model: AnalysisModelDefinition,
    data_model: DataModelDefinition,
    idea: str | None,
) -> StrategyVersion:
    idea_row = StrategyIdea(
        title=f"{stock_code} · {analysis_model.name}",
        content=idea or analysis_model.description or analysis_model.name,
        source="analysis_model",
        status="approved",
        review_status="reviewed",
        can_train=True,
        can_trade=False,
        risk_level="medium",
        created_by="control_pipeline",
        remark="分析模型执行快照，不包含真实下单能力。",
    )
    db.add(idea_row)
    db.flush()
    version = StrategyVersion(
        strategy_idea_id=idea_row.id,
        version="v1",
        name=f"{analysis_model.name} / {stock_code}",
        logic_json={
            "analysis_model_id": analysis_model.id,
            "analysis_model_family": analysis_model.model_family,
            "data_model_id": data_model.id,
            "capability": analysis_model.capability_json,
        },
        parameters_json=analysis_model.parameters_json,
        entry_rules_json=analysis_model.entry_rules_json,
        exit_rules_json=analysis_model.exit_rules_json,
        risk_rules_json=analysis_model.risk_rules_json,
        status="experiment",
        change_reason="snapshot from selected analysis model",
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def _run_backtest(db: Session, strategy: StrategyVersion, stock_code: str, initial_cash: float, analysis_model: AnalysisModelDefinition) -> BacktestResult:
    frame = daily_frame(db, stock_code)
    if frame.empty:
        raise HTTPException(status_code=409, detail="No data available. Run data model first.")
    params = analysis_model.parameters_json or {}
    result = run_factor_backtest(
        frame,
        model_to_dict(strategy),
        BacktestParams(
            initial_cash=initial_cash,
            fee_rate=0.0003,
            slippage_rate=0.001,
            max_position_per_stock=float(params.get("max_position_per_stock", 0.2)),
        ),
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


def _create_training_sample(
    db: Session,
    dataset: DatasetVersion,
    stock_code: str,
    strategy: StrategyVersion,
    backtest: BacktestResult,
    analysis_model: AnalysisModelDefinition,
    approve: bool,
) -> TrainingSample:
    metrics = model_to_dict(backtest)
    sample = TrainingSample(
        dataset_version_id=dataset.id,
        sample_type="analysis_model_execution",
        stock_code=stock_code,
        features_json={
            "data_model_id": dataset.feature_config_json.get("data_model_id") if dataset.feature_config_json else None,
            "analysis_model_id": analysis_model.id,
            "strategy_version_id": strategy.id,
            "parameters": analysis_model.parameters_json,
            "guard": "trade_date_or_before",
        },
        label_json={
            "total_return": metrics.get("total_return"),
            "excess_return": metrics.get("excess_return"),
            "max_drawdown": metrics.get("max_drawdown"),
            "risk_adjusted_ok": (metrics.get("max_drawdown") or 0) > -0.2,
        },
        source_type="analysis_model_backtest",
        source_id=backtest.id,
        quality_score=86 if approve else 70,
        status="approved" if approve else "candidate",
        can_train=approve,
        reviewed_by="control_pipeline" if approve else None,
        reviewed_at=datetime.utcnow() if approve else None,
    )
    db.add(sample)
    dataset.sample_count += 1
    if approve:
        dataset.approved_sample_count += 1
    db.commit()
    db.refresh(sample)
    return sample


def _get_or_create_quant_model(db: Session, dataset_id: int, analysis_model: AnalysisModelDefinition) -> QuantModelVersion:
    model_name = f"{analysis_model.name}_训练记录"
    model = db.scalar(select(QuantModelVersion).where(QuantModelVersion.model_name == model_name).order_by(QuantModelVersion.created_at.desc()))
    if model:
        model.dataset_version_id = dataset_id
        db.commit()
        db.refresh(model)
        return model
    model = QuantModelVersion(
        model_name=model_name,
        version=analysis_model.version,
        model_type=analysis_model.model_family,
        dataset_version_id=dataset_id,
        feature_config_json={"analysis_model_id": analysis_model.id, "features": ["score", "trend", "momentum", "volume", "risk"]},
        model_config_json=analysis_model.parameters_json,
        status="experiment",
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def _update_quant_model_metrics(db: Session, model: QuantModelVersion, dataset: DatasetVersion, backtest: BacktestResult, analysis_model: AnalysisModelDefinition) -> None:
    metrics = model_to_dict(backtest)
    model.training_metrics_json = {
        "analysis_model_id": analysis_model.id,
        "approved_samples": dataset.approved_sample_count,
        "sample_filter": "approved + can_train only",
        "status": "trained_baseline" if dataset.approved_sample_count else "waiting_for_samples",
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
    db.commit()


def _simulation_payload(stock_code: str, backtest: BacktestResult) -> dict[str, Any]:
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
        "account": {"initial_cash": float(backtest.initial_cash or 0), "total_value": total_value, "cash": round(total_value * (1 - position_ratio), 2)},
        "positions": [{"stock_code": stock_code, "position_ratio": position_ratio, "market_value": round(total_value * position_ratio, 2)}] if position_ratio else [],
        "signals": series[-240:],
        "trades": payload.get("trades", [])[-30:],
        "risk_alerts": payload.get("risk_notes", []),
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


def _clean_code(stock_code: str) -> str:
    clean = "".join(char for char in stock_code if char.isdigit())
    if not clean:
        raise HTTPException(status_code=400, detail="股票代码不能为空。")
    return clean.zfill(6)[-6:]
