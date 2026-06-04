"""Canvas LMS proprietary REST API adapter (Layer 3 — NOT portable).

Calls Canvas's own REST API (files, quizzes, …) using the tool's LTI
client-credentials token — no user login. Requires the tool's developer key to
carry the matching Canvas API scopes (e.g. ``url:GET|/api/v1/courses/:id/files``);
the LMS admin approves those once at install.

This works **only** on Canvas. Other LMSs need their own adapter.
"""

from .client import (
    SCOPE_GET_FILE,
    SCOPE_GET_FILE_PUBLIC_URL,
    SCOPE_LIST_COURSE_FILES,
    SCOPE_LIST_QUIZZES,
    CanvasAPIClient,
    TokenProvider,
)

__all__ = [
    "CanvasAPIClient",
    "TokenProvider",
    "SCOPE_LIST_COURSE_FILES",
    "SCOPE_GET_FILE",
    "SCOPE_GET_FILE_PUBLIC_URL",
    "SCOPE_LIST_QUIZZES",
]
