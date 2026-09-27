"""Token counting.

Chunk sizes are set in tokens because that is what the embedding models limit.
The exact counter needs tiktoken's vocabulary, which needs network access at
first use. Where that is unavailable the estimator is used instead, and every
report says which one produced the numbers.
"""

from typing import Protocol


class TokenCounter(Protocol):
    name: str

    def count(self, text: str) -> int: ...


class EstimatedCounter:
    """Character-based estimate. Use only when the exact counter is unavailable."""

    name = "estimated (chars/4)"

    def count(self, text: str) -> int:
        return max(1, round(len(text) / 4))


class TiktokenCounter:
    """Exact counts from a tiktoken encoding."""

    def __init__(self, encoding: str = "cl100k_base"):
        import tiktoken

        self._enc = tiktoken.get_encoding(encoding)
        self.name = f"tiktoken {encoding}"

    def count(self, text: str) -> int:
        return len(self._enc.encode(text))


def default_counter() -> TokenCounter:
    """Exact counter when its vocabulary loads, estimator otherwise."""
    try:
        return TiktokenCounter()
    except Exception:
        return EstimatedCounter()
