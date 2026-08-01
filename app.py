"""Futures Cheat Code — useful autonomous dashboard"""
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import pytz
from dotenv import load_dotenv
import pandas as pd
import plotly.graph_objects as go

load_dotenv()

st.set_page_config(
    page_title="Futures Cheat Code",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
.stApp { background-color: #0b0e14; color: #e8eaed; }
.block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 900px; }
div[data-testid="stMetricValue"] { font-size: 1.4rem; }
.action-long { background: #0d2f1c; border: 1px solid #00c853; border-radius: 12px; padding: 16px; margin: 8px 0; }
.action-short { background: #2f0d0d; border: 1px solid #ff5252; border-radius: 12px; padding: 16px; margin: 8px 0; }
.action-wait { background: #1a1d24; border: 1px solid #3a3f4b; border-radius: 12px; padding: 16px; margin: 8px 0; }
</style>
""", unsafe_allow_html=True)

NY_TZ = pytz.timezone("America/New_York")
CT_TZ = pytz.timezone("America/Chicago")
st_autorefresh(interval=30_000, key="refresh")

from modules.data_fetcher import (
    get_futures_ohlcv, get_session_range, get_mag7_snapshot, get_mag7_confluence_score
)
from modules.strategy import generate_signal, get_asia_window, get_hunt_window
from modules.alerts import send_engine_alert, test_alert
from modules.agent import get_agent_reply

@st.cache_data(ttl=20)
def load_nq():
    return get_futures_ohlcv("NQ=F", period="5d", interval="5m")

@st.cache_data(ttl=60)
def load_mag7():
    return get_mag7_snapshot()

def build_ctx(df, mag7):
    mag_conf = get_mag7_confluence_score(mag7)
    nq_price = float(df.iloc[-1]["Close"]) if not df.empty else None
    rh = rl = o8 = None
    bias = "UNKNOWN"
    sig = {"action": "NONE", "confidence": 0, "reason": "No data", "bias": bias}
    if not df.empty:
        rh, rl, o8 = get_session_range(df, 20, 0, 0, 0)
        if o8 and nq_price:
            bias = "PREMIUM" if nq_price > o8 else "DISCOUNT"
        sig = generate_signal(df, o8, rh, rl, session="ASIA")
        sig["bias"] = bias
    return {
        "nq_price": nq_price, "session_bias": bias, "range_high": rh, "range_low": rl,
        "open_8pm": o8, "mag7_label": mag_conf["label"], "mag7_bullish": mag_conf.get("bullish", 0),
        "mag7_total": mag_conf.get("total", 7), "asia_active": get_asia_window(),
        "hunt_active": get_hunt_window(), "last_signal": sig, "mag_conf": mag_conf,
    }

def verdict(ctx):
    sig = ctx["last_signal"] or {}
    action, conf = sig.get("action", "NONE"), sig.get("confidence", 0)
    bias, asia, hunt, mag = ctx["session_bias"], ctx["asia_active"], ctx["hunt_active"], ctx["mag7_label"]
    if not asia and not hunt:
        if bias == "DISCOUNT" and "BULLISH" in mag:
            return "WAIT", f"Outside Asia window. Lean long (Discount + {mag}). Wait for 8PM ET open or NY session.", conf or 40
        if bias == "PREMIUM" and "BEARISH" in mag:
            return "WAIT", f"Outside Asia window. Lean short (Premium + {mag}). Wait for setup confirmation.", conf or 40
        return "WAIT", f"Outside active windows. Bias is {bias}, Mag7 {mag}. No forced trade.", conf or 20
    if action == "LONG" and conf >= 65:
        return "LONG", sig.get("reason", "Time model long"), conf
    if action == "SHORT" and conf >= 65:
        return "SHORT", sig.get("reason", "Time model short"), conf
    if bias == "DISCOUNT":
        return "WAIT", "In discount — looking for long confirmation (sweep/CISD).", max(conf, 45)
    if bias == "PREMIUM":
        return "WAIT", "In premium — looking for short confirmation (sweep/CISD).", max(conf, 45)
    return "WAIT", "No clear setup. Stand aside.", conf

page = st.sidebar.radio("Navigate", ["⚡ Trade Desk", "🤖 Engine", "🧠 AI Agent", "📊 Mag7", "🔔 Alerts"], label_visibility="collapsed")
now_ny, now_ct = datetime.now(NY_TZ), datetime.now(CT_TZ)
st.sidebar.caption(f"NY {now_ny.strftime('%H:%M')} · CT {now_ct.strftime('%H:%M')}")

df, mag7 = load_nq(), load_mag7()
ctx = build_ctx(df, mag7)
action, reason, conf = verdict(ctx)

if page == "⚡ Trade Desk":
    st.markdown("### ⚡ Futures Cheat Code")
    st.caption("What to do right now")
    if action == "LONG":
        st.markdown(f'<div class="action-long"><h2 style="margin:0;color:#00c853;">▲ LONG</h2><p style="margin:8px 0 0 0;">{reason}</p><p style="margin:4px 0 0 0;font-size:0.85rem;">Confidence {conf}%</p></div>', unsafe_allow_html=True)
    elif action == "SHORT":
        st.markdown(f'<div class="action-short"><h2 style="margin:0;color:#ff5252;">▼ SHORT</h2><p style="margin:8px 0 0 0;">{reason}</p><p style="margin:4px 0 0 0;font-size:0.85rem;">Confidence {conf}%</p></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="action-wait"><h2 style="margin:0;color:#9aa0a6;">■ WAIT</h2><p style="margin:8px 0 0 0;">{reason}</p></div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("NQ", f"{ctx['nq_price']:,.2f}" if ctx["nq_price"] else "—")
    c2.metric("Bias", ctx["session_bias"])
    c3.metric("Mag7", ctx["mag7_label"])

    st.markdown("#### Levels")
    o8, rh, rl, price = ctx["open_8pm"], ctx["range_high"], ctx["range_low"], ctx["nq_price"]
    if o8:
        dist = (price - o8) if price else 0
        st.write(f"**8PM Open:** {o8:,.2f}  ·  distance {dist:+.1f} pts")
    if rh and rl:
        st.write(f"**Asia range:** {rl:,.2f} — {rh:,.2f}")
        st.write(f"**Mid:** {(rh+rl)/2:,.2f}")
    st.write(f"**Windows:** Asia {'🟢' if ctx['asia_active'] else '⚫'}  ·  Hunt {'🟢' if ctx['hunt_active'] else '⚫'}")

    st.markdown("#### NQ (5m)")
    if not df.empty and len(df) > 5:
        plot_df = df.tail(120).copy()
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=plot_df.index, open=plot_df["Open"], high=plot_df["High"],
            low=plot_df["Low"], close=plot_df["Close"], name="NQ",
            increasing_line_color="#00c853", decreasing_line_color="#ff5252"))
        if o8:
            fig.add_hline(y=o8, line_dash="dash", line_color="#ffc107", annotation_text="8PM Open", annotation_position="top left")
        if rh:
            fig.add_hline(y=rh, line_dash="dot", line_color="#5c6bc0", annotation_text="Range High")
        if rl:
            fig.add_hline(y=rl, line_dash="dot", line_color="#5c6bc0", annotation_text="Range Low")
        fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="#0b0e14",
            plot_bgcolor="#0b0e14", font_color="#e8eaed", xaxis_rangeslider_visible=False,
            xaxis=dict(gridcolor="#1f2430"), yaxis=dict(gridcolor="#1f2430", side="right"), showlegend=False)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.warning("No NQ data — refresh shortly.")

elif page == "🤖 Engine":
    st.markdown("### 🤖 Paper Engine")
    st.caption("Trades itself · $3k eval target · $2k max loss")
    try:
        from modules.paper_engine import (
            init_engine_db, get_engine_state, get_open_paper_trade, get_closed_paper_trades,
            compute_engine_stats, engine_decide_and_act, reset_engine, get_dynamic_risk_usd,
            get_phase, MAX_DRAWDOWN_USD, STARTING_EQUITY, PROFIT_TARGET)
        init_engine_db()
        result = engine_decide_and_act(ctx, send_alert_fn=send_engine_alert)
        state = get_engine_state()
        stats = compute_engine_stats()
        open_pos = get_open_paper_trade()
        phase = get_phase(state.get("equity", STARTING_EQUITY))
        profit = state.get("equity", STARTING_EQUITY) - STARTING_EQUITY
        progress = min(100, max(0, profit / PROFIT_TARGET * 100))
        risk_info = get_dynamic_risk_usd(state.get("equity", STARTING_EQUITY), state.get("drawdown_usd", 0),
            confluence=ctx["last_signal"].get("confidence", 75))
        st.markdown(f"**{state.get('status')}** · Phase **{phase}**")
        st.progress(progress / 100, text=f"${profit:,.0f} / ${PROFIT_TARGET:,.0f} to pass eval")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Equity", f"${state.get('equity', 0):,.0f}")
        c2.metric("Drawdown", f"${state.get('drawdown_usd', 0):,.0f}")
        c3.metric("Risk/trade", f"${risk_info['risk_usd']}")
        c4.metric("Open", state.get("open_direction") or "Flat")
        if result.get("action") in ("ENTERED", "EXITED"):
            st.success(f"Engine {result['action']}: {result.get('direction')} @ {result.get('entry', result.get('exit'))}")
        elif result.get("action") == "HOLDING":
            st.info(f"Holding {result.get('direction')} from {result.get('entry')}")
        elif result.get("action") == "HALTED":
            st.error(result.get("reason"))
        if open_pos:
            st.write(f"**Position:** {open_pos['direction']} @ {open_pos['entry_price']} · SL {open_pos['stop_price']} · TP {open_pos['target_price']}")
        st.markdown("#### Self-score")
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Trades", stats["total_trades"])
        s2.metric("Win %", f"{stats['win_rate']}%")
        s3.metric("Avg pts", stats["avg_points"])
        s4.metric("PnL", f"${stats['total_pnl_usd']}")
        closed = get_closed_paper_trades(20)
        if closed:
            st.dataframe(pd.DataFrame(closed)[["direction", "entry_price", "exit_price", "points", "pnl_usd", "exit_reason"]],
                         use_container_width=True, hide_index=True)
        if st.button("Reset engine ($50k)"):
            reset_engine(confirm=True)
            st.rerun()
    except Exception as e:
        st.error(f"Engine: {e}")

elif page == "🧠 AI Agent":
    st.markdown("### 🧠 Ask the engine")
    if "msgs" not in st.session_state:
        st.session_state.msgs = [{"role": "assistant", "content": "Ask: bias, long or short, levels, risk, Asia status."}]
    for m in st.session_state.msgs:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
    if q := st.chat_input("Ask…"):
        st.session_state.msgs.append({"role": "user", "content": q})
        reply = get_agent_reply(q, ctx, st.session_state.msgs[:-1])
        st.session_state.msgs.append({"role": "assistant", "content": reply})
        st.rerun()

elif page == "📊 Mag7":
    st.markdown("### Mag7 confluence")
    conf = ctx["mag_conf"]
    st.metric("Read", conf["label"])
    st.write(f"{conf.get('bullish', 0)} bullish / {conf.get('total', 0)} names")
    if not mag7.empty:
        st.dataframe(mag7, use_container_width=True, hide_index=True)

elif page == "🔔 Alerts":
    st.markdown("### Phone alerts")
    st.write("Add to **Streamlit Secrets**:")
    st.code('TELEGRAM_BOT_TOKEN = "..."\nTELEGRAM_CHAT_ID = "..."', language="toml")
    if st.button("Test alert"):
        st.success("Sent") if test_alert() else st.error("Secrets not set or Telegram failed")

st.sidebar.markdown("---")
st.sidebar.caption("Data: Yahoo NQ=F · refresh 30s")
