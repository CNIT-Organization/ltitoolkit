"""Cookie service adapter for FastAPI/Starlette responses.

Cookies cannot be written until we have a response object, so ``set_cookie``
queues them and :meth:`FastApiCookieService.update_response` flushes them onto a
Starlette ``Response`` just before it is returned.

LTI launches are cross-site POSTs (the LMS posts to the tool), so state cookies
must be sent in that context: ``SameSite=None; Secure``. When the request is not
secure (e.g. local ``http`` development) we fall back to ``SameSite=Lax``, since
browsers reject ``SameSite=None`` without ``Secure``.
"""

from __future__ import annotations

import typing as t

from starlette.responses import Response

from ltitoolkit.core.cookie import CookieService

if t.TYPE_CHECKING:
    from .request import FastApiRequest


class FastApiCookieService(CookieService):
    def __init__(self, request: FastApiRequest) -> None:
        self._request = request
        self._cookie_data_to_set: dict[str, dict[str, t.Any]] = {}

    def _get_key(self, key: str) -> str:
        return self._cookie_prefix + "-" + key

    def get_cookie(self, name: str) -> str | None:
        return self._request.get_cookie(self._get_key(name))

    def set_cookie(
        self, name: str, value: str | int, exp: int | None = 3600
    ) -> None:
        self._cookie_data_to_set[self._get_key(name)] = {"value": value, "exp": exp}

    def update_response(self, response: Response) -> None:
        """Flush all queued cookies onto ``response``."""
        secure = self._request.is_secure()
        for key, cookie_data in self._cookie_data_to_set.items():
            response.set_cookie(
                key=key,
                value=str(cookie_data["value"]),
                max_age=cookie_data["exp"],
                path="/",
                secure=secure,
                httponly=True,
                samesite="none" if secure else "lax",
            )
