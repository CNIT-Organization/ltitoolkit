"""OIDC login adapter — step 1 of an LTI 1.3 launch.

Handles the platform's *third-party initiated login*: validate the request,
mint state/nonce, set the state cookie, and redirect back to the platform's
authorization endpoint. Wraps the framework-specific pieces (redirect + raw HTML
response) around the core's :class:`ltitoolkit.core.oidc_login.OIDCLogin`.
"""

from __future__ import annotations

import typing as t

from starlette.responses import HTMLResponse, Response

from ltitoolkit.core.oidc_login import OIDCLogin

from .cookie import FastApiCookieService
from .redirect import FastApiRedirect
from .session import FastApiSessionService

if t.TYPE_CHECKING:
    from ltitoolkit.core.launch_data_storage.base import LaunchDataStorage
    from ltitoolkit.core.tool_config import ToolConfAbstract

    from .request import FastApiRequest


class FastApiOIDCLogin(OIDCLogin):
    def __init__(
        self,
        request: FastApiRequest,
        tool_config: ToolConfAbstract,
        session_service: FastApiSessionService | None = None,
        cookie_service: FastApiCookieService | None = None,
        launch_data_storage: LaunchDataStorage[t.Any] | None = None,
    ) -> None:
        cookie_service = cookie_service or FastApiCookieService(request)
        session_service = session_service or FastApiSessionService(request)
        super().__init__(
            request, tool_config, session_service, cookie_service, launch_data_storage
        )

    def get_redirect(self, url: str) -> FastApiRedirect:
        return FastApiRedirect(url, self._cookie_service)

    def get_response(self, html: str) -> Response:
        return HTMLResponse(html)
