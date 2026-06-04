"""Tests for the LaunchAdvantage facade (AGS/NRPS), fully offline.

A fake ServiceConnector stands in for the network so we exercise the real core
AGS/NRPS logic (pagination, score POST) through our facade without an LMS.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from ltitoolkit.advantage import AdvantageServiceUnavailable, LaunchAdvantage
from ltitoolkit.core.assignments_grades import AssignmentsGradesService
from ltitoolkit.core.names_roles import NamesRolesProvisioningService

SCORE_SCOPE = "https://purl.imsglobal.org/spec/lti-ags/scope/score"


@dataclass
class FakeConnector:
    """Records service requests and returns queued responses."""

    responses: list = field(default_factory=list)
    calls: list = field(default_factory=list)

    def make_service_request(
        self,
        scopes,
        url,
        is_post=False,
        data=None,
        content_type="application/json",
        accept="application/json",
        case_insensitive_headers=False,
    ):
        self.calls.append(
            {"url": url, "is_post": is_post, "data": data, "content_type": content_type}
        )
        return self.responses.pop(0)


class StubLaunch:
    def __init__(self, *, nrps=None, ags=None) -> None:
        self._nrps = nrps
        self._ags = ags

    def has_nrps(self) -> bool:
        return self._nrps is not None

    def get_nrps(self):
        return self._nrps

    def has_ags(self) -> bool:
        return self._ags is not None

    def get_ags(self):
        return self._ags


def _page(members, next_url=None):
    return {"headers": {}, "body": {"members": members}, "next_page_url": next_url}


def test_get_roster_follows_pagination():
    connector = FakeConnector(
        responses=[
            _page([{"user_id": "u1"}], next_url="https://lms.test/members?page=2"),
            _page([{"user_id": "u2"}], next_url=None),
        ]
    )
    nrps = NamesRolesProvisioningService(
        connector, {"context_memberships_url": "https://lms.test/members"}
    )
    advantage = LaunchAdvantage(StubLaunch(nrps=nrps))

    roster = advantage.get_roster()

    assert [m["user_id"] for m in roster] == ["u1", "u2"]
    assert len(connector.calls) == 2  # two pages fetched


def test_submit_score_posts_to_scores_endpoint():
    connector = FakeConnector(responses=[{"headers": {}, "body": {}, "next_page_url": None}])
    ags = AssignmentsGradesService(
        connector, {"scope": [SCORE_SCOPE], "lineitem": "https://lms.test/li/1"}
    )
    advantage = LaunchAdvantage(StubLaunch(ags=ags))

    advantage.submit_score(user_id="u1", score_given=8.0, score_maximum=10.0, comment="nice")

    assert len(connector.calls) == 1
    call = connector.calls[0]
    assert call["is_post"] is True
    assert call["url"] == "https://lms.test/li/1/scores"
    assert call["content_type"] == "application/vnd.ims.lis.v1.score+json"
    payload = json.loads(call["data"])
    assert payload["userId"] == "u1"
    assert payload["scoreGiven"] == 8.0
    assert payload["scoreMaximum"] == 10.0
    assert payload["comment"] == "nice"
    assert payload["timestamp"]  # auto-filled ISO 8601


def test_missing_services_raise_clear_errors():
    advantage = LaunchAdvantage(StubLaunch())  # neither AGS nor NRPS granted

    assert advantage.has_grades() is False
    assert advantage.has_names_and_roles() is False
    with pytest.raises(AdvantageServiceUnavailable):
        advantage.grades()
    with pytest.raises(AdvantageServiceUnavailable):
        advantage.names_and_roles()
    with pytest.raises(AdvantageServiceUnavailable):
        advantage.submit_score(user_id="u1", score_given=1.0, score_maximum=1.0)
