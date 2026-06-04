"""Message launch adapter — step 2 of an LTI 1.3 launch.

Validates the ``id_token`` posted back by the platform: state, JWT format,
nonce, registration, signature, deployment, and message type.

Validation performs **blocking** network I/O (fetching the platform's JWKS via
``requests``). Calling it directly in an async route would block the event loop,
so :meth:`validate_async` runs the synchronous validation in a threadpool. Use
it from async handlers; the inherited synchronous :meth:`validate` remains
available for non-async contexts.
"""

from __future__ import annotations

import typing as t

from starlette.concurrency import run_in_threadpool

from ltitoolkit.core.message_launch import MessageLaunch

from .cookie import FastApiCookieService
from .session import FastApiSessionService

if t.TYPE_CHECKING:
    import requests

    from ltitoolkit.core.launch_data_storage.base import LaunchDataStorage
    from ltitoolkit.core.tool_config import ToolConfAbstract

    from .request import FastApiRequest


class FastApiMessageLaunch(MessageLaunch):
    def __init__(
        self,
        request: FastApiRequest,
        tool_config: ToolConfAbstract,
        session_service: FastApiSessionService | None = None,
        cookie_service: FastApiCookieService | None = None,
        launch_data_storage: LaunchDataStorage[t.Any] | None = None,
        requests_session: requests.Session | None = None,
    ) -> None:
        cookie_service = cookie_service or FastApiCookieService(request)
        session_service = session_service or FastApiSessionService(request)
        super().__init__(
            request,
            tool_config,
            session_service,
            cookie_service,
            launch_data_storage,
            requests_session,
        )

    def _get_request_param(self, key: str) -> t.Any:
        return self._request.get_param(key)

    async def validate_async(self) -> FastApiMessageLaunch:
        """Run the (blocking) launch validation without blocking the event loop."""
        await run_in_threadpool(self.validate)
        return self
