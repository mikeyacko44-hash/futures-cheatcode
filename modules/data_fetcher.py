"""
Data layer. Primary: yfinance (delayed continuous futures + Mag7).
True CME real-time requires a paid feed (Databento, Rithmic, CQG, etc.) — not wired here.
"""

import os
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
import pytz
from dotenv import load_dotenv

load_dotenv()

NY_TZ = pytz.timezone("America/New_York")

YAHOO_NQ = "NQ=F"
YAHOO_ES = "ES=F"
MAG7 = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA"]
STALE_AFTER_MINUTES = 45


def get_futures_ohlcv(symbol: str = "NQ=F", period: str = "5d", interval: str = "5m") -> pd.DataFrame:
    """Delayed OHLCV via Yahoo. Not exchange real-time."""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        df.index = pd.to_datetime(df.index)
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC").tz_convert(NY_TZ)
        else:
            df.index = df.index.tz_convert(NY_TZ)
        return df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    except Exception as e:
        print(f"yfinance error: {e}")
        return pd.DataFrame()


def is_stale(df: pd.DataFrame, max_age_minutes: int = STALE_AFTER_MINUTES) -> bool:
    if df is None or df.empty:
        return True
    try:
        last_ts = df.index[-1]
        if last_ts.tzinfo is None:
            last_ts = NY_TZ.localize(last_ts.to_pydatetime() if hasattr(last_ts, "to_pydatetime") else last_ts)
        age = datetime.now(NY_TZ) - last_ts.to_pydatetime()
        return age > timedelta(minutes=max_age_minutes)
    except Exception:
        return True


def get_session_range(
    df: pd.DataFrame,
    start_hour: int = 20,
    start_min: int = 0,
    end_hour: int = 0,
    end_min: int = 0,
) -> tuple:
    """High/low/open of the most recent Asia-style window only (overnight-safe)."""
    if df is None or df.empty:
        return None, None, None

    d = df.copy()
    if d.index.tz is None:
        d.index = d.index.tz_localize("UTC").tz_convert(NY_TZ)
    else:
        d.index = d.index.tz_convert(NY_TZ)

    now = datetime.now(NY_TZ)
    start_today = now.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
    start_anchor = start_today - timedelta(days=1) if now < start_today else start_today
    end_anchor = start_anchor.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)
    if end_anchor <= start_anchor:
        end_anchor = end_anchor + timedelta(days=1)
    upper = min(now, end_anchor)
    session = d[(d.index >= start_anchor) & (d.index <= upper)]
    if session.empty:
        session = d.tail(48)
    if session.empty:
        return None, None, None
    return float(session["High"].max()), float(session["Low"].min()), float(session.iloc[0]["Open"])


def get_mag7_snapshot() -> pd.DataFrame:
    rows = []
    for ticker in MAG7:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d", interval="1d")
            if hist.empty:
                continue
            last = hist.iloc[-1]
            prev = hist.iloc[-2] if len(hist) > 1 else last
            change_pct = ((last["Close"] - prev["Close"]) / prev["Close"]) * 100
            bias = (
                "BULLISH" if last["Close"] > last["Open"] and change_pct > 0
                else "BEARISH" if change_pct < -0.3 else "NEUTRAL"
            )
            rows.append({
                "Ticker": ticker,
                "Price": round(float(last["Close"]), 2),
                "Change%": round(float(change_pct), 2),
                "DayHigh": round(float(last["High"]), 2),
                "DayLow": round(float(last["Low"]), 2),
                "Bias": bias,
                "PrevClose": round(float(prev["Close"]), 2),
            })
        except Exception:
            continue
    return pd.DataFrame(rows)


def get_mag7_confluence_score(mag7_df: pd.DataFrame) -> dict:
    if mag7_df is None or mag7_df.empty:
        return {"score": 0, "bullish": 0, "bearish": 0, "label": "NO DATA", "total": 0}
    bull = int((mag7_df["Bias"] == "BULLISH").sum())
    bear = int((mag7_df["Bias"] == "BEARISH").sum())
    total = len(mag7_df)
    score = int((bull / total) * 100) if total else 0
    if score >= 70:
        label = "STRONG BULLISH"
    elif score >= 55:
        label = "BULLISH"
    elif score <= 30:
        label = "STRONG BEARISH"
    elif score <= 45:
        label = "BEARISH"
    else:
        label = "MIXED"
    return {"score": score, "bullish": bull, "bearish": bear, "label": label, "total": total}
