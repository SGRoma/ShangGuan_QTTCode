from __future__ import annotations

import numpy as np
import pandas as pd


def compute_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.sort_values("trade_date").copy()
    close = data["close"].astype(float)
    volume = data["volume"].astype(float).replace(0, np.nan)

    data["ma5"] = close.rolling(5, min_periods=1).mean()
    data["ma20"] = close.rolling(20, min_periods=1).mean()
    data["ma60"] = close.rolling(60, min_periods=1).mean()
    data["momentum_20d"] = close.pct_change(20).fillna(0)
    data["volatility_20d"] = close.pct_change().rolling(20, min_periods=2).std(ddof=0).fillna(0) * np.sqrt(252)
    data["volume_ratio"] = (volume / volume.rolling(20, min_periods=1).mean()).replace([np.inf, -np.inf], np.nan).fillna(1)
    data["rsi"] = _rsi(close)
    data["macd"] = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()

    # MVP uses deterministic placeholder fundamentals so the data contract is present.
    data["pe"] = 18 + (close.rank(pct=True) * 12)
    data["pb"] = 1.2 + (close.rank(pct=True) * 2.4)
    data["roe"] = 0.08 + (data["momentum_20d"].clip(-0.2, 0.2) + 0.2) / 4
    data["market_cap"] = close * volume.fillna(volume.mean()).fillna(1) / 10000
    return data


def score_factors(row: pd.Series) -> dict[str, float | str]:
    valuation = _clamp(100 - float(row.get("pe", 30)) * 2.2)
    quality = _clamp(float(row.get("roe", 0.1)) * 500)
    trend = 75 if float(row.get("close", 0)) >= float(row.get("ma20", 0)) else 45
    if float(row.get("ma20", 0)) > float(row.get("ma60", 0)):
        trend += 10
    momentum = _clamp(50 + float(row.get("momentum_20d", 0)) * 260)
    volume = _clamp(45 + float(row.get("volume_ratio", 1)) * 18)
    risk_penalty = _clamp(float(row.get("volatility_20d", 0)) * 120)
    score = _clamp(valuation * 0.20 + quality * 0.25 + trend * 0.25 + momentum * 0.15 + volume * 0.10 - risk_penalty * 0.15)
    risk_level = "high" if risk_penalty > 55 else "medium" if risk_penalty > 30 else "low"
    signal = "buy_candidate" if score >= 80 and risk_level != "high" else "watch" if score >= 70 else "avoid"
    return {
        "valuation_score": round(valuation, 2),
        "quality_score": round(quality, 2),
        "trend_score": round(trend, 2),
        "momentum_score": round(momentum, 2),
        "volume_score": round(volume, 2),
        "risk_penalty": round(risk_penalty, 2),
        "score": round(score, 2),
        "risk_level": risk_level,
        "signal": signal,
    }


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff().fillna(0)
    gain = delta.clip(lower=0).rolling(period, min_periods=1).mean()
    loss = (-delta.clip(upper=0)).rolling(period, min_periods=1).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))

