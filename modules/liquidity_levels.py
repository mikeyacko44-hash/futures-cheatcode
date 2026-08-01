"""Liquidity / GEX levels — Skylit Heatseeker (optional) + structure fallback."""
from __future__ import annotations
import os
import requests
from typing import Optional, List, Dict, Any

SKYLIT = "https://api.skylit.ai/v1/heatmap"

def skylit_heatmap(symbols: str = "QQQ", metric: str = "gamma") -> Optional[dict]:
    key = os.getenv("SKYLIT_API_KEY") or os.getenv("skylit_api_key")
    if not key:
        return None
    try:
        r = requests.get(
            SKYLIT, params={"symbols": symbols, "metric": metric},
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
            timeout=12,
        )
        if r.status_code != 200:
            print(f"skylit {r.status_code}: {r.text[:200]}")
            return None
        return r.json()
    except Exception as e:
        print(f"skylit error: {e}")
        return None

def extract_key_nodes(payload: dict, max_nodes: int = 8) -> List[Dict[str, Any]]:
    if not payload:
        return []
    data = payload.get("data") or payload
    symbols = data.get("symbols") or []
    if not symbols:
        return []
    sym = symbols[0]
    spot = sym.get("spot")
    strikes = sym.get("strikes") or []
    priority = {"king": 0, "gatekeeper": 1, "pika": 2, "barney": 3, "significant": 4}
    scored = []
    for s in strikes:
        nt = (s.get("nodeType") or "normal").lower()
        val = abs(float(s.get("value") or 0))
        scored.append({
            "strike": float(s["strike"]), "value": float(s.get("value") or 0),
            "node": nt, "velocity": s.get("velocityPct"),
            "pri": priority.get(nt, 9), "abs": val,
        })
    scored.sort(key=lambda x: (x["pri"], -x["abs"]))
    out = []
    for s in scored[:max_nodes]:
        out.append({
            "level": s["strike"], "label": f"{s['node'].upper()} {s['strike']:.0f}",
            "node": s["node"], "value": s["value"], "spot": spot,
        })
    return out

def qqq_to_nq_levels(nodes, nq_price, qqq_spot):
    if not nodes or not nq_price or not qqq_spot or qqq_spot <= 0:
        return nodes
    ratio = nq_price / qqq_spot
    return [{**n, "level": round(n["level"] * ratio, 2), "label": n["label"] + "→NQ", "source": "QQQ×ratio"} for n in nodes]

def fallback_structure_levels(price, o8, rh, rl):
    levels = []
    if o8: levels.append({"level": o8, "label": "8PM Open", "node": "structure"})
    if rh: levels.append({"level": rh, "label": "Asia High", "node": "structure"})
    if rl: levels.append({"level": rl, "label": "Asia Low", "node": "structure"})
    if rh and rl:
        levels.append({"level": (rh + rl) / 2, "label": "Range Mid", "node": "structure"})
    return levels
