"""Tests for the Brightspace Layer-3 adapter (fully offline)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
import requests

from ltitoolkit.adapters.brightspace import (
    SCOPE_CONTENT_READ,
    TYPE_MODULE,
    TYPE_TOPIC,
    BrightspaceAPIClient,
)
from ltitoolkit.exceptions import ExternalRequestError

BASE = "https://university.brightspace.com"
VER = "1.74"


@dataclass
class FakeResponse:
    ok: bool
    status_code: int
    json_body: object = None
    content: bytes = b""
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
        return "tok-xyz"


def make_client(session, scopes=(SCOPE_CONTENT_READ,)):
    return BrightspaceAPIClient(
        BASE, FakeTokenProvider(), scopes, le_version=VER, session=session
    )


def _module(id_, title):
    return {"Id": id_, "Title": title, "Type": TYPE_MODULE}


def _topic(id_, title):
    return {"Id": id_, "Title": title, "Type": TYPE_TOPIC, "TopicType": 1}


def test_get_content_root_path_and_bearer():
    session = FakeSession(responses=[FakeResponse(True, 200, [_module(1, "Week 1")])])
    provider = FakeTokenProvider()
    client = BrightspaceAPIClient(
        BASE, provider, (SCOPE_CONTENT_READ,), le_version=VER, session=session
    )

    modules = client.get_content_root(123)

    assert modules[0]["Title"] == "Week 1"
    assert session.calls[0]["url"] == f"{BASE}/d2l/api/le/{VER}/123/content/root/"
    assert session.calls[0]["headers"]["Authorization"] == "Bearer tok-xyz"
    assert provider.requested_scopes == [(SCOPE_CONTENT_READ,)]


def test_list_course_topics_walks_module_tree():
    # root -> [module 1]; module 1 -> [topic 10, submodule 2]; submodule 2 -> [topic 11]
    session = FakeSession(
        responses=[
            FakeResponse(True, 200, [_module(1, "Unit 1")]),                  # root
            FakeResponse(True, 200, [_topic(10, "Intro"), _module(2, "Unit 1.1")]),  # mod 1
            FakeResponse(True, 200, [_topic(11, "Deep dive")]),               # mod 2
        ]
    )
    client = make_client(session)

    topics = client.list_course_topics(123)

    assert [t["Id"] for t in topics] == [10, 11]
    # 3 calls: root + structure(1) + structure(2)
    assert len(session.calls) == 3
    assert session.calls[1]["url"].endswith("/content/modules/1/structure/")
    assert session.calls[2]["url"].endswith("/content/modules/2/structure/")


def test_list_course_topics_guards_module_cycles():
    # module 1's structure references module 1 again -> must not loop forever.
    session = FakeSession(
        responses=[
            FakeResponse(True, 200, [_module(1, "Unit 1")]),       # root
            FakeResponse(True, 200, [_module(1, "Unit 1 again"), _topic(9, "T")]),  # mod 1
        ]
    )
    topics = make_client(session).list_course_topics(123)
    assert [t["Id"] for t in topics] == [9]
    assert len(session.calls) == 2  # root + structure(1) once; cycle skipped


def test_get_topic():
    session = FakeSession(
        responses=[FakeResponse(True, 200, {"Id": 10, "Title": "Intro", "TopicType": 1})]
    )
    topic = make_client(session).get_topic(123, 10)
    assert topic["Title"] == "Intro"
    assert session.calls[0]["url"] == f"{BASE}/d2l/api/le/{VER}/123/content/topics/10"


def test_download_topic_file_returns_bytes():
    session = FakeSession(responses=[FakeResponse(True, 200, content=b"%PDF-1.4 ...")])
    data = make_client(session).download_topic_file(123, 10)
    assert data == b"%PDF-1.4 ..."
    assert session.calls[0]["url"].endswith("/content/topics/10/file")


def test_non_2xx_raises_external_request_error():
    session = FakeSession(responses=[FakeResponse(False, 403, None, text="forbidden")])
    with pytest.raises(ExternalRequestError) as exc_info:
        make_client(session).get_content_root(123)
    assert exc_info.value.status_code == 403


def test_timeout_is_flagged():
    session = FakeSession(raise_exc=requests.Timeout("slow"))
    with pytest.raises(ExternalRequestError) as exc_info:
        make_client(session).get_topic(123, 10)
    assert exc_info.value.is_timeout is True
