"""Futures Cheat Code — Autonomous Paper Engine"""
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import pytz
from dotenv import load_dotenv
import pandas as pd
load_dotenv()

st.set_page_config(page_title="Futures Cheat Code", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")
st.markdown("<style>.stApp{background-color:#0e1117;}</style>", unsafe_allow_html=True)
NY_TZ = pytz.timezone("America/New_York")
CT_TZ = pytz.timezone("America/Chicago")
st_autorefresh(interval=30*1000, key="data_refresh")

st.sidebar.title("⚡ Futures Cheat Code")
page = st.sidebar.radio("Pages", [
    "🏠 Dashboard", "🌏 Asia Session", "🗽 New York Session",
    "📡 Social Alpha", "🤖 Futures AI Agent", "📈 Performance / Data",
    "📊 Mag 7 Confluence", "🔔 Alerts & Settings"
], label_visibility="collapsed")
st.sidebar.markdown("---")
st.sidebar.write(f"**NY:** {datetime.now(NY_TZ).strftime('%H:%M:%S')}")
st.sidebar.write(f"**CT:** {datetime.now(CT_TZ).strftime('%H:%M:%S')}")

from modules.data_fetcher import get_futures_ohlcv, get_session_range, get_mag7_snapshot, get_mag7_confluence_score
from modules.strategy import generate_signal, get_asia_window, get_hunt_window
from modules.alerts import send_alert, test_alert, send_engine_alert
from modules.social_alpha import parse_tweet, score_confluence, DEFAULT_WATCHLIST, DEMO_SIGNALS
from modules.agent import get_agent_reply

@st.cache_data(ttl=20)
def load_nq():
    return get_futures_ohlcv("NQ=F", period="5d", interval="5m")

@st.cache_data(ttl=60)
def load_mag7():
    return get_mag7_snapshot()

if page == "🏠 Dashboard":
    st.title("⚡ Futures Cheat Code")
    st.caption("Autonomous paper engine · Eval → Funded · Phone alerts")
    df, mag7 = load_nq(), load_mag7()
    conf = get_mag7_confluence_score(mag7)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("NQ Last", f"{df.iloc[-1]['Close']:,.2f}" if not df.empty else "—")
    c2.metric("Mag7", conf["label"])
    c3.metric("Asia Window", "ACTIVE" if get_asia_window() else "Closed")
    c4.metric("Hunt Window", "NOW" if get_hunt_window() else "—")
    if not df.empty:
        rh, rl, o8 = get_session_range(df, 20, 0, 0, 0)
        sig = generate_signal(df, o8, rh, rl, session="ASIA")
        st.subheader(f"Bias: {sig['bias']} | Signal: {sig['action']} ({sig['confidence']}%)")
        st.caption(sig["reason"])
        st.line_chart(df.tail(120)["Close"], height=300)

elif page == "📈 Performance / Data":
    st.title("🤖 Autonomous Paper Engine")
    st.caption("Eval target $3k · Max loss $2k · Confluence-scaled risk")
    try:
        from modules.paper_engine import (
            init_engine_db, get_engine_state, get_open_paper_trade, get_closed_paper_trades,
            compute_engine_stats, engine_decide_and_act, reset_engine, get_dynamic_risk_usd,
            get_phase, MAX_DRAWDOWN_USD, STARTING_EQUITY, PROFIT_TARGET)
        init_engine_db()
        df, mag7 = load_nq(), load_mag7()
        mag_conf = get_mag7_confluence_score(mag7)
        nq_price = float(df.iloc[-1]["Close"]) if not df.empty else None
        rh = rl = o8 = None; session_bias = "UNKNOWN"; last_signal = None
        if not df.empty:
            rh, rl, o8 = get_session_range(df, 20, 0, 0, 0)
            if o8 and nq_price: session_bias = "PREMIUM" if nq_price > o8 else "DISCOUNT"
            last_signal = generate_signal(df, o8, rh, rl, session="ASIA")
        market_ctx = {"nq_price": nq_price, "session_bias": session_bias, "range_high": rh, "range_low": rl,
            "open_8pm": o8, "mag7_label": mag_conf["label"], "mag7_bullish": mag_conf["bullish"],
            "mag7_total": mag_conf["total"], "asia_active": get_asia_window(), "hunt_active": get_hunt_window(),
            "last_signal": last_signal}
        result = engine_decide_and_act(market_ctx, send_alert_fn=send_engine_alert)
        state, open_pos, stats = get_engine_state(), get_open_paper_trade(), compute_engine_stats()
        phase = get_phase(state.get("equity", STARTING_EQUITY))
        profit = state.get("equity", STARTING_EQUITY) - STARTING_EQUITY
        progress = min(100, max(0, profit / PROFIT_TARGET * 100))
        status_color = "🟢" if state.get("status") == "ACTIVE" else "🔴"
        st.markdown(f"### {status_color} **{state.get('status')}** | Phase: **{phase}**")
        st.progress(progress/100, text=f"Profit: ${profit:,.0f} / ${PROFIT_TARGET:,.0f}")
        risk_info = get_dynamic_risk_usd(state.get("equity", STARTING_EQUITY), state.get("drawdown_usd", 0),
            confluence=last_signal.get("confidence", 75) if last_signal else 75)
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Equity", f"${state.get('equity',0):,.0f}")
        c2.metric("Peak", f"${state.get('peak_equity',0):,.0f}")
        c3.metric("Drawdown", f"${state.get('drawdown_usd',0):,.0f}")
        c4.metric("Position", state.get("open_direction") or "Flat")
        c5.metric("Risk/Trade", f"${risk_info['risk_usd']}")
        if result.get("action") in ("ENTERED", "EXITED"): st.success(f"Engine {result['action']}: {result}")
        elif result.get("action") == "HALTED": st.error(result.get("reason"))
        elif result.get("action") == "HOLDING": st.info(f"Holding {result.get('direction')} from {result.get('entry')}")
        st.subheader("Engine Self-Score")
        s1,s2,s3,s4,s5 = st.columns(5)
        s1.metric("Trades", stats["total_trades"]); s2.metric("Win Rate", f"{stats['win_rate']}%")
        s3.metric("Avg Points", stats["avg_points"]); s4.metric("PF", stats["profit_factor"])
        s5.metric("Total PnL", f"${stats['total_pnl_usd']}")
        closed = get_closed_paper_trades(30)
        if closed: st.dataframe(pd.DataFrame(closed), use_container_width=True)
        if st.button("Reset Engine"): reset_engine(confirm=True); st.rerun()
    except Exception as e:
        st.error(f"Engine error: {e}")

elif page == "🤖 Futures AI Agent":
    st.title("🤖 Futures AI Agent")
    df, mag7 = load_nq(), load_mag7()
    mag_conf = get_mag7_confluence_score(mag7)
    nq_price = float(df.iloc[-1]["Close"]) if not df.empty else None
    rh = rl = o8 = None; session_bias = "UNKNOWN"; last_signal = None
    if not df.empty:
        rh, rl, o8 = get_session_range(df, 20, 0, 0, 0)
        if o8 and nq_price: session_bias = "PREMIUM" if nq_price > o8 else "DISCOUNT"
        last_signal = generate_signal(df, o8, rh, rl, session="ASIA")
    market_ctx = {"nq_price": nq_price, "session_bias": session_bias, "range_high": rh, "range_low": rl,
        "open_8pm": o8, "mag7_label": mag_conf["label"], "mag7_bullish": mag_conf["bullish"],
        "mag7_total": mag_conf["total"], "asia_active": get_asia_window(), "hunt_active": get_hunt_window(),
        "last_signal": last_signal}
    if "agent_messages" not in st.session_state:
        st.session_state.agent_messages = [{"role": "assistant", "content": "Ask me anything about the current NQ setup."}]
    for msg in st.session_state.agent_messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
    if prompt := st.chat_input("Ask the Futures AI Agent..."):
        st.session_state.agent_messages.append({"role": "user", "content": prompt})
        reply = get_agent_reply(prompt, market_ctx, st.session_state.agent_messages[:-1])
        st.session_state.agent_messages.append({"role": "assistant", "content": reply})
        st.rerun()

elif page == "📡 Social Alpha":
    st.title("📡 Social Alpha")
    pasted = st.text_area("Paste tweet text")
    author = st.text_input("Author", value="manual")
    if st.button("Parse") and pasted.strip():
        df, mag7 = load_nq(), load_mag7()
        mag_conf = get_mag7_confluence_score(mag7)
        bias = "UNKNOWN"
        if not df.empty:
            _, _, o8 = get_session_range(df, 20, 0, 0, 0)
            if o8: bias = "PREMIUM" if df.iloc[-1]["Close"] > o8 else "DISCOUNT"
        parsed = parse_tweet(pasted, author)
        conf = score_confluence(parsed, bias, mag_conf["label"])
        st.write(parsed); st.write(conf)

elif page == "📊 Mag 7 Confluence":
    st.title("📊 Mag 7")
    mag7 = load_mag7()
    conf = get_mag7_confluence_score(mag7)
    st.metric("Score", conf["label"])
    if not mag7.empty: st.dataframe(mag7, use_container_width=True)

elif page == "🔔 Alerts & Settings":
    st.title("🔔 Alerts")
    st.write("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in Streamlit Secrets.")
    if st.button("Send Test Alert"):
        st.success("Sent") if test_alert() else st.error("Configure secrets first")
else:
    st.title(page)
    st.info("Open **Performance / Data** for the autonomous paper engine.")

st.sidebar.markdown("---")
st.sidebar.caption("Futures Cheat Code · Autonomous Edition")
