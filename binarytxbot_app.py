from pathlib import Path

import sqlite3

import streamlit as st

from auth import authenticate, create_account
from binary_analysis import answer_binary_question, fetch_binary_market, summarize_binary_market
from live_chart import render_realtime_chart


favicon_path = Path(__file__).resolve().parent / "assets" / "binarytxbot-favicon.svg"
page_icon = str(favicon_path) if favicon_path.is_file() else "🎯"
st.set_page_config(page_title="BINARYTXBOT", page_icon=page_icon, layout="wide")
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
    .signal-card { border-radius: 10px; padding: 1rem 1.25rem; margin: 0.2rem 0 0.7rem; border: 1px solid #273449; background: #111a2b; }
    .signal-card .headline { font-size: 2rem; font-weight: 800; letter-spacing: 0.5px; }
    .signal-call .headline { color: #16c784; }
    .signal-put .headline { color: #ea3943; }
    .signal-wait .headline { color: #f4c430; }
    .signal-card .line { color: #cbd5e1; font-size: 1rem; margin-top: 0.2rem; }
    .signal-card .note { color: #9fb0c4; font-size: 0.9rem; margin-top: 0.35rem; }
    @media (max-width: 640px) { .maker-credit { text-align: left; padding-top: 0; } }
    </style>
    """,
    unsafe_allow_html=True,
)

brand_column, maker_column = st.columns([3, 1])
with brand_column:
    logo_path = Path(__file__).resolve().parent / "assets" / "binarytxbot-logo.svg"
    if logo_path.is_file():
        logo_svg = logo_path.read_text(encoding="utf-8")
    else:
        logo_svg = "".join(
            [
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 160" role="img" aria-label="BINARYTXBOT">',
                '<defs><linearGradient id="fb-green" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#00b88a"/><stop offset="1" stop-color="#00f0aa"/></linearGradient></defs>',
                '<path d="M18 118 44 66l20 22L96 32" fill="none" stroke="url(#fb-green)" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>',
                '<path d="M80 32h18v18" fill="none" stroke="url(#fb-green)" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>',
                '<text x="118" y="112" fill="#f6f8fa" font-family="Arial,sans-serif" font-size="62" font-weight="800">BINARY</text>',
                '<text x="352" y="112" fill="url(#fb-green)" font-family="Arial,sans-serif" font-size="62" font-weight="800">BOT</text>',
                '<path d="M312 108 330 78l18 30z" fill="url(#fb-green)"/>',
                '<path d="M312 40 330 70l18-30z" fill="#ff6b7a"/>',
                "</svg>",
            ]
        )
    st.markdown(
        f'<h1 class="sr-only">BINARYTXBOT</h1><div class="brand-logo" role="img" aria-label="BINARYTXBOT">{logo_svg}</div>',
        unsafe_allow_html=True,
    )
    st.caption("Fixed-time binary CALL/PUT signals, momentum timing, and an explainable AI assistant")
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
        st.caption("Signals are public. Sign in to use the AI assistant.")
    st.divider()
    st.header("Binary setup")
    symbol = st.text_input("Market symbol", value="BTC-USD")
    interval = st.selectbox("Candle interval", ["1m", "5m", "15m", "1h"], index=1)
    expiry_choice = st.selectbox("Preferred expiry", ["Auto", "1", "3", "5", "15"], index=0)
    follow_live = st.checkbox("Follow latest candles", value=True)


try:
    candles, live_price = fetch_binary_market(symbol, interval=interval, limit=180)
except RuntimeError as error:
    st.error(str(error))
    st.stop()

if live_price and live_price > 0:
    current_candle = candles[-1]
    current_candle["close"] = live_price
    current_candle["high"] = max(float(current_candle["high"]), live_price)
    current_candle["low"] = min(float(current_candle["low"]), live_price)

summary = summarize_binary_market(
    symbol,
    candles,
    live_price=live_price if live_price and live_price > 0 else None,
    interval=interval,
    expiry_minutes=int(expiry_choice) if expiry_choice != "Auto" else None,
)
st.session_state["current_summary"] = summary

card_class = (
    "signal-call"
    if summary["signal"] == "CALL"
    else "signal-put"
    if summary["signal"] == "PUT"
    else "signal-wait"
)
st.markdown(
    f"""<div class="signal-card {card_class}">
    <div class="headline">{summary['signal']} · {summary['bias']}</div>
    <div class="line">Entry {summary['entry_price']:.2f} · Expiry {summary['expiry_minutes']} min · Expected move ±{summary['expected_move_percent']:.2f}%</div>
    <div class="note">{summary['confidence']}% factor agreement · {summary['signal_quality']} quality · {summary['market_regime']} (ADX {summary['adx']:.1f})</div>
    </div>""",
    unsafe_allow_html=True,
)

st.subheader(f"{symbol} binary setup")
col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Price at load", f"${summary['last_close']:.2f}", f"{summary['price_change_percent']:+.2f}%")
col2.metric("Binary signal", summary["signal"], summary["bias"], delta_color="off")
col3.metric("Confidence", f"{summary['confidence']}%", f"{summary['signal_quality']} quality", delta_color="off")
col4.metric("Suggested expiry", f"{summary['expiry_minutes']} min", f"auto {summary['recommended_expiry_minutes']} min", delta_color="off")
col5.metric("RSI (14)", f"{summary['rsi']:.2f}")
col6.metric("Regime · ADX", summary["market_regime"], f"{summary['adx']:.1f}", delta_color="off")
st.caption(
    "A CALL/PUT needs at least 4 of 7 factors to agree; otherwise BINARYTXBOT returns NO TRADE. "
    "Agreement is not a win probability and no signal guarantees a profitable expiry."
)
with st.expander("More indicator context", expanded=False):
    context1, context2, context3, context4, context5, context6 = st.columns(6)
    context1.metric("Stochastic %K / %D", f"{summary['stochastic_k']:.1f} / {summary['stochastic_d']:.1f}", summary["stochastic_cross"], delta_color="off")
    context2.metric("MACD histogram", f"{summary['macd_histogram']:.4f}")
    context3.metric("ATR (14)", f"{summary['atr_percent']:.2f}% of price")
    context4.metric("Volume vs baseline", f"{summary['volume_ratio']:.2f}x")
    context5.metric("Bollinger position", f"{summary['bollinger_position']:.1f}%")
    context6.metric("Directional movement", f"+DI {summary['plus_di']:.1f} / -DI {summary['minus_di']:.1f}")

    if summary["patterns"]:
        for pattern in summary["patterns"]:
            bias_label = "Bullish" if pattern["bias"] > 0 else "Bearish" if pattern["bias"] < 0 else "Neutral"
            st.write(f"**{pattern['name']}** · {bias_label} — {pattern['note']}")
    else:
        st.write("No classic candlestick pattern is present on the last few candles.")

    st.write(
        f"Support ${summary['support']:.2f} · Resistance ${summary['resistance']:.2f} · "
        f"5-candle momentum {summary['momentum_5']:+.2f}% · 20-candle momentum {summary['momentum_20']:+.2f}%"
    )

st.subheader(f"Live chart · {symbol} · {interval}")
render_realtime_chart(symbol, interval, candles, live_price, summary, follow_live)
st.subheader("BINARYTXBOT AI assistant")
if "signed_in_email" not in st.session_state:
    st.info("Signals are public. Sign in to ask the binary assistant.")
    sign_in_tab, create_account_tab = st.tabs(["Sign in", "Create account"])

    with sign_in_tab:
        with st.form("binary_sign_in_form"):
            login_email = st.text_input("Email address", key="binary_login_email")
            login_password = st.text_input("Password", type="password", key="binary_login_password")
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
        with st.form("binary_create_account_form"):
            new_email = st.text_input("Email address", key="binary_new_email")
            new_password = st.text_input("Password", type="password", key="binary_new_password")
            confirm_password = st.text_input("Confirm password", type="password", key="binary_confirm_password")
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
        ["Explain the signal", "Best expiry", "Candle patterns", "Confidence check"],
        [
            "Explain the current binary signal",
            "Which expiry should I use?",
            "Show recent candle patterns",
            "How confident is this signal?",
        ],
    ):
        if column.button(label, key=f"binary_suggestion_{label}"):
            suggested_question = question

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = suggested_question or st.chat_input(
        "Ask about the signal, expiry, patterns, confidence, stochastic, or risk"
    )
    if prompt:
        current_summary = st.session_state.get("current_summary")
        if current_summary is None:
            st.warning("Market data is not available yet.")
        else:
            response = answer_binary_question(prompt, current_summary)
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()

st.markdown(
    """
    > **Disclaimer:** BINARYTXBOT. All AI-generated binary CALL/PUT signals, expiry suggestions, candlestick
    > patterns, confidence scores, and technical analysis are for educational and informational purposes only.
    > This app does not provide financial or investment advice. Binary options and crypto trading involve a
    > substantial risk of loss and broker payouts are set by the broker. Past signal behaviour is not indicative
    > of future results. **The developer assumes no responsibility or liability for any trading losses, software
    > errors, or data delays.** Use at your own risk.
    """
)