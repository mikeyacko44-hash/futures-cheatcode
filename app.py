"""Futures Cheat Code — mobile-safe single-page nav (no blank-screen tabs). v2"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from datetime import datetime
import traceback

st.set_page_config(
    page_title="Futures Cheat Code",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
html, body, [class*="css"] { font-family: -apple-system, BlinkMacSystemFont, Inter, sans-serif; }
.stApp { background: #0a0c10; color: #e7e9ea; }
.block-container { padding: 0.75rem 0.85rem 2rem; max-width: 820px; margin: 0 auto; }
#MainMenu, footer, header { visibility: hidden; }
.hero { border-radius: 14px; padding: 16px; margin: 0 0 12px 0; border: 1px solid #1e2430; }
.hero-long  { background: #0a1f14; border-color: #00c85355; }
.hero-short { background: #1f0a0a; border-color: #ff525255; }
.hero-wait  { background: #12151c; border-color: #3a415055; }
.hero h1 { margin: 0; font-size: 1.5rem; font-weight: 700; }
.hero p  { margin: 8px 0 0; opacity: 0.9; font-size: 0.9rem; line-height: 1.4; }
.kpi-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 12px; }
.kpi { background: #12151c; border: 1px solid #1e2430; border-radius: 12px; padding: 10px 8px; text-align: center; }
.kpi .label { font-size: 0.65rem; text-transform: uppercase; color: #8b93a7; }
.kpi .value { font-size: 1rem; font-weight: 600; color: #f0f2f5; margin-top: 2px; }
.kpi .sub { font-size: 0.68rem; color: #8b93a7; margin-top: 2px; }
.lvl-box { background: #12151c; border: 1px solid #1e2430; border-radius: 12px; padding: 4px 12px; margin-bottom: 12px; }
.lvl { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #1a1f2a; font-size: 0.88rem; }
.lvl:last-child { border-bottom: none; }
.lvl .k { color: #8b93a7; }
.lvl .v { font-weight: 600; }
.sec { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; color: #8b93a7; margin: 12px 0 8px; font-weight: 600; }
.chip { display: inline-block; padding: 3px 8px; border-radius: 99px; font-size: 0.68rem; font-weight: 600; margin-right: 4px; margin-bottom: 4px; }
.chip-on  { background: #00c85322; color: #00c853; border: 1px solid #00c85344; }
.chip-off { background: #ffffff08; color: #8b93a7; border: 1px solid #ffffff12; }
.hint { font-size: 0.78rem; color: #8b93a7; line-height: 1.4; }
</style>
""",
    unsafe_allow_html=True,
)

try:
    from streamlit_autorefresh import st_autorefresh
    if st.sidebar.checkbox("Auto-refresh (45s)", value=False, key="ar"):
        st_autorefresh(interval=45_000, key="tick")
except Exception:
    pass

import pandas as pd
import pytz

NY = pytz.timezone("America/New_York")
CT = pytz.timezone("America/Chicago")

err_import = None
try:
    from modules.data_fetcher import (
        get_futures_ohlcv, get_session_range, get_mag7_snapshot, get_mag7_confluence_score,
    )
    from modules.strategy import generate_signal, get_asia_window, get_hunt_window
    from modules.alerts import send_engine_alert, test_alert
    from modules.agent import get_agent_reply
    from modules.crypto_rank import fetch_markets, fear_greed, top_longs, top_shorts
    from modules.liquidity_levels import load_gex_for_nq
except Exception as e:
    err_import = e


def format_price(p):
    if p is None:
        return "—"
    try:
        p = float(p)
    except Exception:
        return "—"
    if p >= 1000:
        return f"${p:,.0f}"
    if p >= 1:
        return f"${p:,.2f}"
    if p >= 0.01:
        return f"${p:.4f}"
    return f"${p:.6f}"


def format_mcap(m):
    try:
        m = float(m or 0)
    except Exception:
        return "—"
    if m >= 1e12:
        return f"${m/1e12:.2f}T"
    if m >= 1e9:
        return f"${m/1e9:.1f}B"
    if m >= 1e6:
        return f"${m/1e6:.0f}M"
    return f"${m:,.0f}"


@st.cache_data(ttl=45, show_spinner=False)
def load_nq():
    try:
        return get_futures_ohlcv("NQ=F", period="5d", interval="5m")
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=120, show_spinner=False)
def load_mag7():
    try:
        return get_mag7_snapshot()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=180, show_spinner=False)
def load_crypto():
    try:
        return fetch_markets(per_page=40)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def load_fng():
    try:
        return fear_greed()
    except Exception:
        return {"value": None, "label": "—"}


def build_ctx(df, mag7):
    mag = {"label": "—", "bullish": 0, "total": 7}
    try:
        if mag7 is not None and len(mag7):
            mag = get_mag7_confluence_score(mag7)
    except Exception:
        pass
    price = None
    try:
        if df is not None and len(df):
            price = float(df.iloc[-1]["Close"])
    except Exception:
        pass
    rh = rl = o8 = None
    bias = "UNKNOWN"
    sig = {"action": "NONE", "confidence": 0, "reason": "Waiting on data", "bias": bias}
    try:
        if df is not None and len(df):
            rh, rl, o8 = get_session_range(df, 20, 0, 0, 0)
            if o8 is not None and price is not None:
                bias = "PREMIUM" if price > o8 else "DISCOUNT"
            sig = generate_signal(df, o8, rh, rl, session="ASIA")
            sig["bias"] = bias
    except Exception as e:
        sig = {"action": "NONE", "confidence": 0, "reason": str(e)[:80], "bias": bias}
    try:
        asia, hunt = get_asia_window(), get_hunt_window()
    except Exception:
        asia, hunt = False, False
    return {
        "price": price, "bias": bias, "rh": rh, "rl": rl, "o8": o8, "mag": mag,
        "asia": asia, "hunt": hunt, "sig": sig,
    }


def verdict(ctx):
    s = ctx.get("sig") or {}
    a, c = s.get("action", "NONE"), s.get("confidence", 0) or 0
    bias = ctx.get("bias", "UNKNOWN")
    asia, hunt = ctx.get("asia"), ctx.get("hunt")
    mag = (ctx.get("mag") or {}).get("label", "—")

    # v2: lower threshold so it can actually fire in Asia
    if a == "LONG" and c >= 60:
        return "LONG", s.get("reason", "Model long"), c
    if a == "SHORT" and c >= 60:
        return "SHORT", s.get("reason", "Model short"), c

    if not asia and not hunt:
        if bias == "DISCOUNT" and "BULLISH" in str(mag):
            return "WAIT", f"Lean long — Discount + {mag}. Best after 8PM ET.", max(c, 40)
        if bias == "PREMIUM" and "BEARISH" in str(mag):
            return "WAIT", f"Lean short — Premium + {mag}. Wait confirmation.", max(c, 40)
        return "WAIT", f"Outside windows. Bias {bias} · Mag7 {mag}.", max(c, 25)

    if bias == "DISCOUNT":
        return "WAIT", "Discount — watch for long confirmation.", max(c, 48)
    if bias == "PREMIUM":
        return "WAIT", "Premium — watch for short confirmation.", max(c, 48)
    return "WAIT", "No clear setup.", c


def make_candle(df, o8, rh, rl):
    import plotly.graph_objects as go
    # Focus on recent action only (last ~4-6 hours of 5m bars)
    d = df.tail(72).copy()
    fig = go.Figure(go.Candlestick(
        x=d.index, open=d["Open"], high=d["High"], low=d["Low"], close=d["Close"],
        increasing_line_color="#00c853", increasing_fillcolor="#00c853",
        decreasing_line_color="#ff5252", decreasing_fillcolor="#ff5252",
        whiskerwidth=0.5, name="NQ",
    ))
    if o8:
        fig.add_hline(y=float(o8), line_dash="dash", line_color="#ffc107", line_width=1.2)
    if rh:
        fig.add_hline(y=float(rh), line_dash="dot", line_color="#7c8aff", line_width=1)
    if rl:
        fig.add_hline(y=float(rl), line_dash="dot", line_color="#7c8aff", line_width=1)
    fig.update_layout(
        height=300, margin=dict(l=0, r=4, t=8, b=0),
        paper_bgcolor="#0a0c10", plot_bgcolor="#0a0c10",
        font=dict(color="#c5c9d3", size=10),
        xaxis=dict(showgrid=False, rangeslider_visible=False),
        yaxis=dict(showgrid=True, gridcolor="#151922", side="right"),
        showlegend=False, dragmode=False,
    )
    return fig


if err_import is not None:
    st.error(f"Import failed: {err_import}")
    st.stop()

now_ny = datetime.now(NY)
now_ct = datetime.now(CT)
st.markdown("### ⚡ Futures Cheat Code")
st.caption(f"NY {now_ny.strftime('%H:%M')} · CT {now_ct.strftime('%H:%M')} · Yahoo delayed (Databento ready)")

page = st.radio(
    "nav",
    ["Desk", "Crypto", "Engine", "AI", "Mag7", "Alerts"],
    horizontal=True,
    label_visibility="collapsed",
    key="page_nav",
)

df = load_nq()
mag7 = load_mag7()
ctx = build_ctx(df, mag7)
action, reason, conf = verdict(ctx)

if page == "Desk":
    try:
        if action == "LONG":
            st.markdown(f'<div class="hero hero-long"><h1 style="color:#00c853">▲ LONG</h1><p>{reason}</p></div>', unsafe_allow_html=True)
        elif action == "SHORT":
            st.markdown(f'<div class="hero hero-short"><h1 style="color:#ff5252">▼ SHORT</h1><p>{reason}</p></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="hero hero-wait"><h1 style="color:#9aa0a6">■ WAIT</h1><p>{reason}</p></div>', unsafe_allow_html=True)
        px_ = f"{ctx['price']:,.2f}" if ctx.get("price") else "—"
        dist = f"{(ctx['price']-ctx['o8']):+.1f} from open" if ctx.get("price") and ctx.get("o8") else ""
        mag_lab = str((ctx.get("mag") or {}).get("label", "—")).replace("STRONG ", "")
        st.markdown(f"""<div class="kpi-grid"><div class="kpi"><div class="label">NQ</div><div class="value">{px_}</div><div class="sub">{dist}</div></div><div class="kpi"><div class="label">Bias</div><div class="value">{ctx.get('bias','—')}</div><div class="sub">vs 8PM</div></div><div class="kpi"><div class="label">Mag7</div><div class="value">{mag_lab}</div><div class="sub">{(ctx.get('mag') or {}).get('bullish',0)}/{(ctx.get('mag') or {}).get('total',7)}</div></div></div>""", unsafe_allow_html=True)
        chips = ('<span class="chip chip-on">Asia ON</span>' if ctx.get("asia") else '<span class="chip chip-off">Asia off</span>')
        chips += ('<span class="chip chip-on">Hunt ON</span>' if ctx.get("hunt") else '<span class="chip chip-off">Hunt off</span>')
        st.markdown(chips, unsafe_allow_html=True)
        st.markdown('<div class="sec">Key levels</div>', unsafe_allow_html=True)
        rows = []
        if ctx.get("o8"):
            rows.append(("8PM Open", f"{ctx['o8']:,.2f}"))
        if ctx.get("rh") and ctx.get("rl"):
            rows.append(("Asia High", f"{ctx['rh']:,.2f}"))
            rows.append(("Asia Low", f"{ctx['rl']:,.2f}"))
            rows.append(("Mid", f"{(ctx['rh']+ctx['rl'])/2:,.2f}"))
        try:
            if ctx.get("price"):
                nodes, prov = load_gex_for_nq(ctx["price"])
                for n in (nodes or [])[:4]:
                    rows.append((n.get("label", "GEX"), f"{n['level']:,.2f}"))
                if prov and prov != "none":
                    st.caption(f"GEX: {prov}")
        except Exception:
            pass
        if rows:
            html = '<div class="lvl-box">' + "".join(f'<div class="lvl"><span class="k">{k}</span><span class="v">{v}</span></div>' for k, v in rows) + "</div>"
            st.markdown(html, unsafe_allow_html=True)
        else:
            st.caption("Levels appear when Asia data is ready.")
        if st.checkbox("Show NQ chart", value=True, key="show_nq_chart"):
            if df is not None and len(df) > 5:
                try:
                    fig = make_candle(df, ctx.get("o8"), ctx.get("rh"), ctx.get("rl"))
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                except Exception as e:
                    st.caption(f"Chart error: {type(e).__name__}")
            else:
                st.info("No NQ bars yet.")
        st.caption(f"Confidence {conf}% · not financial advice")
    except Exception as e:
        st.error(f"Desk error: {e}")
        st.code(traceback.format_exc()[-500:])

elif page == "Crypto":
    try:
        st.markdown('<div class="sec">Crypto ranking · score 0–100</div>', unsafe_allow_html=True)
        st.caption("≥60 lean long · ≤40 lean short · 50 neutral")
        fng = load_fng()
        a, b, c = st.columns(3)
        a.metric("Fear & Greed", fng.get("value") if fng.get("value") is not None else "—")
        b.metric("Sentiment", fng.get("label", "—"))
        c.metric("Scale", "0–100")
        crypto = load_crypto()
        if crypto is None or getattr(crypto, "empty", True):
            st.warning("CoinGecko busy — wait a minute and open this page again.")
        else:
            view = st.radio("View", ["Longs", "Shorts", "All"], horizontal=True, key="cv")
            if view == "Longs":
                show = top_longs(crypto, 15)
            elif view == "Shorts":
                show = top_shorts(crypto, 15)
            else:
                show = crypto.head(20)
            if show is not None and not getattr(show, "empty", True):
                t = show.copy()
                if "price" in t.columns:
                    t["Price"] = t["price"].map(format_price)
                if "mcap" in t.columns:
                    t["MCap"] = t["mcap"].map(format_mcap)
                if "score" in t.columns:
                    t["Score"] = t["score"].map(lambda x: f"{float(x):.0f}")
                cols = [c for c in ["symbol", "Price", "1h%", "24h%", "7d%", "Score", "action", "MCap"] if c in t.columns]
                st.dataframe(t[cols], use_container_width=True, hide_index=True, height=420)
    except Exception as e:
        st.error(f"Crypto error: {e}")
        st.code(traceback.format_exc()[-500:])

elif page == "Engine":
    try:
        st.markdown('<div class="sec">Paper engine</div>', unsafe_allow_html=True)
        st.caption("$3k eval target · $2k max DD · confluence risk scaling")
        from modules.paper_engine import (
            init_engine_db, get_engine_state, get_open_paper_trade, get_closed_paper_trades,
            compute_engine_stats, engine_decide_and_act, reset_engine, get_dynamic_risk_usd,
            get_phase, STARTING_EQUITY, PROFIT_TARGET,
        )
        init_engine_db()
        result = engine_decide_and_act(ctx, send_alert_fn=send_engine_alert)
        state = get_engine_state()
        stats = compute_engine_stats()
        open_pos = get_open_paper_trade()
        equity = state.get("equity", STARTING_EQUITY)
        phase = get_phase(equity)
        profit = equity - STARTING_EQUITY
        prog = min(100, max(0, (profit / PROFIT_TARGET) * 100))
        risk = get_dynamic_risk_usd(equity, state.get("drawdown_usd", 0), confluence=ctx.get("sig", {}).get("confidence", 75))
        st.markdown(f"**{state.get('status', '—')}** · Phase **{phase}**")
        st.progress(prog / 100.0, text=f"${profit:,.0f} / ${PROFIT_TARGET:,.0f}")
        a, b, c, d = st.columns(4)
        a.metric("Equity", f"${equity:,.0f}")
        b.metric("DD", f"${state.get('drawdown_usd', 0):,.0f}")
        c.metric("Risk", f"${risk.get('risk_usd', 0)}")
        d.metric("Pos", state.get("open_direction") or "Flat")
        act = result.get("action")
        if act in ("ENTERED", "EXITED"):
            st.success(f"{act}: {result.get('direction')} · {result.get('entry', result.get('exit'))}")
        elif act == "HOLDING":
            st.info(f"Holding {result.get('direction')} from {result.get('entry')}")
        elif act == "HALTED":
            st.error(result.get("reason", "Halted"))
        if open_pos:
            st.write(f"Live: {open_pos['direction']} @ {open_pos['entry_price']} · SL {open_pos['stop_price']} · TP {open_pos['target_price']}")
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Trades", stats.get("total_trades", 0))
        s2.metric("Win%", f"{stats.get('win_rate', 0)}%")
        s3.metric("Avg pts", stats.get("avg_points", 0))
        s4.metric("PnL", f"${stats.get('total_pnl_usd', 0)}")
        closed = get_closed_paper_trades(12)
        if closed:
            st.dataframe(pd.DataFrame(closed)[["direction", "entry_price", "exit_price", "points", "pnl_usd", "exit_reason"]], use_container_width=True, hide_index=True)
        else:
            st.caption("No closed paper trades yet.")
        if st.button("Reset engine $50k", key="rst"):
            reset_engine(confirm=True)
            st.rerun()
    except Exception as e:
        st.error(f"Engine error: {e}")
        st.code(traceback.format_exc()[-500:])

elif page == "AI":
    try:
        st.markdown('<div class="sec">Desk agent</div>', unsafe_allow_html=True)
        st.caption("Ask bias, levels, risk, Asia, crypto.")
        if "chat" not in st.session_state:
            st.session_state.chat = [{"role": "assistant", "content": "Desk live. Ask anything."}]
        for m in st.session_state.chat:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])
        if q := st.chat_input("Ask…"):
            st.session_state.chat.append({"role": "user", "content": q})
            try:
                ans = get_agent_reply(q, ctx, st.session_state.chat[:-1])
            except Exception as e:
                ans = f"Error: {e}"
            st.session_state.chat.append({"role": "assistant", "content": ans})
            st.rerun()
    except Exception as e:
        st.error(f"AI error: {e}")

elif page == "Mag7":
    try:
        st.markdown('<div class="sec">Mag7 confluence</div>', unsafe_allow_html=True)
        m = ctx.get("mag") or {}
        a, b = st.columns(2)
        a.metric("Read", m.get("label", "—"))
        b.metric("Bullish", f"{m.get('bullish', 0)} / {m.get('total', 7)}")
        if mag7 is not None and not getattr(mag7, "empty", True):
            st.dataframe(mag7, use_container_width=True, hide_index=True)
        else:
            st.caption("Mag7 data unavailable.")
    except Exception as e:
        st.error(f"Mag7 error: {e}")

elif page == "Alerts":
    try:
        st.markdown('<div class="sec">Alerts & secrets</div>', unsafe_allow_html=True)
        st.caption("Manage app → Settings → Secrets")
        st.code('TELEGRAM_BOT_TOKEN = "123:ABC"\nTELEGRAM_CHAT_ID = "987654321"\nFLASHALPHA_API_KEY = "your_key"\nDATABENTO_API_KEY = "db-..."', language="toml")
        if st.button("Send test Telegram", key="tg"):
            ok = test_alert()
            st.success("Sent") if ok else st.error("Failed — check secrets")
    except Exception as e:
        st.error(f"Alerts error: {e}")

st.caption("Personal desk · Yahoo delayed (Databento ready) · Not financial advice")
