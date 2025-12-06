"""Quality scoring for identifier ranking."""

from __future__ import annotations
from typing import Counter as CounterType


def calculate_quality_score(
    identifier: str,
    count: int,
    lang_counts: CounterType[str],
    max_count: int = 1
) -> float:
    """
    Calculate a quality score for an identifier based on multiple factors.

    Args:
        identifier: The display name of the identifier
        count: Total occurrence count across all languages
        lang_counts: Counter of occurrences per language
        max_count: Maximum count among all identifiers (for normalization)

    Returns:
        Quality score (higher is better)
    """
    score = 1.0

    # Length scoring
    # Prefer identifiers between 5-20 characters
    id_len = len(identifier)
    if id_len < 4:
        score *= 0.6  # Too short, likely not meaningful
    elif id_len < 6:
        score *= 0.85
    elif id_len <= 20:
        score *= 1.0  # Ideal length
    elif id_len <= 30:
        score *= 0.9  # A bit long but okay
    else:
        score *= 0.7  # Too long

    # Casing scoring
    # Prefer PascalCase (types/classes) over camelCase or snake_case
    if identifier and identifier[0].isupper():
        score *= 1.3  # Types and classes are more interesting
    elif '_' in identifier:
        score *= 0.95  # snake_case is less preferred

    # Frequency scoring
    # Use logarithmic scaling to avoid over-weighting very common identifiers
    # But still reward frequently used ones
    if max_count > 0:
        frequency_ratio = count / max_count
        # Apply a logarithmic boost (diminishing returns)
        if frequency_ratio > 0.5:
            score *= 1.4
        elif frequency_ratio > 0.3:
            score *= 1.3
        elif frequency_ratio > 0.1:
            score *= 1.2
        elif frequency_ratio > 0.05:
            score *= 1.1

    # Language diversity scoring
    # Identifiers used across multiple languages are more interesting
    num_languages = len(lang_counts)
    if num_languages >= 3:
        score *= 1.25
    elif num_languages == 2:
        score *= 1.1

    # Penalize identifiers that are all lowercase (likely not types)
    if identifier.islower():
        score *= 0.85

    # Bonus for identifiers with acronyms (consecutive caps)
    if sum(1 for i in range(len(identifier)-1) if identifier[i].isupper() and identifier[i+1].isupper()) > 0:
        score *= 1.15

    return score


def score_and_rank_identifiers(items: list[dict]) -> list[dict]:
    """
    Score and re-rank identifiers by quality.

    Args:
        items: List of identifier dicts with 'name', 'count', 'langs' keys

    Returns:
        Re-ranked list sorted by quality score
    """
    if not items:
        return items

    max_count = max(item['count'] for item in items)

    # Add quality scores
    for item in items:
        item['quality_score'] = calculate_quality_score(
            item['name'],
            item['count'],
            item.get('langs', CounterType()),
            max_count
        )

    # Sort by quality score (descending)
    items.sort(key=lambda x: x['quality_score'], reverse=True)

    # Remove quality_score from output (internal use only)
    for item in items:
        item.pop('quality_score', None)

    return items


__all__ = ["calculate_quality_score", "score_and_rank_identifiers"]
