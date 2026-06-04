"""Session service adapter.

The core's :class:`ltitoolkit.core.session.SessionService` is framework-neutral:
its default backend (``SessionDataStorage``) simply reads and writes
``request.session``. For FastAPI that is the dict provided by Starlette's
``SessionMiddleware``, so no behaviour needs to change here.
"""

from ltitoolkit.core.session import SessionService


class FastApiSessionService(SessionService):
    pass
