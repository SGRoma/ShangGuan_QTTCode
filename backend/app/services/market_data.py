from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import requests
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import StockBasic, StockDailyPrice, StockFactorDaily
from ..quant.indicators import compute_indicators, score_factors


EASTMONEY_KLINE_FIELDS = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
KNOWN_NAMES = {
    "600418": "江淮汽车",
    "600519": "贵州茅台",
    "601318": "中国平安",
    "000001": "平安银行",
    "300750": "宁德时代",
    "002594": "比亚迪",
}


def sync_daily_prices(db: Session, stock_code: str, stock_name: str | None = None, start: str = "20240101") -> dict[str, Any]:
    clean = _clean_code(stock_code)
    name = stock_name or KNOWN_NAMES.get(clean) or clean
    frame = fetch_daily_prices(clean, start)
    _upsert_stock(db, clean, name)
    db.execute(delete(StockDailyPrice).where(StockDailyPrice.stock_code == clean))
    for row in frame.to_dict(orient="records"):
        db.add(
            StockDailyPrice(
                stock_code=clean,
                trade_date=row["trade_date"],
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                pre_close=row.get("pre_close"),
                volume=row.get("volume"),
                amount=row.get("amount"),
                adj_factor=1,
                data_source=row.get("data_source", "eastmoney"),
            )
        )
    db.commit()
    return {
        "stock_code": clean,
        "stock_name": name,
        "rows": len(frame),
        "start": str(frame["trade_date"].min()),
        "end": str(frame["trade_date"].max()),
        "data_source": str(frame["data_source"].iloc[-1]) if "data_source" in frame else "unknown",
    }


def sync_factors(db: Session, stock_code: str, feature_version: str = "feature_v1") -> dict[str, Any]:
    clean = _clean_code(stock_code)
    prices = daily_frame(db, clean)
    if prices.empty:
        sync_daily_prices(db, clean)
        prices = daily_frame(db, clean)
    factors = compute_indicators(prices)
    db.execute(delete(StockFactorDaily).where(StockFactorDaily.stock_code == clean, StockFactorDaily.feature_version == feature_version))
    for row in factors.to_dict(orient="records"):
        db.add(
            StockFactorDaily(
                stock_code=clean,
                trade_date=row["trade_date"],
                pe=row.get("pe"),
                pb=row.get("pb"),
                roe=row.get("roe"),
                market_cap=row.get("market_cap"),
                ma5=row.get("ma5"),
                ma20=row.get("ma20"),
                ma60=row.get("ma60"),
                rsi=row.get("rsi"),
                macd=row.get("macd"),
                volume_ratio=row.get("volume_ratio"),
                volatility_20d=row.get("volatility_20d"),
                momentum_20d=row.get("momentum_20d"),
                feature_version=feature_version,
            )
        )
    db.commit()
    latest = factors.iloc[-1]
    return {"stock_code": clean, "feature_version": feature_version, "rows": len(factors), "latest_score": score_factors(latest)}


def daily_frame(db: Session, stock_code: str) -> pd.DataFrame:
    rows = db.scalars(select(StockDailyPrice).where(StockDailyPrice.stock_code == _clean_code(stock_code)).order_by(StockDailyPrice.trade_date)).all()
    return pd.DataFrame(
        [
            {
                "trade_date": row.trade_date,
                "open": float(row.open or 0),
                "high": float(row.high or 0),
                "low": float(row.low or 0),
                "close": float(row.close or 0),
                "pre_close": float(row.pre_close or 0),
                "volume": float(row.volume or 0),
                "amount": float(row.amount or 0),
                "data_source": row.data_source,
            }
            for row in rows
        ]
    )


def factor_frame(db: Session, stock_code: str, feature_version: str = "feature_v1") -> pd.DataFrame:
    rows = db.scalars(
        select(StockFactorDaily)
        .where(StockFactorDaily.stock_code == _clean_code(stock_code), StockFactorDaily.feature_version == feature_version)
        .order_by(StockFactorDaily.trade_date)
    ).all()
    return pd.DataFrame(
        [
            {
                "trade_date": row.trade_date,
                "ma5": float(row.ma5 or 0),
                "ma20": float(row.ma20 or 0),
                "ma60": float(row.ma60 or 0),
                "rsi": float(row.rsi or 0),
                "macd": float(row.macd or 0),
                "volume_ratio": float(row.volume_ratio or 0),
                "volatility_20d": float(row.volatility_20d or 0),
                "momentum_20d": float(row.momentum_20d or 0),
                "pe": float(row.pe or 0),
                "pb": float(row.pb or 0),
                "roe": float(row.roe or 0),
                "market_cap": float(row.market_cap or 0),
            }
            for row in rows
        ]
    )


def fetch_daily_prices(stock_code: str, start: str = "20240101") -> pd.DataFrame:
    clean = _clean_code(stock_code)
    errors = []
    for fetcher in (_fetch_eastmoney, _fetch_tencent_kline, _fetch_sina_kline):
        try:
            frame = fetcher(clean, start)
            if not frame.empty:
                return frame
        except Exception as exc:
            errors.append(f"{fetcher.__name__}: {exc}")
    frame = _synthetic_daily(clean)
    frame["data_warning"] = "; ".join(errors)
    return frame


def fetch_realtime_quote(stock_code: str, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    clean = _clean_code(stock_code)
    fallback = fallback or {}
    quote = _fetch_tencent_quote(clean) or _fetch_eastmoney_quote(clean)
    if quote:
        return quote
    source = str(fallback.get("data_source") or "")
    if not fallback or "synthetic" in source:
        return {
            "stock_code": clean,
            "stock_name": KNOWN_NAMES.get(clean) or clean,
            "price": None,
            "open": None,
            "high": None,
            "low": None,
            "pre_close": None,
            "change": None,
            "change_pct": None,
            "volume": None,
            "amount": None,
            "quote_time": datetime.utcnow().isoformat(timespec="seconds"),
            "source": "realtime_unavailable",
            "data_status": "unavailable",
            "message": "实时行情接口不可用，且本地历史数据不是可信行情源。",
        }
    close = float(fallback.get("close") or 0)
    pre_close = float(fallback.get("pre_close") or close or 0)
    change = close - pre_close
    change_pct = (change / pre_close * 100) if pre_close else 0
    return {
        "stock_code": clean,
        "stock_name": KNOWN_NAMES.get(clean) or clean,
        "price": round(close, 4),
        "open": fallback.get("open"),
        "high": fallback.get("high"),
        "low": fallback.get("low"),
        "pre_close": round(pre_close, 4),
        "change": round(change, 4),
        "change_pct": round(change_pct, 4),
        "volume": fallback.get("volume"),
        "amount": fallback.get("amount"),
        "quote_time": str(fallback.get("trade_date") or datetime.utcnow().isoformat(timespec="seconds")),
        "source": "daily_history_fallback",
        "data_status": "stale",
        "message": "实时接口不可用，当前显示最近一条真实历史行情。",
    }


def _fetch_eastmoney_quote(stock_code: str) -> dict[str, Any] | None:
    secid = f"{'1' if stock_code.startswith('6') else '0'}.{stock_code}"
    try:
        url = (
            "https://push2.eastmoney.com/api/qt/stock/get"
            f"?secid={secid}&fields=f43,f44,f45,f46,f47,f48,f57,f58,f60,f86,f107,f170"
        )
        data = (requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}).json().get("data") or {})
        price = _eastmoney_price(data.get("f43"))
        if price is None:
            return None
        pre_close = _eastmoney_price(data.get("f60"))
        change = price - pre_close if price is not None and pre_close else None
        change_pct = _eastmoney_percent(data.get("f170"))
        return {
            "stock_code": stock_code,
            "stock_name": KNOWN_NAMES.get(stock_code) or stock_code,
            "price": price,
            "open": _eastmoney_price(data.get("f46")),
            "high": _eastmoney_price(data.get("f44")),
            "low": _eastmoney_price(data.get("f45")),
            "pre_close": pre_close,
            "change": round(change, 4) if change is not None else None,
            "change_pct": change_pct,
            "volume": data.get("f47"),
            "amount": data.get("f48"),
            "quote_time": datetime.fromtimestamp(data.get("f86")).isoformat() if data.get("f86") else datetime.utcnow().isoformat(timespec="seconds"),
            "source": "eastmoney_realtime",
            "data_status": "realtime",
        }
    except Exception:
        return None


def _fetch_tencent_quote(stock_code: str) -> dict[str, Any] | None:
    prefix = "sh" if stock_code.startswith("6") else "sz"
    try:
        response = requests.get(f"https://qt.gtimg.cn/q={prefix}{stock_code}", timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        text = response.content.decode("gbk", errors="ignore")
        body = text.split('="', 1)[1].rsplit('"', 1)[0]
        parts = body.split("~")
        price = _float_or_none(parts[3] if len(parts) > 3 else None)
        if price is None:
            return None
        quote_time = _parse_tencent_time(parts[30] if len(parts) > 30 else "")
        return {
            "stock_code": stock_code,
            "stock_name": KNOWN_NAMES.get(stock_code) or stock_code,
            "price": price,
            "open": _float_or_none(parts[5] if len(parts) > 5 else None),
            "high": _float_or_none(parts[33] if len(parts) > 33 else None),
            "low": _float_or_none(parts[34] if len(parts) > 34 else None),
            "pre_close": _float_or_none(parts[4] if len(parts) > 4 else None),
            "change": _float_or_none(parts[31] if len(parts) > 31 else None),
            "change_pct": _float_or_none(parts[32] if len(parts) > 32 else None),
            "volume": _float_or_none(parts[36] if len(parts) > 36 else None),
            "amount": (_float_or_none(parts[37] if len(parts) > 37 else None) or 0) * 10000,
            "quote_time": quote_time,
            "source": "tencent_realtime",
            "data_status": "realtime",
        }
    except Exception:
        return None


def ensure_seed_data(db: Session) -> None:
    if db.scalar(select(StockBasic).limit(1)):
        return
    for code in ("600418", "600519", "000001"):
        sync_daily_prices(db, code)
        sync_factors(db, code)


def _fetch_eastmoney(stock_code: str, start: str) -> pd.DataFrame:
    secid = f"{'1' if stock_code.startswith('6') else '0'}.{stock_code}"
    url = (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        f"?secid={secid}&fields1=f1,f2,f3,f4,f5,f6&fields2={EASTMONEY_KLINE_FIELDS}"
        f"&klt=101&fqt=1&beg={start}&end=20500101"
    )
    payload = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"}).json()
    klines = (payload.get("data") or {}).get("klines") or []
    rows = []
    for item in klines:
        parts = item.split(",")
        if len(parts) < 11:
            continue
        rows.append(
            {
                "trade_date": datetime.strptime(parts[0], "%Y-%m-%d").date(),
                "open": float(parts[1]),
                "close": float(parts[2]),
                "high": float(parts[3]),
                "low": float(parts[4]),
                "volume": float(parts[5]),
                "amount": float(parts[6]),
                "pre_close": None,
                "data_source": "eastmoney",
            }
        )
    if not rows:
        raise ValueError("empty eastmoney response")
    frame = pd.DataFrame(rows)
    frame["pre_close"] = frame["close"].shift(1).fillna(frame["open"])
    return frame


def _fetch_tencent_kline(stock_code: str, start: str) -> pd.DataFrame:
    prefix = "sh" if stock_code.startswith("6") else "sz"
    start_date = _parse_start_date(start)
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{stock_code},day,{start_date:%Y-%m-%d},,900,qfq"
    payload = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"}).json()
    stock_payload = (payload.get("data") or {}).get(f"{prefix}{stock_code}") or {}
    klines = stock_payload.get("qfqday") or stock_payload.get("day") or []
    rows = []
    for item in klines:
        if len(item) < 6:
            continue
        trade_date = datetime.strptime(item[0], "%Y-%m-%d").date()
        if trade_date < start_date:
            continue
        open_, close, high, low = map(float, (item[1], item[2], item[3], item[4]))
        volume = float(item[5]) * 100
        rows.append(
            {
                "trade_date": trade_date,
                "open": open_,
                "close": close,
                "high": high,
                "low": low,
                "volume": volume,
                "amount": close * volume,
                "pre_close": None,
                "data_source": "tencent_qfq",
            }
        )
    if not rows:
        raise ValueError("empty tencent response")
    frame = pd.DataFrame(rows)
    frame["pre_close"] = frame["close"].shift(1).fillna(frame["open"])
    return frame.round(4)


def _fetch_sina_kline(stock_code: str, start: str) -> pd.DataFrame:
    prefix = "sh" if stock_code.startswith("6") else "sz"
    start_date = _parse_start_date(start)
    url = (
        "https://quotes.sina.cn/cn/api/jsonp.php/var%20KLC_KL_"
        f"{stock_code}=/CN_MarketDataService.getKLineData?symbol={prefix}{stock_code}&scale=240&ma=no&datalen=900"
    )
    text = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"}).text
    import json

    json_text = text.split("=(", 1)[1].rsplit(");", 1)[0]
    rows = []
    for item in json.loads(json_text):
        trade_date = datetime.strptime(str(item["day"]), "%Y-%m-%d").date()
        if trade_date < start_date:
            continue
        open_ = float(item["open"])
        close = float(item["close"])
        high = float(item["high"])
        low = float(item["low"])
        volume = float(item["volume"])
        rows.append(
            {
                "trade_date": trade_date,
                "open": open_,
                "close": close,
                "high": high,
                "low": low,
                "volume": volume,
                "amount": close * volume,
                "pre_close": None,
                "data_source": "sina",
            }
        )
    if not rows:
        raise ValueError("empty sina response")
    frame = pd.DataFrame(rows)
    frame["pre_close"] = frame["close"].shift(1).fillna(frame["open"])
    return frame.round(4)


def _synthetic_daily(stock_code: str, days: int = 360) -> pd.DataFrame:
    seed = sum(ord(char) for char in stock_code)
    rng = np.random.default_rng(seed)
    end = date.today()
    dates = [end - timedelta(days=i) for i in range(days * 2)]
    dates = [d for d in reversed(dates) if d.weekday() < 5][-days:]
    base = 20 + seed % 80
    drift = rng.normal(0.0005, 0.018, len(dates))
    close = base * np.cumprod(1 + drift)
    open_ = close * (1 + rng.normal(0, 0.006, len(dates)))
    high = np.maximum(open_, close) * (1 + rng.random(len(dates)) * 0.02)
    low = np.minimum(open_, close) * (1 - rng.random(len(dates)) * 0.02)
    volume = rng.integers(2_000_000, 40_000_000, len(dates))
    frame = pd.DataFrame({"trade_date": dates, "open": open_, "high": high, "low": low, "close": close, "volume": volume})
    frame["amount"] = frame["close"] * frame["volume"]
    frame["pre_close"] = frame["close"].shift(1).fillna(frame["open"])
    frame["data_source"] = "synthetic_fallback"
    return frame.round(4)


def _upsert_stock(db: Session, stock_code: str, stock_name: str) -> None:
    stock = db.scalar(select(StockBasic).where(StockBasic.stock_code == stock_code))
    if stock:
        stock.stock_name = stock_name
        stock.updated_at = datetime.utcnow()
    else:
        db.add(StockBasic(stock_code=stock_code, stock_name=stock_name, exchange="SH" if stock_code.startswith("6") else "SZ"))


def _clean_code(stock_code: str) -> str:
    clean = "".join(char for char in stock_code if char.isdigit())
    if not clean:
        raise ValueError("stock_code is required")
    return clean.zfill(6)[-6:]


def _parse_start_date(start: str) -> date:
    clean = "".join(char for char in str(start) if char.isdigit())
    if len(clean) >= 8:
        return datetime.strptime(clean[:8], "%Y%m%d").date()
    return date.today() - timedelta(days=900)


def _eastmoney_price(value: Any) -> float | None:
    try:
        number = float(value)
        if number <= 0:
            return None
        return round(number / 100, 4)
    except (TypeError, ValueError):
        return None


def _eastmoney_percent(value: Any) -> float | None:
    try:
        return round(float(value) / 100, 4)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        if value in {"", None, "--"}:
            return None
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _parse_tencent_time(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y%m%d%H%M%S").isoformat()
    except (TypeError, ValueError):
        return datetime.utcnow().isoformat(timespec="seconds")
