"""FastAPI adapter for ltitoolkit.

PyLTI1p3 ships Django and Flask adapters only; FastAPI is the gap this package
fills. This subpackage maps FastAPI/Starlette ``Request``/``Response`` semantics
(query/form params, cookies, sessions, redirects) onto the vendored core's
abstractions, and adds async-aware helpers
(:meth:`FastApiRequest.from_request`, :meth:`FastApiMessageLaunch.validate_async`).

Requirements:
- ``SessionMiddleware`` must be installed for the default session-backed launch
  storage to persist data across the login → launch round trip.
- ``python-multipart`` must be installed to read the form-encoded ``id_token``
  POST (pulled in by the ``ltitoolkit[fastapi]`` extra).
"""

from .cookie import FastApiCookieService
from .message_launch import FastApiMessageLaunch
from .oidc_login import FastApiOIDCLogin
from .redirect import FastApiRedirect
from .request import FastApiRequest
from .session import FastApiSessionService

__all__ = [
    "FastApiRequest",
    "FastApiCookieService",
    "FastApiSessionService",
    "FastApiRedirect",
    "FastApiOIDCLogin",
    "FastApiMessageLaunch",
]
