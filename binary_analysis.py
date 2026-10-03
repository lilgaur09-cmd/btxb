"""BINARYTXBOT analysis engine.

This module turns the shared TRADEXBOT indicator primitives into fixed-time
binary-options signals. A binary contract predicts whether price will be above
(CALL) or below (PUT) the entry price when the contract expires, so the engine
focuses on short-horizon directional confluence, momentum timing, candlestick
rejection, and an expiry horizon that matches current market energy.
"""

from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any, Dict, List

from crypto_analysis import (
    _adx,
    _ema,
    _ema_series,
    _rsi,
    fetch_live_market,
    generate_sample_candles,
    normalize_coinbase_symbol,
)

BINARY_EXPIRIES_MINUTES = (1, 3, 5, 15)
BINARY_SIGNAL_THRESHOLD = 4
BINARY_FACTOR_LABELS = (
    "EMA 9/21 cross",
    "EMA 21/50 trend",
    "MACD momentum",
    "RSI bias",
    "Stochastic cross",
    "Candle momentum",
    "Directional movement",
)

__all__ = [
    "BINARY_EXPIRIES_MINUTES",
    "BINARY_FACTOR_LABELS",
    "BINARY_SIGNAL_THRESHOLD",
    "answer_binary_question",
    "detect_candle_patterns",
    "fetch_binary_market",
    "generate_binary_signal",
    "recommend_expiry",
    "summarize_binary_market",
]


def _stochastic(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = 14,
    smoothing: int = 3,
) -> tuple[float, float, str]:
    if len(closes) < period:
        return 50.0, 50.0, "No fresh cross"

    k_values: List[float] = []
    for index in range(period - 1, len(closes)):
        window_high = max(highs[index - period + 1 : index + 1])
        window_low = min(lows[index - period + 1 : index + 1])
        span = window_high - window_low
        k_values.append(100 * (closes[index] - window_low) / span if span else 50.0)

    smoothed = [
        mean(k_values[max(0, index - smoothing + 1) : index + 1])
        for index in range(len(k_values))
    ]
    stochastic_k = k_values[-1]
    stochastic_d = smoothed[-1]

    cross = "No fresh cross"
    if len(k_values) >= 2:
        previous_k, previous_d = k_values[-2], smoothed[-2]
        if previous_k <= previous_d and stochastic_k > stochastic_d:
            cross = "Bullish cross"
        elif previous_k >= previous_d and stochastic_k < stochastic_d:
            cross = "Bearish cross"
    return round(stochastic_k, 2), round(stochastic_d, 2), cross


def _make_pattern(name: str, bias: int, note: str) -> Dict[str, Any]:
    return {"name": name, "bias": bias, "note": note}


def detect_candle_patterns(candles: List[Dict[str, Any]], lookback: int = 4) -> List[Dict[str, Any]]:
    """Return the most recent classic candlestick patterns with a directional bias."""
    patterns: List[Dict[str, Any]] = []
    if len(candles) < 2:
        return patterns

    recent = candles[-lookback:]
    for index, candle in enumerate(recent):
        open_price = float(candle["open"])
        high = float(candle["high"])
        low = float(candle["low"])
        close = float(candle["close"])
        span = high - low
        if span <= 0:
            continue

        body = abs(close - open_price)
        upper_wick = high - max(open_price, close)
        lower_wick = min(open_price, close) - low
        bullish = close >= open_price

        if body <= 0.1 * span:
            patterns.append(_make_pattern("Doji", 0, "Indecision candle; binary entries usually wait for confirmation."))
        elif lower_wick >= 2 * body and upper_wick <= body and bullish:
            patterns.append(_make_pattern("Hammer", 1, "Long lower wick rejection favors an upside reaction."))
        elif upper_wick >= 2 * body and lower_wick <= body and not bullish:
            patterns.append(_make_pattern("Shooting star", -1, "Long upper wick rejection favors a downside reaction."))
        elif body >= 0.9 * span:
            patterns.append(
                _make_pattern(
                    "Bullish marubozu" if bullish else "Bearish marubozu",
                    1 if bullish else -1,
                    "Wide-range close with minimal rejection favors continuation.",
                )
            )

        if index == 0:
            continue
        previous_open = float(recent[index - 1]["open"])
        previous_close = float(recent[index - 1]["close"])
        previous_bullish = previous_close >= previous_open
        if bullish and not previous_bullish and close >= previous_open and open_price <= previous_close:
            patterns.append(_make_pattern("Bullish engulfing", 1, "Current body engulfs the prior down candle."))
        elif not bullish and previous_bullish and close <= previous_open and open_price >= previous_close:
            patterns.append(_make_pattern("Bearish engulfing", -1, "Current body engulfs the prior up candle."))

    return patterns[-3:]


def recommend_expiry(
    atr_percent: float,
    adx: float,
    allowed: tuple[int, ...] = BINARY_EXPIRIES_MINUTES,
) -> int:
    """Pick an expiry horizon that matches current market energy.

    Stronger per-candle energy (ATR%) and a trending regime (ADX) favor shorter
    expiries; quiet markets need a longer horizon for the move to develop.
    """
    if atr_percent >= 0.30 and adx >= 22:
        target = 1
    elif atr_percent >= 0.18:
        target = 3
    elif atr_percent >= 0.09:
        target = 5
    else:
        target = 15
    options = sorted(allowed)
    return min(options, key=lambda value: (abs(value - target), value))
def summarize_binary_market(
    symbol: str,
    candles: List[Dict[str, Any]],
    live_price: float | None = None,
    interval: str = "1m",
    expiry_minutes: int | None = None,
) -> Dict[str, Any]:
    """Compute a fixed-time binary (CALL/PUT) signal bundle for the candles."""
    closes = [float(candle["close"]) for candle in candles]
    highs = [float(candle["high"]) for candle in candles]
    lows = [float(candle["low"]) for candle in candles]
    volumes = [float(candle["volume"]) for candle in candles]
    if len(closes) < 2:
        raise ValueError("At least two candles are needed to compute a binary signal.")

    price = float(live_price) if live_price and live_price > 0 else closes[-1]
    fast_ema = _ema(closes, 9)
    slow_ema = _ema(closes, 21)
    trend_ema = _ema(closes, 50)
    rsi = _rsi(closes, 14)
    stochastic_k, stochastic_d, stochastic_cross = _stochastic(highs, lows, closes)

    macd_values = [fast - slow for fast, slow in zip(_ema_series(closes, 12), _ema_series(closes, 26))]
    macd = macd_values[-1]
    macd_signal = _ema_series(macd_values, 9)[-1]
    macd_histogram = macd - macd_signal

    true_ranges: List[float] = []
    for index, (high, low) in enumerate(zip(highs, lows)):
        previous_close = closes[index - 1] if index else closes[index]
        true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    atr = mean(true_ranges[-14:])
    atr_percent = atr / price * 100 if price > 0 else 0.0

    bollinger_window = closes[-20:]
    bollinger_middle = mean(bollinger_window)
    band_deviation = pstdev(bollinger_window)
    bollinger_upper = bollinger_middle + 2 * band_deviation
    bollinger_lower = bollinger_middle - 2 * band_deviation
    bollinger_position = (
        (price - bollinger_lower) / (bollinger_upper - bollinger_lower) * 100
        if bollinger_upper > bollinger_lower
        else 50.0
    )

    previous_volumes = volumes[-21:-1]
    volume_baseline = mean(previous_volumes) if previous_volumes else mean(volumes[:-1])
    volume_ratio = volumes[-1] / volume_baseline if volume_baseline > 0 else 0.0

    adx, plus_di, minus_di = _adx(highs, lows, closes, 14)
    market_regime = "Strong trend" if adx >= 25 else "Ranging" if adx < 20 else "Transitioning"

    short_start = closes[max(0, len(closes) - 6)]
    medium_start = closes[max(0, len(closes) - 21)]
    momentum_5 = ((price - short_start) / short_start) * 100 if short_start else 0.0
    momentum_20 = ((price - medium_start) / medium_start) * 100 if medium_start else 0.0
    price_change = ((closes[-1] - closes[-2]) / closes[-2]) * 100 if closes[-2] else 0.0

    patterns = detect_candle_patterns(candles)

    factors = [
        1 if fast_ema > slow_ema else -1 if fast_ema < slow_ema else 0,
        1 if slow_ema > trend_ema else -1 if slow_ema < trend_ema else 0,
        1 if macd_histogram > 0 else -1 if macd_histogram < 0 else 0,
        1 if rsi >= 55 else -1 if rsi <= 45 else 0,
        1 if stochastic_k > stochastic_d else -1 if stochastic_k < stochastic_d else 0,
        1 if closes[-1] > closes[-2] else -1 if closes[-1] < closes[-2] else 0,
        1 if plus_di > minus_di else -1 if minus_di > plus_di else 0,
    ]
    signal_score = sum(factors)
    signal_factor_count = len(factors)
    direction = 1 if signal_score > 0 else -1 if signal_score < 0 else 0

    if signal_score >= BINARY_SIGNAL_THRESHOLD:
        signal = "CALL"
    elif signal_score <= -BINARY_SIGNAL_THRESHOLD:
        signal = "PUT"
    else:
        signal = "NO TRADE"
    bias = "Bullish" if direction > 0 else "Bearish" if direction < 0 else "Neutral"

    supporting_factors = [
        label for label, factor in zip(BINARY_FACTOR_LABELS, factors) if direction and factor == direction
    ]
    opposing_factors = [
        label for label, factor in zip(BINARY_FACTOR_LABELS, factors) if direction and factor == -direction
    ]

    confidence = round(abs(signal_score) / signal_factor_count * 100)
    if market_regime == "Strong trend":
        confidence = min(100, confidence + 4)
    elif market_regime == "Ranging":
        confidence = max(0, confidence - 6)
    signal_quality = "High" if confidence >= 70 else "Medium" if confidence >= 50 else "Low"

    candle_minutes = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}.get(interval, 1)
    recommended_expiry = recommend_expiry(atr_percent, adx)
    effective_expiry = int(expiry_minutes) if expiry_minutes else recommended_expiry
    expected_move_percent = round(
        atr_percent * math.sqrt(max(effective_expiry, candle_minutes) / candle_minutes), 4
    )

    return {
        "symbol": symbol,
        "interval": interval,
        "last_close": round(price, 2),
        "entry_price": round(price, 2),
        "price_change_percent": round(price_change, 2),
        "trend": "Bullish" if fast_ema > slow_ema else "Bearish" if fast_ema < slow_ema else "Neutral",
        "bias": bias,
        "signal": signal,
        "signal_score": signal_score,
        "signal_factor_count": signal_factor_count,
        "confidence": confidence,
        "signal_quality": signal_quality,
        "supporting_factors": supporting_factors,
        "opposing_factors": opposing_factors,
        "expiry_minutes": effective_expiry,
        "recommended_expiry_minutes": recommended_expiry,
        "expected_move_percent": expected_move_percent,
        "rsi": round(rsi, 2),
        "stochastic_k": stochastic_k,
        "stochastic_d": stochastic_d,
        "stochastic_cross": stochastic_cross,
        "ema_fast": round(fast_ema, 2),
        "ema_slow": round(slow_ema, 2),
        "ema_trend": round(trend_ema, 2),
        "macd": round(macd, 8),
        "macd_signal": round(macd_signal, 8),
        "macd_histogram": round(macd_histogram, 8),
        "atr": round(atr, 8),
        "atr_percent": round(atr_percent, 4),
        "bollinger_lower": round(bollinger_lower, 2),
        "bollinger_middle": round(bollinger_middle, 2),
        "bollinger_upper": round(bollinger_upper, 2),
        "bollinger_position": round(bollinger_position, 2),
        "volume_ratio": round(volume_ratio, 4),
        "market_regime": market_regime,
        "adx": round(adx, 2),
        "plus_di": round(plus_di, 2),
        "minus_di": round(minus_di, 2),
        "momentum_5": round(momentum_5, 2),
        "momentum_20": round(momentum_20, 2),
        "support": round(min(lows[-20:]), 2),
        "resistance": round(max(highs[-20:]), 2),
        "patterns": patterns,
    }


def generate_binary_signal(
    symbol: str,
    candles: List[Dict[str, Any]],
    live_price: float | None = None,
    interval: str = "1m",
    expiry_minutes: int | None = None,
) -> Dict[str, Any]:
    """Alias for :func:`summarize_binary_market` using signal-oriented naming."""
    return summarize_binary_market(
        symbol,
        candles,
        live_price=live_price,
        interval=interval,
        expiry_minutes=expiry_minutes,
    )


def fetch_binary_market(
    symbol: str,
    interval: str = "1m",
    limit: int = 180,
) -> tuple[List[Dict[str, Any]], float]:
    """Fetch Coinbase candles and the live quote for the binary signal engine."""
    return fetch_live_market(symbol, interval=interval, limit=limit)
def answer_binary_question(question: str, summary: Dict[str, Any]) -> str:
    """Deterministic, explainable assistant for BINARYTXBOT signals."""
    query = question.casefold()
    direction_word = (
        "CALL (up)"
        if summary["signal"] == "CALL"
        else "PUT (down)"
        if summary["signal"] == "PUT"
        else "no high-confluence entry"
    )

    if "expiry" in query or "duration" in query or "how long" in query:
        return (
            f"Recommended expiry is {summary['recommended_expiry_minutes']} minute(s); the selected contract "
            f"expires in {summary['expiry_minutes']} minute(s). With ATR at {summary['atr_percent']:.2f}% of price, "
            f"the expected move across the window is roughly {summary['expected_move_percent']:.2f}%. Shorter "
            f"expiries need faster moves; longer expiries give a quiet market more time to develop."
        )

    if any(word in query for word in ["confidence", "confiden", "quality", "win", "accuracy", "payout", "probability"]):
        return (
            f"Confidence is {summary['confidence']}% ({summary['signal_quality']}), which measures how many of the "
            f"{summary['signal_factor_count']} indicators agree. It is not a win rate or payout estimate; binary "
            f"payouts are set by the broker and no signal can guarantee a profitable outcome."
        )

    if any(word in query for word in ["pattern", "candle", "engulf", "hammer", "doji", "star"]):
        if not summary["patterns"]:
            return (
                "No classic reversal or continuation candle pattern is present on the last few candles; "
                "rely on the indicator confluence and the requested expiry instead."
            )
        lines = "; ".join(
            f"{item['name']} ({'bullish' if item['bias'] > 0 else 'bearish' if item['bias'] < 0 else 'neutral'}): {item['note']}"
            for item in summary["patterns"]
        )
        return f"Recent candlestick context — {lines}"

    if "rsi" in query:
        state = "overbought" if summary["rsi"] >= 70 else "oversold" if summary["rsi"] <= 30 else "mid-range"
        return (
            f"RSI(14) is {summary['rsi']:.2f} ({state}). In binary trading, a strong RSI with the trend supports "
            f"continuation, while an extreme RSI against the trend is a reversal warning for the selected expiry."
        )

    if "stoch" in query:
        return (
            f"Stochastic %K/%D is {summary['stochastic_k']:.2f}/{summary['stochastic_d']:.2f} with "
            f"{summary['stochastic_cross'].lower()}. It times an entry inside the broader trend, not the trend itself."
        )

    if "macd" in query:
        momentum_state = (
            "positive" if summary["macd_histogram"] > 0 else "negative" if summary["macd_histogram"] < 0 else "flat"
        )
        return (
            f"MACD is {summary['macd']:.4f}, signal {summary['macd_signal']:.4f}, histogram "
            f"{summary['macd_histogram']:.4f} ({momentum_state}). Use it to confirm momentum into the expiry."
        )
    if any(word in query for word in ["atr", "volatility", "risk", "stop"]):
        return (
            f"ATR(14) is ${summary['atr']:.2f}, about {summary['atr_percent']:.2f}% of price per candle, with an "
            f"expected {summary['expected_move_percent']:.2f}% move across the {summary['expiry_minutes']}-minute "
            f"expiry. This describes movement size, not a personalized risk limit."
        )

    if "support" in query:
        return (
            f"Recent support is near ${summary['support']:.2f} from the last 20 candle lows. Holding it with a "
            f"bullish candle supports a CALL; losing it supports a PUT."
        )
    if "resistance" in query:
        return (
            f"Recent resistance is near ${summary['resistance']:.2f} from the last 20 candle highs. Rejection "
            f"there supports a PUT; a sustained break supports a CALL."
        )

    if any(word in query for word in ["regime", "adx", "trend strength"]):
        return (
            f"The regime is {summary['market_regime']}: ADX {summary['adx']:.2f}, +DI {summary['plus_di']:.2f}, "
            f"-DI {summary['minus_di']:.2f}. Strong trends favor continuation contracts; ranging regimes favor "
            f"reversal or no-trade decisions."
        )

    if any(word in query for word in ["call", "put", "signal", "trade", "entry", "take", "buy", "sell"]):
        supporting = ", ".join(summary["supporting_factors"]) or "none strongly"
        opposing = ", ".join(summary["opposing_factors"]) or "none strongly"
        return (
            f"Binary signal is {summary['signal']} ({direction_word}) from {summary['signal_score']:+d}/"
            f"{summary['signal_factor_count']} factor agreement, scored {summary['confidence']}% "
            f"({summary['signal_quality']} quality). Supporting factors: {supporting}. Conflicting factors: "
            f"{opposing}. Regime is {summary['market_regime']} (ADX {summary['adx']:.2f}); MACD histogram "
            f"{summary['macd_histogram']:.4f}; stochastic {summary['stochastic_k']:.1f}/{summary['stochastic_d']:.1f} "
            f"({summary['stochastic_cross'].lower()}). Agreement is not a win probability."
        )

    supporting = ", ".join(summary["supporting_factors"]) or "none strongly"
    return (
        f"{summary['symbol']} is {summary['bias'].lower()} with a {summary['signal']} binary lean "
        f"({summary['signal_score']:+d}/{summary['signal_factor_count']}, {summary['confidence']}% "
        f"{summary['signal_quality']} quality). Suggested expiry {summary['expiry_minutes']} minute(s); RSI "
        f"{summary['rsi']:.2f}; stochastic {summary['stochastic_k']:.1f}/{summary['stochastic_d']:.1f}; MACD "
        f"histogram {summary['macd_histogram']:.4f}; ATR {summary['atr_percent']:.2f}%. Supporting: {supporting}. "
        f"Ask about the signal, expiry, patterns, confidence, RSI, stochastic, MACD, volatility, or levels for detail."
    )