"""LTI 1.3 Dynamic Registration (1EdTech spec).

Lets an LMS admin install the tool by pasting a single URL and clicking submit:
the tool fetches the LMS's ``openid-configuration``, learns its endpoints
automatically, registers itself, and stores the returned ``client_id`` — no
manual copying of credentials. This is what makes "works with any LMS without
re-reading the docs" real.

Spec: https://www.imsglobal.org/spec/lti-dr/v1p0
"""

from .models import (
    DEFAULT_CLAIMS,
    DEFAULT_SCOPES,
    MESSAGE_DEEP_LINKING,
    MESSAGE_RESOURCE_LINK,
    PlatformConfiguration,
    ToolMessage,
    ToolRegistration,
    ToolRegistrationConfig,
)
from .service import DynamicRegistrationService
from .store import InMemoryRegistrationStore, RegistrationStore
from .tool_conf import StoredToolConf

__all__ = [
    "DynamicRegistrationService",
    "ToolRegistrationConfig",
    "ToolMessage",
    "ToolRegistration",
    "PlatformConfiguration",
    "RegistrationStore",
    "InMemoryRegistrationStore",
    "StoredToolConf",
    "DEFAULT_SCOPES",
    "DEFAULT_CLAIMS",
    "MESSAGE_RESOURCE_LINK",
    "MESSAGE_DEEP_LINKING",
]
