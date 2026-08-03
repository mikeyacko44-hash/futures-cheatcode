"""Core time-based strategy logic - Asia/NY model (v2 more responsive)"""
from datetime import datetime, time
import pytz
import pandas as pd
import numpy as np

NY_TZ = pytz.timezone("America/New_York")

def get_ny_now():
    return datetime.now(NY_TZ)

def is_in_session(dt, start_h, start_m, end_h, end_m):
    t = dt.time()
    start, end = time(start_h, start_m), time(end_h, end_m)
    if start <= end:
        return start <= t <= end
    return t >= start or t <= end

def get_asia_window(dt=None):
    return is_in_session(dt or get_ny_now(), 20, 0, 0, 0)

def get_hunt_window(dt=None):
    return is_in_session(dt or get_ny_now(), 21, 30, 22, 0)

def get_ny_cash_window(dt=None):
    return is_in_session(dt or get_ny_now(), 9, 30, 16, 0)

def compute_premium_discount(current_price, open_8pm):
    if open_8pm is None or (isinstance(open_8pm, float) and np.isnan(open_8pm)):
        return "UNKNOWN"
    if current_price > open_8pm: return "PREMIUM"
    if current_price < open_8pm: return "DISCOUNT"
    return "AT_OPEN"

def detect_sweep(high, low, range_high, range_low, close):
    if range_high is None or range_low is None:
        return None
    if high > range_high and close < range_high: return "HIGH"
    if low < range_low and close > range_low: return "LOW"
    return None

def simple_cisd_long(df, lookback=3):
    if len(df) < lookback + 1: return False
    last = df.iloc[-1]
    body = abs(last["Close"] - last["Open"])
    range_ = last["High"] - last["Low"]
    if range_ == 0: return False
    return last["Close"] > last["Open"] and (body / range_) > 0.50

def simple_cisd_short(df, lookback=3):
    if len(df) < lookback + 1: return False
    last = df.iloc[-1]
    body = abs(last["Close"] - last["Open"])
    range_ = last["High"] - last["Low"]
    if range_ == 0: return False
    return last["Close"] < last["Open"] and (body / range_) > 0.50

def near_level(price, level, tol_pts=8.0):
    if level is None or price is None:
        return False
    return abs(price - level) <= tol_pts

def generate_signal(df, open_8pm, range_high, range_low, session="ASIA"):
    if df is None or len(df) < 5:
        return {"action": "NONE", "bias": "NEUTRAL", "confidence": 0, "reason": "Insufficient data"}

    current = df.iloc[-1]
    price = float(current["Close"])
    high = float(current["High"])
    low = float(current["Low"])
    close = price

    bias = compute_premium_discount(price, open_8pm)
    sweep = detect_sweep(high, low, range_high, range_low, close)

    action, confidence, reason = "NONE", 0, []

    # Stronger long conditions
    if bias == "DISCOUNT":
        if sweep == "LOW" or simple_cisd_long(df):
            action, confidence = "LONG", 68
            reason.append("Discount + sweep/CISD long")
            if sweep == "LOW":
                confidence += 12
                reason.append("Liquidity sweep of range low")
        elif near_level(price, range_low, 12) and simple_cisd_long(df):
            action, confidence = "LONG", 62
            reason.append("Near Asia Low + bullish close")

    # Stronger short conditions
    elif bias == "PREMIUM":
        if sweep == "HIGH" or simple_cisd_short(df):
            action, confidence = "SHORT", 68
            reason.append("Premium + sweep/CISD short")
            if sweep == "HIGH":
                confidence += 12
                reason.append("Liquidity sweep of range high")
        elif near_level(price, range_high, 12) and simple_cisd_short(df):
            action, confidence = "SHORT", 62
            reason.append("Near Asia High + bearish close")

    now = get_ny_now()
    if session == "ASIA" and get_asia_window(now):
        confidence += 8
        reason.append("Inside Asia window")
    if session == "ASIA" and get_hunt_window(now):
        confidence += 10
        reason.append("Inside hunt window")

    # Soften absolute floor so it can actually fire
    confidence = min(confidence, 95)

    return {
        "action": action,
        "bias": bias,
        "confidence": confidence,
        "reason": " | ".join(reason) if reason else "No clear setup",
        "price": price,
        "range_high": range_high,
        "range_low": range_low,
        "open_8pm": open_8pm,
        "timestamp": now.isoformat(),
    }
