"""Typed exception taxonomy for ltitoolkit.

A small, explicit hierarchy so callers can catch precisely (``except
AccessTokenError``) or broadly (``except LtiToolkitError``). External HTTP
failures are wrapped in rich exceptions that carry the status code and response
body, mirroring the practice used by production LTI tools.
"""

from __future__ import annotations


class LtiToolkitError(Exception):
    """Base class for every error raised by ltitoolkit."""


class ExternalRequestError(LtiToolkitError):
    """An HTTP request to the LMS failed (network error or non-2xx response)."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        url: str | None = None,
        response_text: str | None = None,
        is_timeout: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url
        self.response_text = response_text
        self.is_timeout = is_timeout

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        base = super().__str__()
        if self.status_code is not None:
            base = f"{base} (status={self.status_code}, url={self.url})"
        return base


class AccessTokenError(ExternalRequestError):
    """Failed to obtain a client-credentials access token from the platform."""
