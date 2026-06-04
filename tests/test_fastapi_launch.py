"""End-to-end LTI 1.3 launch through the FastAPI adapter.

A simulated platform (its own RSA key) signs an ``id_token``; the tool, built on
the FastAPI adapter, runs the real two-step flow:

  GET  /login   -> 302 redirect to the platform auth endpoint (state + nonce set)
  POST /launch  -> id_token validated, launch claims extracted

The test is hermetic: the platform's public JWKS is supplied inline via the tool
config's ``key_set``, so validation performs no network I/O.
"""

from __future__ import annotations

import json
import time
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from jwcrypto.jwk import JWK
from starlette.middleware.sessions import SessionMiddleware

from ltitoolkit.core.exception import LtiException
from ltitoolkit.core.tool_config.dict import ToolConfDict
from ltitoolkit.fastapi import (
    FastApiMessageLaunch,
    FastApiOIDCLogin,
    FastApiRequest,
)

ISS = "https://canvas.test.instructure.com"
CLIENT_ID = "test-client-123"
DEPLOYMENT_ID = "dep-1"
PLATFORM_KID = "platform-kid-1"
TARGET_LINK_URI = "https://tool.example/launch"


@pytest.fixture
def platform_key() -> JWK:
    return JWK.generate(kty="RSA", size=2048, kid=PLATFORM_KID, use="sig", alg="RS256")


@pytest.fixture
def tool_config(platform_key: JWK) -> ToolConfDict:
    public_jwk = json.loads(platform_key.export_public())
    public_jwk["alg"] = "RS256"
    public_jwk["use"] = "sig"

    tool_key = JWK.generate(kty="RSA", size=2048, kid="tool-kid-1", use="sig", alg="RS256")

    conf = ToolConfDict(
        {
            ISS: {
                "client_id": CLIENT_ID,
                "auth_login_url": f"{ISS}/api/lti/authorize_redirect",
                "auth_token_url": f"{ISS}/login/oauth2/token",
                "key_set": {"keys": [public_jwk]},  # inline -> no network fetch
                "deployment_ids": [DEPLOYMENT_ID],
            }
        }
    )
    conf.set_private_key(ISS, tool_key.export_to_pem(private_key=True, password=None).decode())
    conf.set_public_key(ISS, tool_key.export_to_pem().decode())
    return conf


@pytest.fixture
def app(tool_config: ToolConfDict) -> FastAPI:
    application = FastAPI()
    application.add_middleware(SessionMiddleware, secret_key="test-session-secret")

    @application.api_route("/login", methods=["GET", "POST"])
    async def login(request: Request):  # type: ignore[no-untyped-def]
        lti_request = await FastApiRequest.from_request(request)
        oidc = FastApiOIDCLogin(lti_request, tool_config)
        return oidc.redirect(lti_request.get_param("target_link_uri"))

    @application.post("/launch")
    async def launch(request: Request):  # type: ignore[no-untyped-def]
        lti_request = await FastApiRequest.from_request(request)
        message_launch = FastApiMessageLaunch(lti_request, tool_config)
        await message_launch.validate_async()
        data = message_launch.get_launch_data()
        return {
            "name": data.get("name"),
            "roles": data.get("https://purl.imsglobal.org/spec/lti/claim/roles"),
            "context": data.get("https://purl.imsglobal.org/spec/lti/claim/context"),
            "is_resource_launch": message_launch.is_resource_launch(),
        }

    return application


def _make_id_token(platform_key: JWK, nonce: str) -> str:
    now = int(time.time())
    claims = {
        "iss": ISS,
        "aud": CLIENT_ID,
        "sub": "user-1",
        "exp": now + 3600,
        "iat": now - 5,
        "nonce": nonce,
        "name": "Ada Student",
        "https://purl.imsglobal.org/spec/lti/claim/deployment_id": DEPLOYMENT_ID,
        "https://purl.imsglobal.org/spec/lti/claim/message_type": "LtiResourceLinkRequest",
        "https://purl.imsglobal.org/spec/lti/claim/version": "1.3.0",
        "https://purl.imsglobal.org/spec/lti/claim/roles": [
            "http://purl.imsglobal.org/vocab/lis/v2/membership#Learner"
        ],
        "https://purl.imsglobal.org/spec/lti/claim/resource_link": {"id": "res-1"},
        "https://purl.imsglobal.org/spec/lti/claim/context": {
            "id": "course-sci-1",
            "label": "SCI",
            "title": "Science",
        },
        "https://purl.imsglobal.org/spec/lti/claim/target_link_uri": TARGET_LINK_URI,
    }
    private_pem = platform_key.export_to_pem(private_key=True, password=None).decode()
    return jwt.encode(claims, private_pem, algorithm="RS256", headers={"kid": PLATFORM_KID})


def test_full_login_then_launch(app: FastAPI, platform_key: JWK) -> None:
    client = TestClient(app)

    # Step 1: OIDC login initiation -> redirect to platform auth endpoint.
    login_resp = client.get(
        "/login",
        params={
            "iss": ISS,
            "login_hint": "user-1",
            "target_link_uri": TARGET_LINK_URI,
            "client_id": CLIENT_ID,
        },
        follow_redirects=False,
    )
    assert login_resp.status_code == 302
    location = urlparse(login_resp.headers["location"])
    query = parse_qs(location.query)
    assert location.path == "/api/lti/authorize_redirect"
    assert query["client_id"] == [CLIENT_ID]
    assert query["redirect_uri"] == [TARGET_LINK_URI]
    assert query["response_type"] == ["id_token"]
    assert query["response_mode"] == ["form_post"]
    state = query["state"][0]
    nonce = query["nonce"][0]

    # Step 2: platform posts a signed id_token back to the launch URL.
    id_token = _make_id_token(platform_key, nonce)
    launch_resp = client.post("/launch", data={"state": state, "id_token": id_token})

    assert launch_resp.status_code == 200, launch_resp.text
    body = launch_resp.json()
    assert body["name"] == "Ada Student"
    assert body["is_resource_launch"] is True
    assert body["context"]["title"] == "Science"
    assert "Learner" in body["roles"][0]


def test_launch_rejects_tampered_token(app: FastAPI, platform_key: JWK) -> None:
    """A token signed by an unknown key must fail signature validation."""
    client = TestClient(app)
    login_resp = client.get(
        "/login",
        params={
            "iss": ISS,
            "login_hint": "user-1",
            "target_link_uri": TARGET_LINK_URI,
            "client_id": CLIENT_ID,
        },
        follow_redirects=False,
    )
    state = parse_qs(urlparse(login_resp.headers["location"]).query)["state"][0]
    nonce = parse_qs(urlparse(login_resp.headers["location"]).query)["nonce"][0]

    # Sign with a DIFFERENT key but reuse the trusted kid -> signature must fail.
    rogue_key = JWK.generate(kty="RSA", size=2048, kid=PLATFORM_KID, use="sig", alg="RS256")
    forged = _make_id_token(rogue_key, nonce)

    # TestClient re-raises unhandled server exceptions; signature check must reject.
    with pytest.raises(LtiException, match="Signature verification failed"):
        client.post("/launch", data={"state": state, "id_token": forged})
