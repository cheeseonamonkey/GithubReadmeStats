"""Vercel KV caching layer for code identifiers."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Optional

# Vercel KV client (optional dependency)
try:
    from upstash_redis import Redis
    KV_AVAILABLE = True
except ImportError:
    KV_AVAILABLE = False


def get_kv_client() -> Optional[Redis]:
    """Get Vercel KV client if available and configured."""
    if not KV_AVAILABLE:
        return None
    url = os.environ.get("KV_REST_API_URL")
    token = os.environ.get("KV_REST_API_TOKEN")
    if not url or not token:
        return None
    try:
        return Redis(url=url, token=token)
    except Exception:
        return None


class CacheManager:
    """Manages caching with Vercel KV with fallback to in-memory."""

    TTL_REPOS = 3600      # 1 hour
    TTL_TREE = 1800       # 30 min
    TTL_FILE = 86400      # 24 hours

    # In-memory fallback (per-instance, cleared on cold start)
    _local_cache: dict[str, Any] = {}

    def __init__(self, username: str):
        self.username = username
        self._kv = get_kv_client()

    def _key(self, *parts: str) -> str:
        return ":".join(parts)

    def _hash_url(self, url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    # --- Repos ---
    def get_repos(self) -> Optional[list]:
        key = self._key(self.username, "repos")
        return self._get(key)

    def set_repos(self, repos: list) -> None:
        key = self._key(self.username, "repos")
        self._set(key, repos, self.TTL_REPOS)

    # --- File Trees ---
    def get_tree(self, repo: str) -> Optional[dict]:
        key = self._key(self.username, "tree", repo)
        return self._get(key)

    def set_tree(self, repo: str, tree: dict) -> None:
        key = self._key(self.username, "tree", repo)
        self._set(key, tree, self.TTL_TREE)

    # --- File Content (global, by URL hash) ---
    def get_file(self, url: str) -> Optional[str]:
        key = self._key("file", self._hash_url(url))
        return self._get(key)

    def set_file(self, url: str, content: str) -> None:
        key = self._key("file", self._hash_url(url))
        self._set(key, content, self.TTL_FILE)

    # --- Internal helpers ---
    def _get(self, key: str) -> Optional[Any]:
        # Try KV first
        if self._kv:
            try:
                val = self._kv.get(key)
                if val is not None:
                    return json.loads(val) if isinstance(val, str) else val
            except Exception:
                pass
        # Fallback to local cache
        return self._local_cache.get(key)

    def _set(self, key: str, value: Any, ttl: int) -> None:
        # Try KV first
        if self._kv:
            try:
                self._kv.setex(key, ttl, json.dumps(value))
                return
            except Exception:
                pass
        # Fallback to local cache (no TTL enforcement in-memory)
        self._local_cache[key] = value
