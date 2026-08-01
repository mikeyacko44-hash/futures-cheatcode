"""Futures AI Agent — data-grounded"""
from datetime import datetime
import pytz, os
from typing import Dict, List, Optional
NY_TZ = pytz.timezone("America/New_York")
CT_TZ = pytz.timezone("America/Chicago")

def build_market_context(nq_price, session_bias, range_high, range_low, open_8pm,
    mag7_label, mag7_bullish, mag7_total, asia_active, hunt_active, last_signal=None, social_notes=""):
    now_ny = datetime.now(NY_TZ).strftime("%Y-%m-%d %H:%M ET")
    ctx = f"CURRENT MARKET ({now_ny}):\n- NQ: {nq_price}\n- Bias: {session_bias}\n- Range: {range_low}-{range_high}\n- 8PM Open: {open_8pm}\n- Asia: {asia_active} | Hunt: {hunt_active}\n- Mag7: {mag7_label} ({mag7_bullish}/{mag7_total})\n"
    if last_signal:
        ctx += f"- Signal: {last_signal.get('action')} ({last_signal.get('confidence')}%)\n"
    return ctx

SYSTEM_PROMPT = "You are the Futures AI Agent. Deliver real alpha grounded in market context. Concise, directional, risk-aware."

def rule_based_response(question, ctx):
    q = question.lower().strip()
    price, bias, mag = ctx.get("nq_price"), ctx.get("session_bias", "UNKNOWN"), ctx.get("mag7_label", "—")
    signal = ctx.get("last_signal") or {}
    action, conf = signal.get("action", "NONE"), signal.get("confidence", 0)
    asia, hunt = ctx.get("asia_active", False), ctx.get("hunt_active", False)
    if any(w in q for w in ["bias", "direction", "long or short", "what should i do", "setup"]):
        lines = [f"**NQ:** {price:,.2f}" if price else "**NQ:** —", f"**Bias:** {bias}", f"**Mag7:** {mag}",
                 f"**Signal:** {action} ({conf}%)", f"**Asia:** {'ACTIVE' if asia else 'closed'} | **Hunt:** {'NOW' if hunt else '—'}"]
        if action == "LONG" and conf >= 70: lines.append("\n→ High-probability **LONG**")
        elif action == "SHORT" and conf >= 70: lines.append("\n→ High-probability **SHORT**")
        else: lines.append("\n→ No high-confidence trigger. Stand aside.")
        return "\n".join(lines)
    if any(w in q for w in ["risk", "size", "position"]):
        return "Risk: 0.5–1% per idea in eval. Less in funded. Hard $2k max DD."
    return f"NQ {price} | Bias **{bias}** | Mag7 **{mag}** | Signal **{action}** ({conf}%)\nAsk: bias, long/short, Asia status, risk."

def get_agent_reply(question, market_ctx, chat_history=None, use_llm=False, api_key=None, provider="openai"):
    if use_llm and api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=os.getenv("LLM_BASE_URL") or None)
            context_str = build_market_context(
                market_ctx.get("nq_price"), market_ctx.get("session_bias", "UNKNOWN"),
                market_ctx.get("range_high"), market_ctx.get("range_low"), market_ctx.get("open_8pm"),
                market_ctx.get("mag7_label", "—"), market_ctx.get("mag7_bullish", 0),
                market_ctx.get("mag7_total", 7), market_ctx.get("asia_active", False),
                market_ctx.get("hunt_active", False), market_ctx.get("last_signal"))
            messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n\n" + context_str}]
            if chat_history:
                for t in chat_history[-8:]: messages.append(t)
            messages.append({"role": "user", "content": question})
            resp = client.chat.completions.create(model=os.getenv("LLM_MODEL", "gpt-4o-mini"), messages=messages, temperature=0.3, max_tokens=600)
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return f"(LLM failed: {e})\n\n" + rule_based_response(question, market_ctx)
    return rule_based_response(question, market_ctx)
