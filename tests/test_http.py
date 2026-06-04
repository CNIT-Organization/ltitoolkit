"""Tests for the HTTP session helper."""

from __future__ import annotations

import requests

from ltitoolkit.http import DEFAULT_TIMEOUT, TimeoutHTTPAdapter, build_session


def test_adapter_injects_default_timeout(monkeypatch):
    captured: dict = {}

    def fake_send(self, request, **kwargs):
        captured.update(kwargs)
        return "sent"

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", fake_send)
    adapter = TimeoutHTTPAdapter(timeout=(3.0, 4.0))
    adapter.send(object())

    assert captured["timeout"] == (3.0, 4.0)


def test_adapter_respects_explicit_timeout(monkeypatch):
    captured: dict = {}

    def fake_send(self, request, **kwargs):
        captured.update(kwargs)
        return "sent"

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", fake_send)
    adapter = TimeoutHTTPAdapter(timeout=(3.0, 4.0))
    adapter.send(object(), timeout=(9.0, 9.0))

    assert captured["timeout"] == (9.0, 9.0)


def test_build_session_defaults():
    session = build_session()
    assert session.headers["User-Agent"] == "ltitoolkit"
    adapter = session.get_adapter("https://example.test")
    assert isinstance(adapter, TimeoutHTTPAdapter)
    assert adapter._timeout == DEFAULT_TIMEOUT


def test_build_session_retries_only_idempotent_methods():
    session = build_session(retries=3)
    adapter = session.get_adapter("https://example.test")
    allowed = adapter.max_retries.allowed_methods
    assert "GET" in allowed
    assert "POST" not in allowed  # never retry score/token POSTs
