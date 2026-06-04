"""A clean facade over the LTI Advantage services of a validated launch.

Wraps a validated ``MessageLaunch`` and exposes the two portable, every-LMS
services with explicit availability guards and a couple of ergonomic helpers:

- **NRPS** — the course roster (paginated transparently by the core).
- **AGS** — read/write grades for *this tool's* activities.

It does not reimplement the spec logic (that lives in the vendored core); it
gives applications a small, typed, documented surface so they never import from
``ltitoolkit.core`` directly.
"""

from __future__ import annotations

import typing as t
from datetime import datetime, timezone

from ..core.grade import Grade
from ..exceptions import LtiToolkitError

if t.TYPE_CHECKING:
    from ..core.assignments_grades import AssignmentsGradesService
    from ..core.lineitem import LineItem
    from ..core.message_launch import MessageLaunch
    from ..core.names_roles import NamesRolesProvisioningService, TMember
    from ..core.service_connector import TServiceConnectorResponse


class AdvantageServiceUnavailable(LtiToolkitError):
    """Raised when a launch did not grant the requested Advantage service."""


class LaunchAdvantage:
    """Ergonomic access to AGS/NRPS for a single validated launch."""

    def __init__(self, message_launch: MessageLaunch) -> None:
        self._launch = message_launch

    # -- Names & Role Provisioning (roster) --------------------------------

    def has_names_and_roles(self) -> bool:
        return self._launch.has_nrps()

    def names_and_roles(self) -> NamesRolesProvisioningService:
        if not self.has_names_and_roles():
            raise AdvantageServiceUnavailable(
                "This launch does not include the Names and Role Provisioning Service"
            )
        return self._launch.get_nrps()

    def get_roster(self, resource_link_id: str | None = None) -> list[TMember]:
        """Return all course members (every page), optionally filtered by resource link."""
        return self.names_and_roles().get_members(resource_link_id)

    # -- Assignment & Grade Services (grades) ------------------------------

    def has_grades(self) -> bool:
        return self._launch.has_ags()

    def grades(self) -> AssignmentsGradesService:
        if not self.has_grades():
            raise AdvantageServiceUnavailable(
                "This launch does not include the Assignment and Grade Services"
            )
        return self._launch.get_ags()

    def submit_score(
        self,
        *,
        user_id: str,
        score_given: float,
        score_maximum: float,
        activity_progress: str = "Completed",
        grading_progress: str = "FullyGraded",
        comment: str | None = None,
        timestamp: str | None = None,
        lineitem: LineItem | None = None,
    ) -> TServiceConnectorResponse:
        """Push a score back to the gradebook for ``user_id``.

        Defaults to the line item carried by the launch; pass ``lineitem`` to
        target a specific one. ``timestamp`` defaults to now (ISO 8601, UTC).
        """
        grade = (
            Grade()
            .set_user_id(user_id)
            .set_score_given(score_given)
            .set_score_maximum(score_maximum)
            .set_activity_progress(activity_progress)
            .set_grading_progress(grading_progress)
            .set_timestamp(timestamp or datetime.now(timezone.utc).isoformat())
        )
        if comment is not None:
            grade.set_comment(comment)
        return self.grades().put_grade(grade, lineitem)
