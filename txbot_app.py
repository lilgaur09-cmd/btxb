from pathlib import Path

import sqlite3

import streamlit as st

from auth import authenticate, create_account
from binary_analysis import answer_binary_question, summarize_binary_market
from crypto_analysis import answer_chart_question, summarize_chart
from live_chart import render_realtime_chart
from market_data import ASSET_CLASSES, asset_class_for, fetch_market, market_options

BINARY_KEYWORDS = (
    "call",
    "put",
    "binary",
    "expiry",
    "expire",
    "pattern",
    "doji",
    "hammer",
    "engulf",
    "stochastic",
    "confidence",
    "payout",
    "win rate",
)


def answer_combined(question: str, spot_summary: dict, binary_summary: dict) -> str:
    """Route a question to the spot (TRADEXBOT) or binary (BINARYTXBOT) assistant."""
    query = question.casefold()
    if any(keyword in query for keyword in BINARY_KEYWORDS):
        return answer_binary_question(question, binary_summary)
    return answer_chart_question(question, spot_summary)


favicon_path = Path(__file__).resolve().parent / "assets" / "txbot-favicon.svg"
page_icon = str(favicon_path) if favicon_path.is_file() else "🤖"
st.set_page_config(page_title="TXBOT", page_icon=page_icon, layout="wide")
st.markdown(
    """
    <style>
    html, body, .stApp { height: 100%; }
    .stApp { background: #0b1220; color: #e5e7eb; }
    .block-container { padding: 0.4rem 0.5rem 0.6rem; max-width: 100%; }
    div[data-testid="stMetric"] {
        background: #111a2b;
        border: 1px solid #273449;
        border-radius: 6px;
        padding: 0.75rem 0.85rem;
    }
    div[data-testid="stMetricValue"] { font-size: 1.2rem; }
    div[data-testid="stMetricLabel"] { color: #9fb0c4; }
    .maker-credit { text-align: right; padding-top: 1.05rem; }
    .maker-credit span { display: block; color: #9fb0c4; font-size: 0.85rem; }
    .maker-credit strong { display: block; color: #f6f8fa; font-size: 1.55rem; font-weight: 700; }
    .brand-logo svg { display: block; width: min(100%, 460px); max-height: 106px; }
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
    .signal-card { border-radius: 10px; padding: 0.85rem 1.1rem; margin: 0.2rem 0 0.4rem; border: 1px solid #273449; background: #111a2b; }
    .signal-card .kicker { color: #9fb0c4; font-size: 0.8rem; letter-spacing: 1px; text-transform: uppercase; }
    .signal-card .headline { font-size: 1.75rem; font-weight: 800; letter-spacing: 0.5px; }
    .signal-card .line { color: #cbd5e1; font-size: 0.95rem; margin-top: 0.15rem; }
    .signal-card .note { color: #9fb0c4; font-size: 0.85rem; margin-top: 0.25rem; }
    .signal-buy .headline, .signal-call .headline { color: #16c784; }
    .signal-sell .headline, .signal-put .headline { color: #ea3943; }
    .signal-hold .headline, .signal-wait .headline { color: #f4c430; }
    @media (max-width: 640px) { .maker-credit { text-align: left; padding-top: 0; } }
    </style>
    """,
    unsafe_allow_html=True,
)

brand_column, maker_column = st.columns([3, 1])
with brand_column:
    logo_path = Path(__file__).resolve().parent / "assets" / "txbot-logo.svg"
    if logo_path.is_file():
        logo_svg = logo_path.read_text(encoding="utf-8")
    else:
        logo_svg = "".join(
            [
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 160" role="img" aria-label="TXBOT">',
                '<defs><linearGradient id="fb-green" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#00b88a"/><stop offset="1" stop-color="#00f0aa"/></linearGradient></defs>',
                '<path d="M18 120 46 68l20 22L98 30" fill="none" stroke="url(#fb-green)" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>',
                '<path d="M82 30h18v18" fill="none" stroke="url(#fb-green)" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>',
                '<text x="120" y="114" fill="#f6f8fa" font-family="Arial,sans-serif" font-size="62" font-weight="800">TX</text>',
                '<text x="236" y="114" fill="url(#fb-green)" font-family="Arial,sans-serif" font-size="62" font-weight="800">BOT</text>',
                '<path d="M462 112 482 78l20 34z" fill="url(#fb-green)"/>',
                '<path d="M512 40 532 74l20-34z" fill="#ff6b7a"/>',
                "</svg>",
            ]
        )
    st.markdown(
        f'<h1 class="sr-only">TXBOT</h1><div class="brand-logo" role="img" aria-label="TXBOT">{logo_svg}</div>',
        unsafe_allow_html=True,
    )
    st.caption("TRADEXBOT × BINARYTXBOT · Crypto, Forex, and Metals charts with spot and binary signals")
with maker_column:
    st.markdown(
        '<div class="maker-credit"><span>DEVELOPED BY</span><strong>AtharvX</strong></div>',
        unsafe_allow_html=True,
    )
def render_signal_card(css_class: str, kicker: str, headline: str, line: str, note: str) -> None:
    st.markdown(
        f"""<div class="signal-card {css_class}">
        <div class="kicker">{kicker}</div>
        <div class="headline">{headline}</div>
        <div class="line">{line}</div>
        <div class="note">{note}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def load_market(symbol, asset_class, interval, expiry_choice, follow_live):
    candles, live_price, meta = fetch_market(symbol, interval=interval, limit=180, asset_class=asset_class)
    if live_price and live_price > 0:
        current = candles[-1]
        current["close"] = live_price
        current["high"] = max(float(current["high"]), live_price)
        current["low"] = min(float(current["low"]), live_price)
    usable_price = live_price if live_price and live_price > 0 else None
    spot = summarize_chart(symbol, candles, live_price=usable_price)
    binary = summarize_binary_market(
        symbol,
        candles,
        live_price=usable_price,
        interval=interval,
        expiry_minutes=int(expiry_choice) if expiry_choice != "Auto" else None,
    )
    st.session_state["spot_summary"] = spot
    st.session_state["binary_summary"] = binary
    st.session_state["market_meta"] = meta
    st.session_state["market_candles"] = candles
    st.session_state["market_live_price"] = live_price
    return candles, live_price, meta, spot, binary


def render_market(symbol, asset_class, interval, expiry_choice, follow_live):
    try:
        candles, live_price, meta, spot, binary = load_market(
            symbol, asset_class, interval, expiry_choice, follow_live
        )
    except (RuntimeError, ValueError) as error:
        st.error(str(error))
        return

    st.subheader(f"{symbol} overview · {meta['asset_class']} via {meta['provider']}")
    spot_column, binary_column = st.columns(2)
    with spot_column:
        render_signal_card(
            f"signal-{spot['signal'].lower()}",
            "TRADEXBOT · spot",
            f"{spot['signal']} · {spot['trend']}",
            f"Confluence {spot['signal_score']:+d}/{spot['signal_factor_count']} · {spot['signal_strength']}% agreement",
            f"Regime {spot['market_regime']} (ADX {spot['adx']:.1f}) · RSI {spot['rsi']:.1f}",
        )
    with binary_column:
        binary_class = (
            "signal-call"
            if binary["signal"] == "CALL"
            else "signal-put"
            if binary["signal"] == "PUT"
            else "signal-wait"
        )
        render_signal_card(
            binary_class,
            "BINARYTXBOT · fixed-time",
            f"{binary['signal']} · {binary['bias']}",
            f"Entry {binary['entry_price']:.2f} · Expiry {binary['expiry_minutes']} min · Expected move ±{binary['expected_move_percent']:.2f}%",
            f"{binary['confidence']}% agreement · {binary['signal_quality']} quality · {binary['market_regime']} (ADX {binary['adx']:.1f})",
        )

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Price at load", f"{meta['price_prefix']}{spot['last_close']:.2f}", f"{spot['price_change_percent']:+.2f}%")
    col2.metric("Spot signal", spot["signal"], spot["trend"], delta_color="off")
    col3.metric("Binary signal", binary["signal"], binary["bias"], delta_color="off")
    col4.metric("Binary confidence", f"{binary['confidence']}%", f"{binary['signal_quality']} quality", delta_color="off")
    col5.metric("Suggested expiry", f"{binary['expiry_minutes']} min", f"auto {binary['recommended_expiry_minutes']} min", delta_color="off")
    col6.metric("RSI (14)", f"{spot['rsi']:.2f}")
    st.caption("Spot Buy/Sell needs 5 of 6 factors; binary CALL/PUT needs 4 of 7. Agreement is not a win probability.")

    st.subheader(f"Live chart · {symbol} · {interval}")
    render_realtime_chart(
        symbol,
        interval,
        candles,
        live_price,
        spot,
        follow_live,
        stream=meta["stream"],
        price_prefix=meta["price_prefix"],
    )
with st.sidebar:
    if "signed_in_email" in st.session_state:
        st.caption(f"AI signed in as {st.session_state['signed_in_email']}")
        if st.button("Sign out"):
            st.session_state.pop("signed_in_email", None)
            st.session_state.pop("messages", None)
            st.rerun()
    else:
        st.caption("Charts and signals are public. Sign in to use the AI assistant.")
    st.divider()
    st.header("Market setup")
    market_class = st.selectbox("Market class", list(ASSET_CLASSES), index=0)
    options = market_options(market_class)
    selection = st.selectbox("Symbol", list(options.keys()) + ["Custom…"], index=0)
    if selection == "Custom…":
        symbol = st.text_input(
            "Custom symbol",
            value="BTC-USD",
            help="Coinbase product (e.g. BTC-USD) or Yahoo ticker (e.g. GC=F, EURUSD=X).",
        )
        asset_class = None
    else:
        symbol = options[selection]
        asset_class = market_class
    interval = st.selectbox("Candle interval", ["1m", "5m", "15m", "1h"], index=1)
    expiry_choice = st.selectbox("Binary expiry", ["Auto", "1", "3", "5", "15"], index=0)
    follow_live = st.checkbox("Follow latest candles", value=True)
    auto_refresh = st.number_input(
        "Auto-refresh seconds (forex/metals)",
        min_value=0,
        max_value=600,
        value=15,
        step=5,
        help="Crypto streams live over WebSocket; forex/metals snapshots auto-refresh on this interval. 0 disables.",
    )

resolved_class = asset_class or asset_class_for(symbol)
st.session_state["active_symbol"] = symbol
st.session_state["active_class"] = resolved_class

if resolved_class == "Crypto":
    render_market(symbol, resolved_class, interval, expiry_choice, follow_live)
elif auto_refresh and hasattr(st, "fragment"):
    st.fragment(run_every=f"{int(auto_refresh)}s")(render_market)(
        symbol, resolved_class, interval, expiry_choice, follow_live
    )
else:
    render_market(symbol, resolved_class, interval, expiry_choice, follow_live)