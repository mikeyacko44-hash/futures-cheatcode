"""Futures Cheat Code — Trade Desk + Crypto ranks + liquidity levels"""
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import pytz
from dotenv import load_dotenv
import pandas as pd
import plotly.graph_objects as go
import os

load_dotenv()

st.set_page_config(page_title="Futures Cheat Code", page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }
.stApp { background: #0a0c10; color: #e7e9ea; }
.block-container { padding: 0.75rem 1rem 2rem; max-width: 760px; margin: 0 auto; }
#MainMenu, footer, header { visibility: hidden; }
.hero { border-radius: 16px; padding: 20px 18px; margin: 0 0 14px 0; border: 1px solid transparent; }
.hero-long  { background: linear-gradient(145deg,#0a1f14,#0d2a1a); border-color: #00c85355; }
.hero-short { background: linear-gradient(145deg,#1f0a0a,#2a0d0d); border-color: #ff525255; }
.hero-wait  { background: linear-gradient(145deg,#12151c,#1a1e28); border-color: #3a415055; }
.hero h1 { margin: 0; font-size: 1.75rem; font-weight: 700; }
.hero p  { margin: 8px 0 0; opacity: 0.88; font-size: 0.95rem; line-height: 1.4; }
.hero .meta { margin-top: 10px; font-size: 0.8rem; opacity: 0.65; }
.kpi-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 14px; }
.kpi { background: #12151c; border: 1px solid #1e2430; border-radius: 12px; padding: 12px 10px; text-align: center; }
.kpi .label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.04em; color: #8b93a7; margin-bottom: 4px; }
.kpi .value { font-size: 1.05rem; font-weight: 600; color: #f0f2f5; }
.kpi .sub   { font-size: 0.72rem; color: #8b93a7; margin-top: 2px; }
.levels { background: #12151c; border: 1px solid #1e2430; border-radius: 12px; padding: 4px 14px; margin-bottom: 14px; }
.lvl { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #1a1f2a; font-size: 0.9rem; }
.lvl:last-child { border-bottom: none; }
.lvl .k { color: #8b93a7; }
.lvl .v { font-weight: 600; color: #e7e9ea; font-variant-numeric: tabular-nums; }
.sec { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.06em; color: #8b93a7; margin: 16px 0 8px; font-weight: 600; }
.stTabs [data-baseweb="tab-list"] { gap: 4px; background: #12151c; border-radius: 12px; padding: 4px; border: 1px solid #1e2430; }
.stTabs [data-baseweb="tab"] { border-radius: 9px; padding: 8px 12px; color: #8b93a7; font-weight: 500; }
.stTabs [aria-selected="true"] { background: #1e2430 !important; color: #f0f2f5 !important; }
.chip { display: inline-block; padding: 3px 10px; border-radius: 99px; font-size: 0.72rem; font-weight: 600; margin-right: 6px; }
.chip-on  { background: #00c85322; color: #00c853; border: 1px solid #00c85344; }
.chip-off { background: #ffffff08; color: #8b93a7; border: 1px solid #ffffff12; }
</style>
""", unsafe_allow_html=True)

NY = pytz.timezone("America/New_York")
CT = pytz.timezone("America/Chicago")
st_autorefresh(interval=30_000, key="tick")

from modules.data_fetcher import get_futures_ohlcv, get_session_range, get_mag7_snapshot, get_mag7_confluence_score
from modules.strategy import generate_signal, get_asia_window, get_hunt_window
from modules.alerts import send_engine_alert, test_alert
from modules.agent import get_agent_reply
from modules.crypto_rank import fetch_markets, fear_greed, top_longs, top_shorts
from modules.liquidity_levels import skylit_heatmap, extract_key_nodes, qqq_to_nq_levels, fallback_structure_levels

@st.cache_data(ttl=25, show_spinner=False)
def load_nq():
    return get_futures_ohlcv("NQ=F", period="5d", interval="5m")

@st.cache_data(ttl=90, show_spinner=False)
def load_mag7():
    return get_mag7_snapshot()

@st.cache_data(ttl=120, show_spinner=False)
def load_crypto():
    return fetch_markets(per_page=80)

@st.cache_data(ttl=300, show_spinner=False)
def load_fng():
    return fear_greed()

@st.cache_data(ttl=60, show_spinner=False)
def load_gex_nodes(nq_price):
    raw = skylit_heatmap("QQQ", "gamma")
    nodes = extract_key_nodes(raw, max_nodes=6) if raw else []
    qqq_spot = None
    if raw:
        try:
            qqq_spot = raw.get("data", {}).get("symbols", [{}])[0].get("spot")
        except Exception:
            pass
    if nodes and nq_price and qqq_spot:
        return qqq_to_nq_levels(nodes, nq_price, qqq_spot), True
    return nodes, bool(raw)

def build_ctx(df, mag7):
    mag = get_mag7_confluence_score(mag7)
    price = float(df.iloc[-1]["Close"]) if len(df) else None
    rh = rl = o8 = None
    bias = "UNKNOWN"
    sig = {"action": "NONE", "confidence": 0, "reason": "Waiting on data", "bias": bias}
    if len(df):
        rh, rl, o8 = get_session_range(df, 20, 0, 0, 0)
        if o8 and price is not None:
            bias = "PREMIUM" if price > o8 else "DISCOUNT"
        sig = generate_signal(df, o8, rh, rl, session="ASIA")
        sig["bias"] = bias
    return {
        "price": price, "bias": bias, "rh": rh, "rl": rl, "o8": o8, "mag": mag,
        "asia": get_asia_window(), "hunt": get_hunt_window(), "sig": sig,
        "nq_price": price, "session_bias": bias, "range_high": rh, "range_low": rl,
        "open_8pm": o8, "mag7_label": mag["label"], "mag7_bullish": mag.get("bullish", 0),
        "mag7_total": mag.get("total", 7), "asia_active": get_asia_window(),
        "hunt_active": get_hunt_window(), "last_signal": sig, "mag_conf": mag,
    }

def verdict(ctx):
    s = ctx["sig"]
    a, c = s.get("action", "NONE"), s.get("confidence", 0)
    bias, asia, hunt, mag = ctx["bias"], ctx["asia"], ctx["hunt"], ctx["mag"]["label"]
    if a == "LONG" and c >= 65: return "LONG", s.get("reason", "Model long"), c
    if a == "SHORT" and c >= 65: return "SHORT", s.get("reason", "Model short"), c
    if not asia and not hunt:
        if bias == "DISCOUNT" and "BULLISH" in mag:
            return "WAIT", f"Lean long — Discount + {mag}. Best after 8:00 PM ET Asia open.", max(c, 40)
        if bias == "PREMIUM" and "BEARISH" in mag:
            return "WAIT", f"Lean short — Premium + {mag}. Wait for confirmation.", max(c, 40)
        return "WAIT", f"Outside active windows. Bias {bias} · Mag7 {mag}. No forced trade.", max(c, 25)
    if bias == "DISCOUNT": return "WAIT", "In discount — watching for long confirmation (sweep / CISD).", max(c, 48)
    if bias == "PREMIUM": return "WAIT", "In premium — watching for short confirmation (sweep / CISD).", max(c, 48)
    return "WAIT", "No clear setup. Stand aside.", c

def candle_fig(df, o8, rh, rl, extra_levels=None):
    d = df.tail(100).copy()
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=d.index, open=d["Open"], high=d["High"], low=d["Low"], close=d["Close"],
        increasing_line_color="#00c853", increasing_fillcolor="#00c853",
        decreasing_line_color="#ff5252", decreasing_fillcolor="#ff5252", whiskerwidth=0.6, name="NQ"))
    colors = {"structure": "#ffc107", "king": "#ffeb3b", "gatekeeper": "#7c8aff", "pika": "#69f0ae", "barney": "#e040fb", "significant": "#80cbc4"}
    if o8: fig.add_hline(y=o8, line_dash="dash", line_color="#ffc107", line_width=1.2, annotation_text="8PM", annotation_position="top left", annotation_font_color="#ffc107", annotation_font_size=11)
    if rh: fig.add_hline(y=rh, line_dash="dot", line_color="#7c8aff", line_width=1, annotation_text="High", annotation_font_size=10, annotation_font_color="#7c8aff")
    if rl: fig.add_hline(y=rl, line_dash="dot", line_color="#7c8aff", line_width=1, annotation_text="Low", annotation_font_size=10, annotation_font_color="#7c8aff")
    if extra_levels:
        for lv in extra_levels:
            node = (lv.get("node") or "significant").lower()
            col = colors.get(node, "#80cbc4")
            fig.add_hline(y=lv["level"], line_dash="dashdot", line_color=col, line_width=1, annotation_text=lv.get("label", "")[:12], annotation_font_size=9, annotation_font_color=col)
    fig.update_layout(height=340, margin=dict(l=0, r=8, t=8, b=0), paper_bgcolor="#0a0c10", plot_bgcolor="#0a0c10",
        font=dict(color="#c5c9d3", family="Inter", size=11), xaxis=dict(showgrid=False, rangeslider_visible=False, color="#5c6578"),
        yaxis=dict(showgrid=True, gridcolor="#151922", side="right", color="#5c6578", tickfont=dict(size=10)), showlegend=False, dragmode=False)
    return fig

with st.spinner(""):
    df = load_nq()
    mag7 = load_mag7()
ctx = build_ctx(df, mag7)
action, reason, conf = verdict(ctx)
now_ny, now_ct = datetime.now(NY), datetime.now(CT)
gex_nodes, has_skylit = load_gex_nodes(ctx["price"]) if ctx["price"] else ([], False)
chart_extra = gex_nodes if gex_nodes else []

h1, h2 = st.columns([3, 1])
with h1: st.markdown("### ⚡ Futures Cheat Code")
with h2: st.caption(f"NY {now_ny.strftime('%H:%M')} · CT {now_ct.strftime('%H:%M')}")

tab_desk, tab_crypto, tab_engine, tab_ai, tab_mag, tab_alert = st.tabs(["Trade Desk", "Crypto", "Engine", "AI", "Mag7", "Alerts"])

with tab_desk:
    if action == "LONG":
        st.markdown(f"""<div class="hero hero-long"><h1 style="color:#00c853">▲ LONG</h1><p>{reason}</p><div class="meta">Confidence {conf}% · Auto-refreshes every 30s</div></div>""", unsafe_allow_html=True)
    elif action == "SHORT":
        st.markdown(f"""<div class="hero hero-short"><h1 style="color:#ff5252">▼ SHORT</h1><p>{reason}</p><div class="meta">Confidence {conf}% · Auto-refreshes every 30s</div></div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""<div class="hero hero-wait"><h1 style="color:#9aa0a6">■ WAIT</h1><p>{reason}</p><div class="meta">Confidence {conf}% · No forced trade</div></div>""", unsafe_allow_html=True)
    px_ = f"{ctx['price']:,.2f}" if ctx["price"] else "—"
    dist = f"{(ctx['price']-ctx['o8']):+.1f} pts from open" if ctx["price"] and ctx["o8"] else ""
    st.markdown(f"""<div class="kpi-grid"><div class="kpi"><div class="label">NQ</div><div class="value">{px_}</div><div class="sub">{dist}</div></div><div class="kpi"><div class="label">Bias</div><div class="value">{ctx['bias']}</div><div class="sub">vs 8PM open</div></div><div class="kpi"><div class="label">Mag7</div><div class="value">{ctx['mag']['label'].replace('STRONG ','')}</div><div class="sub">{ctx['mag'].get('bullish',0)}/{ctx['mag'].get('total',7)} bull</div></div></div>""", unsafe_allow_html=True)
    asia_chip = '<span class="chip chip-on">Asia ON</span>' if ctx["asia"] else '<span class="chip chip-off">Asia off</span>'
    hunt_chip = '<span class="chip chip-on">Hunt ON</span>' if ctx["hunt"] else '<span class="chip chip-off">Hunt off</span>'
    gex_chip = '<span class="chip chip-on">GEX live</span>' if has_skylit else '<span class="chip chip-off">GEX needs Skylit key</span>'
    st.markdown(asia_chip + hunt_chip + gex_chip, unsafe_allow_html=True)
    st.markdown('<div class="sec">Key levels</div>', unsafe_allow_html=True)
    rows = []
    if ctx["o8"]: rows.append(("8PM Open", f"{ctx['o8']:,.2f}"))
    if ctx["rh"] and ctx["rl"]:
        rows.append(("Asia High", f"{ctx['rh']:,.2f}")); rows.append(("Asia Low", f"{ctx['rl']:,.2f}")); rows.append(("Range Mid", f"{(ctx['rh']+ctx['rl'])/2:,.2f}"))
    for n in (gex_nodes or [])[:4]:
        rows.append((n.get("label", "GEX"), f"{n['level']:,.2f}"))
    if rows:
        html = '<div class="levels">' + "".join(f'<div class="lvl"><span class="k">{k}</span><span class="v">{v}</span></div>' for k,v in rows) + "</div>"
        st.markdown(html, unsafe_allow_html=True)
    st.markdown('<div class="sec">NQ · 5 minute · liquidity overlays</div>', unsafe_allow_html=True)
    if len(df) > 5:
        st.plotly_chart(candle_fig(df, ctx["o8"], ctx["rh"], ctx["rl"], extra_levels=chart_extra), use_container_width=True, config={"displayModeBar": False})
        if not has_skylit:
            st.caption("Add SKYLIT_API_KEY in Secrets for live King/Gatekeeper gamma nodes (QQQ→NQ scaled).")
    else:
        st.info("Loading NQ candles…")

with tab_crypto:
    st.markdown('<div class="sec">Crypto ranking · where to long / short</div>', unsafe_allow_html=True)
    fng = load_fng()
    c1, c2 = st.columns(2)
    c1.metric("Fear & Greed", f"{fng.get('value', '—')}")
    c2.metric("Sentiment", fng.get("label", "—"))
    crypto = load_crypto()
    if crypto.empty:
        st.warning("CoinGecko rate limit or offline — try again in a minute.")
    else:
        st.caption(f"Top {len(crypto)} by market cap · scored on 1h/24h/7d momentum")
        view = st.radio("View", ["Best longs", "Best shorts", "Full table"], horizontal=True, label_visibility="collapsed")
        if view == "Best longs":
            show = top_longs(crypto, 20); st.markdown("**Highest momentum — long candidates**")
        elif view == "Best shorts":
            show = top_shorts(crypto, 20); st.markdown("**Weakest momentum — short candidates**")
        else:
            show = crypto
        display_cols = [c for c in ["long_rank" if view != "Best shorts" else "short_rank", "symbol", "name", "price", "1h%", "24h%", "7d%", "score", "bias", "action"] if c in show.columns]
        st.dataframe(show[display_cols].rename(columns={"long_rank": "#", "short_rank": "#"}), use_container_width=True, hide_index=True, height=420)

with tab_engine:
    st.markdown('<div class="sec">Autonomous paper engine</div>', unsafe_allow_html=True)
    st.caption("Eval $3,000 target · $2,000 max loss · risk scales with confluence")
    try:
        from modules.paper_engine import (init_engine_db, get_engine_state, get_open_paper_trade, get_closed_paper_trades, compute_engine_stats, engine_decide_and_act, reset_engine, get_dynamic_risk_usd, get_phase, STARTING_EQUITY, PROFIT_TARGET)
        init_engine_db()
        result = engine_decide_and_act(ctx, send_alert_fn=send_engine_alert)
        state = get_engine_state(); stats = compute_engine_stats(); open_pos = get_open_paper_trade()
        phase = get_phase(state.get("equity", STARTING_EQUITY))
        profit = state.get("equity", STARTING_EQUITY) - STARTING_EQUITY
        prog = min(100, max(0, profit / PROFIT_TARGET * 100))
        risk = get_dynamic_risk_usd(state.get("equity", STARTING_EQUITY), state.get("drawdown_usd", 0), confluence=ctx["sig"].get("confidence", 75))
        st.markdown(f"**{state.get('status')}** · Phase **{phase}**")
        st.progress(prog / 100.0, text=f"${profit:,.0f} / ${PROFIT_TARGET:,.0f} eval target")
        a,b,c,d = st.columns(4)
        a.metric("Equity", f"${state.get('equity', 0):,.0f}"); b.metric("Drawdown", f"${state.get('drawdown_usd', 0):,.0f}")
        c.metric("Risk / trade", f"${risk['risk_usd']}"); d.metric("Position", state.get("open_direction") or "Flat")
        if result.get("action") in ("ENTERED", "EXITED"): st.success(f"{result['action']}: {result.get('direction')} · {result.get('entry', result.get('exit'))}")
        elif result.get("action") == "HOLDING": st.info(f"Holding {result.get('direction')} from {result.get('entry')}")
        elif result.get("action") == "HALTED": st.error(result.get("reason", "Halted"))
        if open_pos: st.write(f"**Live:** {open_pos['direction']} @ {open_pos['entry_price']} · SL {open_pos['stop_price']} · TP {open_pos['target_price']}")
        s1,s2,s3,s4 = st.columns(4)
        s1.metric("Trades", stats["total_trades"]); s2.metric("Win rate", f"{stats['win_rate']}%")
        s3.metric("Avg points", stats["avg_points"]); s4.metric("Total PnL", f"${stats['total_pnl_usd']}")
        closed = get_closed_paper_trades(15)
        if closed: st.dataframe(pd.DataFrame(closed)[["direction", "entry_price", "exit_price", "points", "pnl_usd", "exit_reason"]], use_container_width=True, hide_index=True)
        if st.button("Reset engine to $50k"):
            reset_engine(confirm=True); st.rerun()
    except Exception as e:
        st.error(f"Engine unavailable: {e}")

with tab_ai:
    st.markdown('<div class="sec">Ask anything</div>', unsafe_allow_html=True)
    if "chat" not in st.session_state:
        st.session_state.chat = [{"role": "assistant", "content": "Ask me: long or short? levels? risk size? Asia status? crypto bias?"}]
    for m in st.session_state.chat:
        with st.chat_message(m["role"]): st.markdown(m["content"])
    if q := st.chat_input("Ask the desk…"):
        st.session_state.chat.append({"role": "user", "content": q})
        ans = get_agent_reply(q, ctx, st.session_state.chat[:-1])
        st.session_state.chat.append({"role": "assistant", "content": ans}); st.rerun()

with tab_mag:
    st.markdown('<div class="sec">Mag7 confluence</div>', unsafe_allow_html=True)
    m = ctx["mag"]
    st.metric("Read", m["label"]); st.caption(f"{m.get('bullish', 0)} of {m.get('total', 7)} bullish today")
    if not mag7.empty: st.dataframe(mag7, use_container_width=True, hide_index=True)

with tab_alert:
    st.markdown('<div class="sec">Phone alerts + API keys</div>', unsafe_allow_html=True)
    st.write("**Streamlit → Manage app → Settings → Secrets**")
    st.code('TELEGRAM_BOT_TOKEN = "..."\nTELEGRAM_CHAT_ID = "..."\nSKYLIT_API_KEY = "sk_live_..."  # optional GEX heatmaps', language="toml")
    st.caption("Skylit: new accounts get ~5k credits. QQQ gamma nodes scale onto NQ chart. True dark-pool needs paid feed (Unusual Whales).")
    if st.button("Send test alert"):
        ok = test_alert()
        st.success("Sent to Telegram") if ok else st.error("Not configured or failed")

st.caption("NQ · Yahoo · Crypto · CoinGecko · GEX · Skylit optional · Not financial advice")
