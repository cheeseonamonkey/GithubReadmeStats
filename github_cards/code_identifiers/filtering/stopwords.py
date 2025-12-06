"""Stopword lists for filtering out common, non-meaningful identifiers."""

from __future__ import annotations

# Global stopwords - apply to all languages
# Keep this conservative - only truly generic/meaningless identifiers
GLOBAL_STOPWORDS = frozenset({
    # Original stopwords
    "main", "system", "uri", "url",

    # Test/framework terms
    "test", "tests", "mock", "stub", "fixture", "setup", "teardown",
    "spec", "specs",

    # Very generic variables (extremely common and non-meaningful)
    "temp", "tmp",

    # Single letters and common loop variables
    "i", "j", "k", "x", "y", "z", "a", "b", "c",
    "e", "ex", "n", "m", "p", "q", "r", "s", "t",

    # HTTP/API shorthand only (keep full words like "request")
    "req", "res", "resp",

    # Build/deployment
    "build", "dist", "target", "output", "out",

    # Common suffixes that are noise when standalone
    "er", "or",
})

# Language-specific stopwords
LANGUAGE_STOPWORDS = {
    "python": frozenset({
        "args", "kwargs", "self", "cls",
        "__init__", "__main__", "__name__", "__file__",
        "__dict__", "__class__", "__doc__",
        "none", "true", "false",
    }),

    "javascript": frozenset({
        "this", "arguments", "undefined", "null",
        "window", "document", "console",
        "exports", "module", "require",
        "async", "await", "promise",
    }),

    "typescript": frozenset({
        "this", "arguments", "undefined", "null",
        "window", "document", "console",
        "exports", "module", "require",
        "async", "await", "promise",
        "any", "unknown", "never", "void",
    }),

    "java": frozenset({
        "this", "args", "object", "string",
        "tostring", "equals", "hashcode",
        "getclass", "clone", "finalize",
        "void", "null",
    }),

    "csharp": frozenset({
        "this", "args", "object", "string",
        "tostring", "equals", "gethashcode",
        "gettype", "void", "null",
        "async", "await", "task",
    }),

    "go": frozenset({
        "err", "error", "nil",
        "interface", "struct", "func",
    }),

    "ruby": frozenset({
        "self", "initialize", "nil",
        "puts", "print", "require",
    }),

    "php": frozenset({
        "this", "self", "parent",
        "null", "true", "false",
        "echo", "print", "var",
    }),

    "swift": frozenset({
        "self", "nil", "optional",
        "any", "void",
    }),

    "kotlin": frozenset({
        "this", "null", "unit",
        "any", "nothing",
    }),
}

# Substrings to exclude (word-boundary aware)
EXCLUDED_SUBSTRINGS = (
    "system",
    "override",
    "internal",
    "private",
    "deprecated",
    "obsolete",
    "legacy",
    "temp",
    "tmp",
    "test",
    "mock",
    "dummy",
    "fake",
    "stub",
)

__all__ = ["GLOBAL_STOPWORDS", "LANGUAGE_STOPWORDS", "EXCLUDED_SUBSTRINGS"]
