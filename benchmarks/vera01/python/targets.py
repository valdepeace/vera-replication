"""Synthetic Python targets for the VERA-01 harness smoke test."""


def normalize_whitespace(value: str) -> str:
    """Collapse whitespace runs to one space and trim both ends."""
    return " ".join(value.split())


def chunk_text(value: str, size: int) -> list[str]:
    """Split text into consecutive chunks; size must be a positive integer."""
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise ValueError("size must be a positive integer")
    return [value[index:index + size] for index in range(0, len(value), size)]
