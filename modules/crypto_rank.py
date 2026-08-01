"""Crypto ranking — CoinGecko free API. Bullish/bearish score + long/short rank."""
from __future__ import annotations
import requests
import pandas as pd

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

def fetch_markets(vs="usd", per_page=80, page=1) -> pd.DataFrame:
    try:
        r = requests.get(
            f"{COINGECKO}/coins/markets",
            params={
                "vs_currency": vs, "order": "market_cap_desc", "per_page": per_page,
                "page": page, "sparkline": "false",
                "price_change_percentage": "1h,24h,7d",
            },
            timeout=15, headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        rows = []
        for c in r.json():
            ch24 = c.get("price_change_percentage_24h_in_currency") or c.get("price_change_percentage_24h") or 0
            ch7 = c.get("price_change_percentage_7d_in_currency") or 0
            ch1 = c.get("price_change_percentage_1h_in_currency") or 0
            score = (ch1 or 0) * 0.25 + (ch24 or 0) * 0.50 + (ch7 or 0) * 0.25
            if score >= 8: bias, action = "STRONG BULL", "LONG"
            elif score >= 3: bias, action = "BULLISH", "LONG"
            elif score <= -8: bias, action = "STRONG BEAR", "SHORT"
            elif score <= -3: bias, action = "BEARISH", "SHORT"
            else: bias, action = "NEUTRAL", "WAIT"
            rows.append({
                "rank": c.get("market_cap_rank"),
                "symbol": (c.get("symbol") or "").upper(),
                "name": c.get("name"),
                "price": c.get("current_price"),
                "1h%": round(ch1 or 0, 2),
                "24h%": round(ch24 or 0, 2),
                "7d%": round(ch7 or 0, 2),
                "volume": c.get("total_volume") or 0,
                "mcap": c.get("market_cap") or 0,
                "score": round(score, 2),
                "bias": bias,
                "action": action,
            })
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("score", ascending=False).reset_index(drop=True)
            df["long_rank"] = range(1, len(df) + 1)
            df["short_rank"] = range(len(df), 0, -1)
        return df
    except Exception as e:
        print(f"coingecko error: {e}")
        return pd.DataFrame()

def top_longs(df, n=15):
    if df.empty: return df
    return df[df["action"] == "LONG"].head(n)

def top_shorts(df, n=15):
    if df.empty: return df
    return df[df["action"] == "SHORT"].sort_values("score").head(n)
