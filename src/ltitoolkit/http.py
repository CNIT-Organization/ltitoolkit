"""HTTP session construction with sane, safe defaults.

The vendored core issues requests with **no timeout**, which can hang a worker
indefinitely if the LMS stalls. Rather than patch the vendored code, we provide
a session whose adapter injects a default timeout on every request, and we pass
that session into the core services and our own token service.

Retries are **disabled by default** and, when enabled, are restricted to
idempotent methods (GET/HEAD/OPTIONS). LTI score submission and token requests
are POSTs and must never be retried blindly (risk of duplicate side effects).
"""

from __future__ import annotations

import typing as t

import requests
from requests.adapters import HTTPAdapter
from requests.models import PreparedRequest
from urllib3.util.retry import Retry

# (connect timeout, read timeout) in seconds.
DEFAULT_TIMEOUT: tuple[float, float] = (10.0, 30.0)

_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class TimeoutHTTPAdapter(HTTPAdapter):
    """An adapter that applies a default timeout when a call omits one."""

    def __init__(
        self, *args: t.Any, timeout: float | tuple[float, float] = DEFAULT_TIMEOUT, **kwargs: t.Any
    ) -> None:
        self._timeout = timeout
        super().__init__(*args, **kwargs)

    def send(  # noqa: PLR0913 - signature mirrors requests' HTTPAdapter.send
        self,
        request: PreparedRequest,
        stream: bool = False,
        timeout: t.Any = None,
        verify: t.Any = True,
        cert: t.Any = None,
        proxies: t.Any = None,
    ) -> t.Any:
        if timeout is None:
            timeout = self._timeout
        return super().send(
            request, stream=stream, timeout=timeout, verify=verify, cert=cert, proxies=proxies
        )


def build_session(
    *,
    timeout: float | tuple[float, float] = DEFAULT_TIMEOUT,
    retries: int = 0,
    backoff_factor: float = 0.3,
    user_agent: str = "ltitoolkit",
) -> requests.Session:
    """Create a ``requests.Session`` with a default timeout and optional retries.

    :param timeout: default ``(connect, read)`` timeout for every request.
    :param retries: max retries for *idempotent* methods only (0 disables them).
    :param backoff_factor: exponential backoff between retries.
    :param user_agent: ``User-Agent`` header sent with every request.
    """
    session = requests.Session()
    session.headers["User-Agent"] = user_agent

    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=_IDEMPOTENT_METHODS,
        raise_on_status=False,
    )
    adapter = TimeoutHTTPAdapter(timeout=timeout, max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session
