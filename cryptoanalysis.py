"""TRADEXBOT analysis compatibility module.

This exact filename is provided for users who want to import the analysis engine
as cryptoanalysis.py. The implementation remains shared with crypto_analysis.py.
"""

from crypto_analysis import (
    answer_chart_question,
    fetch_live_market,
    fetch_live_klines,
    fetch_live_price,
    generate_sample_candles,
    normalize_coinbase_symbol,
    summarize_chart,
)

__all__ = [
    "answer_chart_question",
    "fetch_live_market",
    "fetch_live_klines",
    "fetch_live_price",
    "generate_sample_candles",
    "normalize_coinbase_symbol",
    "summarize_chart",
]
