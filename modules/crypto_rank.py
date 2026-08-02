"""Crypto ranking — CoinGecko. Clear 0–100 bullishness score + long/short rank."""
from __future__ import annotations
import requests
import pandas as pd
from typing import Optional

COINGECKO = "https://api.coingecko.com/api/v3"
FNG = "https://api.alternative.me/fng/?limit=1"

def fear_greed() -> dict:
    try:
        r = requests.get(FNG, timeout=10)
        r.raise_for_status()
        d = r.json()["data"][0]
        return {"value": int(d["value"]), "label": d["value_classification"], "ts": d.get("timestamp")}
    except Exception as e:
        return {"value": None, "label": "—", "error": str(e)}

def _momentum_to_score(ch1: float, ch24: float, ch7: float) -> float:
    """Map weighted % returns into 0–100 bullishness. 50=neutral, >=60 long, <=40 short."""
    c1 = max(-15.0, min(15.0, ch1 or 0))
    c24 = max(-30.0, min(30.0, ch24 or 0))
    c7 = max(-50.0, min(50.0, ch7 or 0))
    raw = c1 * 0.25 + c24 * 0.50 + c7 * 0.25
    score = 50.0 + (raw / 20.0) * 40.0
    return round(max(0.0, min(100.0, score)), 1)

def _bias_from_score(score: float):
    if score >= 75: return "STRONG BULL", "LONG"
    if score >= 60: return "BULLISH", "LONG"
    if score <= 25: return "STRONG BEAR", "SHORT"
    if score <= 40: return "BEARISH", "SHORT"
    return "NEUTRAL", "WAIT"

def fetch_markets(vs: str = "usd", per_page: int = 80, page: int = 1) -> pd.DataFrame:
    try:
        r = requests.get(
            f"{COINGECKO}/coins/markets",
            params={
                "vs_currency": vs, "order": "market_cap_desc", "per_page": per_page,
                "page": page, "sparkline": "false", "price_change_percentage": "1h,24h,7d",
            },
            timeout=15, headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        rows = []
        for c in r.json():
            ch24 = c.get("price_change_percentage_24h_in_currency") or c.get("price_change_percentage_24h") or 0
            ch7 = c.get("price_change_percentage_7d_in_currency") or 0
            ch1 = c.get("price_change_percentage_1h_in_currency") or 0
            score = _momentum_to_score(float(ch1 or 0), float(ch24 or 0), float(ch7 or 0))
            bias, action = _bias_from_score(score)
            rows.append({
                "mcap_rank": c.get("market_cap_rank"),
                "symbol": (c.get("symbol") or "").upper(),
                "name": c.get("name"),
                "price": c.get("current_price"),
                "1h%": round(float(ch1 or 0), 2),
                "24h%": round(float(ch24 or 0), 2),
                "7d%": round(float(ch7 or 0), 2),
                "volume": c.get("total_volume") or 0,
                "mcap": c.get("market_cap") or 0,
                "score": score,
                "bias": bias,
                "action": action,
            })
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("score", ascending=False).reset_index(drop=True)
            df["long_rank"] = range(1, len(df) + 1)
            df["short_rank"] = list(range(len(df), 0, -1))
        return df
    except Exception as e:
        print(f"coingecko error: {e}")
        return pd.DataFrame()

def top_longs(df: pd.DataFrame, n: int = 15) -> pd.DataFrame:
    if df.empty: return df
    return df[df["action"] == "LONG"].head(n)

def top_shorts(df: pd.DataFrame, n: int = 15) -> pd.DataFrame:
    if df.empty: return df
    return df[df["action"] == "SHORT"].sort_values("score").head(n)

def format_price(p) -> str:
    if p is None: return "—"
    try: p = float(p)
    except (TypeError, ValueError): return "—"
    if p >= 1000: return f"${p:,.0f}"
    if p >= 1: return f"${p:,.2f}"
    if p >= 0.01: return f"${p:.4f}"
    return f"${p:.6f}"

def format_mcap(m) -> str:
    try: m = float(m or 0)
    except (TypeError, ValueError): return "—"
    if m >= 1e12: return f"${m/1e12:.2f}T"
    if m >= 1e9: return f"${m/1e9:.1f}B"
    if m >= 1e6: return f"${m/1e6:.0f}M"
    return f"${m:,.0f}"
