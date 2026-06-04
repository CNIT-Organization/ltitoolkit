"""Brightspace (D2L) proprietary REST API adapter (Layer 3 — NOT portable).

Calls Brightspace's own Valence LE API (course content: modules, topics, files)
using the tool's OAuth2 client-credentials token minted for a Service User — no
user login. Requires the registered OAuth client to carry the matching scopes
(e.g. ``content:modules:read``); the LMS admin approves those once at install.

This works **only** on Brightspace. Other LMSs need their own adapter.
"""

from .client import (
    SCOPE_CONTENT_FILE_READ,
    SCOPE_CONTENT_READ,
    SCOPE_CONTENT_TOPICS_READ,
    SCOPE_ENROLLMENT_READ,
    TOPIC_FILE,
    TOPIC_LINK,
    TYPE_MODULE,
    TYPE_TOPIC,
    BrightspaceAPIClient,
    TokenProvider,
)

__all__ = [
    "BrightspaceAPIClient",
    "TokenProvider",
    "SCOPE_CONTENT_READ",
    "SCOPE_CONTENT_TOPICS_READ",
    "SCOPE_CONTENT_FILE_READ",
    "SCOPE_ENROLLMENT_READ",
    "TYPE_MODULE",
    "TYPE_TOPIC",
    "TOPIC_FILE",
    "TOPIC_LINK",
]
