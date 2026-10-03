"""TXBOT unified market data provider.

Serves candles and a live quote for three asset classes and returns the same
candle shape used everywhere else in the project:

    {"time": ms, "open": float, "high": float, "low": float, "close": float, "volume": float}

- Crypto: Coinbase public Exchange API (supports live WebSocket streaming).
- Forex:  Yahoo Finance intraday chart API (snapshot data).
- Metals: Yahoo Finance intraday chart API (snapshot data).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import requests

from crypto_analysis import (
    _fetch_coinbase_klines,
    _fetch_coinbase_price,
    generate_sample_candles,
    normalize_coinbase_symbol,
)

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
YAHOO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) TXBOT/1.0",
    "Accept": "application/json,text/plain,*/*",
}

INTERVAL_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}
_YAHOO_INTERVAL = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "60m"}
_YAHOO_RANGE = {"1m": "2d", "5m": "5d", "15m": "1mo", "1h": "3mo"}

CRYPTO_MARKETS = [
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
    "XRP-USD",
    "ADA-USD",
    "DOGE-USD",
    "AVAX-USD",
    "LINK-USD",
    "DOT-USD",
    "LTC-USD",
    "BCH-USD",
    "UNI-USD",
]

FOREX_MARKETS = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "USD/CHF": "USDCHF=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "USDCAD=X",
    "NZD/USD": "NZDUSD=X",
    "EUR/GBP": "EURGBP=X",
    "EUR/JPY": "EURJPY=X",
    "GBP/JPY": "GBPJPY=X",
    "AUD/JPY": "AUDJPY=X",
    "USD/INR": "USDINR=X",
    "USD/CNY": "USDCNY=X",
}

METAL_MARKETS = {
    "Gold (XAU/USD)": "GC=F",
    "Silver (XAG/USD)": "SI=F",
    "Platinum (XPT/USD)": "PL=F",
    "Palladium (XPD/USD)": "PA=F",
    "Copper (HG)": "HG=F",
}

ASSET_CLASSES = ("Crypto", "Forex", "Metals")
YAHOO_LABELS = {**FOREX_MARKETS, **METAL_MARKETS}
YAHOO_SYMBOLS = set(YAHOO_LABELS.values())

__all__ = [
    "ASSET_CLASSES",
    "CRYPTO_MARKETS",
    "FOREX_MARKETS",
    "INTERVAL_SECONDS",
    "METAL_MARKETS",
    "asset_class_for",
    "fetch_market",
    "market_options",
]


def asset_class_for(symbol: str) -> str:
    """Best-effort asset-class detection from a symbol string."""
    cleaned = symbol.strip().upper()
    if cleaned in set(METAL_MARKETS.values()) or cleaned.endswith("=F"):
        return "Metals"
    if cleaned in set(FOREX_MARKETS.values()) or cleaned.endswith("=X"):
        return "Forex"
    return "Crypto"


def market_options(asset_class: str) -> Dict[str, str]:
    """Return an ordered {label: provider_symbol} map for a sidebar picker."""
    if asset_class == "Forex":
        return dict(FOREX_MARKETS)
    if asset_class == "Metals":
        return dict(METAL_MARKETS)
    return {symbol: symbol for symbol in CRYPTO_MARKETS}
def _fetch_yahoo_candles(symbol: str, interval: str, limit: int) -> Tuple[List[Dict[str, Any]], float]:
    """Fetch intraday candles and a quote from the Yahoo Finance chart API."""
    if interval not in _YAHOO_INTERVAL:
        raise ValueError(f"Unsupported interval for Yahoo Finance: {interval}")

    response = requests.get(
        f"{YAHOO_CHART_URL}/{symbol}",
        params={"interval": _YAHOO_INTERVAL[interval], "range": _YAHOO_RANGE[interval]},
        headers=YAHOO_HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    result = payload.get("chart", {}).get("result")
    if not result:
        error = payload.get("chart", {}).get("error") or {}
        raise ValueError(error.get("description") or "No chart data returned")

    node = result[0]
    timestamps = node.get("timestamp") or []
    quote = node.get("indicators", {}).get("quote", [{}])[0]
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []

    candles: List[Dict[str, Any]] = []
    for index, timestamp in enumerate(timestamps):
        if index >= len(closes):
            break
        open_price, high, low, close = opens[index], highs[index], lows[index], closes[index]
        if None in (open_price, high, low, close):
            continue
        volume = volumes[index] if index < len(volumes) and volumes[index] is not None else 0.0
        candles.append(
            {
                "time": int(timestamp) * 1000,
                "open": float(open_price),
                "high": float(high),
                "low": float(low),
                "close": float(close),
                "volume": float(volume),
            }
        )

    candles = candles[-limit:]
    if not candles:
        raise ValueError("The market feed returned no usable candles")

    meta = node.get("meta", {})
    live_price = float(meta.get("regularMarketPrice") or candles[-1]["close"])
    return candles, live_price


def fetch_market(
    symbol: str,
    interval: str = "1m",
    limit: int = 180,
    asset_class: str | None = None,
) -> Tuple[List[Dict[str, Any]], float, Dict[str, Any]]:
    """Fetch candles, a live quote, and metadata for any supported market.

    Returns ``(candles, live_price, meta)`` where ``meta`` describes the provider
    and whether live WebSocket streaming is available.
    """
    cleaned = symbol.strip()
    resolved_class = asset_class or asset_class_for(cleaned)

    if resolved_class == "Crypto":
        provider_symbol = normalize_coinbase_symbol(cleaned)
        try:
            candles = _fetch_coinbase_klines(provider_symbol, interval, limit)
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as error:
            raise RuntimeError(f"Live market data unavailable for {cleaned}: {error}") from error
        try:
            live_price = _fetch_coinbase_price(provider_symbol)
        except (requests.RequestException, KeyError, TypeError, ValueError):
            live_price = float(candles[-1]["close"])
        meta = {
            "symbol": cleaned,
            "provider_symbol": provider_symbol,
            "asset_class": "Crypto",
            "provider": "Coinbase",
            "stream": True,
            "price_prefix": "$",
        }
        return candles, live_price, meta

    try:
        candles, live_price = _fetch_yahoo_candles(cleaned, interval, limit)
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as error:
        raise RuntimeError(f"Live market data unavailable for {cleaned}: {error}") from error

    meta = {
        "symbol": cleaned,
        "provider_symbol": cleaned,
        "asset_class": resolved_class,
        "provider": "Yahoo Finance",
        "stream": False,
        "price_prefix": "" if resolved_class == "Forex" else "$",
    }
    return candles, live_price, meta