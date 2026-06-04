"""Client-credentials access-token service.

The tool authenticates to an LMS by signing a short-lived *client assertion* JWT
with its own private key and exchanging it (``grant_type=client_credentials``)
for an access token — no user login, no copied secrets. This is the auth half of
both LTI Advantage service calls and LMS-proprietary API calls (e.g. listing
Canvas files); only the requested *scopes* differ.

This service adds, on top of the vendored core's signing:

- **expiry-aware caching** (reuse a token until it nears expiry), and
- **explicit timeouts** and **typed errors**

which the core's in-memory token cache lacks. The security-critical RSA signing
is delegated to PyJWT exactly as the core does it.
"""

from __future__ import annotations

import hashlib
import time
import typing as t
import uuid

import jwt
import requests

from ..exceptions import AccessTokenError
from ..http import build_session
from .cache import AccessToken, InMemoryTokenCache, TokenCache

if t.TYPE_CHECKING:
    from ..core.registration import Registration

_JWT_BEARER = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
# Client-assertion lifetime. Kept short per the LTI security spec.
_ASSERTION_LIFETIME = 60
# Fallback token lifetime if the platform omits ``expires_in``.
_DEFAULT_TOKEN_LIFETIME = 3600


class AccessTokenService:
    """Mint and cache client-credentials access tokens for a registration."""

    def __init__(
        self,
        registration: Registration,
        *,
        session: requests.Session | None = None,
        cache: TokenCache | None = None,
        timeout: float | tuple[float, float] = (10.0, 30.0),
        expiry_leeway: float = 60.0,
        clock: t.Callable[[], float] = time.time,
    ) -> None:
        self._registration = registration
        self._session = session if session is not None else build_session(timeout=timeout)
        self._cache: TokenCache = cache if cache is not None else InMemoryTokenCache()
        self._timeout = timeout
        self._leeway = expiry_leeway
        self._clock = clock

    def get_token(self, scopes: t.Sequence[str]) -> str:
        """Return a valid access token for ``scopes``, minting one if needed."""
        if not scopes:
            raise ValueError("At least one scope is required")

        key = self._cache_key(scopes)
        cached = self._cache.get(key)
        if cached is not None and not cached.is_expired(
            leeway=self._leeway, now=self._clock()
        ):
            return cached.value

        token = self._request_token(scopes)
        self._cache.set(key, token)
        return token.value

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _cache_key(scopes: t.Sequence[str]) -> str:
        canonical = "|".join(sorted(scopes)).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def _build_client_assertion(self) -> str:
        client_id = self._registration.get_client_id()
        token_url = self._registration.get_auth_token_url()
        assert client_id is not None, "Registration is missing client_id"
        assert token_url is not None, "Registration is missing auth_token_url"
        audience = self._registration.get_auth_audience() or token_url
        private_key = self._registration.get_tool_private_key()
        assert private_key is not None, "Registration is missing the tool private key"

        now = int(self._clock())
        claims: dict[str, t.Any] = {
            "iss": str(client_id),
            "sub": str(client_id),
            "aud": str(audience),
            "iat": now - 5,
            "exp": now + _ASSERTION_LIFETIME,
            "jti": "ltitoolkit-" + uuid.uuid4().hex,
        }
        headers: dict[str, str] = {}
        kid = self._registration.get_kid()
        if kid:
            headers["kid"] = kid

        encoded = jwt.encode(claims, private_key, algorithm="RS256", headers=headers)
        # PyJWT < 2 returned bytes; normalise to str.
        return encoded.decode("utf-8") if isinstance(encoded, bytes) else encoded

    def _request_token(self, scopes: t.Sequence[str]) -> AccessToken:
        token_url = self._registration.get_auth_token_url()
        assert token_url is not None, "Registration is missing auth_token_url"

        payload = {
            "grant_type": "client_credentials",
            "client_assertion_type": _JWT_BEARER,
            "client_assertion": self._build_client_assertion(),
            "scope": " ".join(scopes),
        }

        try:
            response = self._session.post(token_url, data=payload, timeout=self._timeout)
        except requests.Timeout as exc:
            raise AccessTokenError(
                f"Timed out requesting access token: {exc}",
                url=token_url,
                is_timeout=True,
            ) from exc
        except requests.RequestException as exc:
            raise AccessTokenError(
                f"Error requesting access token: {exc}", url=token_url
            ) from exc

        if not response.ok:
            raise AccessTokenError(
                "Access token request rejected by the platform",
                status_code=response.status_code,
                url=token_url,
                response_text=response.text,
            )

        try:
            body = response.json()
            access_token = body["access_token"]
        except (ValueError, KeyError, TypeError) as exc:
            raise AccessTokenError(
                "Malformed access token response from the platform",
                status_code=response.status_code,
                url=token_url,
                response_text=response.text,
            ) from exc

        expires_in = body.get("expires_in", _DEFAULT_TOKEN_LIFETIME)
        try:
            expires_at = self._clock() + float(expires_in)
        except (TypeError, ValueError):
            expires_at = self._clock() + _DEFAULT_TOKEN_LIFETIME

        return AccessToken(
            value=access_token,
            scopes=tuple(sorted(scopes)),
            expires_at=expires_at,
        )
