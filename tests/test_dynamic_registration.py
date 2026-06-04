"""Tests for LTI 1.3 Dynamic Registration (fully offline)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from jwcrypto.jwk import JWK

from ltitoolkit.dynamic_registration import (
    DynamicRegistrationService,
    InMemoryRegistrationStore,
    StoredToolConf,
    ToolMessage,
    ToolRegistration,
    ToolRegistrationConfig,
)
from ltitoolkit.dynamic_registration.models import (
    LTI_TOOL_CONFIGURATION,
    MESSAGE_DEEP_LINKING,
    MESSAGE_RESOURCE_LINK,
    SCOPE_AGS_SCORE,
    SCOPE_NRPS,
    PlatformConfiguration,
)
from ltitoolkit.fastapi.dynamic_registration import handle_dynamic_registration

ISS = "https://canvas.test.instructure.com"
OPENID_CONFIG_URL = f"{ISS}/api/lti/security/openid-configuration"

PLATFORM_DOC = {
    "issuer": ISS,
    "authorization_endpoint": f"{ISS}/api/lti/authorize_redirect",
    "token_endpoint": f"{ISS}/login/oauth2/token",
    "jwks_uri": f"{ISS}/api/lti/security/jwks",
    "registration_endpoint": f"{ISS}/api/lti/registrations",
    "scopes_supported": [SCOPE_AGS_SCORE, SCOPE_NRPS],
    "https://purl.imsglobal.org/spec/lti-platform-configuration": {
        "product_family_code": "canvas",
        "version": "1.3",
    },
}

REGISTRATION_RESPONSE = {
    "client_id": "10000000000123",
    LTI_TOOL_CONFIGURATION: {"deployment_id": "1:abcdef"},
}


@dataclass
class FakeResponse:
    ok: bool
    status_code: int
    json_body: dict | None = None
    text: str = ""

    def json(self) -> dict:
        if self.json_body is None:
            raise ValueError("no json body")
        return self.json_body


@dataclass
class FakeSession:
    get_response: FakeResponse | None = None
    post_response: FakeResponse | None = None
    get_calls: list = field(default_factory=list)
    post_calls: list = field(default_factory=list)

    def get(self, url, timeout=None):
        self.get_calls.append({"url": url, "timeout": timeout})
        return self.get_response

    def post(self, url, json=None, headers=None, timeout=None):
        self.post_calls.append({"url": url, "json": json, "headers": headers})
        return self.post_response


def make_tool_config() -> ToolRegistrationConfig:
    return ToolRegistrationConfig(
        client_name="AI Tutor",
        initiate_login_uri="https://tool.test/lti/login",
        redirect_uris=("https://tool.test/lti/launch",),
        jwks_uri="https://tool.test/lti/jwks",
        target_link_uri="https://tool.test/lti/launch",
        scopes=(SCOPE_AGS_SCORE, SCOPE_NRPS, "https://unsupported.example/scope"),
        messages=(
            ToolMessage(type=MESSAGE_RESOURCE_LINK),
            ToolMessage(type=MESSAGE_DEEP_LINKING, target_link_uri="https://tool.test/lti/dl"),
        ),
    )


# -- build_request ----------------------------------------------------------


def test_build_request_shape():
    platform = PlatformConfiguration.from_dict(PLATFORM_DOC)
    body = make_tool_config().build_request(platform)

    assert body["application_type"] == "web"
    assert body["response_types"] == ["id_token"]
    assert body["token_endpoint_auth_method"] == "private_key_jwt"
    assert body["initiate_login_uri"] == "https://tool.test/lti/login"
    assert body["redirect_uris"] == ["https://tool.test/lti/launch"]
    assert body["jwks_uri"] == "https://tool.test/lti/jwks"

    # Unsupported scope is dropped (intersection with platform scopes_supported).
    assert "https://unsupported.example/scope" not in body["scope"]
    assert SCOPE_AGS_SCORE in body["scope"]

    lti = body[LTI_TOOL_CONFIGURATION]
    assert lti["domain"] == "tool.test"
    assert lti["target_link_uri"] == "https://tool.test/lti/launch"
    message_types = {m["type"] for m in lti["messages"]}
    assert message_types == {MESSAGE_RESOURCE_LINK, MESSAGE_DEEP_LINKING}


# -- register flow ----------------------------------------------------------


def test_register_persists_and_returns_registration():
    session = FakeSession(
        get_response=FakeResponse(True, 200, PLATFORM_DOC),
        post_response=FakeResponse(True, 201, REGISTRATION_RESPONSE),
    )
    store = InMemoryRegistrationStore()
    service = DynamicRegistrationService(make_tool_config(), store, session=session)

    registration = service.register(OPENID_CONFIG_URL, registration_token="secret-token")

    # Returned + persisted registration is correct.
    assert registration.issuer == ISS
    assert registration.client_id == "10000000000123"
    assert registration.auth_login_url == f"{ISS}/api/lti/authorize_redirect"
    assert registration.auth_token_url == f"{ISS}/login/oauth2/token"
    assert registration.key_set_url == f"{ISS}/api/lti/security/jwks"
    assert registration.deployment_ids == ("1:abcdef",)
    assert store.get(ISS, "10000000000123") == registration

    # The registration token was sent as a Bearer header.
    assert session.post_calls[0]["headers"]["Authorization"] == "Bearer secret-token"


def test_register_rejects_response_without_client_id():
    session = FakeSession(
        get_response=FakeResponse(True, 200, PLATFORM_DOC),
        post_response=FakeResponse(True, 201, {"no_client": "here"}),
    )
    service = DynamicRegistrationService(
        make_tool_config(), InMemoryRegistrationStore(), session=session
    )
    from ltitoolkit.exceptions import ExternalRequestError

    with pytest.raises(ExternalRequestError):
        service.register(OPENID_CONFIG_URL)


# -- StoredToolConf ---------------------------------------------------------


def test_stored_tool_conf_resolves_registration_and_deployment():
    key = JWK.generate(kty="RSA", size=2048, kid="tool-kid", use="sig", alg="RS256")
    private_pem = key.export_to_pem(private_key=True, password=None).decode()
    public_pem = key.export_to_pem().decode()

    store = InMemoryRegistrationStore()
    store.save(
        ToolRegistration(
            issuer=ISS,
            client_id="client-9",
            auth_login_url=f"{ISS}/auth",
            auth_token_url=f"{ISS}/token",
            key_set_url=f"{ISS}/jwks",
        )
    )
    conf = StoredToolConf(store, private_key=private_pem, public_key=public_pem)

    registration = conf.find_registration_by_params(ISS, "client-9")
    assert registration.get_client_id() == "client-9"
    assert registration.get_auth_token_url() == f"{ISS}/token"
    assert registration.get_tool_private_key() == private_pem
    assert registration.get_kid()  # derived from the public key

    # No deployment_ids captured -> any deployment from the launch is accepted.
    deployment = conf.find_deployment_by_params(ISS, "dep-xyz", "client-9")
    assert deployment is not None
    assert deployment.get_deployment_id() == "dep-xyz"

    # Unknown client -> no deployment.
    assert conf.find_deployment_by_params(ISS, "dep-xyz", "unknown") is None


# -- completion HTML + FastAPI endpoint ------------------------------------


def test_completion_html_contains_close_postmessage():
    html = DynamicRegistrationService.completion_html()
    assert "postMessage" in html
    assert "org.imsglobal.lti.close" in html


def test_fastapi_endpoint_registers_and_returns_html():
    session = FakeSession(
        get_response=FakeResponse(True, 200, PLATFORM_DOC),
        post_response=FakeResponse(True, 201, REGISTRATION_RESPONSE),
    )
    store = InMemoryRegistrationStore()
    service = DynamicRegistrationService(make_tool_config(), store, session=session)

    app = FastAPI()

    @app.api_route("/lti/register", methods=["GET", "POST"])
    async def register(request: Request):  # type: ignore[no-untyped-def]
        return await handle_dynamic_registration(request, service)

    client = TestClient(app)
    resp = client.get(
        "/lti/register", params={"openid_configuration": OPENID_CONFIG_URL}
    )

    assert resp.status_code == 200
    assert "org.imsglobal.lti.close" in resp.text
    assert store.get(ISS, "10000000000123") is not None


def test_fastapi_endpoint_missing_openid_configuration():
    service = DynamicRegistrationService(
        make_tool_config(), InMemoryRegistrationStore(), session=FakeSession()
    )
    app = FastAPI()

    @app.get("/lti/register")
    async def register(request: Request):  # type: ignore[no-untyped-def]
        return await handle_dynamic_registration(request, service)

    resp = TestClient(app).get("/lti/register")
    assert resp.status_code == 400
