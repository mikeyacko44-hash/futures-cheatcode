"""
Phone alerts via Telegram (free + works on iOS) or Pushover.
"""

import os
import requests
from dotenv import load_dotenv
from datetime import datetime
import pytz

load_dotenv()

NY_TZ = pytz.timezone("America/New_York")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PUSHOVER_USER = os.getenv("PUSHOVER_USER_KEY")
PUSHOVER_TOKEN = os.getenv("PUSHOVER_API_TOKEN")

def send_telegram(message: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url, json=payload, timeout=3)
        return r.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def send_pushover(message: str, title: str = "Futures Cheat Code") -> bool:
    if not PUSHOVER_USER or not PUSHOVER_TOKEN:
        return False
    url = "https://api.pushover.net/1/messages.json"
    payload = {
        "token": PUSHOVER_TOKEN,
        "user": PUSHOVER_USER,
        "message": message,
        "title": title,
        "priority": 0
    }
    try:
        r = requests.post(url, data=payload, timeout=3)
        return r.status_code == 200
    except Exception as e:
        print(f"Pushover error: {e}")
        return False

def send_alert(signal: dict, session: str = "ASIA", extra: str = "") -> bool:
    action = signal.get("action", "NONE")
    if action == "NONE":
        return False

    conf = signal.get("confidence", 0)
    bias = signal.get("bias", "")
    price = signal.get("price", 0)
    reason = signal.get("reason", "")
    now = datetime.now(NY_TZ).strftime("%H:%M ET")

    emoji = "🟢 LONG" if action == "LONG" else "🔴 SHORT"
    msg = (
        f"<b>{emoji} — {session} SETUP</b>\n"
        f"Time: {now}\n"
        f"Confidence: {conf}%\n"
        f"Bias: {bias}\n"
        f"Price: {price:.2f}\n"
        f"Reason: {reason}\n"
        f"{extra}"
    )

    sent = send_telegram(msg)
    if not sent:
        sent = send_pushover(msg.replace("<b>", "").replace("</b>", ""), title=f"{action} {session}")
    return sent

def test_alert():
    test_sig = {
        "action": "LONG",
        "confidence": 80,
        "bias": "DISCOUNT",
        "price": 21500.25,
        "reason": "Test alert from Futures Cheat Code"
    }
    return send_alert(test_sig, session="TEST")

def send_engine_alert(event: dict) -> bool:
    action = event.get("action")
    direction = event.get("direction", "")
    now = datetime.now(NY_TZ).strftime("%H:%M ET")

    if action == "ENTER":
        msg = (
            f"<b>ENGINE ENTERED {direction}</b>\n"
            f"Time: {now}\n"
            f"Entry: {event.get('entry')}\n"
            f"Stop: {event.get('stop')}\n"
            f"Target: {event.get('target')}\n"
            f"Phase: {event.get('phase', '?')}  |  Size: {event.get('contracts', 1)} contracts\n"
            f"Risk: ${event.get('risk_usd', 0)} ({event.get('risk_pct', 0)}%)\n"
            f"Confluence: {event.get('confluence')}%\n"
            f"Bias: {event.get('bias')}\n"
            f"Reason: {event.get('reason', '')}"
        )
    elif action == "EXIT":
        pts = event.get("points", 0)
        emoji = "✅" if pts > 0 else "❌"
        msg = (
            f"<b>{emoji} ENGINE EXITED {direction}</b>\n"
            f"Time: {now}\n"
            f"Entry → Exit: {event.get('entry')} → {event.get('exit')}\n"
            f"Points: {pts}\n"
            f"PnL: ${event.get('pnl_usd', 0)}\n"
            f"Reason: {event.get('reason')}\n"
            f"Equity: ${event.get('equity')} | DD: ${event.get('drawdown')}"
        )
    else:
        msg = f"Engine event: {event}"

    sent = send_telegram(msg)
    if not sent:
        sent = send_pushover(msg.replace("<b>", "").replace("</b>", ""), title="Engine Alert")
    return sent
