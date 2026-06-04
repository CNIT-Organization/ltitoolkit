"""ltitoolkit — a framework-agnostic LTI 1.3 Advantage toolkit for Python.

Connect any Python application to any LTI 1.3 compliant LMS (Canvas, Moodle,
Blackboard, …) with one dependency:

- LTI 1.3 launch + identity (who, which course, what role)
- LTI Advantage: Assignment & Grade Services (AGS), Names & Role Provisioning
  (NRPS), and Deep Linking — portable across every LMS
- Dynamic Registration: single-URL, no-credentials tool install
- Generic client-credentials token minting for LMS service/API calls

The portable LTI engine lives in :mod:`ltitoolkit.core` (vendored). Framework
glue lives in adapters such as :mod:`ltitoolkit.fastapi`. LMS-proprietary REST
calls (listing files, quizzes, etc.) are intentionally *not* part of the core —
they belong in thin, separate per-LMS adapters.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
