"""A thin Brightspace (D2L) Valence REST API client — Layer 3, NOT portable.

Reads course content (modules / topics / files) from the Brightspace **Learning
Environment (LE)** API, authenticated by an OAuth2 *client-credentials* Bearer
token minted for a Brightspace **Service User** — no user login. The token's
scopes are Brightspace scopes (``content:modules:read`` …) approved once on the
registered OAuth client; the admin does that at install, the student does nothing.

Brightspace's client-credentials assertion (``iss``=``sub``=client_id, ``aud``=
token endpoint, RS256 + ``kid``) is exactly what
:class:`ltitoolkit.token.AccessTokenService` already produces — only the token
endpoint differs (``https://auth.brightspace.com/core/connect/token``).

Endpoints (per docs.valence.desire2learn.com):

    GET /d2l/api/le/{ver}/{orgUnitId}/content/root/
    GET /d2l/api/le/{ver}/{orgUnitId}/content/modules/{moduleId}/structure/
    GET /d2l/api/le/{ver}/{orgUnitId}/content/topics/{topicId}
    GET /d2l/api/le/{ver}/{orgUnitId}/content/topics/{topicId}/file

Works **only** on Brightspace. Other LMSs need their own adapter.

.. note::
   Response shapes follow the Valence docs. Verify against the client's instance
   and its LE ``version`` (see ``GET /d2l/api/le/versions/``) before the demo.
"""

from __future__ import annotations

import typing as t

import requests

from ...exceptions import ExternalRequestError
from ...http import build_session

# OAuth2 scopes (format: ``<group>:<resource>:<action>``), approved on the
# registered OAuth client / Service User by the admin once.
SCOPE_CONTENT_READ = "content:modules:read"
SCOPE_CONTENT_TOPICS_READ = "content:topics:read"
SCOPE_CONTENT_FILE_READ = "content:file:read"
SCOPE_ENROLLMENT_READ = "enrollment:orgunit:read"

# ContentObject.Type values.
TYPE_MODULE = 0
TYPE_TOPIC = 1

# Topic.TopicType values.
TOPIC_FILE = 1
TOPIC_LINK = 3

# Default LE API version; override per instance.
_DEFAULT_LE_VERSION = "1.74"
# Recursion guard against pathological / cyclic module structures.
_MAX_MODULE_DEPTH = 25


@t.runtime_checkable
class TokenProvider(t.Protocol):
    """Anything that can mint a Bearer token for a set of scopes."""

    def get_token(self, scopes: t.Sequence[str]) -> str: ...


class BrightspaceAPIClient:
    """Read-only convenience wrapper over the Brightspace LE content API."""

    def __init__(
        self,
        base_url: str,
        token_provider: TokenProvider,
        scopes: t.Sequence[str],
        *,
        le_version: str = _DEFAULT_LE_VERSION,
        session: requests.Session | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._tokens = token_provider
        self._scopes = tuple(scopes)
        self._ver = le_version
        self._session = session if session is not None else build_session()

    # -- public API --------------------------------------------------------

    def get_content_root(self, org_unit_id: str | int) -> list[dict[str, t.Any]]:
        """Top-level modules of a course (``Type == TYPE_MODULE``)."""
        return self._get_list(self._le(org_unit_id, "content/root/"))

    def get_module_structure(
        self, org_unit_id: str | int, module_id: str | int
    ) -> list[dict[str, t.Any]]:
        """Direct children of a module — a mix of submodules and topics."""
        return self._get_list(
            self._le(org_unit_id, f"content/modules/{module_id}/structure/")
        )

    def get_topic(self, org_unit_id: str | int, topic_id: str | int) -> dict[str, t.Any]:
        """Metadata for a single topic (``Title``, ``TopicType``, ``Url`` …)."""
        return self._get_json(self._le(org_unit_id, f"content/topics/{topic_id}"))

    def download_topic_file(
        self, org_unit_id: str | int, topic_id: str | int, *, stream: bool = False
    ) -> bytes:
        """Raw bytes of a file-type topic (feed to NeuralMentor's ingestion)."""
        params = {"stream": "true"} if stream else None
        response = self._request(
            self._le(org_unit_id, f"content/topics/{topic_id}/file"), params
        )
        return response.content

    def list_course_topics(self, org_unit_id: str | int) -> list[dict[str, t.Any]]:
        """Flat list of every topic in a course (walks the full module tree).

        Each topic is the raw ContentObject; useful as "the course's lessons" to
        feed into a lesson-generation pipeline. Submodules are traversed; cycles
        and excessive depth are guarded against.
        """
        topics: list[dict[str, t.Any]] = []
        seen: set[t.Any] = set()

        def walk(entries: list[dict[str, t.Any]], depth: int) -> None:
            if depth > _MAX_MODULE_DEPTH:
                return
            for obj in entries:
                if obj.get("Type") == TYPE_TOPIC:
                    topics.append(obj)
                elif obj.get("Type") == TYPE_MODULE:
                    module_id = obj.get("Id")
                    if module_id is None or module_id in seen:
                        continue
                    seen.add(module_id)
                    walk(self.get_module_structure(org_unit_id, module_id), depth + 1)

        walk(self.get_content_root(org_unit_id), 0)
        return topics

    # -- internals ---------------------------------------------------------

    def _le(self, org_unit_id: str | int, path: str) -> str:
        return f"{self._base}/d2l/api/le/{self._ver}/{org_unit_id}/{path}"

    def _headers(self) -> dict[str, str]:
        token = self._tokens.get_token(self._scopes)
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    def _request(
        self, url: str, params: dict[str, t.Any] | None = None
    ) -> requests.Response:
        try:
            response = self._session.get(url, params=params, headers=self._headers())
        except requests.Timeout as exc:
            raise ExternalRequestError(
                f"Timed out calling Brightspace: {exc}", url=url, is_timeout=True
            ) from exc
        except requests.RequestException as exc:
            raise ExternalRequestError(
                f"Error calling Brightspace: {exc}", url=url
            ) from exc

        if not response.ok:
            raise ExternalRequestError(
                "Brightspace API request failed",
                status_code=response.status_code,
                url=url,
                response_text=response.text,
            )
        return response

    def _get_json(self, url: str) -> dict[str, t.Any]:
        return self._request(url).json()

    def _get_list(self, url: str) -> list[dict[str, t.Any]]:
        body = self._request(url).json()
        if not isinstance(body, list):
            raise ExternalRequestError("Expected a list response from Brightspace", url=url)
        return body
