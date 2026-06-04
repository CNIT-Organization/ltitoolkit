"""Data models and constants for LTI 1.3 Dynamic Registration.

Spec: https://www.imsglobal.org/spec/lti-dr/v1p0

The flow exchanges two JSON documents:
- the platform's *OpenID configuration* (:class:`PlatformConfiguration`), and
- the tool's *registration request* (built by :class:`ToolRegistrationConfig`).

The platform replies with a ``client_id`` (and possibly a ``deployment_id``),
captured as a :class:`ToolRegistration`.
"""

from __future__ import annotations

import typing as t
from dataclasses import dataclass, field
from urllib.parse import urlparse

# -- Spec claim URIs / constants -------------------------------------------

LTI_TOOL_CONFIGURATION = "https://purl.imsglobal.org/spec/lti-tool-configuration"
LTI_PLATFORM_CONFIGURATION = "https://purl.imsglobal.org/spec/lti-platform-configuration"

MESSAGE_RESOURCE_LINK = "LtiResourceLinkRequest"
MESSAGE_DEEP_LINKING = "LtiDeepLinkingRequest"

# Sent to the platform's HTML5 Web Message channel to end registration.
CLOSE_SUBJECT = "org.imsglobal.lti.close"

# LTI Advantage service scopes we request by default.
SCOPE_AGS_LINEITEM = "https://purl.imsglobal.org/spec/lti-ags/scope/lineitem"
SCOPE_AGS_RESULT = "https://purl.imsglobal.org/spec/lti-ags/scope/result.readonly"
SCOPE_AGS_SCORE = "https://purl.imsglobal.org/spec/lti-ags/scope/score"
SCOPE_NRPS = "https://purl.imsglobal.org/spec/lti-nrps/scope/contextmembership.readonly"

DEFAULT_SCOPES: tuple[str, ...] = (
    SCOPE_AGS_LINEITEM,
    SCOPE_AGS_RESULT,
    SCOPE_AGS_SCORE,
    SCOPE_NRPS,
)

DEFAULT_CLAIMS: tuple[str, ...] = ("iss", "sub", "name", "given_name", "family_name", "email")


@dataclass
class ToolMessage:
    """A message type the tool supports (resource link launch / deep linking)."""

    type: str
    target_link_uri: str | None = None
    label: str | None = None
    icon_uri: str | None = None
    placements: tuple[str, ...] | None = None
    custom_parameters: dict[str, str] | None = None

    def to_dict(self) -> dict[str, t.Any]:
        data: dict[str, t.Any] = {"type": self.type}
        if self.target_link_uri:
            data["target_link_uri"] = self.target_link_uri
        if self.label:
            data["label"] = self.label
        if self.icon_uri:
            data["icon_uri"] = self.icon_uri
        if self.placements:
            data["placements"] = list(self.placements)
        if self.custom_parameters:
            data["custom_parameters"] = dict(self.custom_parameters)
        return data


@dataclass
class PlatformConfiguration:
    """The platform's OpenID configuration document (only fields we need)."""

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    registration_endpoint: str
    authorization_server: str | None = None
    scopes_supported: tuple[str, ...] = ()
    product_family_code: str | None = None
    raw: dict[str, t.Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: t.Mapping[str, t.Any]) -> PlatformConfiguration:
        lti = data.get(LTI_PLATFORM_CONFIGURATION, {}) or {}
        required = (
            "issuer",
            "authorization_endpoint",
            "token_endpoint",
            "jwks_uri",
            "registration_endpoint",
        )
        missing = [k for k in required if not data.get(k)]
        if missing:
            raise ValueError(
                f"Platform OpenID configuration is missing fields: {', '.join(missing)}"
            )
        return cls(
            issuer=data["issuer"],
            authorization_endpoint=data["authorization_endpoint"],
            token_endpoint=data["token_endpoint"],
            jwks_uri=data["jwks_uri"],
            registration_endpoint=data["registration_endpoint"],
            authorization_server=data.get("authorization_server"),
            scopes_supported=tuple(data.get("scopes_supported", []) or []),
            product_family_code=lti.get("product_family_code"),
            raw=dict(data),
        )


@dataclass
class ToolRegistration:
    """The persisted result of a successful registration."""

    issuer: str
    client_id: str
    auth_login_url: str
    auth_token_url: str
    key_set_url: str
    auth_audience: str | None = None
    deployment_ids: tuple[str, ...] = ()


@dataclass
class ToolRegistrationConfig:
    """Static description of this tool, used to build the registration request."""

    client_name: str
    initiate_login_uri: str
    redirect_uris: tuple[str, ...]
    jwks_uri: str
    target_link_uri: str
    scopes: tuple[str, ...] = DEFAULT_SCOPES
    claims: tuple[str, ...] = DEFAULT_CLAIMS
    domain: str | None = None
    logo_uri: str | None = None
    description: str | None = None
    custom_parameters: dict[str, str] | None = None
    contacts: tuple[str, ...] | None = None
    messages: tuple[ToolMessage, ...] = ()

    def _domain(self) -> str:
        return self.domain or urlparse(self.target_link_uri).netloc

    def _messages(self) -> list[ToolMessage]:
        if self.messages:
            return list(self.messages)
        # Sensible default: support a basic resource-link launch.
        return [ToolMessage(type=MESSAGE_RESOURCE_LINK)]

    def build_request(self, platform: PlatformConfiguration) -> dict[str, t.Any]:
        """Build the OpenID client registration body to POST to the platform.

        Requested scopes are intersected with the platform's
        ``scopes_supported`` when the platform advertises them.
        """
        if platform.scopes_supported:
            scopes = [s for s in self.scopes if s in platform.scopes_supported]
        else:
            scopes = list(self.scopes)

        lti_config: dict[str, t.Any] = {
            "domain": self._domain(),
            "target_link_uri": self.target_link_uri,
            "claims": list(self.claims),
            "messages": [m.to_dict() for m in self._messages()],
        }
        if self.description:
            lti_config["description"] = self.description
        if self.custom_parameters:
            lti_config["custom_parameters"] = dict(self.custom_parameters)

        body: dict[str, t.Any] = {
            "application_type": "web",
            "response_types": ["id_token"],
            "grant_types": ["client_credentials", "implicit"],
            "initiate_login_uri": self.initiate_login_uri,
            "redirect_uris": list(self.redirect_uris),
            "client_name": self.client_name,
            "jwks_uri": self.jwks_uri,
            "token_endpoint_auth_method": "private_key_jwt",
            "scope": " ".join(scopes),
            LTI_TOOL_CONFIGURATION: lti_config,
        }
        if self.logo_uri:
            body["logo_uri"] = self.logo_uri
        if self.contacts:
            body["contacts"] = list(self.contacts)
        return body
