"""The Dynamic Registration flow.

One method, :meth:`DynamicRegistrationService.register`, performs the whole
exchange: fetch the platform's OpenID configuration, POST a tool registration to
the platform, capture the returned ``client_id``/``deployment_id``, and persist
the result. The admin only ever pastes a single URL — this is what makes
"install on any LMS without re-reading the docs" real.
"""

from __future__ import annotations

import typing as t

import requests

from ..exceptions import ExternalRequestError
from ..http import build_session
from .models import (
    CLOSE_SUBJECT,
    LTI_TOOL_CONFIGURATION,
    PlatformConfiguration,
    ToolRegistration,
    ToolRegistrationConfig,
)
from .store import RegistrationStore


class DynamicRegistrationService:
    def __init__(
        self,
        tool_config: ToolRegistrationConfig,
        store: RegistrationStore,
        *,
        session: requests.Session | None = None,
        timeout: float | tuple[float, float] = (10.0, 30.0),
    ) -> None:
        self._config = tool_config
        self._store = store
        self._session = session if session is not None else build_session(timeout=timeout)
        self._timeout = timeout

    def register(
        self, openid_configuration_url: str, registration_token: str | None = None
    ) -> ToolRegistration:
        """Run the full registration handshake and persist the result."""
        platform = self._fetch_platform_configuration(openid_configuration_url)
        request_body = self._config.build_request(platform)
        response_body = self._post_registration(platform, request_body, registration_token)
        registration = self._to_registration(platform, response_body)
        self._store.save(registration)
        return registration

    @staticmethod
    def completion_html(
        message: str = "Registration complete. You may close this window."
    ) -> str:
        """HTML that signals the platform (via postMessage) that we're done."""
        return (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<title>Registration complete</title></head><body>"
            f"<p>{message}</p>"
            "<script>(window.opener || window.parent)."
            f"postMessage({{subject:'{CLOSE_SUBJECT}'}}, '*');</script>"
            "</body></html>"
        )

    # -- internals ---------------------------------------------------------

    def _fetch_platform_configuration(self, url: str) -> PlatformConfiguration:
        try:
            response = self._session.get(url, timeout=self._timeout)
        except requests.Timeout as exc:
            raise ExternalRequestError(
                f"Timed out fetching OpenID configuration: {exc}", url=url, is_timeout=True
            ) from exc
        except requests.RequestException as exc:
            raise ExternalRequestError(
                f"Error fetching OpenID configuration: {exc}", url=url
            ) from exc

        if not response.ok:
            raise ExternalRequestError(
                "Platform rejected the OpenID configuration request",
                status_code=response.status_code,
                url=url,
                response_text=response.text,
            )
        try:
            return PlatformConfiguration.from_dict(response.json())
        except (ValueError, TypeError) as exc:
            raise ExternalRequestError(
                f"Invalid OpenID configuration document: {exc}", url=url
            ) from exc

    def _post_registration(
        self,
        platform: PlatformConfiguration,
        body: dict[str, t.Any],
        registration_token: str | None,
    ) -> dict[str, t.Any]:
        headers = {"Accept": "application/json"}
        if registration_token:
            headers["Authorization"] = f"Bearer {registration_token}"

        url = platform.registration_endpoint
        try:
            response = self._session.post(
                url, json=body, headers=headers, timeout=self._timeout
            )
        except requests.Timeout as exc:
            raise ExternalRequestError(
                f"Timed out posting registration: {exc}", url=url, is_timeout=True
            ) from exc
        except requests.RequestException as exc:
            raise ExternalRequestError(
                f"Error posting registration: {exc}", url=url
            ) from exc

        if not response.ok:
            raise ExternalRequestError(
                "Platform rejected the tool registration",
                status_code=response.status_code,
                url=url,
                response_text=response.text,
            )
        try:
            return response.json()
        except (ValueError, TypeError) as exc:
            raise ExternalRequestError(
                f"Invalid registration response: {exc}", url=url
            ) from exc

    @staticmethod
    def _to_registration(
        platform: PlatformConfiguration, response_body: t.Mapping[str, t.Any]
    ) -> ToolRegistration:
        client_id = response_body.get("client_id")
        if not client_id:
            raise ExternalRequestError(
                "Registration response did not include a client_id",
                url=platform.registration_endpoint,
            )

        lti_config = response_body.get(LTI_TOOL_CONFIGURATION, {}) or {}
        deployment_id = lti_config.get("deployment_id")
        deployment_ids = (deployment_id,) if deployment_id else ()

        return ToolRegistration(
            issuer=platform.issuer,
            client_id=str(client_id),
            auth_login_url=platform.authorization_endpoint,
            auth_token_url=platform.token_endpoint,
            key_set_url=platform.jwks_uri,
            auth_audience=platform.authorization_server,
            deployment_ids=deployment_ids,
        )
