"""Social Alpha - parse FinTwit into structured signals"""
import re
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict
from datetime import datetime
import pytz
NY_TZ = pytz.timezone("America/New_York")
DEFAULT_WATCHLIST = [
    {"handle": "AdamMancini4", "name": "Adam Mancini", "style": "ES structure"},
    {"handle": "PeterLBrandt", "name": "Peter Brandt", "style": "Classical chart"},
]
DEMO_SIGNALS = [
    {"author": "AdamMancini4", "text": "Elevator down, Failed Breakdown, squeeze. Reclaim takes us higher."},
]

@dataclass
class ParsedSignal:
    direction: str
    instrument: str
    entry_zone: Optional[str] = None
    target: Optional[str] = None
    invalidation: Optional[str] = None
    raw_text: str = ""
    author: str = ""
    confidence: int = 40
    notes: str = ""
    timestamp: str = ""
    def to_dict(self): return asdict(self)

def parse_tweet(text, author="unknown"):
    text_lower = text.lower()
    direction = "NEUTRAL"
    if re.search(r"\b(long|buying|bullish|looking.?long)\b", text_lower): direction = "LONG"
    elif re.search(r"\b(short|selling|bearish|looking.?short)\b", text_lower): direction = "SHORT"
    instrument = "NQ"
    if re.search(r"\b(es|s&p|/es)\b", text_lower): instrument = "ES"
    elif re.search(r"\b(nq|nasdaq|/nq)\b", text_lower): instrument = "NQ"
    levels = [float(m) for m in re.findall(r"\b(\d{3,5}(?:\.\d{1,2})?)\b", text.replace(",", "")) if 500 < float(m) < 100000]
    entry_zone = target = invalidation = None
    conf = 35
    if direction != "NEUTRAL": conf += 20
    if levels:
        if direction == "LONG": entry_zone = str(min(levels)); target = str(max(levels)) if len(levels) > 1 else None
        elif direction == "SHORT": entry_zone = str(max(levels)); target = str(min(levels)) if len(levels) > 1 else None
        conf += 15
    conf = min(conf, 90)
    return ParsedSignal(direction=direction, instrument=instrument, entry_zone=entry_zone, target=target,
        invalidation=invalidation, raw_text=text[:400], author=author, confidence=conf,
        notes="Rule-based parse", timestamp=datetime.now(NY_TZ).strftime("%Y-%m-%d %H:%M ET"))

def score_confluence(parsed, session_bias, mag7_label):
    score = parsed.confidence
    reasons = []
    if session_bias == "DISCOUNT" and parsed.direction == "LONG": score += 20; reasons.append("Aligns with Discount")
    elif session_bias == "PREMIUM" and parsed.direction == "SHORT": score += 20; reasons.append("Aligns with Premium")
    if "BULLISH" in mag7_label and parsed.direction == "LONG": score += 12; reasons.append("Mag7 supports long")
    elif "BEARISH" in mag7_label and parsed.direction == "SHORT": score += 12; reasons.append("Mag7 supports short")
    score = max(0, min(score, 98))
    return {"confluence_score": score, "reasons": reasons, "actionable": score >= 70 and parsed.direction != "NEUTRAL"}
