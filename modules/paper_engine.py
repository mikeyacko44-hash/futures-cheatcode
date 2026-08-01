"""Autonomous Paper Trading Engine - Eval/Funded prop-style"""
import os, sqlite3
from datetime import datetime
from typing import Dict, Optional, List
import pytz

NY_TZ = pytz.timezone("America/New_York")
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "trades.db")
STARTING_EQUITY = 50000.0
PROFIT_TARGET = 3000.0
MAX_DRAWDOWN_USD = 2000.0
POINT_VALUE = 20.0
EVAL_RISK_PCT = 0.008
EVAL_MIN_CONF = 68
EVAL_RR = 1.9
EVAL_MAX_RISK_USD = 900.0
FUNDED_RISK_PCT = 0.004
FUNDED_MIN_CONF = 78
FUNDED_RR = 1.6
FUNDED_MAX_RISK_USD = 500.0
MIN_RISK_USD = 120.0
MAX_CONTRACTS = 10.0
DE_RISK_DD_THRESHOLD = 0.55

def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_engine_db():
    conn = _conn(); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS engine_state (
        id INTEGER PRIMARY KEY CHECK (id = 1), equity REAL, peak_equity REAL, drawdown_usd REAL, status TEXT,
        open_direction TEXT, open_entry REAL, open_stop REAL, open_target REAL, open_session TEXT,
        open_confluence INTEGER, open_time TEXT, last_update TEXT, total_trades INTEGER DEFAULT 0, wins INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS paper_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT, entry_time TEXT, exit_time TEXT, direction TEXT,
        entry_price REAL, exit_price REAL, stop_price REAL, target_price REAL, contracts REAL DEFAULT 1.0,
        points REAL, pnl_usd REAL, r_multiple REAL, session TEXT, session_bias TEXT, confluence INTEGER,
        risk_usd REAL, exit_reason TEXT, status TEXT)""")
    try: c.execute("ALTER TABLE paper_trades ADD COLUMN contracts REAL DEFAULT 1.0")
    except: pass
    try: c.execute("ALTER TABLE paper_trades ADD COLUMN risk_usd REAL")
    except: pass
    if c.execute("SELECT COUNT(*) FROM engine_state").fetchone()[0] == 0:
        c.execute("INSERT INTO engine_state (id, equity, peak_equity, drawdown_usd, status, last_update) VALUES (1,?,?,0,'ACTIVE',?)",
                  (STARTING_EQUITY, STARTING_EQUITY, datetime.now(NY_TZ).isoformat()))
    conn.commit(); conn.close()

def get_engine_state():
    init_engine_db(); conn = _conn()
    row = conn.execute("SELECT * FROM engine_state WHERE id = 1").fetchone(); conn.close()
    return dict(row) if row else {}

def update_engine_state(**kwargs):
    init_engine_db(); conn = _conn()
    kwargs = {k: v for k, v in kwargs.items() if k != "id"}
    if not kwargs: conn.close(); return
    sets = ", ".join(f"{k} = ?" for k in kwargs.keys())
    conn.execute(f"UPDATE engine_state SET {sets} WHERE id = ?", list(kwargs.values()) + [1])
    conn.commit(); conn.close()

def get_open_paper_trade():
    init_engine_db(); conn = _conn()
    row = conn.execute("SELECT * FROM paper_trades WHERE status = 'OPEN' ORDER BY id DESC LIMIT 1").fetchone(); conn.close()
    return dict(row) if row else None

def get_closed_paper_trades(limit=100):
    init_engine_db(); conn = _conn()
    rows = conn.execute("SELECT * FROM paper_trades WHERE status = 'CLOSED' ORDER BY id DESC LIMIT ?", (limit,)).fetchall(); conn.close()
    return [dict(r) for r in rows]

def compute_engine_stats():
    trades = get_closed_paper_trades(500)
    if not trades:
        return {"total_trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "avg_points": 0.0,
                "avg_pnl_usd": 0.0, "profit_factor": 0.0, "expectancy_pts": 0.0, "total_pnl_usd": 0.0}
    import pandas as pd
    df = pd.DataFrame(trades); total = len(df)
    wins, losses = df[df["points"] > 0], df[df["points"] <= 0]
    gp = wins["pnl_usd"].sum() if len(wins) else 0
    gl = abs(losses["pnl_usd"].sum()) if len(losses) else 1e-9
    return {"total_trades": total, "wins": len(wins), "losses": len(losses),
            "win_rate": round(float(len(wins)/total*100), 1), "avg_points": round(float(df["points"].mean()), 2),
            "avg_pnl_usd": round(float(df["pnl_usd"].mean()), 2), "profit_factor": round(float(gp/gl), 2),
            "expectancy_pts": round(float(df["points"].mean()), 2), "total_pnl_usd": round(float(df["pnl_usd"].sum()), 2)}

def get_phase(equity):
    return "FUNDED" if (equity - STARTING_EQUITY) >= PROFIT_TARGET else "EVAL"

def get_dynamic_risk_usd(equity, current_drawdown, confluence=75):
    phase = get_phase(equity)
    if phase == "EVAL": base_pct, max_risk, min_conf = EVAL_RISK_PCT, EVAL_MAX_RISK_USD, EVAL_MIN_CONF
    else: base_pct, max_risk, min_conf = FUNDED_RISK_PCT, FUNDED_MAX_RISK_USD, FUNDED_MIN_CONF
    risk = equity * base_pct
    conf_mult = 1.30 if confluence >= 90 else (1.15 if confluence >= 82 else (1.00 if confluence >= 75 else (0.75 if confluence >= 68 else 0.50)))
    risk *= conf_mult
    dd_ratio = current_drawdown / MAX_DRAWDOWN_USD if MAX_DRAWDOWN_USD > 0 else 0
    if dd_ratio >= DE_RISK_DD_THRESHOLD:
        risk *= max(0.30, 1.0 - (dd_ratio - DE_RISK_DD_THRESHOLD) / (1.0 - DE_RISK_DD_THRESHOLD) * 0.70)
    risk = max(MIN_RISK_USD, min(risk, max_risk))
    return {"risk_usd": round(risk, 2), "risk_pct": round(risk/equity*100, 3) if equity > 0 else 0,
            "phase": phase, "confluence_mult": conf_mult, "dd_ratio": round(dd_ratio, 3),
            "scaled": dd_ratio >= DE_RISK_DD_THRESHOLD, "min_conf_for_phase": min_conf}

def _calculate_size(entry, stop, risk_usd):
    if not stop or abs(entry - stop) < 0.25: return 1.0
    dollar_per = abs(entry - stop) * POINT_VALUE
    if dollar_per <= 0: return 1.0
    return max(0.5, min(round((risk_usd / dollar_per) * 2) / 2, MAX_CONTRACTS))

def engine_decide_and_act(market_ctx, send_alert_fn=None):
    init_engine_db(); state = get_engine_state(); now = datetime.now(NY_TZ).isoformat()
    if state["status"] == "HALTED" or state["drawdown_usd"] >= MAX_DRAWDOWN_USD:
        update_engine_state(status="HALTED", last_update=now)
        return {"action": "HALTED", "reason": f"Max drawdown ${MAX_DRAWDOWN_USD} reached."}
    price = market_ctx.get("nq_price")
    if not price: return {"action": "NO_ACTION", "reason": "No price data"}
    bias = market_ctx.get("session_bias", "UNKNOWN")
    signal = market_ctx.get("last_signal") or {}
    action, conf = signal.get("action", "NONE"), signal.get("confidence", 0)
    asia_active, hunt_active = market_ctx.get("asia_active", False), market_ctx.get("hunt_active", False)
    mag7 = market_ctx.get("mag7_label", "")
    open_trade = get_open_paper_trade()
    if open_trade:
        direction, entry, stop, target = open_trade["direction"], open_trade["entry_price"], open_trade["stop_price"], open_trade["target_price"]
        exit_price = exit_reason = None
        if direction == "LONG":
            if stop and price <= stop: exit_price, exit_reason = price, "Stop hit"
            elif target and price >= target: exit_price, exit_reason = price, "Target hit"
            elif bias == "PREMIUM" and conf >= 70 and action == "SHORT": exit_price, exit_reason = price, "Bias flipped against long"
        else:
            if stop and price >= stop: exit_price, exit_reason = price, "Stop hit"
            elif target and price <= target: exit_price, exit_reason = price, "Target hit"
            elif bias == "DISCOUNT" and conf >= 70 and action == "LONG": exit_price, exit_reason = price, "Bias flipped against short"
        if exit_price is not None:
            points = (exit_price - entry) if direction == "LONG" else (entry - exit_price)
            contracts = open_trade.get("contracts") or 1.0
            pnl_usd = points * POINT_VALUE * contracts
            risk_pts = abs(entry - stop) if stop else 10
            conn = _conn()
            conn.execute("UPDATE paper_trades SET exit_time=?, exit_price=?, points=?, pnl_usd=?, r_multiple=?, exit_reason=?, status='CLOSED' WHERE id=?",
                (now, exit_price, points, pnl_usd, points/risk_pts if risk_pts else 0, exit_reason, open_trade["id"]))
            conn.commit(); conn.close()
            new_equity = state["equity"] + pnl_usd
            new_peak = max(state["peak_equity"], new_equity)
            new_dd = new_peak - new_equity
            update_engine_state(equity=new_equity, peak_equity=new_peak, drawdown_usd=new_dd,
                status="HALTED" if new_dd >= MAX_DRAWDOWN_USD else "ACTIVE",
                open_direction=None, open_entry=None, open_stop=None, open_target=None,
                open_session=None, open_confluence=None, open_time=None, last_update=now,
                total_trades=state["total_trades"]+1, wins=state["wins"]+(1 if points > 0 else 0))
            msg = {"action": "EXIT", "direction": direction, "entry": entry, "exit": exit_price,
                   "points": round(points, 2), "pnl_usd": round(pnl_usd, 2), "reason": exit_reason,
                   "equity": round(new_equity, 2), "drawdown": round(new_dd, 2)}
            if send_alert_fn: send_alert_fn(msg)
            return {"action": "EXITED", **msg}
        return {"action": "HOLDING", "direction": direction, "entry": entry, "price": price}
    if state["status"] != "ACTIVE": return {"action": "HALTED", "reason": "Engine halted"}
    phase = get_phase(state["equity"])
    risk_info = get_dynamic_risk_usd(state["equity"], state["drawdown_usd"], confluence=conf)
    min_conf, rr = risk_info["min_conf_for_phase"], (EVAL_RR if phase == "EVAL" else FUNDED_RR)
    if action in ("LONG", "SHORT") and conf >= min_conf and (asia_active or hunt_active):
        rh, rl = market_ctx.get("range_high"), market_ctx.get("range_low")
        if action == "LONG":
            stop = (rl - 6) if rl else price - 22
            target = price + (price - stop) * rr
        else:
            stop = (rh + 6) if rh else price + 22
            target = price - (stop - price) * rr
        mag7_aligned = (("BULLISH" in mag7 and action == "LONG") or ("BEARISH" in mag7 and action == "SHORT") or "MIXED" in mag7 or mag7 in ("—", ""))
        if phase == "FUNDED" and not mag7_aligned and conf < 85:
            return {"action": "NO_ACTION", "reason": "Funded — waiting for stronger confluence"}
        risk_usd = risk_info["risk_usd"]
        contracts = _calculate_size(price, stop, risk_usd)
        conn = _conn()
        conn.execute("""INSERT INTO paper_trades (entry_time, direction, entry_price, stop_price, target_price,
            contracts, session, session_bias, confluence, risk_usd, status) VALUES (?,?,?,?,?,?,?,?,?,?,'OPEN')""",
            (now, action, price, stop, target, contracts, "ASIA" if asia_active else "NY", bias, conf, risk_usd))
        conn.commit(); conn.close()
        update_engine_state(open_direction=action, open_entry=price, open_stop=stop, open_target=target,
            open_session="ASIA" if asia_active else "NY", open_confluence=conf, open_time=now, last_update=now)
        msg = {"action": "ENTER", "direction": action, "entry": price, "stop": round(stop, 2), "target": round(target, 2),
               "contracts": contracts, "risk_usd": risk_usd, "risk_pct": risk_info["risk_pct"], "phase": phase,
               "rr": rr, "confluence": conf, "bias": bias, "reason": signal.get("reason", "Time model + confluence")}
        if send_alert_fn: send_alert_fn(msg)
        return {"action": "ENTERED", **msg}
    return {"action": "NO_ACTION", "reason": f"No setup (signal={action}, conf={conf})"}

def reset_engine(confirm=False):
    if not confirm: return False
    init_engine_db(); conn = _conn()
    conn.execute("DELETE FROM paper_trades WHERE status = 'OPEN'")
    conn.execute("""UPDATE engine_state SET equity=?, peak_equity=?, drawdown_usd=0, status='ACTIVE',
        open_direction=NULL, open_entry=NULL, open_stop=NULL, open_target=NULL, open_session=NULL,
        open_confluence=NULL, open_time=NULL, total_trades=0, wins=0, last_update=? WHERE id=1""",
        (STARTING_EQUITY, STARTING_EQUITY, datetime.now(NY_TZ).isoformat()))
    conn.commit(); conn.close(); return True
