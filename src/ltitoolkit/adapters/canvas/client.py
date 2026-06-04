"""A thin Canvas REST API client authenticated by the LTI tool token.

Authentication reuses :class:`ltitoolkit.token.AccessTokenService` — the tool
signs with its own key and exchanges it (client-credentials) for a Bearer token.
The token's scopes are Canvas API scopes (``url:METHOD|/api/v1/...``) declared on
the developer key, so **no user login is involved**.

Only a few high-value, read-only endpoints are wrapped here; add more as needed
following the same pattern. Note Canvas has *two* quiz systems: classic quizzes
(``/api/v1/courses/:id/quizzes``, wrapped below) and New Quizzes (a separate
``/api/quiz/v1/...`` API) — extend with a dedicated method if you need the latter.
"""

from __future__ import annotations

import typing as t

import requests

from ...exceptions import ExternalRequestError
from ...http import build_session

# Canvas API scopes (declared on the developer key, approved by the admin once).
SCOPE_LIST_COURSE_FILES = "url:GET|/api/v1/courses/:course_id/files"
SCOPE_GET_FILE = "url:GET|/api/v1/files/:id"
SCOPE_GET_FILE_PUBLIC_URL = "url:GET|/api/v1/files/:id/public_url"
SCOPE_LIST_QUIZZES = "url:GET|/api/v1/courses/:course_id/quizzes"

_DEFAULT_PER_PAGE = 50
_MAX_PAGES = 100  # safety bound against pathological pagination


@t.runtime_checkable
class TokenProvider(t.Protocol):
    """Anything that can mint a Bearer token for a set of scopes."""

    def get_token(self, scopes: t.Sequence[str]) -> str: ...


class CanvasAPIClient:
    """Read-only convenience wrapper over a subset of the Canvas REST API."""

    def __init__(
        self,
        base_url: str,
        token_provider: TokenProvider,
        scopes: t.Sequence[str],
        *,
        session: requests.Session | None = None,
        per_page: int = _DEFAULT_PER_PAGE,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._tokens = token_provider
        self._scopes = tuple(scopes)
        self._session = session if session is not None else build_session()
        self._per_page = per_page

    # -- public API --------------------------------------------------------

    def list_course_files(
        self, course_id: str | int, **params: t.Any
    ) -> list[dict[str, t.Any]]:
        """List files in a course (all pages). Extra kwargs become query params."""
        return self._get_paginated(f"/api/v1/courses/{course_id}/files", params)

    def list_quizzes(self, course_id: str | int) -> list[dict[str, t.Any]]:
        """List classic quizzes in a course (all pages)."""
        return self._get_paginated(f"/api/v1/courses/{course_id}/quizzes")

    def get_file(self, file_id: str | int) -> dict[str, t.Any]:
        """Get a single file's metadata."""
        return self._get(f"/api/v1/files/{file_id}")

    def get_file_public_url(self, file_id: str | int) -> str:
        """Get a temporary, directly-downloadable URL for a file's contents.

        Preferred over proxying bytes: hand this URL to the browser to open the
        PDF/document directly.
        """
        body = self._get(f"/api/v1/files/{file_id}/public_url")
        url = body.get("public_url")
        if not url:
            raise ExternalRequestError(
                "Canvas did not return a public_url for the file",
                url=f"{self._base}/api/v1/files/{file_id}/public_url",
            )
        return url

    # -- internals ---------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        token = self._tokens.get_token(self._scopes)
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    def _request(self, url: str, params: dict[str, t.Any] | None = None) -> requests.Response:
        try:
            response = self._session.get(url, params=params, headers=self._headers())
        except requests.Timeout as exc:
            raise ExternalRequestError(
                f"Timed out calling Canvas: {exc}", url=url, is_timeout=True
            ) from exc
        except requests.RequestException as exc:
            raise ExternalRequestError(f"Error calling Canvas: {exc}", url=url) from exc

        if not response.ok:
            raise ExternalRequestError(
                "Canvas API request failed",
                status_code=response.status_code,
                url=url,
                response_text=response.text,
            )
        return response

    def _get(self, path: str, params: dict[str, t.Any] | None = None) -> dict[str, t.Any]:
        response = self._request(self._base + path, params)
        return response.json()

    def _get_paginated(
        self, path: str, params: dict[str, t.Any] | None = None
    ) -> list[dict[str, t.Any]]:
        query = dict(params or {})
        query.setdefault("per_page", self._per_page)

        results: list[dict[str, t.Any]] = []
        url: str | None = self._base + path
        pages = 0
        # First page carries query params; subsequent `next` links are absolute
        # and already include them.
        next_params: dict[str, t.Any] | None = query
        while url and pages < _MAX_PAGES:
            response = self._request(url, next_params)
            body = response.json()
            if not isinstance(body, list):
                raise ExternalRequestError(
                    "Expected a list response from Canvas", url=url
                )
            results.extend(body)
            next_link = response.links.get("next")
            url = next_link["url"] if next_link else None
            next_params = None
            pages += 1
        return results
