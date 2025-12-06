"""Simple ranking helpers for identifiers (count-only)."""


def score_and_rank_identifiers(items: list[dict]) -> list[dict]:
    """Rank identifiers by raw count (desc), then name (asc) for stability."""
    items.sort(key=lambda x: (-x.get("count", 0), x.get("name", "")))
    return items


__all__ = ["score_and_rank_identifiers"]
