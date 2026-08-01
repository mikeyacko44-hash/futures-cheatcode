"""Phone alerts via Telegram / Pushover"""
import os, requests
from dotenv import load_dotenv
from datetime import datetime
import pytz
load_dotenv()
NY_TZ = pytz.timezone("America/New_York")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PUSHOVER_USER = os.getenv("PUSHOVER_USER_KEY")
PUSHOVER_TOKEN = os.getenv("PUSHOVER_API_TOKEN")

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram not configured")
        return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}"); return False

def send_pushover(message, title="Futures Cheat Code"):
    if not PUSHOVER_USER or not PUSHOVER_TOKEN: return False
    try:
        r = requests.post("https://api.pushover.net/1/messages.json",
            data={"token": PUSHOVER_TOKEN, "user": PUSHOVER_USER, "message": message, "title": title}, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"Pushover error: {e}"); return False

def send_alert(signal, session="ASIA", extra=""):
    action = signal.get("action", "NONE")
    if action == "NONE": return False
    conf, bias, price, reason = signal.get("confidence", 0), signal.get("bias", ""), signal.get("price", 0), signal.get("reason", "")
    now = datetime.now(NY_TZ).strftime("%H:%M ET")
    emoji = "🟢 LONG" if action == "LONG" else "🔴 SHORT"
    msg = f"<b>{emoji} — {session} SETUP</b>\nTime: {now}\nConfidence: {conf}%\nBias: {bias}\nPrice: {price}\nReason: {reason}\n{extra}"
    sent = send_telegram(msg)
    if not sent: sent = send_pushover(msg.replace("<b>","").replace("</b>",""), title=f"{action} {session}")
    return sent

def test_alert():
    return send_alert({"action": "LONG", "confidence": 80, "bias": "DISCOUNT", "price": 21500.25, "reason": "Test alert"}, session="TEST")

def send_engine_alert(event):
    action, direction = event.get("action"), event.get("direction", "")
    now = datetime.now(NY_TZ).strftime("%H:%M ET")
    if action == "ENTER":
        msg = (f"<b>ENGINE ENTERED {direction}</b>\nTime: {now}\nEntry: {event.get('entry')}\nStop: {event.get('stop')}\n"
               f"Target: {event.get('target')}\nPhase: {event.get('phase', '?')} | Size: {event.get('contracts', 1)}\n"
               f"Risk: ${event.get('risk_usd', 0)} ({event.get('risk_pct', 0)}%)\nConfluence: {event.get('confluence')}%\n"
               f"Bias: {event.get('bias')}\nReason: {event.get('reason', '')}")
    elif action == "EXIT":
        pts = event.get("points", 0)
        emoji = "✅" if pts > 0 else "❌"
        msg = (f"<b>{emoji} ENGINE EXITED {direction}</b>\nTime: {now}\nEntry → Exit: {event.get('entry')} → {event.get('exit')}\n"
               f"Points: {pts}\nPnL: ${event.get('pnl_usd', 0)}\nReason: {event.get('reason')}\n"
               f"Equity: ${event.get('equity')} | DD: ${event.get('drawdown')}")
    else:
        msg = f"Engine event: {event}"
    sent = send_telegram(msg)
    if not sent: sent = send_pushover(msg.replace("<b>","").replace("</b>",""), title="Engine Alert")
    return sent
