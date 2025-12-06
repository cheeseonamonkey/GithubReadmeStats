"""Quality scoring for identifier ranking.

We primarily rank by raw count, but nudge the ordering toward identifiers that
feel descriptive or show personality. The bonuses are intentionally small so
high-frequency items still dominate.
"""

from __future__ import annotations
import re
from typing import Counter as CounterType

# Words that often show up in bland identifiers; these get lightly penalized.
BORING_TOKENS = frozenset(
    {
        "data",
        "info",
        "config",
        "util",
        "helper",
        "manager",
        "handler",
        "service",
        "base",
        "impl",
        "client",
        "server",
        "common",
        "default",
        "main",
        "core",
        "module",
        "object",
    }
)

# Tokens that suggest playful, story-like, or otherwise interesting identifiers.
PLAYFUL_TOKENS = frozenset(
    {
        "unicorn",
        "dragon",
        "phoenix",
        "rocket",
        "ninja",
        "pirate",
        "wizard",
        "goblin",
        "ghost",
        "spark",
        "glow",
        "storm",
        "galaxy",
        "nebula",
        "rainbow",
        "aurora",
        "comet",
        "saga",
        "quest",
        "pixel",
    }
)

# Verbs/actions tend to make identifiers feel more purposeful.
ACTION_TOKENS = frozenset(
    {
        "build",
        "launch",
        "explore",
        "craft",
        "forge",
        "render",
        "paint",
        "spark",
        "bloom",
        "drive",
        "dance",
        "wander",
        "drift",
        "sprint",
        "ship",
        "guide",
        "pilot",
        "boost",
    }
)


def _split_identifier_tokens(identifier: str) -> list[str]:
    """Split identifiers into word-like tokens for scoring."""
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", identifier)
    cleaned = re.sub(r"[^A-Za-z0-9]+", " ", spaced.replace("_", " "))
    return [tok for tok in cleaned.split() if tok]


def calculate_quality_score(
    identifier: str,
    count: int,
    lang_counts: CounterType[str],
    max_count: int = 1,
) -> float:
    """
    Calculate a lightly-weighted quality score for an identifier.

    The score is mostly the raw count, with small bonuses/penalties to prefer
    names that show personality or descriptiveness.
    """
    tokens = _split_identifier_tokens(identifier)
    lower_tokens = [t.lower() for t in tokens]

    base_score = float(count)
    bonus = 0.0

    # Reward multi-word / descriptive identifiers.
    if len(tokens) > 1:
        bonus += 0.2

    # Prefer expressive lengths; very short names tend to be noise.
    if len(identifier) >= 14:
        bonus += 0.15
    elif len(identifier) <= 4:
        bonus -= 0.1

    # Boost playful or action-oriented vocab.
    fun_hits = sum(1 for t in lower_tokens if t in PLAYFUL_TOKENS)
    if fun_hits:
        bonus += 0.4 + 0.1 * (fun_hits - 1)

    action_hits = sum(1 for t in lower_tokens if t in ACTION_TOKENS or t.endswith("ing"))
    if action_hits:
        bonus += 0.15 + 0.05 * (action_hits - 1)

    # Lightly penalize boilerplate-y tokens so they don't crowd the top.
    boring_hits = sum(1 for t in lower_tokens if t in BORING_TOKENS)
    if boring_hits:
        bonus -= 0.3 + 0.05 * (boring_hits - 1)

    # Small bonuses for visual flair.
    if any(tok.isupper() and len(tok) >= 3 for tok in tokens):
        bonus += 0.05  # Acronyms add texture
    if any(ch.isdigit() for ch in identifier):
        bonus += 0.05  # Names with numbers stand out

    # Reward identifiers reused across languages (tiny nudge).
    if len(lang_counts) > 1:
        bonus += 0.05 * min(len(lang_counts), 3)

    # Keep the bonus subtle so counts remain dominant.
    bonus = max(min(bonus, 1.25), -1.0)

    # Gentle tie-breaker for extremely common identifiers.
    if max_count > 0:
        bonus += min(count / max_count, 1.0) * 0.05

    return base_score + bonus


def score_and_rank_identifiers(items: list[dict]) -> list[dict]:
    """
    Score and re-rank identifiers by count with slight style nudging.

    Args:
        items: List of identifier dicts with 'name', 'count', 'langs' keys

    Returns:
        Re-ranked list sorted by quality score (count + small bonus).
    """
    if not items:
        return items

    max_count = max(item.get("count", 0) for item in items) or 1

    for item in items:
        item["quality_score"] = calculate_quality_score(
            item.get("name", ""),
            item.get("count", 0),
            item.get("langs", CounterType()),
            max_count,
        )

    items.sort(
        key=lambda x: (
            x["quality_score"],
            x.get("count", 0),
            len(x.get("name", "")),
        ),
        reverse=True,
    )

    for item in items:
        item.pop("quality_score", None)

    return items


__all__ = ["calculate_quality_score", "score_and_rank_identifiers"]
