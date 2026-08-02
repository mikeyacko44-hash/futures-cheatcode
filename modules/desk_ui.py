"""Futures Cheat Code — polished multi-tab desk (crash-isolated tabs)"""
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import pytz
from dotenv import load_dotenv
import pandas as pd
import plotly.graph_objects as go
import traceback

load_dotenv()
st.set_page_config(
    page_title="Futures Cheat Code",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)

NY = pytz.timezone("America/New_York")
CT = pytz.timezone("America/Chicago")
st_autorefresh(interval=45_000, key="tick")

_import_err = None
try:
    from modules.data_fetcher import (
        get_futures_ohlcv,
        get_session_range,
        get_mag7_snapshot,
        get_mag7_confluence_score,
    )
    from modules.strategy import generate_signal, get_asia_window, get_hunt_window
    from modules.alerts import send_engine_alert, test_alert
    from modules.agent import get_agent_reply
    from modules.crypto_rank import fetch_markets, fear_greed, top_longs, top_shorts
    from modules.liquidity_levels import load_gex_for_nq
except Exception as e:
    _import_err = e


def format_price(p) -> str:
    if p is None:
        return "—"
    try:
        p = float(p)
    except (TypeError, ValueError):
        return "—"
    if p >= 1000:
        return f"${p:,.0f}"
    if p >= 1:
        return f"${p:,.2f}"
    if p >= 0.01:
        return f"${p:.4f}"
    return f"${p:.6f}"


def format_mcap(m) -> str:
    try:
        m = float(m or 0)
    except (TypeError, ValueError):
        return "—"
    if m >= 1e12:
        return f"${m/1e12:.2f}T"
    if m >= 1e9:
        return f"${m/1e9:.1f}B"
    if m >= 1e6:
        return f"${m/1e6:.0f}M"
    return f"${m:,.0f}"


@st.cache_data(ttl=30, show_spinner=False)
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
        return fetch_markets(per_page=50)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def load_fng():
    try:
        return fear_greed()
    except Exception:
        return {"value": None, "label": "—"}


def build_ctx(df, mag7):
    try:
        mag = get_mag7_confluence_score(mag7) if mag7 is not None else {
            "label": "—", "bullish": 0, "total": 7
        }
    except Exception:
        mag = {"label": "—", "bullish": 0, "total": 7}
    price = None
    try:
        if df is not None and len(df):
            price = float(df.iloc[-1]["Close"])
    except Exception:
        price = None
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
        sig = {"action": "NONE", "confidence": 0, "reason": f"Signal error: {e}", "bias": bias}
    try:
        asia = get_asia_window()
        hunt = get_hunt_window()
    except Exception:
        asia, hunt = False, False
    return {
        "price": price,
        "bias": bias,
        "rh": rh,
        "rl": rl,
        "o8": o8,
        "mag": mag,
        "asia": asia,
        "hunt": hunt,
        "sig": sig,
        "nq_price": price,
        "session_bias": bias,
        "range_high": rh,
        "range_low": rl,
        "open_8pm": o8,
        "mag7_label": mag.get("label", "—"),
        "mag7_bullish": mag.get("bullish", 0),
        "mag7_total": mag.get("total", 7),
        "asia_active": asia,
        "hunt_active": hunt,
        "last_signal": sig,
        "mag_conf": mag,
    }


def verdict(ctx):
    s = ctx.get("sig") or {}
    a, c = s.get("action", "NONE"), s.get("confidence", 0) or 0
    bias = ctx.get("bias", "UNKNOWN")
    asia, hunt = ctx.get("asia"), ctx.get("hunt")
    mag = (ctx.get("mag") or {}).get("label", "—")
    if a == "LONG" and c >= 65:
        return "LONG", s.get("reason", "Model long"), c
    if a == "SHORT" and c >= 65:
        return "SHORT", s.get("reason", "Model short"), c
    if not asia and not hunt:
        if bias == "DISCOUNT" and "BULLISH" in str(mag):
            return "WAIT", f"Lean long — Discount + {mag}. Best after 8:00 PM ET Asia open.", max(c, 40)
        if bias == "PREMIUM" and "BEARISH" in str(mag):
            return "WAIT", f"Lean short — Premium + {mag}. Wait for confirmation.", max(c, 40)
        return "WAIT", f"Outside active windows. Bias {bias} · Mag7 {mag}. No forced trade.", max(c, 25)
    if bias == "DISCOUNT":
        return "WAIT", "In discount — watching for long confirmation (sweep / CISD).", max(c, 48)
    if bias == "PREMIUM":
        return "WAIT", "In premium — watching for short confirmation (sweep / CISD).", max(c, 48)
    return "WAIT", "No clear setup. Stand aside.", c


def candle_fig(df, o8, rh, rl, extra_levels=None):
    try:
        d = df.tail(80).copy()
        fig = go.Figure()
        fig.add_trace(
            go.Candlestick(
                x=d.index,
                open=d["Open"],
                high=d["High"],
                low=d["Low"],
                close=d["Close"],
                increasing_line_color="#00c853",
                increasing_fillcolor="#00c853",
                decreasing_line_color="#ff5252",
                decreasing_fillcolor="#ff5252",
                whiskerwidth=0.6,
                name="NQ",
            )
        )
        colors = {
            "structure": "#ffc107",
            "king": "#ffeb3b",
            "gatekeeper": "#7c8aff",
            "pika": "#69f0ae",
            "barney": "#e040fb",
            "significant": "#80cbc4",
        }
        if o8:
            fig.add_hline(y=float(o8), line_dash="dash", line_color="#ffc107", line_width=1.2)
        if rh:
            fig.add_hline(y=float(rh), line_dash="dot", line_color="#7c8aff", line_width=1)
        if rl:
            fig.add_hline(y=float(rl), line_dash="dot", line_color="#7c8aff", line_width=1)
        if extra_levels:
            for lv in extra_levels[:6]:
                try:
                    y = float(lv["level"])
                    col = colors.get((lv.get("node") or "significant").lower(), "#80cbc4")
                    fig.add_hline(y=y, line_dash="dashdot", line_color=col, line_width=1)
                except Exception:
                    continue
        fig.update_layout(
            height=320,
            margin=dict(l=0, r=8, t=8, b=0),
            paper_bgcolor="#0a0c10",
            plot_bgcolor="#0a0c10",
            font=dict(color="#c5c9d3", family="Inter", size=11),
            xaxis=dict(showgrid=False, rangeslider_visible=False, color="#5c6578"),
            yaxis=dict(showgrid=True, gridcolor="#151922", side="right", color="#5c6578", tickfont=dict(size=10)),
            showlegend=False,
            dragmode=False,
        )
        return fig
    except Exception:
        return None


def crypto_bar_chart(df, title):
    try:
        if df is None or getattr(df, "empty", True):
            return None
        plot_df = df.head(12).copy()
        if "score" not in plot_df.columns or "symbol" not in plot_df.columns:
            return None
        colors = [
            "#00c853" if s >= 60 else "#ff5252" if s <= 40 else "#8b93a7"
            for s in plot_df["score"]
        ]
        fig = go.Figure(
            go.Bar(
                x=plot_df["score"],
                y=plot_df["symbol"],
                orientation="h",
                marker_color=colors,
                text=[f"{x:.0f}" for x in plot_df["score"]],
                textposition="outside",
                cliponaxis=False,
            )
        )
        fig.update_layout(
            title=dict(text=title, font=dict(size=13, color="#c5c9d3"), x=0),
            height=max(260, 26 * len(plot_df) + 50),
            margin=dict(l=0, r=36, t=36, b=10),
            paper_bgcolor="#0a0c10",
            plot_bgcolor="#0a0c10",
            font=dict(color="#c5c9d3", family="Inter", size=11),
            xaxis=dict(range=[0, 110], showgrid=True, gridcolor="#151922", title="Score 0–100", color="#5c6578"),
            yaxis=dict(autorange="reversed", showgrid=False, color="#c5c9d3"),
            showlegend=False,
        )
        return fig
    except Exception:
        return None


def safe_plotly(fig):
    if fig is None:
        return
    try:
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "responsive": True})
    except Exception as e:
        st.caption(f"Chart unavailable ({type(e).__name__})")


if _import_err is not None:
    st.error(f"Module import failed: {_import_err}")
    st.stop()

try:
    df = load_nq()
    mag7 = load_mag7()
except Exception as e:
    st.error(f"Data load failed: {e}")
    df, mag7 = pd.DataFrame(), pd.DataFrame()

ctx = build_ctx(df, mag7)
action, reason, conf = verdict(ctx)
now_ny, now_ct = datetime.now(NY), datetime.now(CT)

gex_nodes, gex_provider = [], "none"
try:
    if ctx.get("price"):
        gex_nodes, gex_provider = load_gex_for_nq(ctx["price"])
except Exception:
    gex_nodes, gex_provider = [], "none"
has_gex = gex_provider != "none"
chart_extra = gex_nodes or []

h1, h2 = st.columns([3, 1])
with h1:
    st.markdown("### ⚡ Futures Cheat Code")
with h2:
    st.caption(f"NY {now_ny.strftime('%H:%M')} · CT {now_ct.strftime('%H:%M')}")

tab_desk, tab_crypto, tab_engine, tab_ai, tab_mag, tab_alert = st.tabs(
    ["Trade Desk", "Crypto", "Engine", "AI", "Mag7", "Alerts"]
)

with tab_desk:
    try:
        if action == "LONG":
            st.markdown(f"""<div class="hero hero-long"><h1 style="color:#00c853">▲ LONG</h1><p>{reason}</p><div class="meta">Confidence {conf}% · refreshes ~45s</div></div>""", unsafe_allow_html=True)
        elif action == "SHORT":
            st.markdown(f"""<div class="hero hero-short"><h1 style="color:#ff5252">▼ SHORT</h1><p>{reason}</p><div class="meta">Confidence {conf}% · refreshes ~45s</div></div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""<div class="hero hero-wait"><h1 style="color:#9aa0a6">■ WAIT</h1><p>{reason}</p><div class="meta">Confidence {conf}% · no forced trade</div></div>""", unsafe_allow_html=True)
        px_ = f"{ctx['price']:,.2f}" if ctx.get("price") else "—"
        dist = f"{(ctx['price']-ctx['o8']):+.1f} pts from open" if ctx.get("price") and ctx.get("o8") else ""
        mag_lab = str((ctx.get("mag") or {}).get("label", "—")).replace("STRONG ", "")
        st.markdown(f"""<div class="kpi-grid"><div class="kpi"><div class="label">NQ</div><div class="value">{px_}</div><div class="sub">{dist}</div></div><div class="kpi"><div class="label">Bias</div><div class="value">{ctx.get('bias','—')}</div><div class="sub">vs 8PM open</div></div><div class="kpi"><div class="label">Mag7</div><div class="value">{mag_lab}</div><div class="sub">{(ctx.get('mag') or {}).get('bullish',0)}/{(ctx.get('mag') or {}).get('total',7)} bull</div></div></div>""", unsafe_allow_html=True)
        asia_chip = '<span class="chip chip-on">Asia ON</span>' if ctx.get("asia") else '<span class="chip chip-off">Asia off</span>'
        hunt_chip = '<span class="chip chip-on">Hunt ON</span>' if ctx.get("hunt") else '<span class="chip chip-off">Hunt off</span>'
        gex_chip = f'<span class="chip chip-on">GEX {gex_provider}</span>' if has_gex else '<span class="chip chip-off">GEX needs key</span>'
        st.markdown(asia_chip + hunt_chip + gex_chip, unsafe_allow_html=True)
        st.markdown('<div class="sec">Key levels</div>', unsafe_allow_html=True)
        rows = []
        if ctx.get("o8"):
            rows.append(("8PM Open", f"{ctx['o8']:,.2f}"))
        if ctx.get("rh") and ctx.get("rl"):
            rows.append(("Asia High", f"{ctx['rh']:,.2f}"))
            rows.append(("Asia Low", f"{ctx['rl']:,.2f}"))
            rows.append(("Range Mid", f"{(ctx['rh']+ctx['rl'])/2:,.2f}"))
        for n in (gex_nodes or [])[:5]:
            try:
                rows.append((n.get("label", "GEX"), f"{n['level']:,.2f}"))
            except Exception:
                pass
        if rows:
            html = '<div class="levels">' + "".join(f'<div class="lvl"><span class="k">{k}</span><span class="v">{v}</span></div>' for k, v in rows) + "</div>"
            st.markdown(html, unsafe_allow_html=True)
        else:
            st.caption("Levels build once Asia session data is available.")
        st.markdown('<div class="sec">NQ · 5m</div>', unsafe_allow_html=True)
        if df is not None and len(df) > 5:
            safe_plotly(candle_fig(df, ctx.get("o8"), ctx.get("rh"), ctx.get("rl"), chart_extra))
            if not has_gex:
                st.caption("Add FLASHALPHA_API_KEY in Secrets for call/put walls.")
        else:
            st.info("Loading NQ candles… (Yahoo delayed)")
    except Exception as e:
        st.error(f"Trade Desk error: {e}")
        st.code(traceback.format_exc()[-800:])

with tab_crypto:
    try:
        st.markdown('<div class="sec">Crypto ranking</div>', unsafe_allow_html=True)
        st.markdown("""<div class="score-box"><strong>Score is 0–100</strong> from 1h / 24h / 7d momentum.<br><strong>50</strong> neutral · <strong>≥60</strong> long · <strong>≤40</strong> short</div>""", unsafe_allow_html=True)
        fng = load_fng()
        c1, c2, c3 = st.columns(3)
        c1.metric("Fear & Greed", f"{fng.get('value', '—')}" if fng.get("value") is not None else "—")
        c2.metric("Sentiment", fng.get("label", "—"))
        c3.metric("Scale", "0–100")
        crypto = load_crypto()
        if crypto is None or getattr(crypto, "empty", True):
            st.warning("CoinGecko rate limit or offline — wait ~60s and refresh.")
        else:
            n_long = int((crypto["action"] == "LONG").sum()) if "action" in crypto.columns else 0
            n_short = int((crypto["action"] == "SHORT").sum()) if "action" in crypto.columns else 0
            n_wait = int((crypto["action"] == "WAIT").sum()) if "action" in crypto.columns else 0
            st.caption(f"Top {len(crypto)} by mcap · {n_long} long · {n_short} short · {n_wait} neutral")
            view = st.radio("View", ["Best longs", "Best shorts", "Full table"], horizontal=True, label_visibility="collapsed", key="crypto_view")
            if view == "Best longs":
                show = top_longs(crypto, 20)
                st.markdown("**Long candidates**")
            elif view == "Best shorts":
                show = top_shorts(crypto, 20)
                st.markdown("**Short candidates**")
            else:
                show = crypto
            fig = crypto_bar_chart(show if view != "Full table" else crypto.head(15), "Score 0–100")
            safe_plotly(fig)
            if show is not None and not getattr(show, "empty", True):
                table = show.copy()
                if "price" in table.columns:
                    table["Price"] = table["price"].map(format_price)
                if "mcap" in table.columns:
                    table["MCap"] = table["mcap"].map(format_mcap)
                if "score" in table.columns:
                    table["Score"] = table["score"].map(lambda x: f"{x:.0f}")
                rank_col = "long_rank" if view != "Best shorts" else "short_rank"
                cols = [c for c in [rank_col, "symbol", "name", "Price", "1h%", "24h%", "7d%", "Score", "bias", "action", "MCap"] if c in table.columns]
                rename = {rank_col: "#", "symbol": "Sym", "name": "Name", "bias": "Bias", "action": "Action"}
                st.dataframe(table[cols].rename(columns=rename), use_container_width=True, hide_index=True, height=min(480, 40 + 35 * min(len(table), 20)))
    except Exception as e:
        st.error(f"Crypto tab error: {e}")
        st.code(traceback.format_exc()[-600:])

with tab_engine:
    try:
        st.markdown('<div class="sec">Autonomous paper engine</div>', unsafe_allow_html=True)
        st.markdown('<p class="hint">Prop-style paper: $3k eval target · $2k max loss · risk scales with confluence / phase.</p>', unsafe_allow_html=True)
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
        prog = min(100, max(0, profit / PROFIT_TARGET * 100))
        risk = get_dynamic_risk_usd(equity, state.get("drawdown_usd", 0), confluence=ctx.get("sig", {}).get("confidence", 75))
        st.markdown(f"**{state.get('status', '—')}** · Phase **{phase}**")
        st.progress(prog / 100.0, text=f"${profit:,.0f} / ${PROFIT_TARGET:,.0f} eval target")
        a, b, c, d = st.columns(4)
        a.metric("Equity", f"${equity:,.0f}")
        b.metric("Drawdown", f"${state.get('drawdown_usd', 0):,.0f}")
        c.metric("Risk / trade", f"${risk.get('risk_usd', 0)}")
        d.metric("Position", state.get("open_direction") or "Flat")
        act = result.get("action")
        if act in ("ENTERED", "EXITED"):
            st.success(f"{act}: {result.get('direction')} · {result.get('entry', result.get('exit'))}")
        elif act == "HOLDING":
            st.info(f"Holding {result.get('direction')} from {result.get('entry')}")
        elif act == "HALTED":
            st.error(result.get("reason", "Halted"))
        if open_pos:
            st.write(f"**Live:** {open_pos['direction']} @ {open_pos['entry_price']} · SL {open_pos['stop_price']} · TP {open_pos['target_price']}")
        st.markdown('<div class="sec">Self-score (engine only)</div>', unsafe_allow_html=True)
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Trades", stats.get("total_trades", 0))
        s2.metric("Win rate", f"{stats.get('win_rate', 0)}%")
        s3.metric("Avg points", stats.get("avg_points", 0))
        s4.metric("Total PnL", f"${stats.get('total_pnl_usd', 0)}")
        closed = get_closed_paper_trades(15)
        if closed:
            st.dataframe(pd.DataFrame(closed)[["direction", "entry_price", "exit_price", "points", "pnl_usd", "exit_reason"]], use_container_width=True, hide_index=True)
        else:
            st.caption("No closed paper trades yet.")
        if st.button("Reset engine to $50k", key="reset_eng"):
            reset_engine(confirm=True)
            st.rerun()
    except Exception as e:
        st.error(f"Engine unavailable: {e}")
        st.code(traceback.format_exc()[-600:])

with tab_ai:
    try:
        st.markdown('<div class="sec">Desk agent</div>', unsafe_allow_html=True)
        st.markdown('<p class="hint">Ask: long or short? levels? risk size? Asia status? crypto bias?</p>', unsafe_allow_html=True)
        if "chat" not in st.session_state:
            st.session_state.chat = [{"role": "assistant", "content": "Desk is live. Ask for bias, levels, risk, or crypto rankings."}]
        for m in st.session_state.chat:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])
        if q := st.chat_input("Ask the desk…"):
            st.session_state.chat.append({"role": "user", "content": q})
            try:
                ans = get_agent_reply(q, ctx, st.session_state.chat[:-1])
            except Exception as e:
                ans = f"Agent error: {e}"
            st.session_state.chat.append({"role": "assistant", "content": ans})
            st.rerun()
    except Exception as e:
        st.error(f"AI tab error: {e}")

with tab_mag:
    try:
        st.markdown('<div class="sec">Mag7 confluence</div>', unsafe_allow_html=True)
        m = ctx.get("mag") or {}
        st.markdown('<p class="hint">Daily bias from mega-caps — confluence with NQ structure, not a standalone signal.</p>', unsafe_allow_html=True)
        a, b = st.columns(2)
        a.metric("Read", m.get("label", "—"))
        b.metric("Bullish count", f"{m.get('bullish', 0)} / {m.get('total', 7)}")
        if mag7 is not None and not getattr(mag7, "empty", True):
            st.dataframe(mag7, use_container_width=True, hide_index=True)
        else:
            st.caption("Mag7 snapshot unavailable right now.")
    except Exception as e:
        st.error(f"Mag7 tab error: {e}")

with tab_alert:
    try:
        st.markdown('<div class="sec">Phone alerts + API keys</div>', unsafe_allow_html=True)
        st.markdown('<p class="hint">Streamlit → Manage app → Settings → Secrets. Engine ENTER/EXIT → Telegram.</p>', unsafe_allow_html=True)
        st.code('TELEGRAM_BOT_TOKEN = "123:ABC"\nTELEGRAM_CHAT_ID = "987654321"\nFLASHALPHA_API_KEY = "your_fa_key"\nSKYLIT_API_KEY = "sk_live_..."', language="toml")
        st.markdown("""<div class="score-box"><strong>FlashAlpha</strong> — free key at flashalpha.com (5 req/day).<br><strong>Telegram</strong> — @BotFather → bot → chat id via @userinfobot.<br>Without keys: Asia structure still works; GEX stays off.</div>""", unsafe_allow_html=True)
        if st.button("Send test alert", key="test_alert_btn"):
            ok = test_alert()
            st.success("Sent to Telegram") if ok else st.error("Not configured or failed — check secrets")
    except Exception as e:
        st.error(f"Alerts tab error: {e}")

st.caption("NQ · Yahoo delayed · Crypto · CoinGecko · GEX optional · Not financial advice")
