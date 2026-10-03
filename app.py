from pathlib import Path
from typing import Any, Dict, List

import sqlite3
import streamlit as st

from auth import authenticate, create_account
from crypto_analysis import (
    answer_chart_question,
    fetch_live_market,
    summarize_chart,
)
from live_chart import render_realtime_chart


favicon_path = Path(__file__).resolve().parent / "assets" / "tradexbot-favicon.svg"
page_icon = str(favicon_path) if favicon_path.is_file() else "📈"
st.set_page_config(page_title="TRADEXBOT", page_icon=page_icon, layout="wide")
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
    .stTabs [data-baseweb="tab-list"] { gap: 0.4rem; }
    .maker-credit { text-align: right; padding-top: 1.05rem; }
    .maker-credit span { display: block; color: #9fb0c4; font-size: 0.85rem; }
    .maker-credit strong { display: block; color: #f6f8fa; font-size: 1.55rem; font-weight: 700; }
    .brand-logo svg { display: block; width: min(100%, 460px); max-height: 106px; }
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
    @media (max-width: 640px) { .maker-credit { text-align: left; padding-top: 0; } }
    </style>
    """,
    unsafe_allow_html=True,
)

brand_column, maker_column = st.columns([3, 1])
with brand_column:
    logo_path = Path(__file__).resolve().parent / "assets" / "tradexbot-logo.svg"
    if logo_path.is_file():
        logo_svg = logo_path.read_text(encoding="utf-8")
    else:
        logo_svg = """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 700 160" role="img" aria-label="TRADEXBOT">
          <defs><linearGradient id="fallback-green" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#00b88a"/><stop offset="1" stop-color="#00f0aa"/></linearGradient></defs>
          <path d="M20 14h111l-25 24H84v67L59 128V38H20z" fill="#f6f8fa"/>
          <path d="m23 115 35-34 20 17 45-48m-23-1 23-7-5 24" fill="none" stroke="url(#fallback-green)" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>
          <text x="155" y="111" fill="#f6f8fa" font-family="Arial,sans-serif" font-size="61" font-weight="800">TRADE</text>
          <path d="m390 58 38 50m0-50-38 50" fill="none" stroke="#f6f8fa" stroke-width="13" stroke-linecap="round"/>
          <path d="m411 83 17 25m0-50-17 25" fill="none" stroke="url(#fallback-green)" stroke-width="13" stroke-linecap="round"/>
          <text x="445" y="111" fill="url(#fallback-green)" font-family="Arial,sans-serif" font-size="61" font-weight="800">BOT</text>
        </svg>
        """
    st.markdown(
        f'<h1 class="sr-only">TRADEXBOT</h1><div class="brand-logo" role="img" aria-label="TRADEXBOT">{logo_svg}</div>',
        unsafe_allow_html=True,
    )
    st.caption("Live crypto charts, market signals, and AI analysis")
with maker_column:
    st.markdown(
        '<div class="maker-credit"><span>DEVELOPED BY</span><strong>AtharvX</strong></div>',
        unsafe_allow_html=True,
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
    st.header("Chart setup")
    symbol = st.text_input("Crypto symbol", value="BTC-USD")
    interval = st.selectbox("Candles interval", ["1m", "5m", "15m", "1h"], index=1)
    follow_live = st.checkbox("Follow latest candles", value=True)


try:
    initial_candles, initial_live_price = fetch_live_market(symbol, interval=interval, limit=180)
except RuntimeError as error:
    st.error(str(error))
    st.stop()

if initial_live_price and initial_live_price > 0:
    current_candle = initial_candles[-1]
    current_candle["close"] = initial_live_price
    current_candle["high"] = max(float(current_candle["high"]), initial_live_price)
    current_candle["low"] = min(float(current_candle["low"]), initial_live_price)
initial_summary = summarize_chart(
    symbol,
    initial_candles,
    live_price=initial_live_price if initial_live_price and initial_live_price > 0 else None,
)

st.session_state["current_summary"] = initial_summary

st.subheader(f"{symbol} market overview")
col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Price at load", f"${initial_summary['last_close']:.2f}", f"{initial_summary['price_change_percent']:+.2f}%")
col2.metric("Trend", initial_summary["trend"])
col3.metric(
    "Signal",
    initial_summary["signal"],
    f"{initial_summary['signal_strength']}% agreement · {initial_summary['signal_score']:+d}/6",
    delta_color="off",
)
col4.metric("RSI (14)", f"{initial_summary['rsi']:.2f}")
col5.metric("Support", f"${initial_summary['support']:.2f}")
col6.metric("Resistance", f"${initial_summary['resistance']:.2f}")
st.caption("Buy/Sell requires at least 5 of 6 factors to agree. Agreement is not a win probability; no signal guarantees profit.")
with st.expander("More market context", expanded=False):
    context1, context2, context3, context4, context5, context6 = st.columns(6)
    context1.metric("MACD histogram", f"{initial_summary['macd_histogram']:.4f}")
    context2.metric("ATR (14)", f"{initial_summary['atr_percent']:.2f}% of price")
    context3.metric("Volume vs baseline", f"{initial_summary['volume_ratio']:.2f}x")
    context4.metric("Bollinger position", f"{initial_summary['bollinger_position']:.1f}%")
    context5.metric("Regime · ADX (14)", f"{initial_summary['market_regime']} · {initial_summary['adx']:.1f}")
    context6.metric("Directional movement", f"+DI {initial_summary['plus_di']:.1f} / -DI {initial_summary['minus_di']:.1f}")
st.write(
    f"The loaded {symbol} candle history shows a {initial_summary['trend'].lower()} bias with RSI "
    f"{initial_summary['rsi']:.2f}. Regime is {initial_summary['market_regime']} (ADX "
    f"{initial_summary['adx']:.1f}). Support is ${initial_summary['support']:.2f} and resistance is "
    f"${initial_summary['resistance']:.2f}."
)

st.subheader(f"Live chart · {symbol} · {interval}")
render_realtime_chart(symbol, interval, initial_candles, initial_live_price, initial_summary, follow_live)

st.subheader("AI market assistant")
if "signed_in_email" not in st.session_state:
    st.info("Charts and signals are available without an account. Sign in to ask the AI assistant.")
    sign_in_tab, create_account_tab = st.tabs(["Sign in", "Create account"])

    with sign_in_tab:
        with st.form("sign_in_form"):
            login_email = st.text_input("Email address", key="login_email")
            login_password = st.text_input("Password", type="password", key="login_password")
            sign_in_submitted = st.form_submit_button("Sign in", type="primary")

        if sign_in_submitted:
            try:
                signed_in_email = authenticate(login_email, login_password)
            except (OSError, sqlite3.Error):
                st.error("Sign-in is temporarily unavailable. Check the account database configuration.")
            else:
                if signed_in_email:
                    st.session_state["signed_in_email"] = signed_in_email
                    st.rerun()
                else:
                    st.error("Email or password is incorrect.")

    with create_account_tab:
        st.caption("Use a valid email address and a password between 10 and 128 characters.")
        with st.form("create_account_form"):
            new_email = st.text_input("Email address", key="new_email")
            new_password = st.text_input("Password", type="password", key="new_password")
            confirm_password = st.text_input("Confirm password", type="password", key="confirm_password")
            create_submitted = st.form_submit_button("Create account", type="primary")

        if create_submitted:
            if new_password != confirm_password:
                st.error("Passwords do not match.")
            else:
                try:
                    create_account(new_email, new_password)
                except ValueError as error:
                    st.error(str(error))
                except (OSError, sqlite3.Error):
                    st.error("Account creation is temporarily unavailable. Check the account database configuration.")
                else:
                    st.success("Account created. Sign in to continue.")
else:
    st.caption(f"AI assistant ready for {st.session_state['signed_in_email']}.")
    if "messages" not in st.session_state:
        st.session_state.messages = []

    suggestions = st.columns(4)
    suggested_question = None
    for column, label, question in zip(
        suggestions,
        ["Explain the signal", "Check momentum", "Market regime", "Map scenarios"],
        ["Explain the current signal", "Compare momentum indicators", "Explain the ADX regime", "Show conditional scenarios"],
    ):
        if column.button(label, key=f"ai_suggestion_{label}"):
            suggested_question = question

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = suggested_question or st.chat_input("Ask about trend, MACD, volatility, levels, scenarios, or risk")
    if prompt:
        summary = st.session_state.get("current_summary")
        if summary is None:
            st.warning("Live chart data is not available yet.")
        else:
            response = answer_chart_question(prompt, summary)
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()

st.markdown(
    """
    > **Disclaimer:** All AI-generated market sentiments, buy/sell signals, and technical analysis (including support/resistance levels) are for educational and informational purposes only. This app does not provide financial or investment advice. Crypto trading involves substantial risk of loss. Past performance of this AI model is not indicative of future market results. **The developer assumes no responsibility or liability for any trading losses, software errors, or data delays.** Use at your own risk.
    """
)

