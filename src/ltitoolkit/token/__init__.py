"""Generic OAuth2 client-credentials token minting.

The tool authenticates to an LMS by signing a JWT with its *own* private key
(the key behind its JWKS) and exchanging it for an access token via the
client-credentials grant — no user login, no copied credentials.

This is reused for both LTI Advantage service calls (AGS/NRPS — portable) and
LMS-proprietary API calls (Canvas etc. — used by per-LMS adapters). Only the
*scopes* and *endpoints* differ per LMS; the auth mechanism here is shared.
"""

from .cache import AccessToken, InMemoryTokenCache, TokenCache
from .service import AccessTokenService

__all__ = [
    "AccessToken",
    "TokenCache",
    "InMemoryTokenCache",
    "AccessTokenService",
]
