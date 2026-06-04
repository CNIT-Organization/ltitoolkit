"""Access-token value object and pluggable cache.

Tokens are cached per scope-set and reused until they are near expiry. The cache
is an interface (:class:`TokenCache`) so applications can swap the default
in-process dict for Redis, a database, etc. — important when running multiple
workers that should share tokens (the default cache is per-process only).
"""

from __future__ import annotations

import typing as t
from dataclasses import dataclass


@dataclass(frozen=True)
class AccessToken:
    """An OAuth2 access token with the scopes it was issued for and its expiry."""

    value: str
    scopes: tuple[str, ...]
    expires_at: float  # epoch seconds

    def is_expired(self, *, leeway: float = 60.0, now: float) -> bool:
        """True if the token is at/after its expiry (minus a safety ``leeway``)."""
        return now >= (self.expires_at - leeway)


@t.runtime_checkable
class TokenCache(t.Protocol):
    """Minimal cache interface for storing access tokens by key."""

    def get(self, key: str) -> AccessToken | None: ...

    def set(self, key: str, token: AccessToken) -> None: ...


class InMemoryTokenCache:
    """Default per-process cache. Not shared across workers/processes."""

    def __init__(self) -> None:
        self._store: dict[str, AccessToken] = {}

    def get(self, key: str) -> AccessToken | None:
        return self._store.get(key)

    def set(self, key: str, token: AccessToken) -> None:
        self._store[key] = token
