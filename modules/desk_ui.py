"""Futures Cheat Code — polished multi-tab desk"""
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import pytz
from dotenv import load_dotenv
import pandas as pd
import plotly.graph_objects as go

load_dotenv()
st.set_page_config(page_title="Futures Cheat Code", page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }
.stApp { background: #0a0c10; color: #e7e9ea; }
.block-container { padding: 0.6rem 0.9rem 2rem; max-width: 820px; margin: 0 auto; }
#MainMenu, footer, header { visibility: hidden; }
.hero { border-radius: 14px; padding: 18px 16px; margin: 0 0 12px 0; border: 1px solid transparent; }
.hero-long  { background: linear-gradient(145deg,#0a1f14,#0d2a1a); border-color: #00c85355; }
.hero-short { background: linear-gradient(145deg,#1f0a0a,#2a0d0d); border-color: #ff525255; }
.hero-wait  { background: linear-gradient(145deg,#12151c,#1a1e28); border-color: #3a415055; }
.hero h1 { margin: 0; font-size: 1.65rem; font-weight: 700; }
.hero p  { margin: 8px 0 0; opacity: 0.9; font-size: 0.92rem; line-height: 1.4; }
.hero .meta { margin-top: 8px; font-size: 0.78rem; opacity: 0.6; }
.kpi-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 12px; }
.kpi { background: #12151c; border: 1px solid #1e2430; border-radius: 12px; padding: 11px 10px; text-align: center; }
.kpi .label { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.04em; color: #8b93a7; margin-bottom: 3px; }
.kpi .value { font-size: 1.02rem; font-weight: 600; color: #f0f2f5; }
.kpi .sub   { font-size: 0.7rem; color: #8b93a7; margin-top: 2px; }
.levels { background: #12151c; border: 1px solid #1e2430; border-radius: 12px; padding: 2px 14px; margin-bottom: 12px; }
.lvl { display: flex; justify-content: space-between; align-items: center; padding: 9px 0; border-bottom: 1px solid #1a1f2a; font-size: 0.88rem; }
.lvl:last-child { border-bottom: none; }
.lvl .k { color: #8b93a7; }
.lvl .v { font-weight: 600; color: #e7e9ea; font-variant-numeric: tabular-nums; }
.sec { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; color: #8b93a7; margin: 14px 0 8px; font-weight: 600; }
.stTabs [data-baseweb="tab-list"] { gap: 3px; background: #12151c; border-radius: 12px; padding: 4px; border: 1px solid #1e2430; }
.stTabs [data-baseweb="tab"] { border-radius: 9px; padding: 8px 11px; color: #8b93a7; font-weight: 500; font-size: 0.85rem; }
.stTabs [aria-selected="true"] { background: #1e2430 !important; color: #f0f2f5 !important; }
.chip { display: inline-block; padding: 3px 9px; border-radius: 99px; font-size: 0.7rem; font-weight: 600; margin-right: 5px; margin-bottom: 4px; }
.chip-on  { background: #00c85322; color: #00c853; border: 1px solid #00c85344; }
.chip-off { background: #ffffff08; color: #8b93a7; border: 1px solid #ffffff12; }
.hint { font-size: 0.78rem; color: #8b93a7; line-height: 1.45; margin: 0 0 10px; }
.score-box { background: #12151c; border: 1px solid #1e2430; border-radius: 12px; padding: 12px 14px; margin-bottom: 12px; font-size: 0.82rem; color: #b0b6c3; line-height: 1.5; }
.score-box strong { color: #e7e9ea; }
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
from modules.liquidity_levels import load_gex_for_nq

def format_price(p) -> str:
    if p is None: return "—"
    try: p = float(p)
    except (TypeError, ValueError): return "—"
    if p >= 1000: return f"${p:,.0f}"
    if p >= 1: return f"${p:,.2f}"
    if p >= 0.01: return f"${p:.4f}"
    return f"${p:.6f}"

def format_mcap(m) -> str:
    try: m = float(m or 0)
    except (TypeError, ValueError): return "—"
    if m >= 1e12: return f"${m/1e12:.2f}T"
    if m >= 1e9: return f"${m/1e9:.1f}B"
    if m >= 1e6: return f"${m/1e6:.0f}M"
    return f"${m:,.0f}"

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
    fig.add_trace(go.Candlestick(
        x=d.index, open=d["Open"], high=d["High"], low=d["Low"], close=d["Close"],
        increasing_line_color="#00c853", increasing_fillcolor="#00c853",
        decreasing_line_color="#ff5252", decreasing_fillcolor="#ff5252", whiskerwidth=0.6, name="NQ"))
    colors = {"structure": "#ffc107", "king": "#ffeb3b", "gatekeeper": "#7c8aff", "pika": "#69f0ae", "barney": "#e040fb", "significant": "#80cbc4"}
    if o8:
        fig.add_hline(y=o8, line_dash="dash", line_color="#ffc107", line_width=1.2,
                      annotation_text="8PM", annotation_position="top left", annotation_font_color="#ffc107", annotation_font_size=11)
    if rh:
        fig.add_hline(y=rh, line_dash="dot", line_color="#7c8aff", line_width=1,
                      annotation_text="High", annotation_font_size=10, annotation_font_color="#7c8aff")
    if rl:
        fig.add_hline(y=rl, line_dash="dot", line_color="#7c8aff", line_width=1,
                      annotation_text="Low", annotation_font_size=10, annotation_font_color="#7c8aff")
    if extra_levels:
        for lv in extra_levels:
            node = (lv.get("node") or "significant").lower()
            col = colors.get(node, "#80cbc4")
            fig.add_hline(y=lv["level"], line_dash="dashdot", line_color=col, line_width=1,
                          annotation_text=lv.get("label", "")[:12], annotation_font_size=9, annotation_font_color=col)
    fig.update_layout(height=340, margin=dict(l=0, r=8, t=8, b=0), paper_bgcolor="#0a0c10", plot_bgcolor="#0a0c10",
        font=dict(color="#c5c9d3", family="Inter", size=11),
        xaxis=dict(showgrid=False, rangeslider_visible=False, color="#5c6578"),
        yaxis=dict(showgrid=True, gridcolor="#151922", side="right", color="#5c6578", tickfont=dict(size=10)),
        showlegend=False, dragmode=False)
    return fig

def crypto_bar_chart(df, title):
    if df is None or df.empty:
        return None
    plot_df = df.head(12).copy()
    colors = ["#00c853" if s >= 60 else "#ff5252" if s <= 40 else "#8b93a7" for s in plot_df["score"]]
    fig = go.Figure(go.Bar(
        x=plot_df["score"], y=plot_df["symbol"], orientation="h",
        marker_color=colors, text=plot_df["score"].map(lambda x: f"{x:.0f}"),
        textposition="outside", cliponaxis=False,
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color="#c5c9d3"), x=0),
        height=max(280, 28 * len(plot_df) + 60),
        margin=dict(l=0, r=40, t=36, b=10),
        paper_bgcolor="#0a0c10", plot_bgcolor="#0a0c10",
        font=dict(color="#c5c9d3", family="Inter", size=11),
        xaxis=dict(range=[0, 105], showgrid=True, gridcolor="#151922", title="Score (0–100)", color="#5c6578"),
        yaxis=dict(autorange="reversed", showgrid=False, color="#c5c9d3"),
        showlegend=False,
    )
    fig.add_vline(x=50, line_dash="dot", line_color="#3a4150", line_width=1)
    fig.add_vline(x=60, line_dash="dot", line_color="#00c85344", line_width=1)
    fig.add_vline(x=40, line_dash="dot", line_color="#ff525244", line_width=1)
    return fig

with st.spinner(""):
    df = load_nq()
    mag7 = load_mag7()
ctx = build_ctx(df, mag7)
action, reason, conf = verdict(ctx)
now_ny, now_ct = datetime.now(NY), datetime.now(CT)
gex_nodes, gex_provider = load_gex_for_nq(ctx["price"]) if ctx["price"] else ([], "none")
has_gex = gex_provider != "none"
chart_extra = gex_nodes if gex_nodes else []

h1, h2 = st.columns([3, 1])
with h1: st.markdown("### ⚡ Futures Cheat Code")
with h2: st.caption(f"NY {now_ny.strftime('%H:%M')} · CT {now_ct.strftime('%H:%M')}")

tab_desk, tab_crypto, tab_engine, tab_ai, tab_mag, tab_alert = st.tabs(["Trade Desk", "Crypto", "Engine", "AI", "Mag7", "Alerts"])

with tab_desk:
    if action == "LONG":
        st.markdown(f"""<div class=\"hero hero-long\"><h1 style=\"color:#00c853\">▲ LONG</h1><p>{reason}</p><div class=\"meta\">Confidence {conf}% · refreshes every 30s</div></div>""", unsafe_allow_html=True)
    elif action == "SHORT":
        st.markdown(f"""<div class=\"hero hero-short\"><h1 style=\"color:#ff5252\">▼ SHORT</h1><p>{reason}</p><div class=\"meta\">Confidence {conf}% · refreshes every 30s</div></div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""<div class=\"hero hero-wait\"><h1 style=\"color:#9aa0a6\">■ WAIT</h1><p>{reason}</p><div class=\"meta\">Confidence {conf}% · no forced trade</div></div>""", unsafe_allow_html=True)
    px_ = f"{ctx['price']:,.2f}" if ctx["price"] else "—"
    dist = f"{(ctx['price']-ctx['o8']):+.1f} pts from open" if ctx["price"] and ctx["o8"] else ""
    st.markdown(f"""<div class=\"kpi-grid\"><div class=\"kpi\"><div class=\"label\">NQ</div><div class=\"value\">{px_}</div><div class=\"sub\">{dist}</div></div><div class=\"kpi\"><div class=\"label\">Bias</div><div class=\"value\">{ctx['bias']}</div><div class=\"sub\">vs 8PM open</div></div><div class=\"kpi\"><div class=\"label\">Mag7</div><div class=\"value\">{ctx['mag']['label'].replace('STRONG ','')}</div><div class=\"sub\">{ctx['mag'].get('bullish',0)}/{ctx['mag'].get('total',7)} bull</div></div></div>""", unsafe_allow_html=True)
    asia_chip = '<span class=\"chip chip-on\">Asia ON</span>' if ctx["asia"] else '<span class=\"chip chip-off\">Asia off</span>'
    hunt_chip = '<span class=\"chip chip-on\">Hunt ON</span>' if ctx["hunt"] else '<span class=\"chip chip-off\">Hunt off</span>'
    gex_chip = f'<span class=\"chip chip-on\">GEX {gex_provider}</span>' if has_gex else '<span class=\"chip chip-off\">GEX needs key</span>'
    st.markdown(asia_chip + hunt_chip + gex_chip, unsafe_allow_html=True)
    st.markdown('<div class=\"sec\">Key levels</div>', unsafe_allow_html=True)
    rows = []
    if ctx["o8"]: rows.append(("8PM Open", f"{ctx['o8']:,.2f}"))
    if ctx["rh"] and ctx["rl"]:
        rows.append(("Asia High", f"{ctx['rh']:,.2f}")); rows.append(("Asia Low", f"{ctx['rl']:,.2f}")); rows.append(("Range Mid", f"{(ctx['rh']+ctx['rl'])/2:,.2f}"))
    for n in (gex_nodes or [])[:5]:
        rows.append((n.get("label", "GEX"), f"{n['level']:,.2f}"))
    if rows:
        html = '<div class=\"levels\">' + "".join(f'<div class=\"lvl\"><span class=\"k\">{k}</span><span class=\"v\">{v}</span></div>' for k,v in rows) + "</div>"
        st.markdown(html, unsafe_allow_html=True)
    else:
        st.caption("Levels build once Asia session data is available.")
    st.markdown('<div class=\"sec\">NQ · 5m · liquidity overlays</div>', unsafe_allow_html=True)
    if len(df) > 5:
        st.plotly_chart(candle_fig(df, ctx["o8"], ctx["rh"], ctx["rl"], extra_levels=chart_extra), use_container_width=True, config={"displayModeBar": False})
        if not has_gex:
            st.caption("Add FLASHALPHA_API_KEY in Secrets for live call/put walls on NQ.")
    else:
        st.info("Loading NQ candles…")

with tab_crypto:
    st.markdown('<div class=\"sec\">Crypto ranking</div>', unsafe_allow_html=True)
    st.markdown("""<div class=\"score-box\"><strong>Score is 0–100</strong> (bullishness from 1h / 24h / 7d momentum).<br><strong>50</strong> = neutral · <strong>≥60</strong> lean long · <strong>≤40</strong> lean short · <strong>≥75</strong> strong bull · <strong>≤25</strong> strong bear</div>""", unsafe_allow_html=True)
    fng = load_fng()
    c1, c2, c3 = st.columns(3)
    c1.metric("Fear & Greed", f"{fng.get('value', '—')}" if fng.get("value") is not None else "—")
    c2.metric("Sentiment", fng.get("label", "—"))
    c3.metric("Scale", "0–100")
    crypto = load_crypto()
    if crypto.empty:
        st.warning("CoinGecko rate limit or offline — wait ~60s and refresh.")
    else:
        n_long = int((crypto["action"] == "LONG").sum())
        n_short = int((crypto["action"] == "SHORT").sum())
        n_wait = int((crypto["action"] == "WAIT").sum())
        st.caption(f"Top {len(crypto)} by market cap · {n_long} long · {n_short} short · {n_wait} neutral")
        view = st.radio("View", ["Best longs", "Best shorts", "Full table"], horizontal=True, label_visibility="collapsed")
        if view == "Best longs":
            show = top_longs(crypto, 20)
            st.markdown("**Highest bullishness — long candidates**")
            fig = crypto_bar_chart(show, "Long candidates · Score 0–100")
            if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        elif view == "Best shorts":
            show = top_shorts(crypto, 20)
            st.markdown("**Lowest bullishness — short candidates**")
            fig = crypto_bar_chart(show, "Short candidates · Score 0–100")
            if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            show = crypto
            fig = crypto_bar_chart(crypto.head(15), "Top 15 by score · 0–100")
            if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        if not show.empty:
            table = show.copy()
            table["Price"] = table["price"].map(format_price)
            table["MCap"] = table["mcap"].map(format_mcap)
            table["Score"] = table["score"].map(lambda x: f"{x:.0f}")
            rank_col = "long_rank" if view != "Best shorts" else "short_rank"
            cols = [c for c in [rank_col, "symbol", "name", "Price", "1h%", "24h%", "7d%", "Score", "bias", "action", "MCap"] if c in table.columns]
            rename = {rank_col: "#", "symbol": "Sym", "name": "Name", "bias": "Bias", "action": "Action"}
            st.dataframe(table[cols].rename(columns=rename), use_container_width=True, hide_index=True, height=min(480, 40 + 35 * min(len(table), 20)))

with tab_engine:
    st.markdown('<div class=\"sec\">Autonomous paper engine</div>', unsafe_allow_html=True)
    st.markdown('<p class=\"hint\">Models a prop account: $3k eval target · $2k max loss · risk scales with confluence and phase (Eval aggressive / Funded protective).</p>', unsafe_allow_html=True)
    try:
        from modules.paper_engine import (init_engine_db, get_engine_state, get_open_paper_trade, get_closed_paper_trades, compute_engine_stats, engine_decide_and_act, reset_engine, get_dynamic_risk_usd, get_phase, STARTING_EQUITY, PROFIT_TARGET)
        init_engine_db()
        result = engine_decide_and_act(ctx, send_alert_fn=send_engine_alert)
        state = get_engine_state(); stats = compute_engine_stats(); open_pos = get_open_paper_trade()
        phase = get_phase(state.get("equity", STARTING_EQUITY))
        profit = state.get("equity", STARTING_EQUITY) - STARTING_EQUITY
        prog = min(100, max(0, profit / PROFIT_TARGET * 100))
        risk = get_dynamic_risk_usd(state.get("equity", STARTING_EQUITY), state.get("drawdown_usd", 0), confluence=ctx["sig"].get("confidence", 75))
        st.markdown(f"**{state.get('status', '—')}** · Phase **{phase}**")
        st.progress(prog / 100.0, text=f"${profit:,.0f} / ${PROFIT_TARGET:,.0f} eval target")
        a,b,c,d = st.columns(4)
        a.metric("Equity", f"${state.get('equity', 0):,.0f}"); b.metric("Drawdown", f"${state.get('drawdown_usd', 0):,.0f}")
        c.metric("Risk / trade", f"${risk.get('risk_usd', 0)}"); d.metric("Position", state.get("open_direction") or "Flat")
        if result.get("action") in ("ENTERED", "EXITED"): st.success(f"{result['action']}: {result.get('direction')} · {result.get('entry', result.get('exit'))}")
        elif result.get("action") == "HOLDING": st.info(f"Holding {result.get('direction')} from {result.get('entry')}")
        elif result.get("action") == "HALTED": st.error(result.get("reason", "Halted"))
        if open_pos: st.write(f"**Live:** {open_pos['direction']} @ {open_pos['entry_price']} · SL {open_pos['stop_price']} · TP {open_pos['target_price']}")
        st.markdown('<div class=\"sec\">Self-score (engine trades only)</div>', unsafe_allow_html=True)
        s1,s2,s3,s4 = st.columns(4)
        s1.metric("Trades", stats.get("total_trades", 0)); s2.metric("Win rate", f"{stats.get('win_rate', 0)}%")
        s3.metric("Avg points", stats.get("avg_points", 0)); s4.metric("Total PnL", f"${stats.get('total_pnl_usd', 0)}")
        closed = get_closed_paper_trades(15)
        if closed:
            st.dataframe(pd.DataFrame(closed)[["direction", "entry_price", "exit_price", "points", "pnl_usd", "exit_reason"]], use_container_width=True, hide_index=True)
        else:
            st.caption("No closed paper trades yet — engine waits for high-confluence setups.")
        if st.button("Reset engine to $50k"):
            reset_engine(confirm=True); st.rerun()
    except Exception as e:
        st.error(f"Engine unavailable: {e}")

with tab_ai:
    st.markdown('<div class=\"sec\">Desk agent</div>', unsafe_allow_html=True)
    st.markdown('<p class=\"hint\">Ask: long or short? levels? risk size? Asia status? crypto bias? Mag7 read?</p>', unsafe_allow_html=True)
    if "chat" not in st.session_state:
        st.session_state.chat = [{"role": "assistant", "content": "Desk is live. Ask for bias, levels, risk, or crypto rankings."}]
    for m in st.session_state.chat:
        with st.chat_message(m["role"]): st.markdown(m["content"])
    if q := st.chat_input("Ask the desk…"):
        st.session_state.chat.append({"role": "user", "content": q})
        ans = get_agent_reply(q, ctx, st.session_state.chat[:-1])
        st.session_state.chat.append({"role": "assistant", "content": ans}); st.rerun()

with tab_mag:
    st.markdown('<div class=\"sec\">Mag7 confluence</div>', unsafe_allow_html=True)
    m = ctx["mag"]
    st.markdown('<p class=\"hint\">Daily bias from the seven mega-cap names. Used as confluence with NQ Asia structure — not a standalone signal.</p>', unsafe_allow_html=True)
    a, b = st.columns(2)
    a.metric("Read", m.get("label", "—"))
    b.metric("Bullish count", f"{m.get('bullish', 0)} / {m.get('total', 7)}")
    if not mag7.empty:
        st.dataframe(mag7, use_container_width=True, hide_index=True)
    else:
        st.caption("Mag7 snapshot unavailable right now.")

with tab_alert:
    st.markdown('<div class=\"sec\">Phone alerts + API keys</div>', unsafe_allow_html=True)
    st.markdown('<p class=\"hint\">Streamlit → Manage app → Settings → Secrets. Engine ENTER/EXIT pushes to Telegram when configured.</p>', unsafe_allow_html=True)
    st.code('TELEGRAM_BOT_TOKEN = "123:ABC"\nTELEGRAM_CHAT_ID = "987654321"\nFLASHALPHA_API_KEY = "your_fa_key"   # GEX walls on chart\nSKYLIT_API_KEY = "sk_live_..."       # optional heatmap backup', language="toml")
    st.markdown("""<div class=\"score-box\"><strong>FlashAlpha</strong> — free key at flashalpha.com (5 req/day). QQQ may need Basic plan.<br><strong>Telegram</strong> — @BotFather → create bot → chat id via @userinfobot.<br>Without keys: Asia structure levels still work; GEX chip stays off.</div>""", unsafe_allow_html=True)
    if st.button("Send test alert"):
        ok = test_alert()
        st.success("Sent to Telegram") if ok else st.error("Not configured or failed — check secrets")

st.caption("NQ · Yahoo · Crypto · CoinGecko · GEX · FlashAlpha optional · Not financial advice")
