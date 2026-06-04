"""Persistence interface for dynamically-registered platforms.

After a successful registration the resulting :class:`ToolRegistration` must be
stored so later launches can resolve ``(issuer, client_id)`` to its config. The
store is an interface so applications can back it with a database; the default
is in-process only (fine for a single worker / tests).
"""

from __future__ import annotations

import typing as t

from .models import ToolRegistration


@t.runtime_checkable
class RegistrationStore(t.Protocol):
    """Stores and retrieves tool registrations keyed by issuer + client_id."""

    def save(self, registration: ToolRegistration) -> None: ...

    def get(self, issuer: str, client_id: str) -> ToolRegistration | None: ...

    def find_by_issuer(self, issuer: str) -> list[ToolRegistration]: ...


class InMemoryRegistrationStore:
    """Default per-process store. Swap for a DB-backed store in production."""

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], ToolRegistration] = {}

    def save(self, registration: ToolRegistration) -> None:
        self._by_key[(registration.issuer, registration.client_id)] = registration

    def get(self, issuer: str, client_id: str) -> ToolRegistration | None:
        return self._by_key.get((issuer, client_id))

    def find_by_issuer(self, issuer: str) -> list[ToolRegistration]:
        return [reg for (iss, _), reg in self._by_key.items() if iss == issuer]
