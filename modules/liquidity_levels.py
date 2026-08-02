"""Liquidity / GEX levels — FlashAlpha (primary) + Skylit (optional) + structure fallback."""
from __future__ import annotations
import os
import requests
from typing import Optional, List, Dict, Any

FLASHALPHA = "https://lab.flashalpha.com/v1"
SKYLIT = "https://api.skylit.ai/v1/heatmap"

def _fa_key() -> Optional[str]:
    return os.getenv("FLASHALPHA_API_KEY") or os.getenv("flashalpha_api_key")

def _skylit_key() -> Optional[str]:
    return os.getenv("SKYLIT_API_KEY") or os.getenv("skylit_api_key")

def flashalpha_levels(symbol: str = "QQQ") -> Optional[dict]:
    key = _fa_key()
    if not key:
        return None
    try:
        r = requests.get(
            f"{FLASHALPHA}/exposure/levels/{symbol}",
            headers={"X-Api-Key": key, "Accept": "application/json"},
            timeout=12,
        )
        if r.status_code != 200:
            print(f"flashalpha levels {r.status_code}: {r.text[:200]}")
            return None
        return r.json()
    except Exception as e:
        print(f"flashalpha levels error: {e}")
        return None

def flashalpha_gex(symbol: str = "QQQ", expiration: Optional[str] = None) -> Optional[dict]:
    key = _fa_key()
    if not key:
        return None
    try:
        params = {}
        if expiration:
            params["expiration"] = expiration
        r = requests.get(
            f"{FLASHALPHA}/exposure/gex/{symbol}",
            params=params or None,
            headers={"X-Api-Key": key, "Accept": "application/json"},
            timeout=15,
        )
        if r.status_code != 200:
            print(f"flashalpha gex {r.status_code}: {r.text[:200]}")
            return None
        return r.json()
    except Exception as e:
        print(f"flashalpha gex error: {e}")
        return None

def flashalpha_to_nodes(levels: dict, gex: Optional[dict] = None) -> List[Dict[str, Any]]:
    if not levels:
        return []
    nodes = []
    mapping = [
        ("gamma_flip", "FLIP", "king"),
        ("live_gamma_flip", "FLIP", "king"),
        ("call_wall", "CALL WALL", "gatekeeper"),
        ("live_call_wall", "CALL WALL", "gatekeeper"),
        ("put_wall", "PUT WALL", "barney"),
        ("live_put_wall", "PUT WALL", "barney"),
        ("max_pain", "MAX PAIN", "pika"),
        ("live_max_pain", "MAX PAIN", "pika"),
        ("zero_dte_magnet", "0DTE MAG", "significant"),
    ]
    for key, label, node in mapping:
        val = levels.get(key)
        if val is None and isinstance(levels.get("data"), dict):
            val = levels["data"].get(key)
        if val is not None:
            try:
                nodes.append({"level": float(val), "label": label, "node": node, "source": "flashalpha"})
            except (TypeError, ValueError):
                pass
    strikes = None
    if gex:
        strikes = gex.get("strikes") or (gex.get("data") or {}).get("strikes")
    if strikes and isinstance(strikes, list):
        scored = []
        for s in strikes:
            try:
                strike = float(s.get("strike") or s.get("k") or 0)
                net = float(s.get("net_gex") or s.get("net") or s.get("value") or 0)
                scored.append((abs(net), strike, net))
            except (TypeError, ValueError):
                continue
        scored.sort(reverse=True)
        for _, strike, net in scored[:4]:
            if any(abs(strike - n["level"]) < 0.5 for n in nodes):
                continue
            nodes.append({
                "level": strike,
                "label": f"GEX {strike:.0f}",
                "node": "significant" if net >= 0 else "barney",
                "source": "flashalpha",
                "value": net,
            })
    return nodes

def skylit_heatmap(symbols: str = "QQQ", metric: str = "gamma") -> Optional[dict]:
    key = _skylit_key()
    if not key:
        return None
    try:
        r = requests.get(
            SKYLIT,
            params={"symbols": symbols, "metric": metric},
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
            "node": nt, "pri": priority.get(nt, 9), "abs": val, "spot": spot,
        })
    scored.sort(key=lambda x: (x["pri"], -x["abs"]))
    out = []
    for s in scored[:max_nodes]:
        out.append({
            "level": s["strike"], "label": f"{s['node'].upper()} {s['strike']:.0f}",
            "node": s["node"], "value": s["value"], "spot": s.get("spot"), "source": "skylit",
        })
    return out

def qqq_to_nq_levels(nodes: List[dict], nq_price: Optional[float], qqq_spot: Optional[float]) -> List[dict]:
    if not nodes or not nq_price or not qqq_spot or qqq_spot <= 0:
        return nodes
    ratio = nq_price / qqq_spot
    return [{
        **n,
        "level": round(float(n["level"]) * ratio, 2),
        "label": n.get("label", "") + "→NQ",
        "source": n.get("source", "") + "|scaled",
    } for n in nodes]

def fallback_structure_levels(price, o8, rh, rl) -> List[dict]:
    levels = []
    if o8:
        levels.append({"level": o8, "label": "8PM Open", "node": "structure", "source": "structure"})
    if rh:
        levels.append({"level": rh, "label": "Asia High", "node": "structure", "source": "structure"})
    if rl:
        levels.append({"level": rl, "label": "Asia Low", "node": "structure", "source": "structure"})
    if rh and rl:
        levels.append({"level": (rh + rl) / 2, "label": "Range Mid", "node": "structure", "source": "structure"})
    return levels

def load_gex_for_nq(nq_price: Optional[float]):
    """FlashAlpha QQQ/SPY first, then Skylit, else empty. Returns (nodes, provider)."""
    if not nq_price:
        return [], "none"
    fa_levels = flashalpha_levels("QQQ")
    fa_sym = "QQQ"
    if not fa_levels:
        fa_levels = flashalpha_levels("SPY")
        fa_sym = "SPY"
    if fa_levels:
        fa_gex = flashalpha_gex(fa_sym)
        nodes = flashalpha_to_nodes(fa_levels, fa_gex)
        spot = (
            fa_levels.get("underlying_price") or fa_levels.get("spot")
            or (fa_levels.get("data") or {}).get("underlying_price")
            or (fa_gex or {}).get("underlying_price")
        )
        if nodes and spot:
            return qqq_to_nq_levels(nodes, nq_price, float(spot)), f"flashalpha:{fa_sym}"
        if nodes:
            return nodes, f"flashalpha:{fa_sym}"
    raw = skylit_heatmap("QQQ", "gamma")
    if raw:
        nodes = extract_key_nodes(raw, max_nodes=6)
        try:
            qqq_spot = raw.get("data", {}).get("symbols", [{}])[0].get("spot")
        except Exception:
            qqq_spot = None
        if nodes and qqq_spot:
            return qqq_to_nq_levels(nodes, nq_price, float(qqq_spot)), "skylit:QQQ"
        if nodes:
            return nodes, "skylit:QQQ"
    return [], "none"
