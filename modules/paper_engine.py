"""
Autonomous Paper Trading Engine
- Decides entries & exits using Asia/NY time model + Mag7
- Alerts on ENTER / EXIT (deduped)
- Prop-style $2k max drawdown, Eval vs Funded risk
"""

import os
import sqlite3
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

_STATE_COLS = {
    "equity", "peak_equity", "drawdown_usd", "status",
    "open_direction", "open_entry", "open_stop", "open_target",
    "open_session", "open_confluence", "open_time", "last_update",
    "total_trades", "wins", "last_alert_key", "last_alert_ts",
}


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass
    return conn


def init_engine_db():
    conn = _conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS engine_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            equity REAL, peak_equity REAL, drawdown_usd REAL, status TEXT,
            open_direction TEXT, open_entry REAL, open_stop REAL, open_target REAL,
            open_session TEXT, open_confluence INTEGER, open_time TEXT, last_update TEXT,
            total_trades INTEGER DEFAULT 0, wins INTEGER DEFAULT 0,
            last_alert_key TEXT, last_alert_ts TEXT
        )
    """)
    for col, typ in (("last_alert_key", "TEXT"), ("last_alert_ts", "TEXT")):
        try:
            c.execute(f"ALTER TABLE engine_state ADD COLUMN {col} {typ}")
        except Exception:
            pass
    c.execute("""
        CREATE TABLE IF NOT EXISTS paper_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_time TEXT, exit_time TEXT, direction TEXT,
            entry_price REAL, exit_price REAL, stop_price REAL, target_price REAL,
            contracts REAL DEFAULT 1.0, points REAL, pnl_usd REAL, r_multiple REAL,
            session TEXT, session_bias TEXT, confluence INTEGER, risk_usd REAL,
            exit_reason TEXT, status TEXT
        )
    """)
    try:
        c.execute("ALTER TABLE paper_trades ADD COLUMN contracts REAL DEFAULT 1.0")
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE paper_trades ADD COLUMN risk_usd REAL")
    except Exception:
        pass
    c.execute("SELECT COUNT(*) FROM engine_state")
    if c.fetchone()[0] == 0:
        c.execute(
            "INSERT INTO engine_state (id, equity, peak_equity, drawdown_usd, status, last_update) VALUES (1, ?, ?, 0, 'ACTIVE', ?)",
            (STARTING_EQUITY, STARTING_EQUITY, datetime.now(NY_TZ).isoformat()),
        )
    conn.commit()
    conn.close()


def get_engine_state() -> Dict:
    init_engine_db()
    conn = _conn()
    row = conn.execute("SELECT * FROM engine_state WHERE id = 1").fetchone()
    conn.close()
    return dict(row) if row else {}


def update_engine_state(**kwargs):
    init_engine_db()
    conn = _conn()
    kwargs = {k: v for k, v in kwargs.items() if k in _STATE_COLS}
    if not kwargs:
        conn.close()
        return
    sets = ", ".join(f"{k} = ?" for k in kwargs.keys())
    conn.execute(f"UPDATE engine_state SET {sets} WHERE id = ?", list(kwargs.values()) + [1])
    conn.commit()
    conn.close()


def get_open_paper_trade() -> Optional[Dict]:
    init_engine_db()
    conn = _conn()
    row = conn.execute("SELECT * FROM paper_trades WHERE status = 'OPEN' ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


def get_closed_paper_trades(limit: int = 100) -> List[Dict]:
    init_engine_db()
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM paper_trades WHERE status = 'CLOSED' ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def compute_engine_stats() -> Dict:
    trades = get_closed_paper_trades(500)
    if not trades:
        return {
            "total_trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0,
            "avg_points": 0.0, "avg_pnl_usd": 0.0, "profit_factor": 0.0,
            "expectancy_pts": 0.0, "total_pnl_usd": 0.0,
        }
    import pandas as pd
    df = pd.DataFrame(trades)
    total = len(df)
    wins = df[df["points"] > 0]
    losses = df[df["points"] <= 0]
    gp = wins["pnl_usd"].sum() if len(wins) else 0
    gl = abs(losses["pnl_usd"].sum()) if len(losses) else 1e-9
    return {
        "total_trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(float(len(wins) / total * 100), 1),
        "avg_points": round(float(df["points"].mean()), 2),
        "avg_pnl_usd": round(float(df["pnl_usd"].mean()), 2),
        "profit_factor": round(float(gp / gl), 2),
        "expectancy_pts": round(float(df["points"].mean()), 2),
        "total_pnl_usd": round(float(df["pnl_usd"].sum()), 2),
    }


def get_phase(equity: float) -> str:
    return "FUNDED" if (equity - STARTING_EQUITY) >= PROFIT_TARGET else "EVAL"


def get_dynamic_risk_usd(equity: float, current_drawdown: float, confluence: int = 75) -> dict:
    phase = get_phase(equity)
    if phase == "EVAL":
        base_pct, max_risk, min_conf = EVAL_RISK_PCT, EVAL_MAX_RISK_USD, EVAL_MIN_CONF
    else:
        base_pct, max_risk, min_conf = FUNDED_RISK_PCT, FUNDED_MAX_RISK_USD, FUNDED_MIN_CONF
    risk = equity * base_pct
    if confluence >= 90:
        conf_mult = 1.30
    elif confluence >= 82:
        conf_mult = 1.15
    elif confluence >= 75:
        conf_mult = 1.00
    elif confluence >= 68:
        conf_mult = 0.75
    else:
        conf_mult = 0.50
    risk *= conf_mult
    dd_ratio = current_drawdown / MAX_DRAWDOWN_USD if MAX_DRAWDOWN_USD > 0 else 0
    if dd_ratio >= DE_RISK_DD_THRESHOLD:
        scale = max(0.30, 1.0 - (dd_ratio - DE_RISK_DD_THRESHOLD) / (1.0 - DE_RISK_DD_THRESHOLD) * 0.70)
        risk *= scale
    risk = max(MIN_RISK_USD, min(risk, max_risk))
    return {
        "risk_usd": round(risk, 2),
        "risk_pct": round(risk / equity * 100, 3) if equity > 0 else 0,
        "phase": phase,
        "confluence_mult": conf_mult,
        "dd_ratio": round(dd_ratio, 3),
        "scaled": dd_ratio >= DE_RISK_DD_THRESHOLD,
        "min_conf_for_phase": min_conf,
    }


def _calculate_size(entry: float, stop: float, risk_usd: float) -> float:
    if not stop or abs(entry - stop) < 0.25:
        return 1.0
    dollar_per_contract = abs(entry - stop) * POINT_VALUE
    if dollar_per_contract <= 0:
        return 1.0
    contracts = risk_usd / dollar_per_contract
    contracts = round(contracts * 2) / 2
    return max(0.5, min(contracts, MAX_CONTRACTS))


def _should_send_alert(state: Dict, key: str, cooldown_sec: int = 90) -> bool:
    last_key = state.get("last_alert_key")
    last_ts = state.get("last_alert_ts")
    if last_key == key and last_ts:
        try:
            prev = datetime.fromisoformat(last_ts)
            if prev.tzinfo is None:
                prev = NY_TZ.localize(prev)
            if (datetime.now(NY_TZ) - prev).total_seconds() < cooldown_sec:
                return False
        except Exception:
            pass
    return True


def engine_decide_and_act(market_ctx: Dict, send_alert_fn=None) -> Dict:
    init_engine_db()
    state = get_engine_state()
    now = datetime.now(NY_TZ).isoformat()

    if state["status"] == "HALTED" or state["drawdown_usd"] >= MAX_DRAWDOWN_USD:
        update_engine_state(status="HALTED", last_update=now)
        return {"action": "HALTED", "reason": f"Max drawdown ${MAX_DRAWDOWN_USD} reached. Engine paused."}

    price = market_ctx.get("nq_price")
    if not price:
        return {"action": "NO_ACTION", "reason": "No price data"}

    if market_ctx.get("data_stale"):
        return {"action": "NO_ACTION", "reason": "Stale market data — no new entries until feed refreshes"}

    bias = market_ctx.get("session_bias", "UNKNOWN")
    signal = market_ctx.get("last_signal") or {}
    action = signal.get("action", "NONE")
    conf = signal.get("confidence", 0)
    asia_active = market_ctx.get("asia_active", False)
    hunt_active = market_ctx.get("hunt_active", False)
    mag7 = market_ctx.get("mag7_label", "")
    open_trade = get_open_paper_trade()

    if open_trade:
        direction = open_trade["direction"]
        entry = open_trade["entry_price"]
        stop = open_trade["stop_price"]
        target = open_trade["target_price"]
        exit_price = None
        exit_reason = None

        bar_high = market_ctx.get("bar_high", price)
        bar_low = market_ctx.get("bar_low", price)
        try:
            bar_high = float(bar_high) if bar_high is not None else price
            bar_low = float(bar_low) if bar_low is not None else price
        except (TypeError, ValueError):
            bar_high, bar_low = price, price

        if direction == "LONG":
            if stop and bar_low <= stop:
                exit_price, exit_reason = float(stop), "Stop hit"
            elif target and bar_high >= target:
                exit_price, exit_reason = float(target), "Target hit"
            elif bias == "PREMIUM" and conf >= 70 and action == "SHORT":
                exit_price, exit_reason = price, "Bias flipped against long"
        else:
            if stop and bar_high >= stop:
                exit_price, exit_reason = float(stop), "Stop hit"
            elif target and bar_low <= target:
                exit_price, exit_reason = float(target), "Target hit"
            elif bias == "DISCOUNT" and conf >= 70 and action == "LONG":
                exit_price, exit_reason = price, "Bias flipped against short"

        if exit_price is not None:
            points = (exit_price - entry) if direction == "LONG" else (entry - exit_price)
            contracts = open_trade.get("contracts") or 1.0
            pnl_usd = points * POINT_VALUE * contracts
            risk_pts = abs(entry - stop) if stop else 10
            r_mult = points / risk_pts if risk_pts > 0 else 0

            conn = _conn()
            conn.execute(
                """UPDATE paper_trades SET exit_time=?, exit_price=?, points=?, pnl_usd=?,
                   r_multiple=?, exit_reason=?, status='CLOSED' WHERE id=?""",
                (now, exit_price, points, pnl_usd, r_mult, exit_reason, open_trade["id"]),
            )
            conn.commit()
            conn.close()

            new_equity = state["equity"] + pnl_usd
            new_peak = max(state["peak_equity"], new_equity)
            new_dd = new_peak - new_equity
            new_status = "HALTED" if new_dd >= MAX_DRAWDOWN_USD else "ACTIVE"
            wins = state["wins"] + (1 if points > 0 else 0)

            update_engine_state(
                equity=new_equity, peak_equity=new_peak, drawdown_usd=new_dd, status=new_status,
                open_direction=None, open_entry=None, open_stop=None, open_target=None,
                open_session=None, open_confluence=None, open_time=None, last_update=now,
                total_trades=state["total_trades"] + 1, wins=wins,
            )

            msg = {
                "action": "EXIT", "direction": direction, "entry": entry, "exit": exit_price,
                "points": round(points, 2), "pnl_usd": round(pnl_usd, 2), "reason": exit_reason,
                "equity": round(new_equity, 2), "drawdown": round(new_dd, 2),
            }
            alert_key = f"EXIT:{open_trade['id']}:{exit_reason}"
            if send_alert_fn and _should_send_alert(state, alert_key, cooldown_sec=120):
                send_alert_fn(msg)
                update_engine_state(last_alert_key=alert_key, last_alert_ts=now)
            return {"action": "EXITED", **msg}

        return {"action": "HOLDING", "direction": direction, "entry": entry, "price": price}

    if state["status"] != "ACTIVE":
        return {"action": "HALTED", "reason": "Engine halted by drawdown rule"}

    phase = get_phase(state["equity"])
    risk_info = get_dynamic_risk_usd(state["equity"], state["drawdown_usd"], confluence=conf)
    min_conf = risk_info["min_conf_for_phase"]
    rr = EVAL_RR if phase == "EVAL" else FUNDED_RR

    high_conf = conf >= min_conf
    good_session = asia_active or hunt_active
    mag7_aligned = (
        ("BULLISH" in mag7 and action == "LONG")
        or ("BEARISH" in mag7 and action == "SHORT")
        or "MIXED" in mag7
        or mag7 in ("—", "")
    )

    if action in ("LONG", "SHORT") and high_conf and good_session:
        range_high = market_ctx.get("range_high")
        range_low = market_ctx.get("range_low")
        if action == "LONG":
            stop = (range_low - 6) if range_low else price - 22
            target = price + (price - stop) * rr
        else:
            stop = (range_high + 6) if range_high else price + 22
            target = price - (stop - price) * rr

        if phase == "FUNDED" and not mag7_aligned and conf < 85:
            return {"action": "NO_ACTION", "reason": "Funded stage — waiting for stronger confluence"}

        risk_usd = risk_info["risk_usd"]
        contracts = _calculate_size(price, stop, risk_usd)

        conn = _conn()
        conn.execute(
            """INSERT INTO paper_trades (
                entry_time, direction, entry_price, stop_price, target_price,
                contracts, session, session_bias, confluence, risk_usd, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')""",
            (now, action, price, stop, target, contracts,
             "ASIA" if asia_active else "NY", bias, conf, risk_usd),
        )
        conn.commit()
        conn.close()

        update_engine_state(
            open_direction=action, open_entry=price, open_stop=stop, open_target=target,
            open_session="ASIA" if asia_active else "NY", open_confluence=conf,
            open_time=now, last_update=now,
        )

        msg = {
            "action": "ENTER", "direction": action, "entry": price,
            "stop": round(stop, 2), "target": round(target, 2),
            "contracts": contracts, "risk_usd": risk_usd, "risk_pct": risk_info["risk_pct"],
            "phase": phase, "rr": rr, "confluence": conf, "bias": bias,
            "reason": signal.get("reason", "Time model + confluence"),
        }
        alert_key = f"ENTER:{action}:{round(price, 2)}:{now[:16]}"
        if send_alert_fn and _should_send_alert(state, alert_key, cooldown_sec=90):
            send_alert_fn(msg)
            update_engine_state(last_alert_key=alert_key, last_alert_ts=now)
        return {"action": "ENTERED", **msg}

    return {
        "action": "NO_ACTION",
        "reason": f"No high-confidence setup (signal={action}, conf={conf}, session_ok={good_session})",
    }


def reset_engine(confirm: bool = False):
    if not confirm:
        return False
    init_engine_db()
    conn = _conn()
    conn.execute("DELETE FROM paper_trades WHERE status = 'OPEN'")
    conn.execute(
        """UPDATE engine_state SET
            equity=?, peak_equity=?, drawdown_usd=0, status='ACTIVE',
            open_direction=NULL, open_entry=NULL, open_stop=NULL, open_target=NULL,
            open_session=NULL, open_confluence=NULL, open_time=NULL,
            total_trades=0, wins=0, last_update=?, last_alert_key=NULL, last_alert_ts=NULL
        WHERE id=1""",
        (STARTING_EQUITY, STARTING_EQUITY, datetime.now(NY_TZ).isoformat()),
    )
    conn.commit()
    conn.close()
    return True
