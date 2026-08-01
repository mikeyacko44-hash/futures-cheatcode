"""Data layer - yfinance for NQ + Mag7"""
import os, pandas as pd, yfinance as yf
from datetime import datetime
import pytz
from dotenv import load_dotenv
load_dotenv()
NY_TZ = pytz.timezone("America/New_York")
MAG7 = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA"]

def get_futures_ohlcv(symbol="NQ=F", period="5d", interval="5m"):
    try:
        df = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=True)
        if df.empty: return pd.DataFrame()
        df.index = pd.to_datetime(df.index)
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC").tz_convert(NY_TZ)
        else:
            df.index = df.index.tz_convert(NY_TZ)
        return df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    except Exception as e:
        print(f"yfinance error: {e}"); return pd.DataFrame()

def get_session_range(df, start_hour=20, start_min=0, end_hour=0, end_min=0):
    if df.empty: return None, None, None
    df = df.copy()
    df["hour"] = df.index.hour
    mask = (df["hour"] >= start_hour) | (df["hour"] < end_hour if end_hour < start_hour else df["hour"] <= end_hour)
    session_df = df[mask]
    if session_df.empty: session_df = df.tail(48)
    if session_df.empty: return None, None, None
    return float(session_df["High"].max()), float(session_df["Low"].min()), float(session_df.iloc[0]["Open"])

def get_mag7_snapshot():
    rows = []
    for ticker in MAG7:
        try:
            hist = yf.Ticker(ticker).history(period="5d", interval="1d")
            if hist.empty: continue
            last, prev = hist.iloc[-1], hist.iloc[-2] if len(hist) > 1 else hist.iloc[-1]
            change_pct = ((last["Close"] - prev["Close"]) / prev["Close"]) * 100
            bias = "BULLISH" if last["Close"] > last["Open"] and change_pct > 0 else ("BEARISH" if change_pct < -0.3 else "NEUTRAL")
            rows.append({"Ticker": ticker, "Price": round(last["Close"], 2), "Change%": round(change_pct, 2),
                "DayHigh": round(last["High"], 2), "DayLow": round(last["Low"], 2), "Bias": bias, "PrevClose": round(prev["Close"], 2)})
        except: continue
    return pd.DataFrame(rows)

def get_mag7_confluence_score(mag7_df):
    if mag7_df.empty: return {"score": 0, "bullish": 0, "bearish": 0, "label": "NO DATA", "total": 0}
    bull = (mag7_df["Bias"] == "BULLISH").sum()
    bear = (mag7_df["Bias"] == "BEARISH").sum()
    total = len(mag7_df)
    score = int((bull / total) * 100) if total else 0
    if score >= 70: label = "STRONG BULLISH"
    elif score >= 55: label = "BULLISH"
    elif score <= 30: label = "STRONG BEARISH"
    elif score <= 45: label = "BEARISH"
    else: label = "MIXED"
    return {"score": score, "bullish": int(bull), "bearish": int(bear), "label": label, "total": total}

def get_databento_live(symbol="NQ.FUT"):
    return None
