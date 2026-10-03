from __future__ import annotations

import math
import random
from statistics import mean, pstdev
from typing import Any, Dict, List

import requests

COINBASE_BASE_URL = "https://api.exchange.coinbase.com"


def normalize_coinbase_symbol(symbol: str) -> str:
    cleaned = symbol.strip().upper().replace("/", "-")
    if cleaned.endswith("-USDT"):
        return cleaned[:-5] + "-USD"
    if "-" in cleaned:
        return cleaned
    if cleaned.endswith("USDT"):
        return cleaned[:-4] + "-USD"
    if cleaned.endswith("USD"):
        return cleaned[:-3] + "-USD"
    return cleaned


def _fetch_coinbase_price(symbol: str) -> float:
    product = normalize_coinbase_symbol(symbol)
    response = requests.get(f"{COINBASE_BASE_URL}/products/{product}/ticker", timeout=10)
    response.raise_for_status()
    return float(response.json()["price"])


def _fetch_coinbase_klines(symbol: str, interval: str, limit: int) -> List[Dict[str, Any]]:
    granularity = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}[interval]
    product = normalize_coinbase_symbol(symbol)
    response = requests.get(
        f"{COINBASE_BASE_URL}/products/{product}/candles",
        params={"granularity": granularity},
        timeout=10,
    )
    response.raise_for_status()
    rows = sorted(response.json(), key=lambda item: item[0])[-limit:]
    if not rows:
        raise ValueError("No candles returned")
    return [
        {
            "time": int(item[0]) * 1000,
            "low": float(item[1]),
            "high": float(item[2]),
            "open": float(item[3]),
            "close": float(item[4]),
            "volume": float(item[5]),
        }
        for item in rows
    ]


def fetch_live_market(
    symbol: str,
    interval: str = "1m",
    limit: int = 200,
) -> tuple[List[Dict[str, Any]], float]:
    """Fetch Coinbase candles and quote from the same market source."""
    try:
        candles = _fetch_coinbase_klines(symbol, interval, limit)
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as error:
        raise RuntimeError(f"Live market data unavailable for {symbol}: {error}") from error

    try:
        live_price = _fetch_coinbase_price(symbol)
    except (requests.RequestException, KeyError, TypeError, ValueError):
        live_price = float(candles[-1]["close"])
    return candles, live_price


def fetch_live_price(symbol: str) -> float:
    try:
        return _fetch_coinbase_price(symbol)
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return 0.0


def fetch_live_klines(symbol: str, interval: str = "1m", limit: int = 200) -> List[Dict[str, Any]]:
    try:
        return _fetch_coinbase_klines(symbol, interval, limit)
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as error:
        raise RuntimeError(f"Live market data unavailable for {symbol}: {error}") from error


def generate_sample_candles(symbol: str, periods: int = 90, start_price: float = 42000.0) -> List[Dict[str, float | str | int]]:
    random.seed(hash(symbol) % 2**32)
    candles: List[Dict[str, float | str | int]] = []
    price = float(start_price)
    for i in range(periods):
        drift = 0.0009 if i % 3 == 0 else -0.0005
        change = (drift + random.uniform(-0.010, 0.010)) * price
        open_price = price
        close = max(1.0, open_price + change)
        high = max(open_price, close) * random.uniform(1.0015, 1.019)
        low = min(open_price, close) * random.uniform(0.983, 0.998)
        volume = int(random.uniform(1400, 8000) * (1 + abs(change) / max(price, 1)))
        candles.append({
            "time": f"-{periods - i}",
            "open": round(open_price, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close, 2),
            "volume": volume,
        })
        price = close
    return candles


def _ema(values: List[float], period: int) -> float:
    if not values:
        return 0.0
    multiplier = 2 / (period + 1)
    ema = values[0]
    for value in values[1:]:
        ema = (value - ema) * multiplier + ema
    return ema


def _ema_series(values: List[float], period: int) -> List[float]:
    if not values:
        return []
    multiplier = 2 / (period + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append(result[-1] + multiplier * (value - result[-1]))
    return result


def _rsi(values: List[float], period: int = 14) -> float:
    if len(values) < period + 1:
        return 50.0
    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(delta, 0) for delta in deltas[-period:]]
    losses = [abs(min(delta, 0)) for delta in deltas[-period:]]
    avg_gain = sum(gains) / len(gains)
    avg_loss = sum(losses) / len(losses)
    if avg_loss == 0:
        return 100.0
    return round(100 - (100 / (1 + avg_gain / avg_loss)), 2)


def _adx(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> tuple[float, float, float]:
    true_ranges: List[float] = []
    positive_moves: List[float] = []
    negative_moves: List[float] = []
    for index in range(1, len(closes)):
        upward_move = highs[index] - highs[index - 1]
        downward_move = lows[index - 1] - lows[index]
        true_ranges.append(
            max(
                highs[index] - lows[index],
                abs(highs[index] - closes[index - 1]),
                abs(lows[index] - closes[index - 1]),
            )
        )
        positive_moves.append(upward_move if upward_move > downward_move and upward_move > 0 else 0.0)
        negative_moves.append(downward_move if downward_move > upward_move and downward_move > 0 else 0.0)

    if not true_ranges:
        return 0.0, 0.0, 0.0

    warmup = min(period, len(true_ranges))
    smoothed_range = sum(true_ranges[:warmup])
    smoothed_positive = sum(positive_moves[:warmup])
    smoothed_negative = sum(negative_moves[:warmup])
    dx_values: List[float] = []

    for index in range(warmup - 1, len(true_ranges)):
        if index >= warmup:
            smoothed_range += true_ranges[index] - smoothed_range / period
            smoothed_positive += positive_moves[index] - smoothed_positive / period
            smoothed_negative += negative_moves[index] - smoothed_negative / period
        if smoothed_range <= 0:
            positive_di = negative_di = 0.0
        else:
            positive_di = 100 * smoothed_positive / smoothed_range
            negative_di = 100 * smoothed_negative / smoothed_range
        denominator = positive_di + negative_di
        dx_values.append(100 * abs(positive_di - negative_di) / denominator if denominator else 0.0)

    adx = mean(dx_values[:period])
    for dx in dx_values[period:]:
        adx = (adx * (period - 1) + dx) / period
    return adx, positive_di, negative_di


def summarize_chart(symbol: str, candles: List[Dict[str, Any]], live_price: float | None = None) -> Dict[str, Any]:
    closes = [float(candle["close"]) for candle in candles]
    highs = [float(candle["high"]) for candle in candles]
    lows = [float(candle["low"]) for candle in candles]
    volumes = [int(candle["volume"]) for candle in candles]
    if len(closes) < 2:
        raise ValueError("A chart needs at least two candles to compute analysis.")

    fast_ema = _ema(closes, 9)
    slow_ema = _ema(closes, 21)
    trend_ema = _ema(closes, 50)
    rsi = _rsi(closes, 14)
    momentum = ((closes[-1] - closes[0]) / closes[0]) * 100
    price_change = ((closes[-1] - closes[-2]) / closes[-2]) * 100
    short_start = closes[max(0, len(closes) - 6)]
    medium_start = closes[max(0, len(closes) - 21)]
    momentum_5 = ((closes[-1] - short_start) / short_start) * 100
    momentum_20 = ((closes[-1] - medium_start) / medium_start) * 100
    current_price = live_price if live_price and live_price > 0 else closes[-1]

    macd_values = [
        fast - slow
        for fast, slow in zip(_ema_series(closes, 12), _ema_series(closes, 26))
    ]
    macd_signal_values = _ema_series(macd_values, 9)
    macd = macd_values[-1]
    macd_signal = macd_signal_values[-1]
    macd_histogram = macd - macd_signal

    true_ranges = []
    for index, (high, low) in enumerate(zip(highs, lows)):
        previous_close = closes[index - 1] if index else closes[index]
        true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    atr = mean(true_ranges[-14:])
    atr_percent = atr / current_price * 100 if current_price > 0 else 0.0

    bollinger_window = closes[-20:]
    bollinger_middle = mean(bollinger_window)
    band_deviation = pstdev(bollinger_window)
    bollinger_upper = bollinger_middle + 2 * band_deviation
    bollinger_lower = bollinger_middle - 2 * band_deviation
    bollinger_width_percent = (
        (bollinger_upper - bollinger_lower) / bollinger_middle * 100
        if bollinger_middle > 0
        else 0.0
    )
    bollinger_position = (
        (current_price - bollinger_lower) / (bollinger_upper - bollinger_lower) * 100
        if bollinger_upper > bollinger_lower
        else 50.0
    )

    previous_volumes = volumes[-21:-1]
    volume_baseline = mean(previous_volumes) if previous_volumes else mean(volumes[:-1])
    volume_ratio = volumes[-1] / volume_baseline if volume_baseline > 0 else 0.0
    adx, plus_di, minus_di = _adx(highs, lows, closes, 14)
    market_regime = "Strong trend" if adx >= 25 else "Ranging" if adx < 20 else "Transitioning"
    trend = "Bullish" if fast_ema > slow_ema else "Bearish" if fast_ema < slow_ema else "Neutral"
    sentiment = "Bullish" if rsi > 60 else "Bearish" if rsi < 40 else "Neutral"
    returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    volatility = pstdev(returns) * 100 if len(returns) > 1 else 0.0

    signal_factor_labels = ["EMA 9/21", "MACD", "Price vs EMA 50", "RSI", "20-candle momentum", "Directional movement"]
    signal_factors = [
        1 if fast_ema > slow_ema else -1 if fast_ema < slow_ema else 0,
        1 if macd_histogram > 0 else -1 if macd_histogram < 0 else 0,
        1 if current_price > trend_ema else -1 if current_price < trend_ema else 0,
        1 if rsi >= 55 else -1 if rsi <= 45 else 0,
        1 if momentum_20 > 0 else -1 if momentum_20 < 0 else 0,
        1 if plus_di > minus_di else -1 if minus_di > plus_di else 0,
    ]
    signal_score = sum(signal_factors)
    signal_factor_count = len(signal_factors)
    signal = "Buy" if signal_score >= 5 else "Sell" if signal_score <= -5 else "Hold"
    signal_strength = round(abs(signal_score) / signal_factor_count * 100)
    signal_direction = 1 if signal_score > 0 else -1 if signal_score < 0 else 0
    supporting_factors = [
        label for label, factor in zip(signal_factor_labels, signal_factors)
        if signal_direction and factor == signal_direction
    ]
    opposing_factors = [
        label for label, factor in zip(signal_factor_labels, signal_factors)
        if signal_direction and factor == -signal_direction
    ]
    return {
        "symbol": symbol,
        "trend": trend,
        "sentiment": sentiment,
        "signal": signal,
        "support": round(min(lows[-20:]), 2),
        "resistance": round(max(highs[-20:]), 2),
        "volatility": round(volatility, 4),
        "rsi": round(rsi, 2),
        "ema_fast": round(fast_ema, 2),
        "ema_slow": round(slow_ema, 2),
        "ema_trend": round(trend_ema, 2),
        "macd": round(macd, 8),
        "macd_signal": round(macd_signal, 8),
        "macd_histogram": round(macd_histogram, 8),
        "atr": round(atr, 8),
        "atr_percent": round(atr_percent, 4),
        "bollinger_lower": round(bollinger_lower, 8),
        "bollinger_middle": round(bollinger_middle, 8),
        "bollinger_upper": round(bollinger_upper, 8),
        "bollinger_width_percent": round(bollinger_width_percent, 4),
        "bollinger_position": round(bollinger_position, 2),
        "volume_ratio": round(volume_ratio, 4),
        "signal_score": signal_score,
        "signal_factor_count": signal_factor_count,
        "signal_strength": signal_strength,
        "supporting_factors": supporting_factors,
        "opposing_factors": opposing_factors,
        "adx": round(adx, 2),
        "plus_di": round(plus_di, 2),
        "minus_di": round(minus_di, 2),
        "market_regime": market_regime,
        "momentum_percent": round(momentum, 2),
        "momentum_5": round(momentum_5, 2),
        "momentum_20": round(momentum_20, 2),
        "last_close": round(live_price if live_price and live_price > 0 else closes[-1], 2),
        "avg_volume": int(sum(volumes[-10:]) / max(len(volumes[-10:]), 1)),
        "price_change_percent": round(price_change, 2),
    }


def answer_chart_question(question: str, summary: Dict[str, Any]) -> str:
    q = question.casefold()
    signal_score = summary["signal_score"]
    direction = "bullish" if signal_score > 0 else "bearish" if signal_score < 0 else "mixed"

    if "macd" in q:
        momentum_state = "positive" if summary["macd_histogram"] > 0 else "negative" if summary["macd_histogram"] < 0 else "near its signal line"
        return (
            f"MACD is {summary['macd']:.4f}, its signal line is {summary['macd_signal']:.4f}, "
            f"and its histogram is {summary['macd_histogram']:.4f} ({momentum_state}). "
            f"Use it as momentum confirmation alongside price structure, not as a standalone entry signal."
        )

    if any(word in q for word in ["bollinger", "bands", "squeeze"]):
        return (
            f"The 20-period Bollinger range is ${summary['bollinger_lower']:.2f} to "
            f"${summary['bollinger_upper']:.2f}. Price is at {summary['bollinger_position']:.1f}% "
            f"of the band, with {summary['bollinger_width_percent']:.2f}% width. A band touch alone "
            f"does not confirm a reversal."
        )

    if any(word in q for word in ["volume", "participation"]):
        return (
            f"The latest candle volume is {summary['volume_ratio']:.2f}x its recent baseline. "
            f"Higher-than-usual volume can confirm a move; a breakout on low volume deserves more caution."
        )

    if any(word in q for word in ["adx", "regime", "trend strength", "ranging"]):
        directional_bias = "buyers" if summary["plus_di"] > summary["minus_di"] else "sellers" if summary["minus_di"] > summary["plus_di"] else "neither side"
        return (
            f"The market regime reads {summary['market_regime']} with ADX(14) at {summary['adx']:.2f}. "
            f"+DI is {summary['plus_di']:.2f} and -DI is {summary['minus_di']:.2f}, so {directional_bias} "
            f"currently have directional movement advantage. ADX measures trend strength, not direction or certainty."
        )

    if any(word in q for word in ["atr", "risk", "stop", "volatility"]):
        return (
            f"ATR(14) is ${summary['atr']:.2f}, around {summary['atr_percent']:.2f}% of price per candle; "
            f"recent log-return volatility is {summary['volatility']:.4f}%. These describe market movement, "
            f"not a personalized stop or risk recommendation."
        )

    if "support" in q:
        return (
            f"Recent support is around ${summary['support']:.2f}, based on the last 20 candle lows. "
            f"A reaction with confirming volume is more informative than a level touch alone."
        )
    if "resistance" in q:
        return (
            f"Recent resistance is around ${summary['resistance']:.2f}, based on the last 20 candle highs. "
            f"A sustained close and follow-through matter more than a brief wick above the level."
        )
    if "rsi" in q:
        condition = (
            "above the common 70 overbought threshold" if summary["rsi"] >= 70
            else "below the common 30 oversold threshold" if summary["rsi"] <= 30
            else "between the common 30/70 thresholds"
        )
        return (
            f"RSI(14) is {summary['rsi']:.2f}, {condition}. RSI can stay extreme in a strong trend, "
            f"so check whether price structure and volume confirm it."
        )

    if any(word in q for word in ["buy", "sell", "trade", "signal"]):
        supporting = ", ".join(summary["supporting_factors"]) or "none strongly"
        opposing = ", ".join(summary["opposing_factors"]) or "none strongly"
        return (
            f"Indicator confluence is {summary['signal']} ({signal_score:+d}/6; "
            f"{summary['signal_strength']}% directional agreement, not win probability). Supporting factors: "
            f"{supporting}. Conflicting factors: {opposing}. Regime is {summary['market_regime']} "
            f"(ADX {summary['adx']:.2f}); MACD histogram {summary['macd_histogram']:.4f}; RSI "
            f"{summary['rsi']:.2f}; 20-candle momentum {summary['momentum_20']:+.2f}%. This is analysis, not a trade instruction."
        )

    if any(word in q for word in ["scenario", "outlook", "forecast", "next move", "breakout"]):
        return (
            f"Scenario map for {summary['symbol']}: a sustained close above ${summary['resistance']:.2f} with "
            f"above-baseline volume would strengthen the upside case; a loss of ${summary['support']:.2f} would "
            f"weaken it. Current direction is {direction}; regime is {summary['market_regime']} "
            f"(ADX {summary['adx']:.2f}); ATR is {summary['atr_percent']:.2f}% of price. These are conditional levels, not predictions."
        )

    return (
        f"{summary['symbol']} is {summary['trend'].lower()} by EMA structure, with {direction} indicator "
        f"confluence ({signal_score:+d}/6). Regime is {summary['market_regime']} (ADX {summary['adx']:.2f}); "
        f"RSI is {summary['rsi']:.2f}; MACD histogram is "
        f"{summary['macd_histogram']:.4f}; 5/20-candle momentum is {summary['momentum_5']:+.2f}% / "
        f"{summary['momentum_20']:+.2f}%; ATR is {summary['atr_percent']:.2f}% of price; volume is "
        f"{summary['volume_ratio']:.2f}x baseline. Recent support is ${summary['support']:.2f} and "
        f"resistance is ${summary['resistance']:.2f}. Ask about MACD, ATR, volume, Bollinger bands, RSI, "
        f"levels, or scenarios for more detail."
    )
