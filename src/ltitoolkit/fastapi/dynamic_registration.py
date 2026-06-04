"""FastAPI binding for the Dynamic Registration endpoint.

Wire this to a single route (e.g. ``/lti/register``); that URL is what an LMS
admin pastes to install the tool. The platform may use GET or POST and supplies
``openid_configuration`` and (optionally) ``registration_token``.
"""

from __future__ import annotations

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request as StarletteRequest
from starlette.responses import HTMLResponse, PlainTextResponse, Response

from ..dynamic_registration.service import DynamicRegistrationService


async def handle_dynamic_registration(
    request: StarletteRequest, service: DynamicRegistrationService
) -> Response:
    """Perform registration for an incoming initiation request.

    Returns the completion HTML (which closes the registration window via
    postMessage) on success, or a 400 if ``openid_configuration`` is missing.
    """
    params: dict[str, str] = dict(request.query_params)
    if request.method == "POST":
        form = await request.form()
        for key in ("openid_configuration", "registration_token"):
            if key in form and key not in params:
                params[key] = str(form[key])

    openid_configuration = params.get("openid_configuration")
    if not openid_configuration:
        return PlainTextResponse("Missing 'openid_configuration'", status_code=400)

    # Registration performs blocking HTTP; keep the event loop free.
    await run_in_threadpool(
        service.register, openid_configuration, params.get("registration_token")
    )
    return HTMLResponse(service.completion_html())
