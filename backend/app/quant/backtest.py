from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .indicators import compute_indicators, score_factors


@dataclass(frozen=True)
class BacktestParams:
    initial_cash: float = 1_000_000
    fee_rate: float = 0.0003
    slippage_rate: float = 0.001
    max_position_per_stock: float = 0.2


def run_factor_backtest(prices: pd.DataFrame, strategy: dict[str, Any], params: BacktestParams) -> dict[str, Any]:
    if prices.empty:
        raise ValueError("No price data available for backtest.")

    data = compute_indicators(prices).copy()
    min_score = float(strategy.get("parameters_json", {}).get("min_score", 70))
    stop_loss = float(strategy.get("risk_rules_json", {}).get("stop_loss", -0.08) if strategy.get("risk_rules_json") else -0.08)

    factor_scores = data.apply(score_factors, axis=1, result_type="expand")
    data = pd.concat([data, factor_scores], axis=1)
    data["raw_signal"] = ((data["score"].astype(float) >= min_score) & (data["risk_level"] != "high")).astype(int)
    data["position"] = data["raw_signal"].shift(1).fillna(0).astype(float) * params.max_position_per_stock
    returns = data["close"].astype(float).pct_change().fillna(0)
    trades = data["position"].diff().abs().fillna(data["position"].abs())
    data["strategy_return"] = data["position"] * returns - trades * (params.fee_rate + params.slippage_rate)

    # Basic protective stop: next day goes flat after a large single-day loss.
    stop_hits = returns <= stop_loss
    data.loc[stop_hits.shift(1).fillna(False), "position"] = 0
    data["strategy_return"] = data["position"] * returns - data["position"].diff().abs().fillna(0) * (params.fee_rate + params.slippage_rate)
    data["equity_curve"] = (1 + data["strategy_return"]).cumprod()
    data["benchmark_curve"] = (1 + returns).cumprod()
    data["drawdown"] = data["equity_curve"] / data["equity_curve"].cummax() - 1
    data["benchmark_drawdown"] = data["benchmark_curve"] / data["benchmark_curve"].cummax() - 1

    metrics = _metrics(data, params.initial_cash)
    trades_rows = _trade_rows(data, params)
    monthly = data.set_index(pd.to_datetime(data["trade_date"]))["strategy_return"].resample("ME").apply(lambda x: (1 + x).prod() - 1)
    return {
        "metrics": metrics,
        "series": _series_rows(data),
        "trades": trades_rows,
        "monthly_returns": [{"month": idx.strftime("%Y-%m"), "return": round(float(value), 6)} for idx, value in monthly.items()],
        "risk_notes": _risk_notes(metrics),
    }


def _metrics(data: pd.DataFrame, initial_cash: float) -> dict[str, float | int]:
    total_return = float(data["equity_curve"].iloc[-1] - 1)
    benchmark_return = float(data["benchmark_curve"].iloc[-1] - 1)
    days = max(1, len(data))
    annual_return = float((1 + total_return) ** (252 / days) - 1)
    volatility = float(data["strategy_return"].std(ddof=0) * np.sqrt(252))
    sharpe = float(annual_return / volatility) if volatility else 0.0
    trade_count = int((data["position"].diff().abs().fillna(0) > 0).sum())
    wins = data.loc[data["strategy_return"] > 0, "strategy_return"]
    losses = data.loc[data["strategy_return"] < 0, "strategy_return"]
    win_rate = float(len(wins) / max(1, len(wins) + len(losses)))
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = abs(float(losses.mean())) if len(losses) else 0.0
    profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0
    turnover_rate = float(data["position"].diff().abs().fillna(0).sum())
    loss_streak = _max_loss_streak(data["strategy_return"])
    return {
        "initial_cash": round(initial_cash, 4),
        "final_value": round(initial_cash * (1 + total_return), 4),
        "total_return": _round(total_return),
        "annual_return": _round(annual_return),
        "max_drawdown": _round(float(data["drawdown"].min())),
        "sharpe_ratio": _round(sharpe),
        "win_rate": _round(win_rate),
        "profit_loss_ratio": _round(profit_loss_ratio),
        "trade_count": trade_count,
        "turnover_rate": _round(turnover_rate),
        "consecutive_loss_count": loss_streak,
        "benchmark_return": _round(benchmark_return),
        "excess_return": _round(total_return - benchmark_return),
    }


def _trade_rows(data: pd.DataFrame, params: BacktestParams) -> list[dict[str, Any]]:
    rows = []
    changed = data[data["position"].diff().fillna(data["position"]).abs() > 0]
    for _, row in changed.tail(80).iterrows():
        rows.append(
            {
                "trade_date": row["trade_date"].isoformat() if hasattr(row["trade_date"], "isoformat") else str(row["trade_date"]),
                "side": "buy" if row["position"] > 0 else "sell",
                "price": _round(float(row["open"]) * (1 + params.slippage_rate), 4),
                "quantity_ratio": _round(float(row["position"]), 4),
                "fee_rate": params.fee_rate,
                "reason": "T+1 signal execution, no future function",
            }
        )
    return rows


def _series_rows(data: pd.DataFrame) -> list[dict[str, Any]]:
    sample = data.tail(360)
    return [
        {
            "trade_date": row["trade_date"].isoformat() if hasattr(row["trade_date"], "isoformat") else str(row["trade_date"]),
            "close": _round(float(row["close"]), 4),
            "score": _round(float(row["score"]), 2),
            "position": _round(float(row["position"]), 4),
            "equity_curve": _round(float(row["equity_curve"]), 6),
            "benchmark_curve": _round(float(row["benchmark_curve"]), 6),
            "drawdown": _round(float(row["drawdown"]), 6),
        }
        for _, row in sample.iterrows()
    ]


def _max_loss_streak(returns: pd.Series) -> int:
    streak = 0
    max_streak = 0
    for value in returns:
        if value < 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    return max_streak


def _risk_notes(metrics: dict[str, Any]) -> list[str]:
    notes = ["回测信号按 T 日生成、T+1 执行，避免未来函数。"]
    if metrics["max_drawdown"] < -0.2:
        notes.append("最大回撤超过 20%，需要人工风险复核。")
    if metrics["trade_count"] > 80:
        notes.append("交易次数偏高，需关注滑点与换手率。")
    return notes


def _round(value: float, digits: int = 6) -> float:
    if not np.isfinite(value):
        return 0.0
    return round(float(value), digits)
