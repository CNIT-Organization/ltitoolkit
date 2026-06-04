"""Tests for the client-credentials AccessTokenService (fully offline)."""

from __future__ import annotations

from dataclasses import dataclass, field

import jwt
import pytest
import requests
from jwcrypto.jwk import JWK

from ltitoolkit.core.registration import Registration
from ltitoolkit.exceptions import AccessTokenError
from ltitoolkit.token import AccessTokenService

TOKEN_URL = "https://lms.test/login/oauth2/token"
CLIENT_ID = "client-1"


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
    responses: list = field(default_factory=list)
    raise_exc: Exception | None = None
    calls: list = field(default_factory=list)

    def post(self, url, data=None, timeout=None):
        self.calls.append({"url": url, "data": data, "timeout": timeout})
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.responses.pop(0)


@pytest.fixture(scope="module")
def keypair() -> tuple[str, str]:
    key = JWK.generate(kty="RSA", size=2048, kid="tool-kid-1", use="sig", alg="RS256")
    private_pem = key.export_to_pem(private_key=True, password=None).decode()
    public_pem = key.export_to_pem().decode()
    return private_pem, public_pem


def make_registration(private_pem: str) -> Registration:
    return (
        Registration()
        .set_client_id(CLIENT_ID)
        .set_auth_token_url(TOKEN_URL)
        .set_tool_private_key(private_pem)
    )


def ok_token(access="abc", expires_in=3600) -> FakeResponse:
    return FakeResponse(True, 200, {"access_token": access, "expires_in": expires_in})


def test_mint_token_and_assertion_claims(keypair):
    private_pem, public_pem = keypair
    session = FakeSession(responses=[ok_token("the-token")])
    service = AccessTokenService(
        make_registration(private_pem), session=session, clock=lambda: 1000.0
    )

    token = service.get_token(["scopeA", "scopeB"])

    assert token == "the-token"
    assert len(session.calls) == 1
    sent = session.calls[0]["data"]
    assert sent["grant_type"] == "client_credentials"
    assert sent["client_assertion_type"].endswith("jwt-bearer")
    assert sent["scope"] == "scopeA scopeB"

    # The client assertion is a valid RS256 JWT with the right LTI claims.
    claims = jwt.decode(
        sent["client_assertion"],
        public_pem,
        algorithms=["RS256"],
        audience=TOKEN_URL,
        options={"verify_exp": False, "verify_iat": False},
    )
    assert claims["iss"] == CLIENT_ID
    assert claims["sub"] == CLIENT_ID
    assert claims["jti"].startswith("ltitoolkit-")


def test_token_is_cached_per_scope(keypair):
    private_pem, _ = keypair
    session = FakeSession(responses=[ok_token()])
    service = AccessTokenService(
        make_registration(private_pem), session=session, clock=lambda: 1000.0
    )

    service.get_token(["s"])
    service.get_token(["s"])  # served from cache

    assert len(session.calls) == 1


def test_token_refetched_after_expiry(keypair):
    private_pem, _ = keypair
    clock = {"t": 1000.0}
    session = FakeSession(responses=[ok_token("t1", 100), ok_token("t2", 100)])
    service = AccessTokenService(
        make_registration(private_pem),
        session=session,
        clock=lambda: clock["t"],
        expiry_leeway=60,
    )

    assert service.get_token(["s"]) == "t1"  # expires_at = 1100
    clock["t"] = 1039  # now < 1100 - 60 -> still valid
    assert service.get_token(["s"]) == "t1"
    clock["t"] = 1041  # now >= 1040 -> within leeway, refetch
    assert service.get_token(["s"]) == "t2"
    assert len(session.calls) == 2


def test_non_2xx_raises_access_token_error(keypair):
    private_pem, _ = keypair
    session = FakeSession(responses=[FakeResponse(False, 401, None, "denied")])
    service = AccessTokenService(make_registration(private_pem), session=session)

    with pytest.raises(AccessTokenError) as exc_info:
        service.get_token(["s"])
    assert exc_info.value.status_code == 401
    assert exc_info.value.is_timeout is False


def test_timeout_raises_flagged_error(keypair):
    private_pem, _ = keypair
    session = FakeSession(raise_exc=requests.Timeout("too slow"))
    service = AccessTokenService(make_registration(private_pem), session=session)

    with pytest.raises(AccessTokenError) as exc_info:
        service.get_token(["s"])
    assert exc_info.value.is_timeout is True


def test_empty_scopes_rejected(keypair):
    private_pem, _ = keypair
    service = AccessTokenService(make_registration(private_pem), session=FakeSession())
    with pytest.raises(ValueError):
        service.get_token([])
