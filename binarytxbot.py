"""BINARYTXBOT analysis compatibility module.

This exact filename is provided for users who want to import the binary
signal engine as binarytxbot.py. The implementation remains shared with
binary_analysis.py.
"""

from binary_analysis import (
    BINARY_EXPIRIES_MINUTES,
    BINARY_FACTOR_LABELS,
    BINARY_SIGNAL_THRESHOLD,
    answer_binary_question,
    detect_candle_patterns,
    fetch_binary_market,
    generate_binary_signal,
    recommend_expiry,
    summarize_binary_market,
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