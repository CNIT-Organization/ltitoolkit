"""Tests for the Canvas Layer-3 adapter (fully offline)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
import requests

from ltitoolkit.adapters.canvas import (
    SCOPE_LIST_COURSE_FILES,
    CanvasAPIClient,
)
from ltitoolkit.exceptions import ExternalRequestError

BASE = "https://canvas.test.instructure.com"


@dataclass
class FakeResponse:
    ok: bool
    status_code: int
    json_body: object = None
    links: dict = field(default_factory=dict)
    text: str = ""

    def json(self):
        return self.json_body


@dataclass
class FakeSession:
    responses: list = field(default_factory=list)
    raise_exc: Exception | None = None
    calls: list = field(default_factory=list)

    def get(self, url, params=None, headers=None):
        self.calls.append({"url": url, "params": params, "headers": headers})
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.responses.pop(0)


class FakeTokenProvider:
    def __init__(self) -> None:
        self.requested_scopes: list = []

    def get_token(self, scopes):
        self.requested_scopes.append(tuple(scopes))
        return "tok-123"


def make_client(session, scopes=(SCOPE_LIST_COURSE_FILES,)):
    return CanvasAPIClient(BASE, FakeTokenProvider(), scopes, session=session)


def test_list_course_files_follows_pagination():
    session = FakeSession(
        responses=[
            FakeResponse(
                True,
                200,
                [{"id": 1, "display_name": "a.pdf"}],
                links={"next": {"url": f"{BASE}/api/v1/courses/9/files?page=2"}},
            ),
            FakeResponse(True, 200, [{"id": 2, "display_name": "b.pdf"}], links={}),
        ]
    )
    client = make_client(session)

    files = client.list_course_files(9)

    assert [f["id"] for f in files] == [1, 2]
    assert len(session.calls) == 2
    # First call hits the course files path with per_page; second follows next link.
    assert session.calls[0]["url"] == f"{BASE}/api/v1/courses/9/files"
    assert session.calls[0]["params"]["per_page"] == 50
    assert session.calls[1]["url"] == f"{BASE}/api/v1/courses/9/files?page=2"


def test_requests_carry_bearer_token():
    session = FakeSession(responses=[FakeResponse(True, 200, [], links={})])
    provider = FakeTokenProvider()
    client = CanvasAPIClient(BASE, provider, (SCOPE_LIST_COURSE_FILES,), session=session)

    client.list_course_files(9)

    assert session.calls[0]["headers"]["Authorization"] == "Bearer tok-123"
    assert provider.requested_scopes == [(SCOPE_LIST_COURSE_FILES,)]


def test_list_quizzes():
    session = FakeSession(
        responses=[FakeResponse(True, 200, [{"id": 5, "title": "Quiz 1"}], links={})]
    )
    quizzes = make_client(session).list_quizzes(9)
    assert quizzes[0]["title"] == "Quiz 1"
    assert session.calls[0]["url"] == f"{BASE}/api/v1/courses/9/quizzes"


def test_get_file_public_url():
    session = FakeSession(
        responses=[FakeResponse(True, 200, {"public_url": "https://files.example/a.pdf"})]
    )
    url = make_client(session).get_file_public_url(123)
    assert url == "https://files.example/a.pdf"
    assert session.calls[0]["url"] == f"{BASE}/api/v1/files/123/public_url"


def test_get_file_public_url_missing_raises():
    session = FakeSession(responses=[FakeResponse(True, 200, {})])
    with pytest.raises(ExternalRequestError):
        make_client(session).get_file_public_url(123)


def test_non_2xx_raises_external_request_error():
    session = FakeSession(responses=[FakeResponse(False, 403, None, text="forbidden")])
    with pytest.raises(ExternalRequestError) as exc_info:
        make_client(session).list_quizzes(9)
    assert exc_info.value.status_code == 403


def test_timeout_is_flagged():
    session = FakeSession(raise_exc=requests.Timeout("slow"))
    with pytest.raises(ExternalRequestError) as exc_info:
        make_client(session).list_quizzes(9)
    assert exc_info.value.is_timeout is True
