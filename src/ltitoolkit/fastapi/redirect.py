"""Redirect adapter producing Starlette responses.

The core asks for two redirect styles: a normal HTTP 302 redirect and a
JavaScript redirect (used to break out of an iframe / re-assert cookies). Both
flush any queued cookies (e.g. the short-lived OIDC ``state`` cookie) onto the
outgoing response.
"""

from __future__ import annotations

import html
import typing as t

from starlette.responses import HTMLResponse, RedirectResponse, Response

from ltitoolkit.core.redirect import Redirect

if t.TYPE_CHECKING:
    from .cookie import FastApiCookieService


class FastApiRedirect(Redirect):
    def __init__(
        self, location: str, cookie_service: FastApiCookieService | None = None
    ) -> None:
        super().__init__()
        self._location = location
        self._cookie_service = cookie_service

    def do_redirect(self) -> Response:
        return self._process_response(
            RedirectResponse(url=self._location, status_code=302)
        )

    def do_js_redirect(self) -> Response:
        safe_location = html.escape(self._location, quote=True)
        return self._process_response(
            HTMLResponse(
                f'<script type="text/javascript">'
                f'window.location="{safe_location}";'
                f"</script>"
            )
        )

    def set_redirect_url(self, location: str) -> None:
        self._location = location

    def get_redirect_url(self) -> str:
        return self._location

    def _process_response(self, response: Response) -> Response:
        if self._cookie_service:
            self._cookie_service.update_response(response)
        return response
