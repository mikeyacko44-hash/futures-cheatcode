"""Core time-based strategy logic - Asia/NY model"""
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
    if high > range_high and close < range_high: return "HIGH"
    if low < range_low and close > range_low: return "LOW"
    return None

def simple_cisd_long(df, lookback=3):
    if len(df) < lookback + 1: return False
    last = df.iloc[-1]
    body = abs(last["Close"] - last["Open"])
    range_ = last["High"] - last["Low"]
    if range_ == 0: return False
    return last["Close"] > last["Open"] and (body / range_) > 0.55

def simple_cisd_short(df, lookback=3):
    if len(df) < lookback + 1: return False
    last = df.iloc[-1]
    body = abs(last["Close"] - last["Open"])
    range_ = last["High"] - last["Low"]
    if range_ == 0: return False
    return last["Close"] < last["Open"] and (body / range_) > 0.55

def generate_signal(df, open_8pm, range_high, range_low, session="ASIA"):
    if df is None or len(df) < 5:
        return {"action": "NONE", "bias": "NEUTRAL", "confidence": 0, "reason": "Insufficient data"}
    current = df.iloc[-1]
    price, high, low, close = current["Close"], current["High"], current["Low"], current["Close"]
    bias = compute_premium_discount(price, open_8pm)
    sweep = detect_sweep(high, low, range_high, range_low, close) if range_high and range_low else None
    action, confidence, reason = "NONE", 0, []
    if bias == "DISCOUNT" and (sweep == "LOW" or simple_cisd_long(df)):
        action, confidence = "LONG", 65
        reason.append("Discount + sweep/CISD long")
        if sweep == "LOW": confidence += 15; reason.append("Liquidity sweep of range low")
    elif bias == "PREMIUM" and (sweep == "HIGH" or simple_cisd_short(df)):
        action, confidence = "SHORT", 65
        reason.append("Premium + sweep/CISD short")
        if sweep == "HIGH": confidence += 15; reason.append("Liquidity sweep of range high")
    now = get_ny_now()
    if session == "ASIA" and get_asia_window(now): confidence += 10; reason.append("Inside Asia window")
    if session == "ASIA" and get_hunt_window(now): confidence += 10; reason.append("Inside hunt window")
    return {"action": action, "bias": bias, "confidence": min(confidence, 95),
            "reason": " | ".join(reason) if reason else "No setup", "price": price,
            "range_high": range_high, "range_low": range_low, "open_8pm": open_8pm,
            "timestamp": now.isoformat()}
