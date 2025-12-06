"""Normalization logic for identifier deduplication."""

from __future__ import annotations
import re

# Common prefixes to strip for similarity matching
STRIP_PREFIXES = frozenset({
    "get", "set", "is", "has", "can", "should", "will", "do",
    "m_", "_", "on", "handle", "process", "create", "make",
})

# Common suffixes to strip for similarity matching
STRIP_SUFFIXES = frozenset({
    "er", "or", "handler", "service", "manager", "controller",
    "provider", "factory", "builder", "helper", "utility",
    "impl", "implementation", "base", "abstract",
})


def normalize_identifier(name: str) -> str:
    """
    Normalize an identifier for deduplication purposes.

    Handles:
    - camelCase → snake_case
    - PascalCase → snake_case
    - Consecutive uppercase (acronyms) → grouped lowercase
    - Non-alphanumeric characters → underscores

    Examples:
        "HTTPSConnection" → "https_connection"
        "getUserData" → "get_user_data"
        "MyClass" → "my_class"
        "some-variable" → "some_variable"
    """
    if not name:
        return name.lower()

    # Handle acronyms: consecutive uppercase letters
    # Insert underscore before a lowercase letter that follows uppercase
    # But keep consecutive caps together (HTTPServer → HTTP_Server, not H_T_T_P_Server)
    result = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)

    # Insert underscore before uppercase letters that follow lowercase/digits
    result = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', result)

    # Replace any non-alphanumeric characters with underscores
    result = re.sub(r'[^a-zA-Z0-9]+', '_', result)

    # Convert to lowercase and strip trailing/leading underscores
    result = result.lower().strip('_')

    return result or name.lower()


def strip_common_affixes(name: str) -> str:
    """
    Remove common prefixes and suffixes for similarity comparison.

    Examples:
        "getUserData" → "UserData"
        "DataHandler" → "Data"
        "isActive" → "Active"
    """
    lower_name = name.lower()

    # Strip prefixes
    for prefix in STRIP_PREFIXES:
        if lower_name.startswith(prefix):
            # Check if there's actually something after the prefix
            candidate = name[len(prefix):]
            if candidate and (candidate[0].isupper() or candidate[0] == '_'):
                return candidate.lstrip('_')

    # Strip suffixes
    for suffix in STRIP_SUFFIXES:
        if lower_name.endswith(suffix):
            # Check if there's actually something before the suffix
            candidate = name[:-len(suffix)]
            if candidate and len(candidate) > 2:
                return candidate.rstrip('_')

    return name


def get_canonical_form(name: str) -> str:
    """
    Get canonical form by stripping affixes and normalizing.

    Used for advanced similarity detection.
    """
    stripped = strip_common_affixes(name)
    return normalize_identifier(stripped)


def are_similar(name1: str, name2: str) -> bool:
    """
    Check if two identifiers are similar enough to be considered duplicates.

    Returns True if:
    - Normalized forms are identical, OR
    - Canonical forms (with affixes stripped) are identical
    """
    if normalize_identifier(name1) == normalize_identifier(name2):
        return True

    canonical1 = get_canonical_form(name1)
    canonical2 = get_canonical_form(name2)

    return canonical1 == canonical2 and len(canonical1) > 2


def prefer_type_over_instance(name1: str, name2: str) -> str:
    """
    Given two similar names, prefer the type (PascalCase) over instance (camelCase).

    Examples:
        ("User", "user") → "User"
        ("UserData", "userData") → "UserData"
        ("http_client", "HTTPClient") → "HTTPClient"
    """
    # Prefer names that start with uppercase (types/classes)
    if name1[0].isupper() and not name2[0].isupper():
        return name1
    elif name2[0].isupper() and not name1[0].isupper():
        return name2

    # If both uppercase or both lowercase, prefer the longer one
    # (usually more descriptive)
    if len(name1) >= len(name2):
        return name1
    else:
        return name2


__all__ = [
    "normalize_identifier",
    "strip_common_affixes",
    "get_canonical_form",
    "are_similar",
    "prefer_type_over_instance",
]
