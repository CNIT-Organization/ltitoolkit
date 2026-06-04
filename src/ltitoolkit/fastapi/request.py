"""Starlette/FastAPI request adapter for the vendored LTI core.

The core's :class:`ltitoolkit.core.request.Request` exposes a *synchronous*
``get_param()``. Starlette, however, reads the form body asynchronously
(``await request.form()``). We bridge this by extracting all request data
*eagerly* in :meth:`FastApiRequest.from_request` (inside the async route) and
then serving it synchronously from an in-memory mapping — so the core never has
to ``await`` anything.
"""

from __future__ import annotations

import typing as t

from starlette.requests import Request as StarletteRequest

from ltitoolkit.core.request import Request


class FastApiRequest(Request):
    """A core ``Request`` backed by data pulled from a Starlette request.

    Construct it with :meth:`from_request` from inside an async handler; that is
    the only place the (async) form body can be read.
    """

    def __init__(
        self,
        *,
        cookies: t.Mapping[str, str],
        session: t.MutableMapping[str, t.Any],
        request_data: t.Mapping[str, t.Any],
        request_is_secure: bool,
    ) -> None:
        super().__init__()
        self._cookies = cookies
        self._session = session
        self._request_data = request_data
        self._request_is_secure = request_is_secure

    @classmethod
    async def from_request(cls, request: StarletteRequest) -> FastApiRequest:
        """Eagerly read query/form params, cookies and session from Starlette.

        The default launch-data storage writes to ``request.session``, which
        requires Starlette's ``SessionMiddleware`` to be installed. If it is not,
        a throwaway dict is used (fine for cache-backed storage, but session
        storage will not persist across requests).
        """
        request_data: dict[str, t.Any] = dict(request.query_params)
        if request.method != "GET":
            form = await request.form()
            request_data.update({key: form[key] for key in form})

        # request.session only exists when SessionMiddleware is active.
        session: t.MutableMapping[str, t.Any]
        session = request.session if "session" in request.scope else {}

        return cls(
            cookies=dict(request.cookies),
            session=session,
            request_data=request_data,
            request_is_secure=request.url.scheme == "https",
        )

    @property
    def session(self) -> t.MutableMapping[str, t.Any]:
        return self._session

    def get_param(self, key: str) -> t.Any:
        return self._request_data.get(key)

    def get_cookie(self, key: str) -> str | None:
        return self._cookies.get(key)

    def is_secure(self) -> bool:
        return self._request_is_secure
